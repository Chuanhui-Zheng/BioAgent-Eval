from __future__ import annotations

import re
from dataclasses import dataclass

from augmentation.schema import ContextPackage, EvidencePassage, EvidenceStatus
from retrieval.service import RetrievalResponse


@dataclass(frozen=True)
class AugmentationConfig:
    max_context_tokens: int = 1800
    max_passages: int = 5
    chars_per_token: int = 4


def _estimate_tokens(text: str, chars_per_token: int) -> int:
    return max(1, (len(text) + chars_per_token - 1) // chars_per_token)


def _requested_symbols(question: str) -> set[str]:
    symbol_stopwords = {
        "LDSC",
        "GWAS",
        "OGTT",
        "T2D",
        "WHAT",
        "DOES",
        "GENE",
        "COMMON",
        "RARE",
        "WES",
        "SNP",
        "SNPS",
        "EU",
        "EA",
        "BETA",
        "PVALUE",
    }
    return {
        token.upper()
        for token in re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{1,}\b", question)
        if (any(char.isdigit() for char in token) or token.isupper())
        and token.upper() not in symbol_stopwords
        and not token.lower().startswith("2hr")
    }


def _passage_entities(passage: EvidencePassage) -> set[str]:
    return _metadata_entities(passage.metadata)


def _metadata_entities(metadata: dict) -> set[str]:
    values: list[object] = []
    for key in (
        "gene",
        "gene_symbol",
        "other_phenotype",
        "ensembl",
        "ensembl_gene_id",
        "hgnc_id",
        "entrezgene",
        "uniprot_accession",
        "alternative_names",
        "phenotype",
        "annotation",
        "tissue",
        "lead_variant_id",
    ):
        value = metadata.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value:
            values.append(value)
    return {str(value).upper() for value in values}


def _entities_match(requested: set[str], evidence: set[str]) -> bool:
    return bool(requested.intersection(evidence)) or any(
        entity.startswith(symbol + "_") for symbol in requested for entity in evidence
    )


def _status(
    question: str, passages: list[EvidencePassage]
) -> tuple[EvidenceStatus, list[str]]:
    q = question.lower()
    limitations: list[str] = []
    if any(
        term in q
        for term in (
            "my glucose",
            "my insulin",
            "normal level",
            "diagnose me",
            "patient",
        )
    ):
        return "refuse", [
            "The corpus contains population-level evidence, not individual medical advice."
        ]
    if not passages:
        return "refuse", ["No authorized supporting evidence was retrieved."]
    requested_symbols = _requested_symbols(question)
    if requested_symbols:
        evidence_entities = set().union(*(_passage_entities(p) for p in passages))
        if not _entities_match(requested_symbols, evidence_entities):
            return "refuse", [
                "Retrieved passages do not match the requested entity in the authorized corpus."
            ]
    if requested_symbols:
        missing = {
            symbol
            for symbol in requested_symbols
            if not _entities_match({symbol}, evidence_entities)
        }
        if missing:
            limitations.append(
                "Selected evidence does not cover requested entities: "
                + ", ".join(sorted(missing))
            )
    if any(term in q for term in ("causal", "causes", "proves")):
        limitations.append(
            "Association and genetic-correlation evidence does not establish causality."
        )
    requested_phenotypes = {
        match.upper()
        for match in re.findall(
            r"\b(?:T2D|2hrG|2hrI|2hrFFA|BMI|HbA1c|CAD|LDL|HDL|TG)\b",
            question,
            re.IGNORECASE,
        )
    }
    if "type 2 diabetes" in q:
        requested_phenotypes.add("T2D")
    supported_phenotypes = {
        str(p.metadata.get(key, "")).upper()
        for p in passages
        for key in ("phenotype", "other_phenotype", "anchor_phenotype")
    }
    supported_phenotypes.update(
        token.upper() for p in passages for token in p.chunk_id.split(":")
    )
    missing_phenotypes = requested_phenotypes - supported_phenotypes
    if missing_phenotypes:
        limitations.append(
            "Selected evidence does not directly cover requested phenotypes: "
            + ", ".join(sorted(missing_phenotypes))
        )
    if any(
        term in q
        for term in ("agonist", "antagonist", "inhibitor", "therapeutic mechanism")
    ):
        limitations.append(
            "Retrieved associations or gene annotations alone do not establish a therapeutic mechanism."
        )
    nonsignificant = []
    missing_function = []
    for p in passages:
        m = p.metadata
        if m.get("is_significant") is False or m.get("is_significant_mixed") is False:
            nonsignificant.append(p.chunk_id)
        if "function" in q and m.get("has_function_summary") is False:
            missing_function.append(p.chunk_id)
        if m.get("definition_status") == "unconfirmed" or m.get(
            "unconfirmed_definitions"
        ):
            limitations.append(
                "Some source field definitions are unconfirmed; consult the cited source limitations."
            )
        note = m.get("data_quality_note")
        if note:
            limitations.append(str(note))
    if nonsignificant:
        limitations.append(
            "Retrieved statistical evidence includes non-significant results."
        )
    if missing_function:
        limitations.append(
            "The approved corpus does not provide a function summary for one or more genes."
        )
        if len(missing_function) == len(passages):
            return "refuse", list(dict.fromkeys(limitations))
    return ("qualified" if limitations else "answer"), list(dict.fromkeys(limitations))


@dataclass
class ContextBuilder:
    config: AugmentationConfig = AugmentationConfig()

    def build(self, response: RetrievalResponse) -> ContextPackage:
        seen: set[str] = set()
        passages: list[EvidencePassage] = []
        used_tokens = 0
        excluded: list[str] = []
        duplicates_removed = 0
        requested = _requested_symbols(response.question)
        # Reserve early positions for each requested entity before applying the budget.
        priority = []
        remainder = []
        covered: set[str] = set()
        for hit in response.results:
            entities = _metadata_entities(hit.chunk.get("metadata") or {})
            matched = {
                symbol for symbol in requested if _entities_match({symbol}, entities)
            }
            if matched - covered:
                priority.append(hit)
                covered.update(matched)
            else:
                remainder.append(hit)
        remainder.sort(
            key=lambda hit: (
                not _entities_match(
                    requested, _metadata_entities(hit.chunk.get("metadata") or {})
                )
            )
        )
        for result in [*priority, *remainder]:
            if result.collection not in response.effective_collections:
                raise PermissionError(f"context isolation violation: {result.chunk_id}")
            if result.chunk_id in seen:
                duplicates_removed += 1
                continue
            chunk = result.chunk
            citation = dict(chunk.get("citation") or {})
            if citation.get("chunk_id") != result.chunk_id:
                raise ValueError(f"unresolvable citation for {result.chunk_id}")
            passage = EvidencePassage(
                chunk_id=result.chunk_id,
                collection=result.collection,
                rank=result.rank,
                score=result.score,
                title=str(chunk.get("title", "")),
                content=str(chunk.get("content", "")),
                metadata=dict(chunk.get("metadata") or {}),
                citation=citation,
            )
            if passage.collection == "gtex_tissue_expression":
                # Keep compact top-tissue summaries, adding any explicitly requested
                # tissue from the complete source statistics before budgeting.
                q = response.question.lower()
                details = []
                for assay, entries in passage.metadata.get("expression", {}).items():
                    for entry in entries:
                        tissue = entry["tissue"]
                        aliases = [tissue.lower(), tissue.lower().split(" - ")[0]]
                        if any(re.search(r"\b" + re.escape(alias) + r"\b", q) for alias in aliases):
                            details.append(f"{assay} {tissue}: source median {entry['median']:g}; units unconfirmed.")
                if details:
                    passage.content += "\nRequested tissue evidence:\n" + "\n".join(details)
            cost = _estimate_tokens(
                passage.title + "\n" + passage.content, self.config.chars_per_token
            )
            if (
                len(passages) >= self.config.max_passages
                or used_tokens + cost > self.config.max_context_tokens
            ):
                excluded.append(result.chunk_id)
                continue
            passages.append(passage)
            seen.add(result.chunk_id)
            used_tokens += cost
        requested = _requested_symbols(response.question)
        matching = [
            p for p in passages if _entities_match(requested, _passage_entities(p))
        ]
        if requested and matching:
            dropped = [p.chunk_id for p in passages if p not in matching]
            excluded.extend(dropped)
            passages = matching
            used_tokens = sum(
                _estimate_tokens(
                    p.title + "\n" + p.content, self.config.chars_per_token
                )
                for p in passages
            )
        # When an exact requested trait pair is present, do not append unrelated
        # correlations simply to fill the passage budget.
        requested_traits = {m.upper() for m in re.findall(r"\b(?:T2D|2hrG|2hrI|2hrFFA|BMI|HbA1c|CAD|LDL|HDL|TG)\b", response.question, re.I)}
        if len(requested_traits) >= 2:
            pair_passages = [p for p in passages if requested_traits.issubset({str(p.metadata.get(k, "")).upper() for k in ("phenotype", "other_phenotype", "anchor_phenotype")})]
            if pair_passages:
                excluded.extend(p.chunk_id for p in passages if p not in pair_passages)
                passages = pair_passages
                used_tokens = sum(_estimate_tokens(p.title + "\n" + p.content, self.config.chars_per_token) for p in passages)
        status, limitations = _status(response.question, passages)
        if response.diagnostics.get("ranking_note"):
            limitations.append(response.diagnostics["ranking_note"])
            if status == "answer": status = "qualified"
        registry = {p.chunk_id: p.citation for p in passages}
        return ContextPackage(
            question=response.question,
            authorized_collections=response.authorized_collections,
            effective_collections=response.effective_collections,
            retrieval_method=response.method,
            passages=passages,
            citation_registry=registry,
            evidence_status=status,
            limitations=limitations,
            estimated_tokens=used_tokens,
            max_context_tokens=self.config.max_context_tokens,
            diagnostics={
                "input_passages": len(response.results),
                "selected_passages": len(passages),
                "excluded_chunk_ids": excluded,
                "duplicates_removed": duplicates_removed,
                "isolation_violations": 0,
            },
        )
