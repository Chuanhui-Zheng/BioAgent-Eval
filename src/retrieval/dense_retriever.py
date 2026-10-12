from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import faiss
import numpy as np

from retrieval.corpus import LoadedCorpus, metadata_matches
from retrieval.schema import ChunkRecord, SearchResult

ProgressFn = Callable[[int, int, float, float], None]


class Encoder(Protocol):
    dimension: int
    model_name: str
    revision: str
    device: str

    def encode_documents(self, texts: list[str]) -> np.ndarray: ...

    def encode_queries(self, texts: list[str]) -> np.ndarray: ...


class MockEncoder:
    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension
        self.model_name = "mock"
        self.revision = "mock"
        self.device = "cpu"

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            seed = abs(hash(text)) % (2**32)
            rng = np.random.default_rng(seed)
            vectors[row] = rng.standard_normal(self.dimension).astype(np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)
        return vectors / norms

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)


_WEIGHT_FILENAMES = (
    "model.safetensors",
    "model.safetensors.index.json",
    "pytorch_model.bin",
)


def embedding_model_is_cached(model_name: str, cache_dir: str | Path | None = None) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ModuleNotFoundError:
        return False

    kwargs: dict[str, Any] = {}
    if cache_dir is not None:
        kwargs["cache_dir"] = str(cache_dir)
    config_path = try_to_load_from_cache(repo_id=model_name, filename="config.json", **kwargs)
    if not isinstance(config_path, str):
        return False
    return any(
        isinstance(
            try_to_load_from_cache(repo_id=model_name, filename=name, **kwargs),
            str,
        )
        for name in _WEIGHT_FILENAMES
    )


def ensure_embedding_model_downloaded(model_name: str, cache_dir: str | Path | None = None) -> Path:
    from huggingface_hub import snapshot_download
    from huggingface_hub.constants import HF_HUB_CACHE

    cache = str(cache_dir) if cache_dir is not None else HF_HUB_CACHE
    if embedding_model_is_cached(model_name, cache):
        print(f"Embedding model already cached locally: {model_name}", flush=True)
        print(f"Hugging Face model cache: {cache}", flush=True)
        return Path(cache)

    print(
        f"Embedding model {model_name} not found locally. "
        f"Downloading to {cache} (~1GB+, network required).",
        flush=True,
    )
    print(
        "See the progress bar below. Set HF_TOKEN for higher Hugging Face rate limits.",
        flush=True,
    )
    try:
        snapshot_path = snapshot_download(repo_id=model_name, cache_dir=cache)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download {model_name}. Check network or set HF_TOKEN and retry. "
            f"Reason: {exc}"
        ) from exc
    print(f"Model download complete: {snapshot_path}", flush=True)
    return Path(snapshot_path)


class SentenceTransformerEncoder:
    def __init__(
        self,
        model_name: str,
        device: str,
        max_seq_length: int,
        dimension: int,
    ) -> None:
        try:
            # Windows: transformers/sentence-transformers may import pandas after torch
            # and abort with 0xc0000374 unless pandas is already loaded.
            import pandas  # noqa: F401
            import torch
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            missing = getattr(exc, "name", None) or "torch/sentence-transformers"
            raise ModuleNotFoundError(
                f"Missing {missing}. For GPU, install with: "
                "pip install torch --index-url https://download.pytorch.org/whl/cu126 && "
                "pip install sentence-transformers"
            ) from exc

        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        elif device == "cuda" and not torch.cuda.is_available():
            print("CUDA not available, falling back to CPU", flush=True)
            device = "cpu"
        self.model_name = model_name
        self.device = device
        self.dimension = dimension
        ensure_embedding_model_downloaded(model_name)
        print(f"Loading embedding model {model_name} on {device}...", flush=True)
        self.model = SentenceTransformer(model_name, device=device)
        self.model.max_seq_length = max_seq_length
        self.revision = str(
            getattr(getattr(self.model, "model_card_data", None), "base_model_revision", None)
            or getattr(self.model, "revision", None)
            or "unpinned"
        )
        print(f"Model ready. revision={self.revision} max_seq_length={max_seq_length}", flush=True)

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            prompt_name="query",
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(vectors, dtype=np.float32)


def default_progress(done: int, total: int, elapsed_s: float, eta_s: float) -> None:
    if done != total and done % 1024 != 0:
        return
    percent = (100.0 * done / total) if total else 100.0
    print(
        f"[dense] {done}/{total} ({percent:.1f}%) elapsed={elapsed_s:.0f}s eta={eta_s:.0f}s",
        flush=True,
    )


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (vectors / norms).astype(np.float32)


@dataclass
class DenseIndex:
    faiss_index: Any
    records: list[ChunkRecord]
    encoder: Encoder
    meta: dict[str, Any]

    def search(
        self,
        query: str,
        top_k: int = 10,
        collections: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            return []
        allowed = [
            index
            for index, record in enumerate(self.records)
            if (collections is None or record.collection in collections)
            and metadata_matches(record, filters)
        ]
        if not allowed:
            return []
        allowed_set = set(allowed)
        n_docs = len(self.records)
        filtered = collections is not None or filters
        retrieve_k = min(n_docs, top_k if not filtered else min(n_docs, max(top_k * 20, 200)))
        query_vec = _l2_normalize(self.encoder.encode_queries([query]))
        scores, indices = self.faiss_index.search(query_vec, retrieve_k)
        ranked: list[SearchResult] = []
        for rank_pos, (doc_index, score) in enumerate(zip(indices[0], scores[0]), start=1):
            doc_index = int(doc_index)
            if doc_index < 0:
                continue
            if filtered and doc_index not in allowed_set:
                continue
            record = self.records[doc_index]
            ranked.append(
                SearchResult(
                    chunk_id=record.chunk_id,
                    collection=record.collection,
                    rank=len(ranked) + 1,
                    score=float(score),
                    method="dense",
                    component_scores={"dense": float(score), "dense_rank": rank_pos},
                    chunk=record.to_dict(),
                )
            )
            if len(ranked) >= top_k:
                break
        return ranked


def encode_corpus(
    records: list[ChunkRecord],
    encoder: Encoder,
    batch_size: int,
    progress: ProgressFn | None = default_progress,
) -> np.ndarray:
    texts = [record.content for record in records]
    total = len(texts)
    chunks: list[np.ndarray] = []
    started = time.perf_counter()
    for start in range(0, total, batch_size):
        batch = texts[start : start + batch_size]
        encoded = encoder.encode_documents(batch)
        if encoded.shape[1] != encoder.dimension:
            raise ValueError(
                f"Encoder dimension {encoded.shape[1]} != configured {encoder.dimension}"
            )
        chunks.append(_l2_normalize(encoded))
        done = min(start + batch_size, total)
        elapsed = time.perf_counter() - started
        rate = done / elapsed if elapsed > 0 else 0.0
        eta = (total - done) / rate if rate > 0 else 0.0
        if progress is not None:
            progress(done, total, elapsed, eta)
    return np.vstack(chunks) if chunks else np.zeros((0, encoder.dimension), dtype=np.float32)


def build_dense_index(
    corpus: LoadedCorpus,
    encoder: Encoder,
    batch_size: int,
    progress: ProgressFn | None = default_progress,
) -> DenseIndex:
    vectors = encode_corpus(corpus.records, encoder, batch_size, progress=progress)
    index = faiss.IndexFlatIP(encoder.dimension)
    index.add(vectors)
    meta = {
        "model": encoder.model_name,
        "revision": encoder.revision,
        "dimension": encoder.dimension,
        "normalized": True,
        "similarity": "ip",
        "faiss_index": "IndexFlatIP",
        "device": encoder.device,
        "document_count": len(corpus.records),
        "chunk_hashes": corpus.chunk_hashes,
        "collection_counts": corpus.collection_counts,
        "embed_field": "content",
        "identifier_boost": False,
    }
    return DenseIndex(faiss_index=index, records=corpus.records, encoder=encoder, meta=meta)


def save_dense_index(index: DenseIndex, index_dir: Path) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index.faiss_index, str(index_dir / "index.faiss"))
    with (index_dir / "doc_map.jsonl").open("w", encoding="utf-8") as handle:
        for position, record in enumerate(index.records):
            handle.write(
                json.dumps(
                    {
                        "index": position,
                        "chunk_id": record.chunk_id,
                        "collection": record.collection,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    with (index_dir / "index_meta.json").open("w", encoding="utf-8") as handle:
        json.dump(index.meta, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_dense_index(index_dir: Path, records: list[ChunkRecord], encoder: Encoder) -> DenseIndex:
    meta_path = index_dir / "index_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Dense index metadata not found: {meta_path}")
    with meta_path.open("r", encoding="utf-8") as handle:
        meta = json.load(handle)
    faiss_index = faiss.read_index(str(index_dir / "index.faiss"))
    if faiss_index.ntotal != len(records):
        raise ValueError(
            f"FAISS ntotal {faiss_index.ntotal} != corpus size {len(records)}"
        )
    if faiss_index.d != encoder.dimension:
        raise ValueError(f"FAISS dim {faiss_index.d} != encoder dim {encoder.dimension}")
    return DenseIndex(faiss_index=faiss_index, records=records, encoder=encoder, meta=meta)


def load_encoder_from_config(config) -> Encoder:
    return SentenceTransformerEncoder(
        model_name=config.dense_model,
        device=config.dense_device,
        max_seq_length=config.dense_max_seq_length,
        dimension=config.dense_dimension,
    )
