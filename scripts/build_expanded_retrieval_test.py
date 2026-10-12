"""Build the 100-query expanded retrieval test set from indexed chunks.

The frozen baseline test set is not read or modified. Targets used by
data/evaluation/retrieval_expanded_dev.jsonl are excluded.
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from retrieval.router import route_query  # noqa: E402

OUTPUT = ROOT / "data" / "evaluation" / "retrieval_expanded_test.jsonl"
COLLECTIONS = [
    "gene_info",
    "ldsc_genetic_correlation",
    "gene_association_common",
    "gene_association_rare",
    "ldsc_partitioned_heritability",
    "variant_association_clumped",
    "gene_association_wes",
]
EXCLUDED_PARTITION_GROUPS = {
    ("accessible_chromatin", "adipose_tissue", "adipose_tissue"),
    ("accessible_chromatin", "adrenal_tissue", "adrenal_gland"),
    ("accessible_chromatin", "bile_duct", "cholangiocyte"),
}
EXCLUDED_WES_GENES = {"HIF3A", "ACTR1B", "FAM120AOS", "C16orf13"}
CROSS_GENES = ["INS", "TCF7L2", "ADCY5", "SLC30A8"]
CLUMP_CROSS_GENE = "GCK"
ANCESTRY_WORDS = {
    "EA": "East Asian ancestry code EA",
    "EU": "European ancestry code EU",
    "HS": "Hispanic ancestry code HS",
    "Mixed": "mixed ancestry code Mixed",
}
ANNOTATION_WORDS = {
    "accessible_chromatin": "accessible chromatin",
    "binding_sites": "binding sites",
    "promoter": "promoter",
    "enhancer": "enhancer",
}


def sig4(value: float) -> str:
    return f"{value:.4g}"


def words(value: str) -> str:
    return value.replace("_", " ")


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def existing_query_ids() -> set[str]:
    found = set()
    for path in (ROOT / "data" / "evaluation").glob("*.jsonl"):
        if path.name in {"manual_review_decisions.jsonl", OUTPUT.name}:
            continue
        for row in load_jsonl(path):
            if "query_id" in row:
                found.add(row["query_id"])
    return found


def load_partitioned() -> dict[tuple, list[dict]]:
    groups = defaultdict(list)
    path = ROOT / "artifacts" / "chunks" / "ldsc_partitioned_2hrG.chunks.jsonl"
    for row in load_jsonl(path):
        meta = row["metadata"]
        biosample = meta.get("biosample")
        key = (meta["annotation"], meta["tissue"], biosample)
        groups[key].append(
            {
                "chunk_id": row["chunk_id"],
                "ancestry": meta["ancestry"],
                "enrichment_beta": meta["enrichment_beta"],
                "p_value": meta["pValue"],
            }
        )
    return groups


def load_wes() -> dict[str, dict]:
    genes: dict[str, dict] = {}
    path = ROOT / "artifacts" / "chunks" / "wes_2hrG.chunks.jsonl"
    for row in load_jsonl(path):
        meta = row["metadata"]
        gene = meta["gene"]
        entry = genes.setdefault(gene, {"summary": None, "masks": {}})
        if row["chunk_id"].endswith(":summary"):
            parent = meta["raw_parent"]
            entry["summary"] = {
                "chunk_id": row["chunk_id"],
                "p_value": parent["pValue"],
                "beta": parent["beta"],
                "mask_count": meta["mask_count"],
            }
        else:
            raw = meta["raw_mask"]
            entry["masks"][raw["mask"]] = {
                "chunk_id": row["chunk_id"],
                "p_value": raw["pValue"],
                "beta": raw["beta"],
            }
    return genes


def load_clumped() -> list[dict]:
    path = ROOT / "artifacts" / "chunks" / "metaanalysis_clumped_2hrG_EU.chunks.jsonl"
    rows = []
    for row in load_jsonl(path):
        meta = row["metadata"]
        lead = next(member for member in meta["members"] if member["leadSNP"])
        rows.append(
            {
                "chunk_id": row["chunk_id"],
                "chromosome": meta["chromosome"],
                "clump": meta["clump"],
                "start": meta["clumpStart"],
                "end": meta["clumpEnd"],
                "member_count": meta["member_count"],
                "lead_variant": meta["lead_variant_id"],
                "p_value": lead["pValue"],
                "beta": lead["beta"],
            }
        )
    return rows


def load_gene_symbols() -> set[str]:
    path = ROOT / "artifacts" / "chunks" / "gene_info.chunks.jsonl"
    symbols = set()
    for row in load_jsonl(path):
        if row["chunk_id"].startswith("gene:"):
            symbols.add(row["chunk_id"].split(":", 1)[1])
    return symbols


def neighbors(symbol: str, ordered: list[str], limit: int) -> list[str]:
    prefix = symbol[:4] if len(symbol) >= 4 else symbol
    chosen = [item for item in ordered if item != symbol and item.startswith(prefix)]
    if len(chosen) < limit and symbol in ordered:
        index = ordered.index(symbol)
        distance = 1
        while len(chosen) < limit and distance < len(ordered):
            for probe in (index - distance, index + distance):
                if 0 <= probe < len(ordered) and ordered[probe] not in chosen and ordered[probe] != symbol:
                    chosen.append(ordered[probe])
                    if len(chosen) >= limit:
                        break
            distance += 1
    return chosen[:limit]


def example(
    query_id: str,
    query: str,
    query_type: str,
    difficulty: str,
    targets: list[str],
    graded: list[tuple[str, int]],
    answerable: bool,
    notes: str,
) -> dict:
    seen = set()
    assessed = []
    judgments = []
    for chunk_id, grade in graded:
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        assessed.append(chunk_id)
        judgments.append({"chunk_id": chunk_id, "grade": grade})
    return {
        "query_id": query_id,
        "query": query,
        "query_type": query_type,
        "difficulty": difficulty,
        "target_collections": targets,
        "assessed_chunk_ids": assessed,
        "relevance_judgments": judgments,
        "answerable": answerable,
        "notes": notes,
    }


def partition_queries(groups: dict[tuple, list[dict]]) -> list[dict]:
    by_annotation = defaultdict(list)
    for key in sorted(groups, key=lambda item: (item[0], item[1], item[2] or "")):
        annotation, _tissue, biosample = key
        if biosample is None or key in EXCLUDED_PARTITION_GROUPS:
            continue
        ancestries = {item["ancestry"] for item in groups[key]}
        if ancestries >= {"EA", "EU", "HS", "Mixed"}:
            by_annotation[annotation].append(key)
    quotas = {
        "binding_sites": 10,
        "promoter": 10,
        "enhancer": 9,
        "accessible_chromatin": 9,
    }
    picked = []
    for annotation, count in quotas.items():
        pool = by_annotation[annotation]
        step = len(pool) / count
        picked.extend(pool[int(i * step)] for i in range(count))
    difficulties = ["easy"] * 16 + ["medium"] * 16 + ["hard"] * 6
    random.Random(46).shuffle(difficulties)
    rows = []
    for index, key in enumerate(picked):
        annotation, tissue, biosample = key
        members = {item["ancestry"]: item for item in groups[key]}
        difficulty = difficulties[index]
        ancestry = ("EA", "EU", "HS", "Mixed")[index % 4]
        target = members[ancestry]
        negatives = [members[name]["chunk_id"] for name in ("EA", "EU", "HS", "Mixed") if name != ancestry]
        same_tissue = [
            item["chunk_id"]
            for other, items in groups.items()
            if other != key and other[1] == tissue and other[2] is not None
            for item in items
            if item["ancestry"] == ancestry and other[0] != annotation
        ][:4]
        same_annotation = [
            item["chunk_id"]
            for other, items in groups.items()
            if other != key and other[0] == annotation and other[1] != tissue and other[2] is not None
            for item in items
            if item["ancestry"] == ancestry
        ][:4]
        graded = [(target["chunk_id"], 2)] + [(chunk_id, 0) for chunk_id in negatives + same_tissue + same_annotation]
        biosample_text = words(biosample)
        tissue_text = words(tissue)
        annotation_text = ANNOTATION_WORDS[annotation]
        if difficulty == "easy":
            query = (
                f"For LDSC partitioned heritability of 2hrG, annotation {annotation}, "
                f"tissue {tissue}, biosample {biosample}, ancestry code {ancestry}, "
                "what enrichment_beta and enrichment_stdErr are reported?"
            )
        elif difficulty == "medium":
            query = (
                f"What heritability enrichment does the LDSC partitioned analysis report for "
                f"2-hour glucose in {tissue_text} ({biosample_text}), {annotation_text}, "
                f"{ANCESTRY_WORDS[ancestry]}?"
            )
        else:
            query = (
                "Which ancestry-specific partitioned heritability record for 2-hour glucose "
                f"reports enrichment_beta of approximately {sig4(target['enrichment_beta'])} "
                f"for {annotation_text} in {tissue_text}, biosample {biosample_text}?"
            )
        rows.append(
            example(
                f"test-partitioned-{index + 1:03d}",
                query,
                "ldsc_partitioned_heritability",
                difficulty,
                ["ldsc_partitioned_heritability"],
                graded,
                True,
                "Partitioned-heritability lookup. Other ancestries and nearby annotation or tissue records are hard negatives.",
            )
        )
    return rows


def wes_summary_queries(wes: dict[str, dict], symbols: list[str], reserved: set[str]) -> list[dict]:
    pool = [
        gene
        for gene in symbols
        if gene not in reserved and gene not in EXCLUDED_WES_GENES and wes[gene]["summary"]
    ]
    chosen = pool[200:222]
    difficulties = ["easy"] * 10 + ["medium"] * 10 + ["hard"] * 2
    rows = []
    for index, gene in enumerate(chosen):
        summary = wes[gene]["summary"]
        difficulty = difficulties[index]
        negative_ids = [
            wes[other]["summary"]["chunk_id"]
            for other in neighbors(gene, symbols, 8)
            if wes.get(other, {}).get("summary")
        ]
        if difficulty == "easy":
            query = (
                f"For the WES gene-level summary of {gene} and 2hrG, what top-level "
                "pValue, beta and supplied mask count are reported?"
            )
        elif difficulty == "medium":
            query = (
                f"What whole-exome sequencing summary is reported for {gene} and 2-hour glucose, "
                "including the source top-level beta?"
            )
        else:
            direction = "positive" if summary["beta"] > 0 else "negative"
            query = (
                f"Does the whole-exome summary for {gene} report a {direction} top-level beta "
                "for 2-hour glucose?"
            )
        rows.append(
            example(
                f"test-wes-{index + 1:03d}",
                query,
                "gene_association_wes",
                difficulty,
                ["gene_association_wes"],
                [(summary["chunk_id"], 2)] + [(chunk_id, 0) for chunk_id in negative_ids],
                True,
                "WES gene-summary lookup. Similar gene symbols are hard negatives.",
            )
        )
    return rows


def wes_mask_queries(wes: dict[str, dict], symbols: list[str], reserved: set[str]) -> list[dict]:
    preferred = ["LoF_HC", "5of5", "11of11", "16of16", "5of5_LoF_LC", "0of5_1pct", "1of5_1pct"]
    pool = []
    for gene in symbols:
        if gene in reserved or gene in EXCLUDED_WES_GENES or not wes[gene]["masks"]:
            continue
        labels = list(wes[gene]["masks"])
        if len(labels) < 2:
            continue
        pool.append(gene)
    chosen = pool[80:98]
    difficulties = ["easy"] * 7 + ["medium"] * 9 + ["hard"] * 2
    rows = []
    for index, gene in enumerate(chosen):
        masks = wes[gene]["masks"]
        label = next(item for item in preferred if item in masks)
        target = masks[label]
        difficulty = difficulties[index]
        negatives = [item["chunk_id"] for name, item in masks.items() if name != label]
        for other in neighbors(gene, symbols, 6):
            other_mask = wes.get(other, {}).get("masks", {}).get(label)
            if other_mask:
                negatives.append(other_mask["chunk_id"])
            if len(negatives) >= 12:
                break
        if difficulty == "easy":
            query = (
                f"For WES {gene} and 2hrG, what source-reported results are in the {label} mask?"
            )
        elif difficulty == "medium":
            query = (
                f"What whole-exome {label} mask result is reported for {gene} and 2-hour glucose?"
            )
        else:
            query = (
                f"Among the WES masks reported for {gene} and 2-hour glucose, which mask has "
                f"pValue approximately {sig4(target['p_value'])}?"
            )
        rows.append(
            example(
                f"test-wes-{index + 23:03d}",
                query,
                "gene_association_wes",
                difficulty,
                ["gene_association_wes"],
                [(target["chunk_id"], 2)] + [(chunk_id, 0) for chunk_id in negatives],
                True,
                "WES mask lookup. Other masks of the same gene and the same mask of similar genes are hard negatives.",
            )
        )
    return rows


def clumped_queries(regions: list[dict]) -> list[dict]:
    regions = sorted(regions, key=lambda item: (int(item["chromosome"]), item["start"]))
    difficulties = ["easy", "medium", "medium", "easy", "medium", "medium", "medium"]
    templates = [
        "Which source-designated lead variant is listed for the clumped association region of 2-hour glucose on chromosome {chromosome}, clump {clump}, spanning {start}-{end}?",
        "How many supplied member variants does the clumped association region for 2hrG contain on chromosome {chromosome}, clump {clump}, interval {start}-{end}?",
        "What lead-variant pValue is reported for the clumped association region of 2hrG on chromosome {chromosome}, clump {clump}, interval {start}-{end}?",
        "What lead-variant beta is reported for the clumped association region of 2-hour glucose on chromosome {chromosome}, clump {clump}, spanning {start}-{end}?",
        "Which clumped association region of 2hrG on chromosome {chromosome} lists lead variant {lead_variant}?",
        "For chromosome {chromosome}, what member count is reported in the clumped association region of 2hrG spanning {start}-{end}?",
        "What lead variant and member count are reported for the clumped association region of 2-hour glucose at chromosome {chromosome}:{start}-{end}?",
    ]
    rows = []
    for index, region in enumerate(regions):
        negatives = [item["chunk_id"] for item in regions if item["chunk_id"] != region["chunk_id"]]
        query = templates[index].format(**region)
        rows.append(
            example(
                f"test-clumped-{index + 1:03d}",
                query,
                "variant_association_clumped",
                difficulties[index],
                ["variant_association_clumped"],
                [(region["chunk_id"], 2)] + [(chunk_id, 0) for chunk_id in negatives],
                True,
                "Paraphrased clumped-region lookup. The other supplied regions are hard negatives.",
            )
        )
    return rows


def cross_queries(
    wes: dict[str, dict],
    symbols: list[str],
    gene_symbols: set[str],
    regions: list[dict],
) -> list[dict]:
    rows = []
    for index, gene in enumerate(CROSS_GENES):
        summary = wes[gene]["summary"]["chunk_id"]
        gene_id = f"gene:{gene}"
        negatives = []
        for other in neighbors(gene, symbols, 6):
            if wes.get(other, {}).get("summary"):
                negatives.append(wes[other]["summary"]["chunk_id"])
            if other in gene_symbols:
                negatives.append(f"gene:{other}")
        if index % 2 == 0:
            query = (
                f"What gene function is reported for {gene}, and what WES gene-level summary "
                f"is reported for {gene} and 2-hour glucose?"
            )
        else:
            query = (
                f"For {gene}, report the gene function and the whole-exome summary statistics "
                "for 2-hour glucose."
            )
        rows.append(
            example(
                f"test-cross-{101 + index}",
                query,
                "cross_collection",
                "hard",
                ["gene_info", "gene_association_wes"],
                [(gene_id, 2), (summary, 2)] + [(chunk_id, 0) for chunk_id in negatives],
                True,
                "Requires the gene_info record and the WES summary for the same gene.",
            )
        )
    region = regions[0]
    gene = CLUMP_CROSS_GENE
    negatives = [f"gene:{other}" for other in neighbors(gene, symbols, 4) if other in gene_symbols]
    negatives += [item["chunk_id"] for item in regions if item["chunk_id"] != region["chunk_id"]]
    query = (
        f"What gene function is reported for {gene}, and which lead variant is listed for the "
        f"clumped association region of 2hrG on chromosome {region['chromosome']}, "
        f"clump {region['clump']}, spanning {region['start']}-{region['end']}?"
    )
    rows.append(
        example(
            "test-cross-105",
            query,
            "cross_collection",
            "hard",
            ["gene_info", "variant_association_clumped"],
            [(f"gene:{gene}", 2), (region["chunk_id"], 2)] + [(chunk_id, 0) for chunk_id in negatives],
            True,
            "Requires the gene_info record and one clumped association region.",
        )
    )
    return rows


def unanswerable_queries(groups: dict[tuple, list[dict]], regions: list[dict]) -> list[dict]:
    def partition_distractors(annotation: str, tissue: str) -> list[str]:
        found = []
        for key, items in groups.items():
            if key[0] == annotation and key[1] == tissue:
                found.extend(item["chunk_id"] for item in items)
        return found[:8]

    specs = [
        (
            "What partitioned heritability enrichment_beta is reported for HbA1c, annotation promoter, tissue liver, biosample hepatocyte, ancestry code EA?",
            ["ldsc_partitioned_heritability"],
            partition_distractors("promoter", "liver"),
            "HbA1c is not a partitioned-heritability phenotype in the indexed corpus.",
        ),
        (
            "What partitioned heritability enrichment is reported for BMI, annotation enhancer, tissue pancreas, biosample islet, ancestry code EU?",
            ["ldsc_partitioned_heritability"],
            partition_distractors("enhancer", "pancreas"),
            "BMI is not a partitioned-heritability phenotype in the indexed corpus.",
        ),
        (
            "What partitioned heritability record reports enrichment_beta for LDL cholesterol, annotation binding_sites, tissue blood, biosample monocyte, ancestry code HS?",
            ["ldsc_partitioned_heritability"],
            partition_distractors("binding_sites", "blood"),
            "LDL cholesterol is not a partitioned-heritability phenotype in the indexed corpus.",
        ),
        (
            "What partitioned heritability enrichment_beta is reported for waist circumference, annotation accessible_chromatin, tissue muscle, biosample skeletal_muscle, ancestry code Mixed?",
            ["ldsc_partitioned_heritability"],
            partition_distractors("accessible_chromatin", "muscle"),
            "Waist circumference is not a partitioned-heritability phenotype in the indexed corpus.",
        ),
        (
            "For the WES gene-level summary of NOTAREALGENE99 and 2hrG, what top-level pValue and beta are reported?",
            ["gene_association_wes"],
            [],
            "NOTAREALGENE99 has no WES record.",
        ),
        (
            "For WES XXXFAKEGENE and 2hrG, what source-reported results are in the LoF_HC mask?",
            ["gene_association_wes"],
            [],
            "XXXFAKEGENE has no WES mask record.",
        ),
        (
            "What whole-exome summary is reported for TCF7L2 and HbA1c?",
            ["gene_association_wes"],
            ["wes:2hrG:TCF7L2:summary"],
            "The indexed WES summary is for 2hrG, not HbA1c.",
        ),
        (
            "What lead variant is reported for the clumped association region of 2hrG on chromosome 22, source clump 99, interval 1-5000?",
            ["variant_association_clumped"],
            [item["chunk_id"] for item in regions],
            "No supplied clumped region is on chromosome 22.",
        ),
        (
            "What lead variant is reported for the clumped association region of 2hrG, ancestry code AFR, chromosome 10, source clump 3, interval 114752503-114808903?",
            ["variant_association_clumped"],
            [item["chunk_id"] for item in regions],
            "The supplied clumped regions are EU, not AFR.",
        ),
        (
            "How many member variants are in the clumped association region of 2hrG on chromosome 1, source clump 8, interval 100-200?",
            ["variant_association_clumped"],
            [item["chunk_id"] for item in regions],
            "No supplied clumped region is on chromosome 1.",
        ),
    ]
    rows = []
    for index, (query, targets, negatives, notes) in enumerate(specs, start=1):
        rows.append(
            example(
                f"test-unanswerable-{100 + index}",
                query,
                "unanswerable",
                "hard",
                targets,
                [(chunk_id, 0) for chunk_id in negatives],
                False,
                notes,
            )
        )
    return rows


def validate(rows: list[dict], known_ids: set[str], prior_ids: set[str]) -> None:
    if len(rows) != 100:
        raise SystemExit(f"expected 100 queries, found {len(rows)}")
    ids = [row["query_id"] for row in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate query ids")
    overlap = set(ids) & prior_ids
    if overlap:
        raise SystemExit(f"query ids overlap existing benchmarks: {sorted(overlap)}")
    counts = defaultdict(int)
    difficulties = defaultdict(int)
    for row in rows:
        counts[row["query_type"]] += 1
        difficulties[row["difficulty"]] += 1
        grades = [item["grade"] for item in row["relevance_judgments"]]
        if row["answerable"] and 2 not in grades:
            raise SystemExit(f"{row['query_id']} has no grade-2 judgment")
        if not row["answerable"] and any(grade > 0 for grade in grades):
            raise SystemExit(f"{row['query_id']} unanswerable query has a positive grade")
        if [item["chunk_id"] for item in row["relevance_judgments"]] != row["assessed_chunk_ids"]:
            raise SystemExit(f"{row['query_id']} assessed ids diverge from judgments")
        missing = [chunk_id for chunk_id in row["assessed_chunk_ids"] if chunk_id not in known_ids]
        if missing:
            raise SystemExit(f"{row['query_id']} missing chunks: {missing[:5]}")
        route = route_query(row["query"], available_collections=COLLECTIONS)
        if set(route.collections) != set(row["target_collections"]):
            raise SystemExit(
                f"{row['query_id']} routed to {route.collections} via {route.matched_rules}, "
                f"expected {row['target_collections']}: {row['query']}"
            )
    expected = {
        "ldsc_partitioned_heritability": 38,
        "gene_association_wes": 40,
        "variant_association_clumped": 7,
        "cross_collection": 5,
        "unanswerable": 10,
    }
    if dict(counts) != expected:
        raise SystemExit(f"type counts {dict(counts)} != {expected}")
    if dict(difficulties) != {"easy": 35, "medium": 40, "hard": 25}:
        raise SystemExit(f"difficulty counts {dict(difficulties)}")
    print("types", dict(counts))
    print("difficulty", dict(difficulties))


def main() -> None:
    print("loading chunks")
    groups = load_partitioned()
    wes = load_wes()
    regions = load_clumped()
    gene_symbols = load_gene_symbols()
    wes_symbols = sorted(gene for gene, entry in wes.items() if entry["summary"])
    reserved = set(CROSS_GENES) | {CLUMP_CROSS_GENE}
    for gene in CROSS_GENES:
        if gene not in gene_symbols or not wes.get(gene, {}).get("summary"):
            raise SystemExit(f"{gene} is missing from gene_info or WES")
    if CLUMP_CROSS_GENE not in gene_symbols:
        raise SystemExit(f"{CLUMP_CROSS_GENE} is missing from gene_info")
    rows = []
    rows.extend(partition_queries(groups))
    summary_rows = wes_summary_queries(wes, wes_symbols, reserved)
    used_summary_genes = {
        row["relevance_judgments"][0]["chunk_id"].split(":")[2] for row in summary_rows
    }
    rows.extend(summary_rows)
    rows.extend(wes_mask_queries(wes, wes_symbols, reserved | used_summary_genes))
    rows.extend(clumped_queries(regions))
    rows.extend(cross_queries(wes, wes_symbols, gene_symbols, regions))
    rows.extend(unanswerable_queries(groups, regions))
    known = {item["chunk_id"] for items in groups.values() for item in items}
    known.update(item["chunk_id"] for item in regions)
    for gene, entry in wes.items():
        if entry["summary"]:
            known.add(entry["summary"]["chunk_id"])
        known.update(item["chunk_id"] for item in entry["masks"].values())
    known.update(f"gene:{symbol}" for symbol in gene_symbols)
    validate(rows, known, existing_query_ids())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} -> {OUTPUT}")


if __name__ == "__main__":
    main()
