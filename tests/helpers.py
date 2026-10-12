from __future__ import annotations

from typing import Any

from retrieval.schema import SearchResult


def result(
    chunk_id: str,
    collection: str,
    *,
    rank: int = 1,
    metadata: dict[str, Any] | None = None,
    content: str = "Function: Approved evidence summary.",
) -> SearchResult:
    inferred = dict(metadata or {})
    if collection == "gene_info" and "gene_symbol" not in inferred:
        inferred["gene_symbol"] = chunk_id.split(":", 1)[-1]
        inferred["has_function_summary"] = True
    return SearchResult(
        chunk_id=chunk_id,
        collection=collection,
        rank=rank,
        score=1.0 / rank,
        method="fixture",
        chunk={
            "chunk_id": chunk_id,
            "collection": collection,
            "entity_type": "fixture",
            "title": f"Evidence {chunk_id}",
            "content": content,
            "metadata": inferred,
            "citation": {"source_name": "Approved fixture", "chunk_id": chunk_id},
        },
    )


class FakeBackend:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def search(self, query, top_k=10, collections=None, filters=None):
        self.calls.append({"query": query, "collections": collections, "filters": filters})
        return [r for r in self.results if collections is None or r.collection in collections][:top_k]
