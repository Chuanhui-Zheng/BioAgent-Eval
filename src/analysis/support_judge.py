"""Claim-level factual-support checks for generated answers.

Two complementary layers:

* ``deterministic_grounding`` — every number and every identifier-like token
  (gene symbols, Ensembl IDs, chr coordinates, variant IDs) in a claim must occur
  in that claim's cited passages. Cheap, reproducible, catches fabricated values
  and wrong-entity citations, but cannot judge paraphrased meaning.
* ``LLMSupportJudge`` — an LLM reads each claim with only its cited passages and
  labels it supported / partial / unsupported / contradicted. Any OpenAI-compatible
  provider can act as judge; use a different model from the generator where
  possible. Judge labels are an automated estimate and must be spot-checked
  against the human review rubric.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any

NUMBER_TOKEN = re.compile(r"(?<![A-Za-z0-9_])[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?(?![A-Za-z0-9_])")
ENTITY_TOKEN = re.compile(
    r"\bENSG\d{11}\b|\bchr[0-9XYM]+(?::\d+(?:-\d+)?)?\b|\b\d{1,2}:\d+:[ACGT]+:[ACGT]+\b|\b[A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)?\b"
)
# Upper-case words that are vocabulary, not entities that must be grounded.
ENTITY_STOPWORDS = {
    "LDSC", "GWAS", "WES", "OGTT", "HUGE", "GTEX", "RNA", "DNA", "MRNA", "SNP", "SNPS", "EA", "EU", "HS", "AND", "OR",
    "THE", "NOT", "NA", "N/A", "ID", "IDS", "HGNC", "BH", "GO", "LOF", "LC", "AF", "MAF", "SE", "BF", "TDI", "BMI",
    "T2D", "HDL", "LDL", "TG", "HG", "GRCH37", "GRCH38", "AMP", "PRS", "P", "Z", "RG", "UTR", "CDS", "ATP", "GTP",
}
LABELS = ("supported", "partial", "unsupported", "contradicted")


def _numbers(text: str) -> list[float]:
    values = []
    for match in NUMBER_TOKEN.finditer(text):
        try:
            value = float(match.group())
        except ValueError:
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def _metadata_numbers(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)] if math.isfinite(float(value)) else []
    if isinstance(value, dict):
        return [n for item in value.values() for n in _metadata_numbers(item)]
    if isinstance(value, list):
        return [n for item in value for n in _metadata_numbers(item)]
    if isinstance(value, str):
        return _numbers(value)
    return []


def _number_supported(value: float, pool: list[float]) -> bool:
    if float(value).is_integer() and abs(value) < 100:
        # Small integers (counts, chromosome numbers, list positions) are grounded
        # if they appear anywhere in the cited text.
        return any(value == item for item in pool)
    return any(math.isclose(value, item, rel_tol=5e-4, abs_tol=1e-300) for item in pool)


@dataclass
class ClaimGrounding:
    claim: str
    citations: list[str]
    unsupported_numbers: list[float] = field(default_factory=list)
    unsupported_entities: list[str] = field(default_factory=list)

    @property
    def grounded(self) -> bool:
        return not self.unsupported_numbers and not self.unsupported_entities


def deterministic_grounding(answer, passages) -> list[ClaimGrounding]:
    """Check each claim's numbers and identifiers against its own cited passages only."""
    by_id = {p.chunk_id: p for p in passages}
    results = []
    for claim in answer.claims:
        cited = [by_id[cid] for cid in claim.citations if cid in by_id]
        text = "\n".join(f"{p.title}\n{p.content}\n{p.chunk_id}" for p in cited)
        pool = _numbers(text) + [n for p in cited for n in _metadata_numbers(p.metadata)]
        haystack = (text + "\n" + json.dumps([p.metadata for p in cited], ensure_ascii=False, default=str)).upper()
        # Numbers inside identifiers (ENSG…, chr12:…, gene names like ABCC8) are covered by the entity check.
        stripped = ENTITY_TOKEN.sub(" ", claim.text)
        unsupported_numbers = [v for v in dict.fromkeys(_numbers(stripped)) if not _number_supported(v, pool)]
        entities = [t for t in dict.fromkeys(ENTITY_TOKEN.findall(claim.text)) if t.upper() not in ENTITY_STOPWORDS]
        unsupported_entities = [t for t in entities if t.upper() not in haystack]
        results.append(ClaimGrounding(claim.text, list(claim.citations), unsupported_numbers, unsupported_entities))
    return results


JUDGE_PROMPT = """You are a strict scientific fact-checker. Decide whether the CLAIM is supported
by the EVIDENCE passages alone. Do not use outside knowledge.
Labels:
- supported: every factual element of the claim is stated in or directly entailed by the evidence.
- partial: some elements are supported but at least one is missing, overstated or imprecise.
- unsupported: the evidence does not state the claim.
- contradicted: the evidence states something incompatible with the claim.
Overstating association as causation, or adding clinical/drug advice, is never "supported".
Return JSON only: {"label": "supported|partial|unsupported|contradicted", "reason": "<= 30 words"}"""


@dataclass
class ClaimJudgement:
    claim: str
    citations: list[str]
    label: str
    reason: str


class LLMSupportJudge:
    """LLM-as-judge over (claim, cited passages) pairs using any OpenAI-compatible generator."""

    def __init__(self, llm, max_passage_chars: int = 3000) -> None:
        self.llm = llm
        self.max_passage_chars = max_passage_chars

    @property
    def description(self) -> dict[str, Any]:
        return self.llm.describe() if hasattr(self.llm, "describe") else {"judge": type(self.llm).__name__}

    def judge_claim(self, claim, passages_by_id) -> ClaimJudgement:
        evidence = [
            {"chunk_id": cid, "title": passages_by_id[cid].title,
             "content": passages_by_id[cid].content[: self.max_passage_chars]}
            for cid in claim.citations if cid in passages_by_id
        ]
        if not evidence:
            return ClaimJudgement(claim.text, list(claim.citations), "unsupported", "No cited passage is in context.")
        messages = [
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": json.dumps({"claim": claim.text, "evidence": evidence}, ensure_ascii=False)},
        ]
        try:
            raw = self.llm.complete(messages, max_tokens=200)
            payload = _first_json_object(raw)
            label = str(payload.get("label", "")).strip().lower()
            if label not in LABELS:
                raise ValueError(f"invalid label {label!r}")
            return ClaimJudgement(claim.text, list(claim.citations), label, str(payload.get("reason", ""))[:300])
        except Exception as exc:  # judge failures are recorded, never counted as support
            return ClaimJudgement(claim.text, list(claim.citations), "judge_error", type(exc).__name__)

    def judge(self, answer, passages) -> list[ClaimJudgement]:
        by_id = {p.chunk_id: p for p in passages}
        return [self.judge_claim(claim, by_id) for claim in answer.claims]


def _first_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character == "{":
            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    raise ValueError("judge returned no JSON object")


def summarise_support(groundings: list[ClaimGrounding], judgements: list[ClaimJudgement] | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "claims": len(groundings),
        "grounded_claims": sum(g.grounded for g in groundings),
        "ungrounded": [asdict(g) for g in groundings if not g.grounded],
    }
    if judgements is not None:
        counts = {label: 0 for label in (*LABELS, "judge_error")}
        for item in judgements:
            counts[item.label] = counts.get(item.label, 0) + 1
        summary["judge_labels"] = counts
        summary["judge_details"] = [asdict(item) for item in judgements if item.label != "supported"]
    return summary
