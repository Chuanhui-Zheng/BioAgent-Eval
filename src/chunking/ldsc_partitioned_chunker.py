from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

from chunking.phenotype_glossary import PhenotypeGlossary
from chunking.schema import Chunk
from chunking.utils import file_sha256, relative_source_path


IDENTITY_FIELDS = ("phenotype", "annotation", "tissue", "ancestry")
STATISTIC_FIELDS = (
    "SNPs", "h2_beta", "h2_stdErr", "enrichment_beta", "enrichment_stdErr",
    "coefficient_beta", "coefficient_stdErr", "diff_beta", "diff_stdErr", "pValue",
)
UNCONFIRMED_DEFINITIONS = (
    "SNPs", "h2_beta", "enrichment_beta", "coefficient_beta", "diff_beta",
    "pValue", "ancestry", "source_release",
)


def _validate(row: dict[str, Any], line: int) -> str:
    for field in IDENTITY_FIELDS:
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Source line {line}: {field} must be a nonempty string")

    biosample = row.get("biosample")
    if "biosample" not in row:
        status = "missing"
    elif biosample is None:
        status = "null"
    elif isinstance(biosample, str) and biosample.strip():
        status = "provided"
    else:
        raise ValueError(f"Source line {line}: biosample must be a nonempty string or null")

    for field in STATISTIC_FIELDS:
        value = row.get(field)
        try:
            valid = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError(f"Source line {line}: {field} must be a finite number")
        if field.endswith("stdErr") and value < 0:
            raise ValueError(f"Source line {line}: {field} must be nonnegative")
    if not 0 <= row["pValue"] <= 1:
        raise ValueError(f"Source line {line}: pValue must be in [0, 1]")
    return status


def _canonical(value: list[Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _identifier(prefix: str, canonical: str) -> str:
    values = json.loads(canonical)
    components = []
    for value in values:
        if isinstance(value, dict):
            component = (quote(value["value"], safe="-_.") if value["state"] == "provided"
                         else f"[{value['state']}]")
        else:
            component = quote(value, safe="-_.")
        components.append(component)
    return prefix + ":".join(components)


def chunk_ldsc_partitioned(
    jsonl_path: Path,
    glossary: PhenotypeGlossary,
    project_root: Path,
) -> Iterator[Chunk]:
    """Build one evidence chunk per annotation/biosample/ancestry result.

    Validate the complete input before yielding, rejecting duplicate identities.
    Original numeric values and extra fields remain in metadata.raw_record;
    content displays numeric values to four significant digits.
    """
    source_file = relative_source_path(jsonl_path.resolve(), project_root.resolve())
    source_hash = file_sha256(jsonl_path)
    records: list[tuple[str, str, dict[str, Any], int, str]] = []
    seen: dict[str, int] = {}

    with jsonl_path.open(encoding="utf-8-sig") as handle:
        for source_row, text in enumerate(handle, start=1):
            if not text.strip():
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Source line {source_row}: invalid JSON in {source_file}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Source line {source_row}: expected a JSON object in {source_file}")
            biosample_status = _validate(row, source_row)
            group = [row["phenotype"], row["annotation"], row["tissue"],
                     {"state": biosample_status, "value": row.get("biosample")}]
            group_key = _canonical(group)
            identity = _canonical(group + [row["ancestry"]])
            if identity in seen:
                raise ValueError(
                    f"Duplicate identity in {source_file}: source rows {seen[identity]} and {source_row}"
                )
            seen[identity] = source_row
            records.append((identity, group_key, row, source_row, biosample_status))

    for identity, group_key, row, source_row, biosample_status in sorted(records, key=lambda r: r[0]):
        phenotype_label, label_confidence = glossary.get_label(row["phenotype"])
        biosample_text = row["biosample"] if biosample_status == "provided" else f"[{biosample_status}]"
        biosample_display = biosample_text
        if biosample_status == "provided" and "_" in biosample_text:
            biosample_display += f" ({biosample_text.replace('_', ' ')})"
        chunk_id = _identifier("ldsc_partitioned:", identity)
        group_id = _identifier("ldsc_partitioned_group:", group_key)
        content = "\n".join([
            f"LDSC partitioned heritability. Ancestry code: {row['ancestry']}. "
            f"Phenotype: {phenotype_label} ({row['phenotype']}).",
            f"Annotation: {row['annotation']} ({row['annotation'].replace('_', ' ')}). "
            f"Tissue: {row['tissue']} ({row['tissue'].replace('_', ' ')}). "
            f"Biosample: {biosample_display}.",
            "Source-reported statistics (4 significant digits):",
            *[f"- {field}={row[field]:.4g}" for field in STATISTIC_FIELDS],
            "Population-level estimates, not causal evidence or individual measurements. "
            "Field definitions, ancestry-code meanings, pValue test and source release are unconfirmed. "
            "Complete values and provenance are retained in metadata and citation.",
        ])
        metadata = {
            "entity_type": "partitioned_heritability",
            **{field: row[field] for field in IDENTITY_FIELDS},
            "biosample": row.get("biosample"),
            "biosample_status": biosample_status,
            "phenotype_label": phenotype_label,
            "phenotype_label_confidence": label_confidence,
            **{field: row[field] for field in STATISTIC_FIELDS},
            "raw_record": row,
            "group_id": group_id,
            "method": "LDSC",
            "definition_status": "unconfirmed",
            "unconfirmed_definitions": list(UNCONFIRMED_DEFINITIONS),
            "source_file": source_file,
            "source_row": source_row,
            "source_sha256": source_hash,
        }
        citation = {
            "source_name": "Client-provided LDSC partitioned heritability results",
            "source_release": None,
            "source_file": source_file,
            "source_row": source_row,
            "source_sha256": source_hash,
            "chunk_id": chunk_id,
            "method": "LDSC",
        }
        yield Chunk(
            chunk_id=chunk_id,
            collection="ldsc_partitioned_heritability",
            entity_type="partitioned_heritability",
            title=(f"LDSC partitioned heritability: {row['phenotype']} | {row['annotation']} | "
                   f"{row['tissue']} | {biosample_text} | {row['ancestry']}"),
            content=content,
            metadata=metadata,
            citation=citation,
        )
