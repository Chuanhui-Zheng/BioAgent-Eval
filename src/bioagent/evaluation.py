from __future__ import annotations

from statistics import mean, median
from typing import Any, Iterable


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_traces(traces: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(traces)
    latencies = [float(row["latency_s"]) for row in rows if row.get("latency_s") is not None]
    calls = [event for row in rows for event in row.get("events", []) if event.get("event") == "tool_execution"]
    errors = [event for event in calls if event.get("status") == "error"]
    duplicates = [event for event in calls if event.get("duplicate")]
    return {
        "runs": len(rows),
        "completed_rate": sum(row.get("final_status") == "completed" for row in rows) / len(rows) if rows else None,
        "mean_steps": mean([len([e for e in row.get("events", []) if e.get("event") == "model_decision"]) for row in rows]) if rows else None,
        "mean_tool_calls": len(calls) / len(rows) if rows else None,
        "tool_failure_rate": len(errors) / len(calls) if calls else None,
        "duplicate_tool_call_rate": len(duplicates) / len(calls) if calls else None,
        "recovery_success_rate": sum(
            any(e.get("status") == "error" for e in row.get("events", [])) and row.get("final_status") == "completed"
            for row in rows
        ) / max(1, sum(any(e.get("status") == "error" for e in row.get("events", [])) for row in rows)),
        "latency_s": {
            "mean": mean(latencies) if latencies else None,
            "median": median(latencies) if latencies else None,
            "p95": percentile(latencies, 0.95),
        },
        "usage": {
            "input_tokens": _sum_usage(rows, "input_tokens"),
            "output_tokens": _sum_usage(rows, "output_tokens"),
            "total_tokens": _sum_usage(rows, "total_tokens"),
            "estimated": any(row.get("usage", {}).get("estimated", False) for row in rows),
        },
        "limitations": [
            "Metrics are computed from supplied execution traces and do not establish scientific answer quality.",
            "Recovery success requires a trace containing an error event followed by completed status.",
        ],
    }


def _sum_usage(rows: list[dict[str, Any]], field: str) -> int | None:
    values = [row.get("usage", {}).get(field) for row in rows]
    if any(value is None for value in values):
        return None
    return sum(int(value) for value in values)
