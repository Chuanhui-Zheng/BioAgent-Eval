from __future__ import annotations

import re
from typing import Any

from retrieval.schema import ChunkRecord
from retrieval.tokenizer import normalize_text

ANCHOR_CODES = {"2hri", "2hrg"}
PAREN_RE = re.compile(r"\([^)]*\)")


def _string_values(value: Any) -> list[str]:
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            items.extend(_string_values(item))
        return items
    text = str(value).strip()
    return [text] if text else []


def record_identifier_keys(record: ChunkRecord) -> set[str]:
    metadata = record.metadata
    keys: set[str] = set()
    for field_name in (
        "gene_symbol",
        "gene",
        "ensembl_gene_id",
        "ensembl",
        "hgnc_id",
        "entrezgene",
        "uniprot_accession",
    ):
        for value in _string_values(metadata.get(field_name)):
            normalized = normalize_text(value)
            if normalized:
                keys.add(normalized)

    for value in _string_values(metadata.get("other_phenotype")):
        normalized = normalize_text(value)
        if normalized:
            keys.add(normalized)

    for value in _string_values(metadata.get("alternative_names")):
        normalized = normalize_text(value)
        if normalized:
            keys.add(normalized)

    # Partitioned IDs end in ancestry, shared by many unrelated tissues.
    # Pinning that suffix bypasses text relevance and sorts those records by ID.
    if record.collection != "ldsc_partitioned_heritability":
        last = normalize_text(record.chunk_id.split(":")[-1])
        if last and last not in ANCHOR_CODES:
            keys.add(last)
    return keys


def record_label_needles(record: ChunkRecord) -> list[str]:
    needles: list[str] = []
    for value in _string_values(record.metadata.get("other_phenotype_label")):
        cleaned = PAREN_RE.sub("", value).strip().lower()
        if cleaned:
            needles.append(cleaned)
    return needles


def exact_match_score(
    query: str,
    query_tokens: list[str],
    keys: set[str],
    needles: list[str],
) -> int:
    token_set = set(query_tokens)
    score = sum(1 for token in token_set if token in keys)
    query_norm = f" {normalize_text(query)} "
    for needle in needles:
        if len(needle) < 4:
            continue
        if f" {needle} " in query_norm or needle in query_norm:
            score += 1
            break
    return score
