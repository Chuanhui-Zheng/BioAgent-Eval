from __future__ import annotations

from types import SimpleNamespace

import pytest

from retrieval.factory import build_search_backend, configured_method
from retrieval.reranker import RerankingSearcher, fuse_reranked, passage_text
from retrieval.service import RetrievalRequest, RetrieverService
from tests.helpers import result


class KeywordScorer:
    """Deterministic stand-in for a cross-encoder: scores keyword overlap."""

    model_name = "fixture-reranker"

    def __init__(self):
        self.calls = []

    def score(self, query, passages):
        self.calls.append((query, passages))
        words = set(query.lower().split())
        return [float(len(words & set(text.lower().split()))) for text in passages]


class ListBackend:
    def __init__(self, hits):
        self.hits = hits
        self.records = None
        self.requested_k = []

    def search(self, query, top_k=10, collections=None, filters=None):
        self.requested_k.append(top_k)
        items = [h for h in self.hits if collections is None or h.collection in collections]
        return items[:top_k]


def hits():
    return [
        result("gene:A", "gene_info", rank=1, content="unrelated text"),
        result("gene:B", "gene_info", rank=2, content="insulin secretion beta cell"),
        result("rare:C", "gene_association_rare", rank=3, content="insulin"),
    ]


def test_pure_rerank_reorders_by_cross_encoder_score():
    searcher = RerankingSearcher(ListBackend(hits()), KeywordScorer(), candidate_k=3, alpha=1.0)
    ranked = searcher.search("insulin secretion", top_k=3)
    assert [r.chunk_id for r in ranked] == ["gene:B", "rare:C", "gene:A"]
    assert ranked[0].component_scores["first_stage_rank"] == 2
    assert ranked[0].component_scores["rerank_model"] == "fixture-reranker"
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_alpha_zero_keeps_first_stage_order():
    searcher = RerankingSearcher(ListBackend(hits()), KeywordScorer(), candidate_k=3, alpha=0.0)
    assert [r.chunk_id for r in searcher.search("insulin secretion", top_k=3)] == ["gene:A", "gene:B", "rare:C"]


def test_candidate_depth_and_top_k_truncation():
    backend = ListBackend(hits())
    searcher = RerankingSearcher(backend, KeywordScorer(), candidate_k=20, alpha=1.0)
    assert len(searcher.search("insulin", top_k=1)) == 1
    assert backend.requested_k == [20]


def test_reranking_cannot_leak_outside_effective_collections():
    service = RetrieverService(RerankingSearcher(ListBackend(hits()), KeywordScorer(), candidate_k=5), "bm25_rerank")
    response = service.retrieve(RetrievalRequest("insulin secretion function", authorized_collections=("gene_info",)))
    assert {r.collection for r in response.results} <= {"gene_info"}


def test_fuse_requires_one_score_per_candidate():
    with pytest.raises(ValueError):
        fuse_reranked(hits(), [1.0], alpha=1.0, rrf_k=60, top_k=3, model_name="m")


def test_invalid_settings_rejected():
    with pytest.raises(ValueError):
        RerankingSearcher(ListBackend([]), KeywordScorer(), alpha=1.5)
    with pytest.raises(ValueError):
        RerankingSearcher(ListBackend([]), KeywordScorer(), candidate_k=0)


def test_passage_text_falls_back_to_records():
    bare = SimpleNamespace(chunk={}, chunk_id="x")
    record = SimpleNamespace(title="T", content="C")
    assert passage_text(bare, {"x": record}) == "T\nC"


def _config(tmp_path, method="hybrid_rerank"):
    return SimpleNamespace(
        raw={"pipeline": {"default_method": method}, "reranker": {"candidate_k": 7, "alpha": 0.5}},
        index_dir=tmp_path / "bm25", dense_index_dir=tmp_path / "missing_dense",
        hybrid_candidate_k=50, hybrid_rrf_k=60, hybrid_weight_bm25=1.0, hybrid_weight_dense=1.0,
    )


def test_factory_degrades_when_dense_index_is_missing(tmp_path, monkeypatch):
    bm25 = ListBackend(hits())
    monkeypatch.setattr("retrieval.factory.load_bm25_index", lambda *a, **k: bm25)
    corpus = SimpleNamespace(records=[], chunk_hashes={})
    bundle = build_search_backend(_config(tmp_path), corpus, scorer=KeywordScorer())
    assert bundle.requested_method == "hybrid_rerank"
    assert bundle.method == "bm25_rerank"
    assert any("hybrid_rerank unavailable" in reason for reason in bundle.fallback_reasons)
    assert isinstance(bundle.backend, RerankingSearcher)
    assert (bundle.backend.candidate_k, bundle.backend.alpha) == (7, 0.5)


def test_method_override_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_RETRIEVAL_METHOD", "bm25")
    assert configured_method(_config(tmp_path)) == "bm25"
    monkeypatch.setenv("RAG_RETRIEVAL_METHOD", "magic")
    with pytest.raises(ValueError):
        configured_method(_config(tmp_path))
