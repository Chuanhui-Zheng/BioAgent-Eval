"""Merge pooled top-10 candidates into the expanded retrieval test judgments.

Designated grade-2 chunks stay grade 2. Every other pooled candidate is recorded
as an explicit grade-0 review. Chunks that were not retrieved are left unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "evaluation" / "retrieval_expanded_test.jsonl"
POOL = ROOT / "artifacts" / "evaluation" / "retrieval_expanded_test" / "pooled_candidates.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK)
    parser.add_argument("--pool", type=Path, default=POOL)
    args = parser.parse_args()
    benchmark = args.benchmark
    examples = {row["query_id"]: row for row in load_jsonl(benchmark)}
    pooled = load_jsonl(args.pool)
    if len(pooled) != len(examples):
        raise SystemExit(f"pool has {len(pooled)} queries, benchmark has {len(examples)}")
    for item in pooled:
        example = examples[item["query_id"]]
        grades = {
            judgment["chunk_id"]: int(judgment["grade"])
            for judgment in example["relevance_judgments"]
        }
        for candidate in item["candidates"]:
            grades.setdefault(candidate["chunk_id"], 0)
        if example["answerable"] and not any(grade >= 2 for grade in grades.values()):
            raise SystemExit(f"{example['query_id']} lost its grade-2 judgment")
        if not example["answerable"] and any(grade > 0 for grade in grades.values()):
            raise SystemExit(f"{example['query_id']} gained a positive unanswerable grade")
        example["relevance_judgments"] = [
            {"chunk_id": chunk_id, "grade": grade} for chunk_id, grade in grades.items()
        ]
        example["assessed_chunk_ids"] = list(grades)
    with benchmark.open("w", encoding="utf-8", newline="\n") as handle:
        for example in examples.values():
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")
    print(f"updated {len(examples)} queries -> {benchmark}")


if __name__ == "__main__":
    main()
