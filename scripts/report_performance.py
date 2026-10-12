"""Summarise recorded retrieval latency and serialized index sizes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import fmean, median


def percentile(values: list[float], percentage: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * percentage / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_latencies(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p95": None}
    return {
        "n": len(values),
        "mean": round(fmean(values), 6),
        "median": round(median(values), 6),
        "p95": round(percentile(values, 95), 6),
    }


def directory_size(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def _latencies(path: Path) -> list[float]:
    values = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                latency = row.get("routed", {}).get("latency_s")
                if latency is not None:
                    values.append(float(latency))
    return values


def _method_result(result_dir: Path, index_dir: Path) -> dict:
    result_path = result_dir / "per_query_results.jsonl"
    latencies = _latencies(result_path) if result_path.exists() else []
    size = directory_size(index_dir)
    return {
        "latency_s": summarize_latencies(latencies),
        "serialized_index_size_bytes": size if size else None,
        "document_encoding_time_s": "not_recorded",
        "index_build_time_s": "not_recorded",
        "cold_start_load_time_s": "not_recorded",
        "search_only_latency_s": "not_separately_recorded",
        "end_to_end_query_latency_s": "not_separately_recorded",
        "source": {
            "evaluation_dir": str(result_dir),
            "index_dir": str(index_dir),
        },
    }


def _format_seconds(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def _write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# Retrieval Performance Summary",
        "",
        "Latency values are extracted from the existing final per-query evaluation outputs; no retriever was rerun.",
        "",
        "| Method | Mean (s) | Median (s) | P95 (s) | Serialized index size |",
        "|---|---:|---:|---:|---:|",
    ]
    for method, data in report["methods"].items():
        latency = data["latency_s"]
        size = data["serialized_index_size_bytes"]
        size_text = "—" if size is None else f"{size / (1024 ** 2):.2f} MiB"
        lines.append(
            f"| {method} | {_format_seconds(latency['mean'])} | "
            f"{_format_seconds(latency['median'])} | {_format_seconds(latency['p95'])} | {size_text} |"
        )
    lines += [
        "",
        "Build time, document encoding time, cold-start load time, and separately isolated search-only/end-to-end timings were not recorded in the existing runs.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/evaluation/performance"))
    parser.add_argument("--bm25-results", type=Path, default=Path("artifacts/evaluation/bm25_test"))
    parser.add_argument("--dense-results", type=Path, default=Path("artifacts/evaluation/dense_test"))
    parser.add_argument("--hybrid-results", type=Path, default=Path("artifacts/evaluation/hybrid_test"))
    parser.add_argument("--bm25-index", type=Path, default=Path("artifacts/indexes/bm25_title_content"))
    parser.add_argument("--dense-index", type=Path, default=Path("artifacts/indexes/dense_qwen3_06b"))
    args = parser.parse_args()

    report = {
        "methods": {
            "bm25": _method_result(args.bm25_results, args.bm25_index),
            "dense": _method_result(args.dense_results, args.dense_index),
            "hybrid": _method_result(
                args.hybrid_results,
                args.bm25_index,
            ),
        }
    }
    report["methods"]["hybrid"]["source"]["index_note"] = (
        "Hybrid uses the BM25 and dense indexes; combined size requires summing both index directories."
    )
    dense_size = report["methods"]["dense"]["serialized_index_size_bytes"] or 0
    bm25_size = report["methods"]["bm25"]["serialized_index_size_bytes"] or 0
    report["methods"]["hybrid"]["serialized_index_size_bytes"] = bm25_size + dense_size

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "performance_summary.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    _write_markdown(args.output_dir / "report.md", report)
    print(json.dumps(report, indent=2))
    print(f"Wrote performance summary -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
