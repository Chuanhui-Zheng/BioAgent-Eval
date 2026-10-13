from __future__ import annotations

import re

from retrieval.schema import RouteDecision

ALL_COLLECTIONS = [
    "gene_info",
    "ldsc_genetic_correlation",
    "gene_association_common",
    "gene_association_rare",
]

_LDSC_RE = re.compile(
    r"\b(genetic correlation|genetically correlated|trait[- ]versus[- ]trait|2hri|"
    r"2-hour insulin|ogtt insulin)\b",
    re.IGNORECASE,
)
_PARTITIONED_RE = re.compile(
    r"\b(partition(?:ed)? heritability|partitioned_heritability|heritability enrichment|"
    r"annotation enrichment|accessible_chromatin|h2_beta|enrichment_beta)\b|分区遗传力|遗传力富集",
    re.IGNORECASE,
)
_GENERIC_LDSC_RE = re.compile(r"\bldsc\b", re.IGNORECASE)
_EXPLICIT_CORRELATION_RE = re.compile(
    r"\b(genetic correlation|genetically correlated|trait[- ]versus[- ]trait)\b", re.IGNORECASE,
)
_EXPLICIT_COMMON_RE = re.compile(r"\b(common[- ]variant|common variants|bf_common)\b", re.IGNORECASE)
PARTITIONED_COLLECTION = "ldsc_partitioned_heritability"
CLUMPED_COLLECTION = "variant_association_clumped"
WES_COLLECTION = "gene_association_wes"
GTEX_COLLECTION = "gtex_tissue_expression"
SUPPORTED_COLLECTIONS = [*ALL_COLLECTIONS, PARTITIONED_COLLECTION, CLUMPED_COLLECTION, WES_COLLECTION, GTEX_COLLECTION]
_GTEX_RE = re.compile(r"\b(tissue|tissues|expression|expressed|proteomics|rnaseq|tpm|adipose|liver|brain|pancreas|heart|lung|muscle|gtex)\b|组织表达|表达量", re.IGNORECASE)
_WES_RE = re.compile(r"\b(wes|whole[- ]exome|masks?|LoF_HC|5of5|5of5_LoF_LC|0of5_1pct|1of5_1pct|11of11|16of16)\b|外显子组", re.IGNORECASE)
_CLUMPED_RE = re.compile(
    r"\b(clumps?|clumped|lead[_ -]?snp|lead variants?|association (?:regions?|loci))\b|关联区域|先导变异",
    re.IGNORECASE,
)
_GENE_ASSOCIATION_RE = re.compile(r"\bgene[- ](?:level[- ])?association\b|\bgene[- ]based\b", re.IGNORECASE)
_COMMON_RE = re.compile(
    r"\b(common[- ]variant|common variants|common[- ]gene[- ]association|gwas|bf_common)\b",
    re.IGNORECASE,
)
_RARE_RE = re.compile(
    r"\b(rare[- ]variant|rare variants|rare[- ]gene[- ]association|bf_rare|gene-based test|gene based test)\b",
    re.IGNORECASE,
)
_ASSOC_RE = re.compile(
    r"\b(association|associated with|gene-phenotype|gene phenotype|evidence tiers?|huge)\b",
    re.IGNORECASE,
)
_BOTH_ASSOC_RE = re.compile(
    r"\b(common and rare|rare and common|common-and-rare)\b",
    re.IGNORECASE,
)
_GENE_RE = re.compile(
    r"\b(gene function|function|role of|role does|alternative names?|alias|ensembl|hgnc|entrez|uniprot|"
    r"genomic location|coordinates|which gene|identified by|ensg[0-9]+)\b",
    re.IGNORECASE,
)


def route_query(query: str, *, available_collections: list[str] | tuple[str, ...] | None = None) -> RouteDecision:
    available = list(ALL_COLLECTIONS if available_collections is None else available_collections)
    known_order = [*ALL_COLLECTIONS, PARTITIONED_COLLECTION, CLUMPED_COLLECTION, WES_COLLECTION, GTEX_COLLECTION]
    if set(available) - set(known_order):
        raise ValueError("Router received an unsupported collection")
    available = [name for name in known_order if name in available]
    matched: list[str] = []
    collections: set[str] = set()

    common = bool(_COMMON_RE.search(query))
    rare = bool(_RARE_RE.search(query))
    both = bool(_BOTH_ASSOC_RE.search(query))
    assoc = bool(_ASSOC_RE.search(query))
    ldsc = bool(_LDSC_RE.search(query))
    generic_ldsc = bool(_GENERIC_LDSC_RE.search(query))
    partitioned = bool(_PARTITIONED_RE.search(query))
    clumped = bool(_CLUMPED_RE.search(query))
    wes = bool(_WES_RE.search(query))
    if partitioned and not _EXPLICIT_CORRELATION_RE.search(query):
        ldsc = False
    gene = bool(_GENE_RE.search(query))
    if partitioned and not _EXPLICIT_COMMON_RE.search(query) and not assoc and not both:
        common = False
    if clumped and not _GENE_ASSOCIATION_RE.search(query) and not both:
        common = False

    if both or (common and rare):
        collections.update(["gene_association_common", "gene_association_rare"])
        matched.append("explicit_common_and_rare")
    else:
        if common:
            collections.add("gene_association_common")
            matched.append("explicit_common_variant")
        if rare:
            collections.add("gene_association_rare")
            matched.append("explicit_rare_variant")
        if assoc and not common and not rare and not ldsc and not partitioned and not wes and (not clumped or _GENE_ASSOCIATION_RE.search(query)):
            collections.update(["gene_association_common", "gene_association_rare"])
            matched.append("association_without_variant_class")

    if wes:
        collections.add(WES_COLLECTION)
        matched.append("wes_or_named_mask")
    if partitioned:
        collections.add(PARTITIONED_COLLECTION)
        matched.append("ldsc_partitioned_heritability")
    if clumped:
        collections.add(CLUMPED_COLLECTION)
        matched.append("clumped_region_or_lead_variant")
    if _GTEX_RE.search(query):
        collections.add(GTEX_COLLECTION)
        matched.append("gtex_tissue_expression")

    if ldsc or (generic_ldsc and not partitioned):
        collections.add("ldsc_genetic_correlation")
        matched.append("ldsc_or_trait_correlation")
        if generic_ldsc and not ldsc and not partitioned and PARTITIONED_COLLECTION in available:
            collections.add(PARTITIONED_COLLECTION)
            matched.append("ambiguous_ldsc_evidence")

    if gene:
        collections.add("gene_info")
        matched.append("gene_function_or_identifier")

    if not collections:
        return RouteDecision(collections=available, matched_rules=["unmatched_all_collections"])

    ordered = [name for name in available if name in collections]
    if not ordered:
        matched.append("requested_evidence_collection_unavailable")
    return RouteDecision(collections=ordered, matched_rules=matched)
