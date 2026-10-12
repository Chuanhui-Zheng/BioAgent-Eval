from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from chunking.phenotype_glossary import PhenotypeGlossary
from chunking.schema import Chunk
from chunking.utils import file_sha256, relative_source_path

COLLECTION = "variant_association_clumped"
OUTPUT_NAME = "metaanalysis_clumped_2hrG_EU.chunks.jsonl"
DEFINITIONS = ["genome_build", "effect_scale_and_allele", "n", "alignment",
               "clumping_rules_and_reference", "meta_selection", "release"]


def _reject_constant(value):
    raise ValueError(f"Nonstandard JSON constant: {value}")


def _validate(row: dict, line: int) -> None:
    for field in ("phenotype", "chromosome", "varId", "reference", "alt",
                  "freqType", "metaType", "inMetaTypes", "paramType"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise ValueError(f"Source line {line}: invalid {field}")
    for field in ("clump", "clumpStart", "clumpEnd", "position"):
        if type(row.get(field)) is not int or row[field] < 0:
            raise ValueError(f"Source line {line}: invalid {field}")
    if type(row.get("leadSNP")) is not bool:
        raise ValueError(f"Source line {line}: leadSNP must be boolean")
    for field in ("beta", "stdErr", "pValue", "n", "alignment"):
        value = row.get(field)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"Source line {line}: invalid {field}")
    if not 0 <= row["pValue"] <= 1 or row["stdErr"] <= 0 or row["n"] <= 0:
        raise ValueError(f"Source line {line}: invalid pValue/stdErr/n range")
    if not row["clumpStart"] <= row["position"] <= row["clumpEnd"]:
        raise ValueError(f"Source line {line}: position outside source interval")
    if row["varId"] != f"{row['chromosome']}:{row['position']}:{row['reference']}:{row['alt']}":
        raise ValueError(f"Source line {line}: varId/component mismatch")


def chunk_clumped_regions(jsonl_path: Path, glossary: PhenotypeGlossary,
                          project_root: Path) -> Iterator[Chunk]:
    """One source clump per chunk; complete members stay outside ranking text."""
    parent = jsonl_path.parent.name
    if not parent.startswith("ancestry=") or not parent[len("ancestry="):].strip():
        raise ValueError("Clumped source requires an ancestry=<code> directory")
    ancestry = parent[len("ancestry="):]
    source_file = relative_source_path(jsonl_path.resolve(), project_root.resolve())
    source_hash = file_sha256(jsonl_path)
    groups = defaultdict(list)
    seen = set()
    with jsonl_path.open(encoding="utf-8-sig") as handle:
        for line, text in enumerate(handle, 1):
            if not text.strip():
                continue
            try:
                row = json.loads(text, parse_constant=_reject_constant)
            except ValueError as exc:
                raise ValueError(f"Source line {line}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Source line {line}: expected object")
            _validate(row, line)
            identity = (row["phenotype"], row["varId"])
            if identity in seen:
                raise ValueError(f"Source line {line}: duplicate variant {identity}")
            seen.add(identity)
            groups[(row["phenotype"], row["chromosome"], row["clump"])].append((line, row))

    # Validate every group before yielding, rather than publishing partial evidence.
    for key, members in groups.items():
        consistent = {tuple(r[f] for f in ("clumpStart", "clumpEnd", "freqType", "metaType", "paramType"))
                      for _, r in members}
        leads = [r for _, r in members if r["leadSNP"]]
        if len(consistent) != 1 or len(leads) != 1:
            raise ValueError(f"Clump {key}: inconsistent boundaries/context or lead count")
        if leads[0]["pValue"] != min(r["pValue"] for _, r in members):
            raise ValueError(f"Clump {key}: designated lead is not a minimum supplied pValue")

    for (phenotype, chromosome, clump), entries in sorted(groups.items()):
        entries.sort(key=lambda item: (item[1]["position"], item[1]["varId"]))
        members = [r for _, r in entries]
        source_rows = [line for line, _ in entries]
        lead = next(r for r in members if r["leadSNP"])
        label, confidence = glossary.get_label(phenotype)
        interval = f"{lead['clumpStart']}-{lead['clumpEnd']}"
        identifier = "clumped:" + ":".join(quote(str(v), safe="-_.") for v in
                                           (phenotype, ancestry, chromosome, clump, interval))
        content = "\n".join([
            f"Client-reported clumped variant association: {label} ({phenotype}).",
            f"Ancestry code: {ancestry} (from source directory, not a row field).",
            f"Chromosome: {chromosome}; source clump: {clump}; source interval: {interval}.",
            f"Supplied member variants: {len(members)}.",
            f"Source-designated lead variant: {lead['varId']}.",
            "Lead statistics (displayed to 4 significant digits): " + "; ".join(
                f"{f}={lead[f]:.4g}" for f in ("beta", "stdErr", "pValue", "n", "alignment")),
            f"freqType={lead['freqType']}; metaType={lead['metaType']}; paramType={lead['paramType']}.",
            "Genome build, effect scale/allele, n definition, alignment, clumping rules and release are unconfirmed.",
            "Lead status is not causal proof; coverage is limited to supplied records. Do not flip beta using alignment.",
            "Full member records and numeric precision are retained in metadata; member n values may differ.",
            "Member IDs/statistics outside the lead are not indexed in this summary.",
            f"Source: {source_file}",
        ])
        yield Chunk(identifier, COLLECTION, "variant_association_region",
                    f"Clumped association: {phenotype} | {ancestry} | chr{chromosome}:{interval} | clump {clump}",
                    content,
                    {"phenotype": phenotype, "phenotype_label": label, "phenotype_label_confidence": confidence,
                     "ancestry": ancestry, "ancestry_source": "directory", "chromosome": chromosome,
                     "clump": clump, "clumpStart": lead["clumpStart"], "clumpEnd": lead["clumpEnd"],
                     "group_id": identifier, "member_count": len(members), "lead_variant_id": lead["varId"],
                     "members": members, "source_rows": source_rows, "source_file": source_file,
                     "source_sha256": source_hash, "definition_status": "unconfirmed",
                     "unconfirmed_definitions": DEFINITIONS.copy()},
                    {"source_name": "Client-provided clumped association results", "release": None,
                     "source_file": source_file, "source_rows": source_rows,
                     "source_sha256": source_hash, "chunk_id": identifier})
