from __future__ import annotations

import argparse
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"


def environment_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the Scientific RAG demonstration.")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild chunks and BM25 index.")
    args = parser.parse_args()

    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required.")

    if not environment_python().exists():
        print(f"Creating virtual environment at {VENV_DIR}")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)

    python = str(environment_python())
    run(python, "-m", "pip", "install", "--upgrade", "pip")
    run(python, "-m", "pip", "install", "-r", "requirements-demo.txt")
    run(python, "-m", "pip", "install", "-e", ".", "--no-deps")

    chunk_marker = ROOT / "artifacts" / "manifest.json"
    if args.rebuild or not chunk_marker.exists():
        run(python, "scripts/chunk_corpus.py")

    index_marker = ROOT / "artifacts" / "indexes" / "bm25_title_content" / "index_meta.json"
    if args.rebuild or not index_marker.exists():
        run(python, "scripts/build_bm25_index.py")

    print("\nSetup complete. Start the demo with: python run_demo.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
