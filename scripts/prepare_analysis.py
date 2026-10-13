from __future__ import annotations
import argparse
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from analysis.data import DataStore
from analysis.statistics import parse_gmt


def main():
    parser = argparse.ArgumentParser(
        description="Build structured data indexes; optionally download public gene-set libraries (no user gene lists are sent)."
    )
    parser.add_argument("--download-libraries", action="store_true")
    args = parser.parse_args()
    if args.download_libraries:
        base = "https://maayanlab.cloud/Enrichr"
        with urllib.request.urlopen(
            base + "/datasetStatistics", timeout=30
        ) as response:
            stats = json.load(response)
        names = [row["libraryName"] for row in stats["statistics"]]
        directory = ROOT / "data/reference/gene_sets"
        directory.mkdir(parents=True, exist_ok=True)
        for prefix in ["WikiPathways_", "GO_Biological_Process_"]:
            candidates = sorted(
                name
                for name in names
                if name.startswith(prefix)
                and ("Human" in name if prefix == "WikiPathways_" else True)
            )
            if not candidates:
                raise RuntimeError("No public library found for " + prefix)
            name = candidates[-1]
            url = (
                base
                + "/geneSetLibrary?"
                + urllib.parse.urlencode({"mode": "text", "libraryName": name})
            )
            with urllib.request.urlopen(url, timeout=45) as response:
                data = response.read(16_000_001)
            if len(data) > 16_000_000:
                raise RuntimeError("Public library exceeds download limit")
            terms = parse_gmt(data.decode())
            (directory / (name + ".gmt")).write_bytes(data)
            (directory / (name + ".provenance.json")).write_text(
                json.dumps(
                    {
                        "library": name,
                        "source_url": url,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "terms": len(terms),
                        "retrieved_date": "2026-10-13",
                        "method": "Public library download; user genes never transmitted",
                    },
                    indent=2,
                )
            )
            print("Library ready:", name, len(terms))
    print(json.dumps(DataStore(ROOT).catalog(), indent=2))


if __name__ == "__main__":
    main()
