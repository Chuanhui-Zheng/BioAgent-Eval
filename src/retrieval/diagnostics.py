from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from retrieval.config import RetrievalConfig


def environment_diagnostics(config: RetrievalConfig) -> dict[str, Any]:
    dependencies = {
        name: importlib.util.find_spec(name) is not None
        for name in ("yaml", "numpy", "bm25s", "faiss", "sentence_transformers", "torch")
    }
    indexes: dict[str, Any] = {}
    for name, directory in (("bm25", config.index_dir), ("dense", config.dense_index_dir)):
        meta_file = directory / "index_meta.json"
        payload: dict[str, Any] = {"path": str(directory), "available": meta_file.exists()}
        if meta_file.exists():
            payload["metadata"] = json.loads(meta_file.read_text(encoding="utf-8"))
        indexes[name] = payload
    return {"dependencies": dependencies, "indexes": indexes}


def write_diagnostics(config: RetrievalConfig, output: Path) -> dict[str, Any]:
    payload = environment_diagnostics(config)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
