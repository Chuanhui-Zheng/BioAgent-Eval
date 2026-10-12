from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if not PYTHON.exists():
    raise SystemExit("Demo environment not found. Run: python setup_demo.py")

raise SystemExit(
    subprocess.run(
        [
            str(PYTHON),
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--browser.gatherUsageStats=false",
        ],
        cwd=ROOT,
    ).returncode
)
