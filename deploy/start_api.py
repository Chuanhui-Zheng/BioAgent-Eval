"""Prepare a fresh container once, then serve the API."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "artifacts/indexes/bm25_title_content/index_meta.json").exists():
    from huggingface_hub import snapshot_download

    snapshot_download(
        "Qwen/Qwen3-Embedding-0.6B", allow_patterns=["*.json", "*.txt", "*.model"]
    )
    for script in ["prepare_api_corpus.py", "build_bm25_index.py"]:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT, check=True
        )
subprocess.run(
    [sys.executable, str(ROOT / "scripts/prepare_analysis.py")], cwd=ROOT, check=True
)
subprocess.run(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "server:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ],
    cwd=ROOT,
    check=True,
)
