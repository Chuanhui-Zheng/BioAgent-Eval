"""Build a deduplicated pooled Top-10 candidate file for manual judging."""

from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from pathlib import Path


METHODS = ("bm25", "dense", "hybrid")


def load_results(path: Path) -> dict[str, dict]:
    rows = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                rows[row["query_id"]] = row
    return rows


def build_pool(input_dirs: dict[str, Path]) -> list[dict]:
    loaded = {
        method: load_results(directory / "per_query_results.jsonl")
        for method, directory in input_dirs.items()
    }
    query_ids = list(loaded["bm25"])
    if any(set(loaded[method]) != set(query_ids) for method in METHODS[1:]):
        raise ValueError("BM25, dense, and hybrid outputs do not contain the same query IDs")

    pooled = []
    for query_id in query_ids:
        base = loaded["bm25"][query_id]["example"]
        candidates: OrderedDict[str, dict] = OrderedDict()
        for method in METHODS:
            results = loaded[method][query_id]["routed"]["results"]
            for result in results[:10]:
                candidate = candidates.setdefault(
                    result["chunk_id"],
                    {
                        "chunk_id": result["chunk_id"],
                        "collection": result["collection"],
                        "source_methods": [],
                        "ranks": {},
                        "grade": None,
                        "review_note": "",
                    },
                )
                candidate["source_methods"].append(method)
                candidate["ranks"][method] = result["rank"]

        pooled.append(
            {
                "query_id": query_id,
                "query": base["query"],
                "query_type": base["query_type"],
                "answerable": base["answerable"],
                "candidates": list(candidates.values()),
            }
        )
    return pooled


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bm25-dir", type=Path, required=True)
    parser.add_argument("--dense-dir", type=Path, required=True)
    parser.add_argument("--hybrid-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    pool = build_pool(
        {
            "bm25": args.bm25_dir,
            "dense": args.dense_dir,
            "hybrid": args.hybrid_dir,
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in pool:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(pool)} pooled queries -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
