"""Versioned GTEx source summaries; source units have not been confirmed."""
from __future__ import annotations
import csv
import json
import math
import os
import statistics
from collections import defaultdict
from pathlib import Path
from chunking.utils import file_sha256

VERSION = "gtex-2.0"

def build_gtex(root: Path) -> dict:
    data_root = Path(os.environ.get("BIOAGENT_DATA_ROOT", str(root))).resolve()
    raw = data_root / "data/raw/gtx_tissue_expression"
    paths = {"rna": raw / "ALL_GENES_GTEx_RNAseq.csv", "protein": raw / "ALL_GENES_GTEx_Proteomics.csv"}
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f"Required GTEx source missing: {path}")
    sources = {kind: {"source_file": str(path.relative_to(data_root)), "source_sha256": file_sha256(path)} for kind, path in paths.items()}
    rna = defaultdict(list)
    proteins = defaultdict(lambda: defaultdict(list))
    rejected = 0
    with paths["rna"].open(encoding="utf-8-sig") as handle:
        for rowno, row in enumerate(csv.DictReader(handle), 2):
            if row["tissue"] != "50%":
                continue
            gene = row["gene"].strip().upper()
            for tissue, text in row.items():
                if tissue in {"gene", "tissue"}:
                    continue
                try:
                    value = float(text)
                    if not math.isfinite(value): raise ValueError()
                except (ValueError, TypeError):
                    rejected += 1
                    continue
                rna[gene].append({"tissue": tissue, "median": value, "source_rows": [rowno], "statistic": "source 50% summary"})
    with paths["protein"].open(encoding="utf-8-sig") as handle:
        for rowno, row in enumerate(csv.DictReader(handle), 2):
            try:
                value = float(row["value"])
                if not math.isfinite(value): raise ValueError()
            except (ValueError, TypeError):
                rejected += 1
                continue
            proteins[row["gene"].strip().upper()][row["tissue"]].append((value, rowno))
    output = data_root / "artifacts/chunks/gtex_tissue_expression.chunks.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    temporary = output.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for gene in sorted(set(rna) | set(proteins)):
            protein = [{"tissue": tissue, "median": statistics.median(v for v, _ in observations),
                        "source_rows": [r for _, r in observations], "statistic": "median of supplied observations", "n": len(observations)}
                       for tissue, observations in proteins[gene].items()]
            expression = {"rna": rna[gene], "protein": protein}
            lines = [f"Gene: {gene}", "GTEx tissue expression. Units and transformations are unconfirmed."]
            cited_sources = []
            for kind, entries in expression.items():
                if not entries: continue
                top = sorted(entries, key=lambda e: (-e["median"], e["tissue"]))[:5]
                values = "; ".join(f"{e['tissue']} (median {e['median']:g})" for e in top)
                lines.append(f"Top {kind} tissues among {len(entries)} supplied tissues: {values}.")
                cited_sources.append({**sources[kind], "source_rows": sorted({r for e in entries for r in e["source_rows"]}),
                                      "record_key": {"gene": gene, "statistic": "50%" if kind == "rna" else "individual observations"}})
            lines.append("Expression does not establish disease association or a therapeutic mechanism. Protein medians are derived summaries without inferred sample identity.")
            cid = f"gtex:{gene}"
            record = {"chunk_id": cid, "collection": "gtex_tissue_expression", "entity_type": "gene_expression",
                      "title": f"GTEx Tissue Expression for {gene}", "content": "\n".join(lines),
                      "metadata": {"gene_symbol": gene, "expression": expression, "definition_status": "unconfirmed", "units": None},
                      "citation": {"chunk_id": cid, "source_name": "Client-supplied GTEx expression files", "source_url": "https://gtexportal.org/",
                                   "source_file": cited_sources[0]["source_file"], "source_sha256": cited_sources[0]["source_sha256"],
                                   "sources": cited_sources, "transform_version": VERSION,
                                   "source_version": "sha256:" + sources["rna"]["source_sha256"] + ":" + sources["protein"]["source_sha256"]}}
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            count += 1
    temporary.replace(output)
    report = {"version": VERSION, "collection": "gtex_tissue_expression", "status": "passed", "sources": sources,
              "output": {"path": str(output.relative_to(data_root)), "chunks": count, "sha256": file_sha256(output)}, "rejected_values": rejected}
    report_path = data_root / "artifacts/ingestion_dev/gtex/manifest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report

def validate_gtex(root: Path, path: Path) -> dict:
    data_root = Path(os.environ.get("BIOAGENT_DATA_ROOT", str(root))).resolve()
    report = json.loads((data_root / "artifacts/ingestion_dev/gtex/manifest.json").read_text())
    if report.get("version") != VERSION or report.get("status") != "passed":
        raise ValueError("GTEx build is outdated or failed; rebuild required")
    if (data_root / report["output"]["path"]).resolve() != path.resolve() or file_sha256(path) != report["output"]["sha256"]:
        raise ValueError("GTEx output path/hash mismatch")
    for source in report["sources"].values():
        if file_sha256(data_root / source["source_file"]) != source["source_sha256"]:
            raise ValueError("GTEx source changed; rebuild required")
    return report
