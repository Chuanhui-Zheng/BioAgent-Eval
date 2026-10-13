from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from retrieval.router import SUPPORTED_COLLECTIONS, route_query
from retrieval.schema import SearchResult


class SearchBackend(Protocol):
    def search(
        self,
        query: str,
        top_k: int = 10,
        collections: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]: ...


@dataclass(frozen=True)
class RetrievalRequest:
    question: str
    authorized_collections: tuple[str, ...] = tuple(SUPPORTED_COLLECTIONS)
    top_k: int = 10
    filters: dict[str, Any] = field(default_factory=dict)
    use_router: bool = True

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("question must not be empty")
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        invalid = sorted(set(self.authorized_collections) - set(SUPPORTED_COLLECTIONS))
        if invalid:
            raise ValueError(f"unknown authorized collections: {invalid}")


@dataclass
class RetrievalResponse:
    question: str
    authorized_collections: list[str]
    routed_collections: list[str]
    effective_collections: list[str]
    matched_rules: list[str]
    results: list[SearchResult]
    method: str
    latency_s: float
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrieverService:
    backend: SearchBackend
    method: str

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        authorized = [name for name in SUPPORTED_COLLECTIONS if name in request.authorized_collections]
        if request.use_router:
            decision = route_query(request.question, available_collections=authorized)
            routed = decision.collections
            rules = decision.matched_rules
        else:
            routed = list(SUPPORTED_COLLECTIONS)
            rules = ["router_disabled"]
        effective = [name for name in routed if name in authorized]
        started = time.perf_counter()
        results = (
            self.backend.search(
                request.question,
                top_k=request.top_k,
                collections=effective,
                filters=request.filters,
            )
            if effective
            else []
        )
        overview = None
        if hasattr(self.backend, "records") and effective:
            from retrieval.association_overview import select_association_overview
            overview = select_association_overview(request.question, self.backend.records, effective, request.filters, request.top_k)
            if overview is not None:
                results = overview
        latency = time.perf_counter() - started
        leaked = [item.chunk_id for item in results if item.collection not in effective]
        if leaked:
            raise PermissionError(f"retrieval isolation violation: {leaked}")
        return RetrievalResponse(
            question=request.question,
            authorized_collections=authorized,
            routed_collections=list(routed),
            effective_collections=effective,
            matched_rules=list(rules),
            results=results,
            method="source_statistic_overview" if overview is not None else self.method,
            latency_s=latency,
            diagnostics={"result_count": len(results), "isolation_violations": 0,
                         "ranking_note": "Common records are ordered by source bf_common > 1; rare records use source significance and ascending pValue. Evidence classes are interleaved, not combined into a target ranking." if overview is not None else None},
        )
