from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from chunking.phenotype_glossary import PhenotypeGlossary
from chunking.schema import Chunk
from chunking.utils import format_optional, load_jsonl, relative_source_path, significance_tag


PHENOTYPE_DESCRIPTIONS = {
    "2hrG": (
        "2-hour glucose from oral glucose tolerance test (OGTT), "
        "a quantitative metabolic trait studied at population level via GWAS summary statistics."
    ),
}


def _phenotype_description(phenotype: str, glossary: PhenotypeGlossary) -> str:
    if phenotype in PHENOTYPE_DESCRIPTIONS:
        return PHENOTYPE_DESCRIPTIONS[phenotype]
    label, _ = glossary.get_label(phenotype)
    return f"{label} ({phenotype}), studied at population level via GWAS summary statistics."


def _infer_common_evidence_tier(row: dict[str, Any]) -> str:
    bf_common = row.get("bf_common")
    has_causal = bool(row.get("varIdCausal"))
    if has_causal and isinstance(bf_common, (int, float)) and bf_common >= 10:
        return "strong"
    if has_causal or (isinstance(bf_common, (int, float)) and bf_common > 1):
        return "annotated"
    return "baseline"


def _build_common_causal_lines(row: dict[str, Any]) -> list[str]:
    if not row.get("varIdCausal"):
        return []

    return [
        "Causal / GWAS annotation:",
        f"- Causal variant (GWAS): {row['varIdCausal']}, p={format_optional(row.get('pValueCausal'))}",
        f"- Consequence impact: {format_optional(row.get('consequenceImpact'))}",
        (
            "- Causal flags: "
            f"coding={format_optional(row.get('causalCoding'))}, "
            f"nearest={format_optional(row.get('causalNearest'))}, "
            f"gwas={format_optional(row.get('causalGWAS'))}"
        ),
    ]


def _common_chunk_id(phenotype: str, gene: str, ensembl: str, gene_symbol_count: int) -> str:
    base = f"gassoc_common:{phenotype}:{gene}"
    if gene_symbol_count > 1:
        return f"{base}:{ensembl}"
    return base


def chunk_gene_association_common(
    jsonl_path: Path,
    glossary: PhenotypeGlossary,
    project_root: Path,
) -> Iterator[Chunk]:
    source_file_rel = relative_source_path(jsonl_path, project_root)
    rows = list(load_jsonl(jsonl_path))
    raw_row_count = len(rows)
    gene_symbol_counts: dict[str, int] = {}
    for row in rows:
        gene_symbol_counts[row["gene"]] = gene_symbol_counts.get(row["gene"], 0) + 1

    for row in rows:
        gene = row["gene"]
        phenotype = row["phenotype"]
        phenotype_label, phenotype_label_confidence = glossary.get_label(phenotype)
        has_causal = bool(row.get("varIdCausal"))
        evidence_tier = _infer_common_evidence_tier(row)
        bf_common = row.get("bf_common")

        evidence_note = (
            "Genes with bf_common=1 and no causal annotation were included in the screen "
            "without strong causal annotation in this export."
            if evidence_tier == "baseline"
            else "See causal/GWAS annotation below when present."
        )

        content_lines = [
            (
                "Gene-phenotype association (common variants, HuGE): "
                f"{gene} and {phenotype_label} ({phenotype})"
            ),
            "Analysis type: Common-variant gene-level evidence from T2D Knowledge Portal HuGE export",
            f"Anchor trait: {_phenotype_description(phenotype, glossary)}",
            "",
            f"Genomic location: chr{row['chromosome']}:{row['start']}-{row['end']}",
            f"Ensembl: {row['ensembl']}",
            "",
            "Evidence summary:",
            f"- Bayes factor (common): bf_common={format_optional(bf_common)}",
            f"- Evidence tier: {evidence_tier}",
            *_build_common_causal_lines(row),
            "",
            "Interpretation boundaries:",
            "- Describes population-level genetic association evidence, not individual glucose test results.",
            "- bf_common and causal annotations indicate strength/type of evidence, not proven causality in individuals.",
            f"- {evidence_note}",
            "",
            "Source: T2D Knowledge Portal HuGE (common variants)",
            f"Provenance: {source_file_rel}",
        ]

        metadata: dict[str, Any] = {
            "entity_type": "gene_phenotype_association",
            "variant_class": "common",
            "gene": gene,
            "ensembl": row.get("ensembl"),
            "chromosome": row.get("chromosome"),
            "start": row.get("start"),
            "end": row.get("end"),
            "phenotype": phenotype,
            "phenotype_label": phenotype_label,
            "phenotype_label_confidence": phenotype_label_confidence,
            "bf_common": bf_common,
            "has_causal_annotation": has_causal,
            "evidence_tier": evidence_tier,
            "method": "HuGE_common",
            "source_file": source_file_rel,
        }

        for field in (
            "varIdCausal",
            "pValueCausal",
            "consequenceImpact",
            "consequenceGeneId",
            "nearestGene",
            "causalCoding",
            "causalNearest",
            "causalGWAS",
        ):
            if field in row:
                metadata[field] = row[field]

        chunk_id = _common_chunk_id(
            phenotype,
            gene,
            str(row.get("ensembl")),
            gene_symbol_counts[gene],
        )
        citation = {
            "source_name": "T2D Knowledge Portal",
            "source_file": source_file_rel,
            "chunk_id": chunk_id,
            "method": "HuGE_common",
            "phenotype": phenotype,
            "gene": gene,
        }

        yield Chunk(
            chunk_id=chunk_id,
            collection="gene_association_common",
            entity_type="gene_phenotype_association",
            title=f"Common-variant gene evidence: {gene} and {phenotype_label} ({phenotype})",
            content="\n".join(content_lines),
            metadata=metadata,
            citation=citation,
        )

    chunk_gene_association_common.raw_row_count = raw_row_count  # type: ignore[attr-defined]


def _rare_data_quality_note(row: dict[str, Any]) -> str | None:
    std_err = row.get("stdErr")
    if isinstance(std_err, (int, float)) and std_err < 0:
        return "stdErr in source row is non-positive; use pValue/beta/bf_rare from metadata for reporting."
    return None


def chunk_gene_association_rare(
    jsonl_path: Path,
    glossary: PhenotypeGlossary,
    project_root: Path,
) -> Iterator[Chunk]:
    source_file_rel = relative_source_path(jsonl_path, project_root)
    raw_row_count = 0

    for row in load_jsonl(jsonl_path):
        raw_row_count += 1
        gene = row["gene"]
        phenotype = row["phenotype"]
        phenotype_label, phenotype_label_confidence = glossary.get_label(phenotype)
        p_value = float(row["pValue"])
        is_significant = p_value < 0.05
        quality_note = _rare_data_quality_note(row)

        content_lines = [
            (
                "Gene-phenotype association (rare variants, HuGE): "
                f"{gene} and {phenotype_label} ({phenotype})"
            ),
            "Analysis type: Rare-variant gene-based test (population GWAS summary statistics)",
            "",
            "Association statistics:",
            f"- p-value={p_value:.6g}{significance_tag(p_value)}",
            f"- beta={row['beta']}",
            f"- z={row['z']}",
            f"- Bayes factor (rare): bf_rare={row['bf_rare']}",
            "",
            "Interpretation boundaries:",
            "- Gene-based rare variant evidence at population level; not individual diagnosis or lab values.",
            "- Non-significant p-values do not support a strong rare-variant association under this analysis.",
            "- Do not equate with common-variant GWAS hits or LDSC genetic correlation (rg).",
            "",
            "Source: T2D Knowledge Portal HuGE (rare variants)",
            f"Provenance: {source_file_rel}",
        ]

        metadata: dict[str, Any] = {
            "entity_type": "gene_phenotype_association",
            "variant_class": "rare",
            "gene": gene,
            "phenotype": phenotype,
            "phenotype_label": phenotype_label,
            "phenotype_label_confidence": phenotype_label_confidence,
            "pValue": p_value,
            "beta": row.get("beta"),
            "z": row.get("z"),
            "stdErr": row.get("stdErr"),
            "v": row.get("v"),
            "bf_rare": row.get("bf_rare"),
            "is_significant": is_significant,
            "method": "HuGE_rare",
            "source_file": source_file_rel,
        }
        if quality_note:
            metadata["data_quality_note"] = quality_note

        chunk_id = f"gassoc_rare:{phenotype}:{gene}"
        citation = {
            "source_name": "T2D Knowledge Portal",
            "source_file": source_file_rel,
            "chunk_id": chunk_id,
            "method": "HuGE_rare",
            "phenotype": phenotype,
            "gene": gene,
        }

        yield Chunk(
            chunk_id=chunk_id,
            collection="gene_association_rare",
            entity_type="gene_phenotype_association",
            title=f"Rare-variant gene evidence: {gene} and {phenotype_label} ({phenotype})",
            content="\n".join(content_lines),
            metadata=metadata,
            citation=citation,
        )

    chunk_gene_association_rare.raw_row_count = raw_row_count  # type: ignore[attr-defined]
