"""Rebuild all configured collections before publishing their shared manifest."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from chunk_ldsc_partitioned import build_partitioned, build_clumped, build_wes
from prepare_partitioned_retrieval import prepare_manifest


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts/chunk_corpus.py")], check=True)
    config = ROOT / "config/ldsc_partitioned_dev.yaml"
    for build in (build_partitioned, build_clumped, build_wes):
        report = build(config, project_root=ROOT, paths_config_file=ROOT / "config/paths.yaml")
        if report["status"] != "passed":
            raise RuntimeError(f"{build.__name__}: {report.get('error', report)}")
        print(f"{build.__name__}: {report['chunks']} chunks validated")
    result = prepare_manifest(ROOT / "config/retrieval.yaml", project_root=ROOT)
    print(result)


if __name__ == "__main__":
    main()
