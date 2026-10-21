"""Cross-encoder reranking (e.g. BAAI/bge-reranker-v2-m3) over a first-stage retriever.

The first stage (BM25, dense or hybrid RRF) supplies ``candidate_k`` passages
already restricted to the caller's effective collections; the cross-encoder only
reorders them, so reranking can never widen the access boundary. The final order
fuses the reranker rank with the first-stage rank:

    score = alpha / (rrf_k + rerank_rank) + (1 - alpha) / (rrf_k + first_stage_rank)

``alpha = 1`` is pure reranking. ``candidate_k``, ``alpha`` and the model are
selected on development questions only (scripts/tune_retrieval.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from retrieval.schema import SearchResult


class PairScorer(Protocol):
    model_name: str

    def score(self, query: str, passages: list[str]) -> list[float]: ...


def passage_text(result: SearchResult, records_by_id: dict[str, Any] | None = None, max_chars: int = 2400) -> str:
    chunk = result.chunk or {}
    title = chunk.get("title")
    content = chunk.get("content")
    if (title is None or content is None) and records_by_id and result.chunk_id in records_by_id:
        record = records_by_id[result.chunk_id]
        title, content = record.title, record.content
    text = f"{title or ''}\n{content or ''}".strip()
    return text[:max_chars]


class CrossEncoderScorer:
    """sentence-transformers CrossEncoder wrapper with device auto-selection."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", device: str = "auto",
                 max_length: int = 512, batch_size: int = 16, dtype: str = "float32") -> None:
        try:
            import torch
            from sentence_transformers import CrossEncoder
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Reranking requires: pip install -r requirements/embed.txt"
            ) from exc
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else (
                "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu")
        model_kwargs = {} if dtype == "float32" else {"torch_dtype": getattr(torch, dtype)}
        self.model = CrossEncoder(model_name, device=device, max_length=max_length, model_kwargs=model_kwargs)
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        scores = self.model.predict([(query, text) for text in passages], batch_size=self.batch_size,
                                    show_progress_bar=False)
        return [float(value) for value in scores]


def fuse_reranked(hits: list[SearchResult], scores: list[float], *, alpha: float, rrf_k: int,
                  top_k: int, model_name: str) -> list[SearchResult]:
    if len(hits) != len(scores):
        raise ValueError("one reranker score is required per candidate")
    order = sorted(range(len(hits)), key=lambda i: (-scores[i], hits[i].rank, hits[i].chunk_id))
    rerank_rank = {index: position for position, index in enumerate(order, start=1)}
    fused = []
    for index, hit in enumerate(hits):
        first_rank = index + 1
        value = alpha / (rrf_k + rerank_rank[index]) + (1.0 - alpha) / (rrf_k + first_rank)
        fused.append((value, rerank_rank[index], hit, scores[index], first_rank))
    fused.sort(key=lambda item: (-item[0], item[1], item[2].chunk_id))
    results = []
    for position, (value, r_rank, hit, raw, first_rank) in enumerate(fused[: max(0, top_k)], start=1):
        results.append(SearchResult(
            chunk_id=hit.chunk_id,
            collection=hit.collection,
            rank=position,
            score=float(value),
            method=f"{hit.method}+rerank",
            component_scores={**hit.component_scores, "first_stage_rank": first_rank,
                              "first_stage_score": hit.score, "rerank_score": raw, "rerank_rank": r_rank,
                              "rerank_model": model_name, "rerank_alpha": alpha},
            chunk=hit.chunk,
        ))
    return results


@dataclass
class RerankingSearcher:
    """Search backend that reranks a first-stage backend's candidates."""

    base: Any
    scorer: PairScorer
    candidate_k: int = 30
    alpha: float = 1.0
    rrf_k: int = 60
    last_latency_s: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if self.candidate_k <= 0:
            raise ValueError("candidate_k must be positive")
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        records = getattr(self.base, "records", None)
        self._records_by_id = {record.chunk_id: record for record in records} if records else {}

    @property
    def records(self):
        return getattr(self.base, "records", None)

    @property
    def meta(self) -> dict[str, Any]:
        return {**(getattr(self.base, "meta", {}) or {}),
                "reranker": {"model": self.scorer.model_name, "candidate_k": self.candidate_k,
                             "alpha": self.alpha, "rrf_k": self.rrf_k}}

    def search(self, query: str, top_k: int = 10, collections: list[str] | None = None,
               filters: dict[str, Any] | None = None) -> list[SearchResult]:
        if top_k <= 0:
            return []
        hits = self.base.search(query, top_k=max(top_k, self.candidate_k), collections=collections, filters=filters)
        candidates = hits[: max(top_k, self.candidate_k)]
        started = time.perf_counter()
        scores = self.scorer.score(query, [passage_text(hit, self._records_by_id) for hit in candidates])
        self.last_latency_s = time.perf_counter() - started
        return fuse_reranked(candidates, scores, alpha=self.alpha, rrf_k=self.rrf_k, top_k=top_k,
                             model_name=self.scorer.model_name)
