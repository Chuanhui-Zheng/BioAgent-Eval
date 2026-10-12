from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from chunking.utils import file_sha256


@dataclass(frozen=True)
class BenchmarkMetadata:
    label: str
    hash_filename: str
    comparison_label: str


def benchmark_metadata(path: Path, query_count: int | None = None) -> BenchmarkMetadata:
    """Return stable display and output names for an evaluation benchmark."""
    name = path.name.lower()
    if "dev" in name:
        label = "development"
        hash_filename = "dev_set.sha256.txt"
    elif "test" in name:
        label = "test"
        hash_filename = "test_set.sha256.txt"
    else:
        label = "benchmark"
        hash_filename = "benchmark.sha256.txt"

    count_label = "N" if query_count is None else str(query_count)
    return BenchmarkMetadata(
        label=label,
        hash_filename=hash_filename,
        comparison_label=f"same {count_label} queries, same router",
    )


def load_matching_metrics(output_dir: Path, benchmark_path: Path, metadata: BenchmarkMetadata) -> dict | None:
    """Load comparison metrics only when they were generated for this benchmark."""
    metrics_path = output_dir / "metrics.json"
    hash_path = output_dir / metadata.hash_filename
    if not metrics_path.exists() or not hash_path.exists():
        return None
    if hash_path.read_text(encoding="utf-8").strip() != file_sha256(benchmark_path):
        return None
    return json.loads(metrics_path.read_text(encoding="utf-8"))
