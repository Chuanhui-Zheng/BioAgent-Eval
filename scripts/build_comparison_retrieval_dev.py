"""Build a small comparison-query DEVELOPMENT set for retrieval/reranker tuning.

The existing dev sets contain no comparison questions, yet comparison is where
first-stage methods differ most. This set reuses the comparison-test question
templates but excludes every partitioned group, WES gene and clumped region that
carries a grade-2 label in any test or blind file, so tuning on it cannot see
test targets. Output: data/evaluation/retrieval_comparison_dev.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_comparison_retrieval_test as comparison  # noqa: E402
from build_expanded_retrieval_test import ROOT, load_clumped, load_jsonl, load_partitioned, load_wes  # noqa: E402

OUTPUT = ROOT / "data" / "evaluation" / "retrieval_comparison_dev.jsonl"
HELD_OUT = [
    *sorted((ROOT / "data" / "evaluation").glob("*test*.jsonl")),
    *sorted((ROOT / "data" / "evaluation" / "blind").glob("*.jsonl")),
]


def held_out_gold_ids() -> set[str]:
    gold: set[str] = set()
    for path in HELD_OUT:
        for row in load_jsonl(path):
            for item in row.get("relevance_judgments", []):
                if item.get("grade", 0) >= 2:
                    gold.add(item["chunk_id"])
            gold.update(row.get("gold_citations", []))
    return gold


def main() -> None:
    gold = held_out_gold_ids()
    groups = load_partitioned()
    wes = load_wes()
    chunk_to_key = {item["chunk_id"]: key for key, items in groups.items() for item in items}
    held_groups = {chunk_to_key[cid] for cid in gold if cid in chunk_to_key}
    held_genes = {cid.split(":")[2] for cid in gold if cid.startswith("wes:")}

    original_partitions, original_genes = comparison.used_partition_keys, comparison.used_wes_genes
    comparison.used_partition_keys = lambda mapping: original_partitions(mapping) | held_groups
    comparison.used_wes_genes = lambda: original_genes() | held_genes
    try:
        symbols = sorted(gene for gene, entry in wes.items() if entry["summary"])
        partitioned = comparison.partitioned_queries(groups, 1)
        wes_rows = comparison.wes_queries(wes, symbols, 101)
    finally:
        comparison.used_partition_keys, comparison.used_wes_genes = original_partitions, original_genes

    # Every third row keeps the easy/medium/hard mix while staying small.
    picked = partitioned[::3] + wes_rows[::3]
    rows = []
    for index, row in enumerate(picked, start=1):
        row = dict(row)
        row["query_id"] = f"dev-compare-{index:03d}"
        row["labeling_status"] = "programmatic_from_source_groups"
        row["notes"] = row.get("notes", "") + " Development only; disjoint from test/blind grade-2 targets."
        targets = {item["chunk_id"] for item in row["relevance_judgments"] if item["grade"] >= 2}
        if targets & gold:
            raise SystemExit(f"{row['query_id']} overlaps held-out gold labels")
        rows.append(row)
    regions = {item["chunk_id"] for item in load_clumped()}
    assert not any(t in regions for r in rows for t in r["assessed_chunk_ids"] if t in gold)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} development comparison queries -> {OUTPUT}")


if __name__ == "__main__":
    main()
