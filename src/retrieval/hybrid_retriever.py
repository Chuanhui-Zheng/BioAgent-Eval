from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from retrieval.schema import SearchResult


class ComponentSearcher(Protocol):
    def search(
        self,
        query: str,
        top_k: int = 10,
        collections: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]: ...


def rrf_fuse(
    bm25_hits: list[SearchResult],
    dense_hits: list[SearchResult],
    *,
    rrf_k: int = 60,
    weight_bm25: float = 1.0,
    weight_dense: float = 1.0,
    top_k: int = 10,
) -> list[SearchResult]:
    by_id: dict[str, dict[str, Any]] = {}

    def add(hits: list[SearchResult], method: str) -> None:
        for item in hits:
            entry = by_id.setdefault(
                item.chunk_id,
                {
                    "chunk_id": item.chunk_id,
                    "collection": item.collection,
                    "chunk": item.chunk,
                    "bm25": 0.0,
                    "bm25_rank": None,
                    "dense": 0.0,
                    "dense_rank": None,
                },
            )
            if method == "bm25":
                entry["bm25"] = item.score
                entry["bm25_rank"] = int(item.rank)
            else:
                entry["dense"] = item.score
                entry["dense_rank"] = int(item.rank)
            if item.chunk:
                entry["chunk"] = item.chunk
            if item.collection:
                entry["collection"] = item.collection

    add(bm25_hits, "bm25")
    add(dense_hits, "dense")

    fused: list[SearchResult] = []
    for entry in by_id.values():
        rrf = 0.0
        ranks: list[int] = []
        if entry["bm25_rank"] is not None:
            rrf += weight_bm25 / (rrf_k + entry["bm25_rank"])
            ranks.append(entry["bm25_rank"])
        if entry["dense_rank"] is not None:
            rrf += weight_dense / (rrf_k + entry["dense_rank"])
            ranks.append(entry["dense_rank"])
        best_component_rank = min(ranks) if ranks else 10**9
        fused.append(
            SearchResult(
                chunk_id=entry["chunk_id"],
                collection=entry["collection"],
                rank=0,
                score=float(rrf),
                method="hybrid_rrf",
                component_scores={
                    "bm25": entry["bm25"],
                    "bm25_rank": entry["bm25_rank"],
                    "dense": entry["dense"],
                    "dense_rank": entry["dense_rank"],
                    "rrf": float(rrf),
                    "best_component_rank": best_component_rank,
                },
                chunk=entry["chunk"] or {},
            )
        )

    fused.sort(
        key=lambda item: (
            -item.score,
            item.component_scores["best_component_rank"],
            item.chunk_id,
        )
    )
    trimmed = fused[: max(0, top_k)]
    for index, item in enumerate(trimmed, start=1):
        item.rank = index
    return trimmed


@dataclass
class HybridRetriever:
    bm25: ComponentSearcher
    dense: ComponentSearcher
    candidate_k: int = 50
    rrf_k: int = 60
    weight_bm25: float = 1.0
    weight_dense: float = 1.0

    def search(
        self,
        query: str,
        top_k: int = 10,
        collections: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            return []
        retrieve_k = max(top_k, self.candidate_k)
        bm25_hits = self.bm25.search(
            query, top_k=retrieve_k, collections=collections, filters=filters
        )
        dense_hits = self.dense.search(
            query, top_k=retrieve_k, collections=collections, filters=filters
        )
        return rrf_fuse(
            bm25_hits,
            dense_hits,
            rrf_k=self.rrf_k,
            weight_bm25=self.weight_bm25,
            weight_dense=self.weight_dense,
            top_k=top_k,
        )
