"""Shared machinery for dev-set tuning and frozen test evaluation of retrieval methods.

All runs go through ``RetrieverService`` (router, access boundary and the
association-overview override) so measured behaviour equals served behaviour.
First-stage candidate lists are computed once at depth ``depth``; reranking
configurations then reuse cached cross-encoder scores, which is exact because
every first stage returns a stable ranked prefix.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retrieval.metrics import aggregate_dev_metrics
from retrieval.reranker import fuse_reranked, passage_text
from retrieval.schema import SearchResult
from retrieval.service import RetrievalRequest, RetrieverService

HELD_OUT_MARKERS = ("test", "blind")


def load_examples(paths: list[Path], *, allow_held_out: bool) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        if not allow_held_out and any(marker in path.name.lower() for marker in HELD_OUT_MARKERS):
            raise SystemExit(f"Refusing to tune on held-out file {path.name}; use development sets only")
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                row.setdefault("query", row.get("question"))
                row["_source"] = path.name
                rows.append(row)
    return rows


@dataclass
class FirstStageRun:
    name: str
    results: dict[str, list[SearchResult]] = field(default_factory=dict)
    routes: dict[str, list[str]] = field(default_factory=dict)
    overview: dict[str, bool] = field(default_factory=dict)
    latency_s: dict[str, float] = field(default_factory=dict)


def run_first_stage(name: str, backend: Any, examples: list[dict[str, Any]], depth: int = 50) -> FirstStageRun:
    service = RetrieverService(backend, name)
    run = FirstStageRun(name)
    for example in examples:
        started = time.perf_counter()
        response = service.retrieve(RetrievalRequest(example["query"], top_k=depth))
        qid = example["query_id"]
        run.latency_s[qid] = time.perf_counter() - started
        run.results[qid] = response.results
        run.routes[qid] = response.effective_collections
        run.overview[qid] = response.method == "source_statistic_overview"
    return run


class ScoreCache:
    """Cross-encoder scores cached per (model, query_id, chunk_id)."""

    def __init__(self, scorer: Any, records_by_id: dict[str, Any]):
        self.scorer = scorer
        self.records_by_id = records_by_id
        self.scores: dict[tuple[str, str], float] = {}
        self.pairs_scored = 0
        self.seconds = 0.0

    def ensure(self, example: dict[str, Any], hits: list[SearchResult]) -> None:
        qid = example["query_id"]
        missing = [hit for hit in hits if (qid, hit.chunk_id) not in self.scores]
        if not missing:
            return
        started = time.perf_counter()
        values = self.scorer.score(example["query"], [passage_text(hit, self.records_by_id) for hit in missing])
        self.seconds += time.perf_counter() - started
        self.pairs_scored += len(missing)
        for hit, value in zip(missing, values):
            self.scores[(qid, hit.chunk_id)] = value

    def get(self, qid: str, hits: list[SearchResult]) -> list[float]:
        return [self.scores[(qid, hit.chunk_id)] for hit in hits]

    @property
    def seconds_per_pair(self) -> float:
        return self.seconds / self.pairs_scored if self.pairs_scored else 0.0


def ranked_lists(run: FirstStageRun, examples: list[dict[str, Any]], *, top_k: int = 10,
                 cache: ScoreCache | None = None, candidate_k: int = 0, alpha: float = 1.0,
                 rrf_k: int = 60) -> dict[str, list[SearchResult]]:
    output = {}
    for example in examples:
        qid = example["query_id"]
        hits = run.results[qid]
        if cache is None or candidate_k <= 0 or run.overview[qid]:
            output[qid] = hits[:top_k]
            continue
        candidates = hits[: max(top_k, candidate_k)]
        cache.ensure(example, candidates)
        output[qid] = fuse_reranked(candidates, cache.get(qid, candidates), alpha=alpha, rrf_k=rrf_k,
                                    top_k=top_k, model_name=getattr(cache.scorer, "model_name", "reranker"))
    return output


def all_targets_at_k(ranked: dict[str, list[SearchResult]], examples: list[dict[str, Any]], k: int = 10) -> float | None:
    """Share of multi-target (comparison) queries whose grade-2 targets are ALL in the top k."""
    values = []
    for example in examples:
        gold = {j["chunk_id"] for j in example.get("relevance_judgments", []) if j.get("grade", 0) >= 2}
        if len(gold) < 2:
            continue
        top = {hit.chunk_id for hit in ranked[example["query_id"]][:k]}
        values.append(1.0 if gold <= top else 0.0)
    return sum(values) / len(values) if values else None


def score(ranked: dict[str, list[SearchResult]], run: FirstStageRun, examples: list[dict[str, Any]],
          report_ks: tuple[int, ...] = (1, 3, 5, 10)) -> dict[str, Any]:
    rows = [{"example": example,
             "view": {"results": [{"chunk_id": hit.chunk_id} for hit in ranked[example["query_id"]]]},
             "route": {"collections": run.routes[example["query_id"]]}} for example in examples]
    metrics = aggregate_dev_metrics(rows, report_ks, "view")
    metrics["AllTargets@10"] = all_targets_at_k(ranked, examples, 10)
    metrics["by_source"] = {}
    for source in sorted({example["_source"] for example in examples}):
        subset = [row for row in rows if row["example"]["_source"] == source]
        part = aggregate_dev_metrics(subset, report_ks, "view")["metrics"]
        part["AllTargets@10"] = all_targets_at_k(ranked, [r["example"] for r in subset], 10)
        part["n"] = len(subset)
        metrics["by_source"][source] = part
    return metrics
