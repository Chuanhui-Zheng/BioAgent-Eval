from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ChunkSource:
    collection: str
    path: Path


@dataclass(frozen=True)
class RetrievalConfig:
    project_root: Path
    config_file: Path
    chunk_sources: tuple[ChunkSource, ...]
    manifest_file: Path
    text_fields: tuple[str, ...]
    index_dir: Path
    dense_index_dir: Path
    dense_model: str
    dense_dimension: int
    dense_batch_size: int
    dense_max_seq_length: int
    dense_device: str
    hybrid_candidate_k: int
    hybrid_rrf_k: int
    hybrid_weight_bm25: float
    hybrid_weight_dense: float
    top_k: int
    report_ks: tuple[int, ...]
    dev_set: Path
    eval_output_dir: Path
    dense_eval_output_dir: Path
    hybrid_eval_output_dir: Path
    raw: dict[str, Any]


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def load_retrieval_config(
    project_root: Path,
    config_file: Path | None = None,
) -> RetrievalConfig:
    config_path = (config_file or project_root / "config" / "retrieval.yaml").resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Retrieval config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    root_value = data.get("project_root", ".")
    resolved_root = project_root.resolve() if root_value == "." else _resolve(project_root, root_value)

    sources = tuple(
        ChunkSource(collection=item["collection"], path=_resolve(resolved_root, item["path"]))
        for item in data["chunks"]
    )
    retrieval = data.get("retrieval", {})
    evaluation = data.get("evaluation", {})
    bm25 = data.get("bm25", {})
    dense = data.get("dense", {})
    hybrid = data.get("hybrid", {})
    report_ks = tuple(int(value) for value in retrieval.get("report_ks", [5, 10]))
    top_k = int(retrieval.get("top_k", max(report_ks) if report_ks else 10))
    if report_ks and top_k < max(report_ks):
        top_k = max(report_ks)

    return RetrievalConfig(
        project_root=resolved_root,
        config_file=config_path,
        chunk_sources=sources,
        manifest_file=_resolve(resolved_root, data.get("manifest", "artifacts/manifest.json")),
        text_fields=tuple(bm25.get("text_fields", ["title", "content"])),
        index_dir=_resolve(resolved_root, bm25.get("index_dir", "artifacts/indexes/bm25_title_content")),
        dense_index_dir=_resolve(
            resolved_root, dense.get("index_dir", "artifacts/indexes/dense_qwen3_06b")
        ),
        dense_model=str(dense.get("model", "Qwen/Qwen3-Embedding-0.6B")),
        dense_dimension=int(dense.get("dimension", 1024)),
        dense_batch_size=int(dense.get("batch_size", 8)),
        dense_max_seq_length=int(dense.get("max_seq_length", 512)),
        dense_device=str(dense.get("device", "cuda")),
        hybrid_candidate_k=int(hybrid.get("candidate_k", 50)),
        hybrid_rrf_k=int(hybrid.get("rrf_k", 60)),
        hybrid_weight_bm25=float(hybrid.get("weight_bm25", 1.0)),
        hybrid_weight_dense=float(hybrid.get("weight_dense", 1.0)),
        top_k=top_k,
        report_ks=report_ks or (top_k,),
        dev_set=_resolve(resolved_root, evaluation.get("dev_set", "data/evaluation/retrieval_dev.jsonl")),
        eval_output_dir=_resolve(
            resolved_root, evaluation.get("output_dir", "artifacts/evaluation/bm25_dev")
        ),
        dense_eval_output_dir=_resolve(
            resolved_root, evaluation.get("dense_output_dir", "artifacts/evaluation/dense_dev")
        ),
        hybrid_eval_output_dir=_resolve(
            resolved_root, evaluation.get("hybrid_output_dir", "artifacts/evaluation/hybrid_dev")
        ),
        raw=data,
    )
