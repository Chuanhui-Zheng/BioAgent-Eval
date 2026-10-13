"""Rebuild source-versioned expression chunks."""
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from chunking.gtex_chunker import build_gtex
if __name__ == "__main__":
    print(json.dumps(build_gtex(ROOT), indent=2))
