"""Build the 50-query comparison retrieval test set.

A comparison query needs several evidence chunks of the same group at once, so
every query has two or more grade-2 targets. The earlier benchmarks are not read
for tuning; they are only used to avoid reusing the same partitioned groups,
WES genes and query ids.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_expanded_retrieval_test import (  # noqa: E402
    ANCESTRY_WORDS,
    ANNOTATION_WORDS,
    COLLECTIONS,
    EXCLUDED_PARTITION_GROUPS,
    EXCLUDED_WES_GENES,
    ROOT,
    example,
    load_clumped,
    load_jsonl,
    load_partitioned,
    load_wes,
    words,
)
from retrieval.router import route_query  # noqa: E402

OUTPUT = ROOT / "data" / "evaluation" / "retrieval_comparison_test.jsonl"
ANCESTRY_PAIRS = [("EA", "EU"), ("EU", "HS"), ("EA", "HS"), ("EU", "Mixed"), ("EA", "Mixed"), ("HS", "Mixed")]
MASK_SETS = [
    ("5of5", "0of5_1pct"),
    ("5of5", "1of5_1pct"),
    ("5of5_LoF_LC", "0of5_1pct"),
    ("0of5_1pct", "1of5_1pct"),
    ("5of5", "5of5_LoF_LC"),
]
PARTITION_QUOTAS = {"binding_sites": 8, "promoter": 8, "enhancer": 7, "accessible_chromatin": 7}


def used_partition_keys(chunk_to_key: dict[str, tuple]) -> set[tuple]:
    used = set(EXCLUDED_PARTITION_GROUPS)
    for name in ("retrieval_expanded_test.jsonl", "retrieval_expanded_dev.jsonl"):
        path = ROOT / "data" / "evaluation" / name
        for row in load_jsonl(path):
            for item in row["relevance_judgments"]:
                if item["grade"] >= 2 and item["chunk_id"] in chunk_to_key:
                    used.add(chunk_to_key[item["chunk_id"]])
    return used


def used_wes_genes() -> set[str]:
    used = set(EXCLUDED_WES_GENES)
    for name in ("retrieval_expanded_test.jsonl", "retrieval_expanded_dev.jsonl"):
        path = ROOT / "data" / "evaluation" / name
        for row in load_jsonl(path):
            for item in row["relevance_judgments"]:
                if item["grade"] >= 2 and item["chunk_id"].startswith("wes:"):
                    used.add(item["chunk_id"].split(":")[2])
    return used


def partitioned_queries(groups: dict[tuple, list[dict]], start: int) -> list[dict]:
    chunk_to_key = {item["chunk_id"]: key for key, items in groups.items() for item in items}
    used = used_partition_keys(chunk_to_key)
    by_annotation = defaultdict(list)
    for key in sorted(groups, key=lambda item: (item[0], item[1], item[2] or "")):
        annotation, _tissue, biosample = key
        if biosample is None or key in used:
            continue
        if {item["ancestry"] for item in groups[key]} >= {"EA", "EU", "HS", "Mixed"}:
            by_annotation[annotation].append(key)
    chosen = {}
    for annotation, count in PARTITION_QUOTAS.items():
        pool = by_annotation[annotation]
        step = len(pool) / count
        chosen[annotation] = [pool[int(i * step)] for i in range(count)]
    # round-robin across annotations so each difficulty tier mixes them
    picked = []
    for position in range(max(PARTITION_QUOTAS.values())):
        for annotation in PARTITION_QUOTAS:
            if position < len(chosen[annotation]):
                picked.append(chosen[annotation][position])
    rows = []
    for index, key in enumerate(picked):
        annotation, tissue, biosample = key
        members = {item["ancestry"]: item for item in groups[key]}
        if index < 12:
            ancestries, difficulty = ANCESTRY_PAIRS[index % 6], "easy"
        elif index < 24:
            ancestries, difficulty = ANCESTRY_PAIRS[index % 6], "medium"
        elif index < 28:
            ancestries = [("EA", "EU", "HS"), ("EU", "HS", "Mixed"), ("EA", "EU", "Mixed"), ("EA", "HS", "Mixed")][index - 24]
            difficulty = "hard"
        else:
            ancestries, difficulty = ("EA", "EU", "HS", "Mixed"), "hard"
        targets = [members[name]["chunk_id"] for name in ancestries]
        negatives = [members[name]["chunk_id"] for name in members if name not in ancestries]
        same_tissue = [
            item["chunk_id"]
            for other, items in groups.items()
            if other != key and other[1] == tissue and other[2] is not None
            for item in items
            if item["ancestry"] in ancestries and other[0] != annotation
        ][:4]
        tissue_text, biosample_text = words(tissue), words(biosample)
        joined = " and ".join(ancestries) if len(ancestries) == 2 else ", ".join(ancestries[:-1]) + f" and {ancestries[-1]}"
        if difficulty == "easy":
            query = (
                f"For LDSC partitioned heritability of 2hrG, annotation {annotation}, tissue {tissue}, "
                f"biosample {biosample}, compare enrichment_beta between ancestry codes {joined}."
            )
        elif difficulty == "medium":
            first, second = ancestries
            query = (
                f"How does the LDSC partitioned heritability enrichment for 2-hour glucose in "
                f"{tissue_text} ({biosample_text}), {ANNOTATION_WORDS[annotation]}, differ between "
                f"{ANCESTRY_WORDS[first]} and {ANCESTRY_WORDS[second]}?"
            )
        elif len(ancestries) == 3:
            query = (
                f"Compare the LDSC partitioned heritability enrichment_beta of 2hrG for "
                f"{ANNOTATION_WORDS[annotation]} in {tissue_text}, biosample {biosample_text}, "
                f"across ancestry codes {joined}."
            )
        else:
            query = (
                f"Across all four ancestry codes, which has the largest enrichment_beta in the LDSC "
                f"partitioned heritability of 2hrG for {ANNOTATION_WORDS[annotation]}, tissue "
                f"{tissue_text}, biosample {biosample_text}?"
            )
        rows.append(
            example(
                f"test-compare-{start + index:03d}",
                query,
                "comparison_partitioned",
                difficulty,
                ["ldsc_partitioned_heritability"],
                [(chunk_id, 2) for chunk_id in targets] + [(chunk_id, 0) for chunk_id in negatives + same_tissue],
                True,
                f"Ancestry comparison within one group; needs all {len(targets)} ancestry records.",
            )
        )
    return rows


def wes_queries(wes: dict[str, dict], symbols: list[str], start: int) -> list[dict]:
    used = used_wes_genes()
    pool = [
        gene for gene in symbols
        if gene not in used and wes[gene]["summary"] and len(wes[gene]["masks"]) >= 3
        and {"5of5", "0of5_1pct", "1of5_1pct"} <= set(wes[gene]["masks"])
    ]
    pool = pool[300:]
    rows = []
    number = start

    def neighbors_masks(gene: str, labels: list[str]) -> list[str]:
        return [item["chunk_id"] for name, item in wes[gene]["masks"].items() if name not in labels]

    # mask-vs-mask: 4 easy, 4 medium, 2 hard (three masks)
    for index in range(10):
        gene = pool[index]
        masks = wes[gene]["masks"]
        if index < 4:
            labels, difficulty = list(MASK_SETS[index % len(MASK_SETS)]), "easy"
            query = f"For WES {gene} and 2hrG, compare the {labels[0]} and {labels[1]} mask results."
        elif index < 8:
            labels, difficulty = list(MASK_SETS[(index + 1) % len(MASK_SETS)]), "medium"
            query = (
                f"How do the whole-exome {labels[0]} and {labels[1]} mask pValues differ for {gene} "
                "and 2-hour glucose?"
            )
        else:
            labels, difficulty = ["5of5", "0of5_1pct", "1of5_1pct"], "hard"
            query = (
                f"Across the 5of5, 0of5_1pct and 1of5_1pct WES masks for {gene} and 2-hour glucose, "
                "which mask has the smallest pValue?"
            )
        targets = [masks[label]["chunk_id"] for label in labels]
        rows.append(
            example(
                f"test-compare-{number:03d}",
                query,
                "comparison_wes",
                difficulty,
                ["gene_association_wes"],
                [(chunk_id, 2) for chunk_id in targets] + [(chunk_id, 0) for chunk_id in neighbors_masks(gene, labels)],
                True,
                f"Mask comparison for one gene; needs all {len(targets)} mask chunks.",
            )
        )
        number += 1
    # summary-vs-mask: 2 easy, 2 medium, 2 hard
    for offset in range(6):
        gene = pool[10 + offset]
        masks = wes[gene]["masks"]
        label = ["5of5", "0of5_1pct", "1of5_1pct"][offset % 3]
        summary = wes[gene]["summary"]["chunk_id"]
        target_mask = masks[label]["chunk_id"]
        if offset < 2:
            difficulty = "easy"
            query = f"For WES {gene} and 2hrG, compare the gene-level summary with the {label} mask result."
        elif offset < 4:
            difficulty = "medium"
            query = (
                f"How does the whole-exome gene-level summary of {gene} for 2-hour glucose differ from "
                f"its {label} mask result?"
            )
        else:
            difficulty = "hard"
            query = (
                f"Is the top-level WES pValue for {gene} and 2-hour glucose lower than the pValue of its "
                f"{label} mask?"
            )
        others = [item["chunk_id"] for name, item in masks.items() if name != label]
        rows.append(
            example(
                f"test-compare-{number:03d}",
                query,
                "comparison_wes",
                difficulty,
                ["gene_association_wes"],
                [(summary, 2), (target_mask, 2)] + [(chunk_id, 0) for chunk_id in others],
                True,
                "Summary versus one mask of the same gene; needs both chunks.",
            )
        )
        number += 1
    return rows


def clumped_queries(regions: list[dict], start: int) -> list[dict]:
    regions = sorted(regions, key=lambda item: (int(item["chromosome"]), item["start"]))
    by_chr = {item["chromosome"]: item for item in regions}
    specs = [
        ("easy", ["10", "15"], "Compare the lead variants of the clumped association regions of 2hrG on chromosome {a} (clump {ca}) and chromosome {b} (clump {cb})."),
        ("easy", ["2", "3"], "Compare the lead variants of the clumped association regions of 2hrG on chromosome {a} (clump {ca}) and chromosome {b} (clump {cb})."),
        ("medium", ["7", "19"], "Which clumped association region of 2-hour glucose has more supplied member variants: chromosome {a} (clump {ca}) or chromosome {b} (clump {cb})?"),
        ("hard", ["8", "10", "19"], "Among the clumped association regions of 2hrG on chromosomes {a}, {b} and {c}, which has the smallest lead-variant pValue?"),
    ]
    rows = []
    for index, (difficulty, chromosomes, template) in enumerate(specs):
        selected = [by_chr[name] for name in chromosomes]
        values = {"a": chromosomes[0], "b": chromosomes[1], "ca": selected[0]["clump"], "cb": selected[1]["clump"]}
        if len(chromosomes) == 3:
            values["c"] = chromosomes[2]
        target_ids = [item["chunk_id"] for item in selected]
        negatives = [item["chunk_id"] for item in regions if item["chunk_id"] not in target_ids]
        rows.append(
            example(
                f"test-compare-{start + index:03d}",
                template.format(**values),
                "comparison_clumped",
                difficulty,
                ["variant_association_clumped"],
                [(chunk_id, 2) for chunk_id in target_ids] + [(chunk_id, 0) for chunk_id in negatives],
                True,
                f"Comparison across {len(target_ids)} supplied clumped regions.",
            )
        )
    return rows


def prior_query_ids() -> set[str]:
    found = set()
    for path in (ROOT / "data" / "evaluation").glob("*.jsonl"):
        if path.name in {"manual_review_decisions.jsonl", OUTPUT.name}:
            continue
        found.update(row["query_id"] for row in load_jsonl(path) if "query_id" in row)
    return found


def validate(rows: list[dict], known: set[str], prior_ids: set[str]) -> None:
    ids = [row["query_id"] for row in rows]
    if len(rows) != 50 or len(set(ids)) != 50:
        raise SystemExit(f"expected 50 unique queries, found {len(rows)} / {len(set(ids))}")
    if set(ids) & prior_ids:
        raise SystemExit("query ids overlap an existing benchmark")
    counts = defaultdict(int)
    difficulty = defaultdict(int)
    for row in rows:
        counts[row["query_type"]] += 1
        difficulty[row["difficulty"]] += 1
        golds = [item["chunk_id"] for item in row["relevance_judgments"] if item["grade"] >= 2]
        if len(golds) < 2:
            raise SystemExit(f"{row['query_id']} has fewer than two targets")
        missing = [chunk_id for chunk_id in row["assessed_chunk_ids"] if chunk_id not in known]
        if missing:
            raise SystemExit(f"{row['query_id']} missing chunks: {missing[:3]}")
        route = route_query(row["query"], available_collections=COLLECTIONS)
        if set(route.collections) != set(row["target_collections"]):
            raise SystemExit(f"{row['query_id']} routed to {route.collections} via {route.matched_rules}: {row['query']}")
    if dict(counts) != {"comparison_partitioned": 30, "comparison_wes": 16, "comparison_clumped": 4}:
        raise SystemExit(f"type counts {dict(counts)}")
    if dict(difficulty) != {"easy": 20, "medium": 19, "hard": 11}:
        raise SystemExit(f"difficulty counts {dict(difficulty)}")
    print("types", dict(counts))
    print("difficulty", dict(difficulty))


def main() -> None:
    groups = load_partitioned()
    wes = load_wes()
    regions = load_clumped()
    symbols = sorted(gene for gene, entry in wes.items() if entry["summary"])
    rows = []
    rows.extend(partitioned_queries(groups, 1))
    rows.extend(wes_queries(wes, symbols, 31))
    rows.extend(clumped_queries(regions, 47))
    known = {item["chunk_id"] for items in groups.values() for item in items}
    known.update(item["chunk_id"] for item in regions)
    for entry in wes.values():
        if entry["summary"]:
            known.add(entry["summary"]["chunk_id"])
        known.update(item["chunk_id"] for item in entry["masks"].values())
    validate(rows, known, prior_query_ids())
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} -> {OUTPUT}")


if __name__ == "__main__":
    main()
