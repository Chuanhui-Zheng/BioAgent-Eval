"""Check explicitly labelled scientific numbers against their cited evidence.

This deterministic check catches numeric fabrication; it is not an entailment judge.
Rounded source displays are accepted at 5e-4 relative tolerance (four significant digits).
"""

from __future__ import annotations
import math
import re
from augmentation.schema import ContextPackage
from generation.schema import GeneratedAnswer

NUMBER = re.compile(
    r"(?P<field>pValue|p[- ]value|mixed_pvalue|mixed_rg|bf_common|bf_rare|enrichment_beta|h2_beta|stdErr|median|beta|rg|z|p)\s*(?:=|:|\bis\b|\bof\b)\s*(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
    re.I,
)
ALIASES = {"p": "pvalue", "p-value": "pvalue", "p value": "pvalue", "rg": "mixed_rg"}


def fields(value):
    result = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                isinstance(item, (int, float))
                and not isinstance(item, bool)
                and math.isfinite(float(item))
            ):
                result.setdefault(key.lower(), []).append(float(item))
            elif isinstance(item, (dict, list)):
                for field, numbers in fields(item).items():
                    result.setdefault(field, []).extend(numbers)
    elif isinstance(value, list):
        for item in value:
            for field, numbers in fields(item).items():
                result.setdefault(field, []).extend(numbers)
    return result


def numeric_errors(answer: GeneratedAnswer, context: ContextPackage) -> list[str]:
    passages = {p.chunk_id: p for p in context.passages}
    errors = []
    claims = [(claim.text, claim.citations) for claim in answer.claims]
    claims.append(
        (
            answer.answer,
            list(dict.fromkeys(cid for c in answer.claims for cid in c.citations)),
        )
    )
    for text, citations in claims:
        expected = {}
        for cid in citations:
            if cid not in passages:
                continue
            passage = passages[cid]
            for field, numbers in fields(passage.metadata).items():
                expected.setdefault(field, []).extend(numbers)
            for match in NUMBER.finditer(passage.content):
                key = ALIASES.get(match["field"].lower(), match["field"].lower())
                expected.setdefault(key, []).append(float(match["number"]))
        for match in NUMBER.finditer(text):
            key = ALIASES.get(match["field"].lower(), match["field"].lower())
            number = float(match["number"])
            # p and rg may be supplied under Mixed ancestry names by the offline generator.
            candidates = expected.get(key, [])
            if key == "pvalue":
                candidates += expected.get("mixed_pvalue", [])
            if not any(
                math.isclose(number, truth, rel_tol=5e-4, abs_tol=1e-300)
                for truth in candidates
            ):
                errors.append(
                    f"unsupported numeric value: {match['field']}={match['number']}"
                )
    return list(dict.fromkeys(errors))
