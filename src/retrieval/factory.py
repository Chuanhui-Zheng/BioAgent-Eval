"""Build the configured retrieval backend with an explicit, logged fallback chain.

Methods: ``bm25``, ``dense``, ``hybrid`` (BM25 + dense RRF), and the reranked
variants ``bm25_rerank`` / ``hybrid_rerank``. The default comes from
``pipeline.default_method`` in config/retrieval.yaml (chosen on dev questions)
and can be overridden with RAG_RETRIEVAL_METHOD. When the dense index, its
dependencies or the reranker are unavailable the factory degrades step by step
(hybrid_rerank -> hybrid -> bm25_rerank -> bm25) and records why, instead of
failing to start.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from retrieval.bm25_retriever import load_bm25_index
from retrieval.config import RetrievalConfig
from retrieval.corpus import LoadedCorpus

logger = logging.getLogger(__name__)

METHODS = ("bm25", "dense", "hybrid", "bm25_rerank", "hybrid_rerank")
_FALLBACKS = {
    "hybrid_rerank": ("hybrid_rerank", "hybrid", "bm25_rerank", "bm25"),
    "hybrid": ("hybrid", "bm25"),
    "dense": ("dense", "bm25"),
    "bm25_rerank": ("bm25_rerank", "bm25"),
    "bm25": ("bm25",),
}


@dataclass
class BackendBundle:
    backend: Any
    method: str
    requested_method: str
    fallback_reasons: list[str] = field(default_factory=list)


def reranker_settings(config: RetrievalConfig) -> dict[str, Any]:
    raw = config.raw.get("reranker", {}) or {}
    return {
        "model": str(raw.get("model", "BAAI/bge-reranker-v2-m3")),
        "candidate_k": int(raw.get("candidate_k", 30)),
        "alpha": float(raw.get("alpha", 1.0)),
        "rrf_k": int(raw.get("rrf_k", 60)),
        "max_length": int(raw.get("max_length", 512)),
        "batch_size": int(raw.get("batch_size", 16)),
        "device": str(raw.get("device", "auto")),
        "dtype": str(raw.get("dtype", "float32")),
    }


def configured_method(config: RetrievalConfig) -> str:
    method = os.environ.get("RAG_RETRIEVAL_METHOD") or (config.raw.get("pipeline", {}) or {}).get("default_method", "bm25")
    method = str(method).strip().lower()
    if method not in METHODS:
        raise ValueError(f"Unknown retrieval method '{method}'. Choose one of {METHODS}")
    return method


class _Components:
    def __init__(self, config: RetrievalConfig, corpus: LoadedCorpus, scorer: Any | None, encoder: Any | None):
        self.config, self.corpus = config, corpus
        self._bm25 = None
        self._dense = None
        self._scorer = scorer
        self._encoder = encoder

    def bm25(self):
        if self._bm25 is None:
            self._bm25 = load_bm25_index(self.config.index_dir, self.corpus.records,
                                         expected_chunk_hashes=self.corpus.chunk_hashes)
        return self._bm25

    def dense(self):
        if self._dense is None:
            from retrieval.dense_retriever import load_dense_index, load_encoder_from_config

            meta_path = self.config.dense_index_dir / "index_meta.json"
            if not meta_path.exists():
                raise FileNotFoundError(f"dense index missing: {meta_path} (run scripts/build_dense_index.py)")
            import json

            from pathlib import Path

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            # Keys may be absolute paths from another machine; compare by file name.
            stored = {Path(k).name: v for k, v in meta.get("chunk_hashes", {}).items()}
            current = {Path(k).name: v for k, v in self.corpus.chunk_hashes.items()}
            if stored != current:
                raise ValueError("dense index was built from a different corpus; rebuild it")
            with (self.config.dense_index_dir / "doc_map.jsonl").open(encoding="utf-8") as handle:
                order = [json.loads(line)["chunk_id"] for line in handle if line.strip()]
            if order != [record.chunk_id for record in self.corpus.records]:
                raise ValueError("dense index document order does not match the corpus; rebuild it")
            encoder = self._encoder or load_encoder_from_config(self.config, dtype=meta.get("dtype"))
            self._dense = load_dense_index(self.config.dense_index_dir, self.corpus.records, encoder)
        return self._dense

    def scorer(self):
        if self._scorer is None:
            from retrieval.reranker import CrossEncoderScorer

            settings = reranker_settings(self.config)
            self._scorer = CrossEncoderScorer(settings["model"], device=settings["device"],
                                              max_length=settings["max_length"],
                                              batch_size=settings["batch_size"], dtype=settings["dtype"])
        return self._scorer

    def build(self, method: str):
        from retrieval.hybrid_retriever import HybridRetriever
        from retrieval.reranker import RerankingSearcher

        if method == "bm25":
            return self.bm25()
        if method == "dense":
            return self.dense()
        if method in {"hybrid", "hybrid_rerank"}:
            base = HybridRetriever(self.bm25(), self.dense(), candidate_k=self.config.hybrid_candidate_k,
                                   rrf_k=self.config.hybrid_rrf_k, weight_bm25=self.config.hybrid_weight_bm25,
                                   weight_dense=self.config.hybrid_weight_dense)
        else:
            base = self.bm25()
        if method.endswith("_rerank"):
            settings = reranker_settings(self.config)
            return RerankingSearcher(base, self.scorer(), candidate_k=settings["candidate_k"],
                                     alpha=settings["alpha"], rrf_k=settings["rrf_k"])
        return base


def build_search_backend(config: RetrievalConfig, corpus: LoadedCorpus, method: str | None = None, *,
                         scorer: Any | None = None, encoder: Any | None = None) -> BackendBundle:
    requested = (method or configured_method(config)).lower()
    if requested not in METHODS:
        raise ValueError(f"Unknown retrieval method '{requested}'. Choose one of {METHODS}")
    components = _Components(config, corpus, scorer, encoder)
    reasons: list[str] = []
    for candidate in _FALLBACKS[requested]:
        try:
            backend = components.build(candidate)
        except Exception as exc:  # missing optional dependency, model or index
            if candidate == "bm25":
                raise
            reason = f"{candidate} unavailable: {type(exc).__name__}: {exc}"
            logger.warning(reason)
            reasons.append(reason)
            continue
        return BackendBundle(backend, candidate, requested, reasons)
    raise RuntimeError("no retrieval backend available")  # pragma: no cover - bm25 raises above
