from __future__ import annotations
import csv
import gzip
import hashlib
import io
import json
import math
import sqlite3
import threading
import uuid
from pathlib import Path
import numpy as np

_LOCK = threading.RLock()
VERSION = 1


def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def provenance(path: Path, root: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "source_file": str(path.relative_to(root)),
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
    }


class DataStore:
    def __init__(self, root: Path):
        self.root = root
        self.raw = root / "data/raw"
        self.path = root / "artifacts/structured/analysis.sqlite"
        self.sources = []
        self.ready = False

    def ensure(self):
        with _LOCK:
            if self.ready:
                return
            files = sorted(
                f
                for f in self.raw.rglob("*")
                if f.is_file()
                and f.suffix in {".csv", ".gz", ".zst", ".json", ".jsonl"}
            )
            # Content identity survives clone/unzip and detects changes even when
            # file size and timestamp are preserved. Relative paths are portable.
            source_identity = {
                str(f.relative_to(self.root)): provenance(f, self.root) for f in files
            }
            fingerprint = json.dumps(
                [(name, info["bytes"], info["sha256"])
                 for name, info in source_identity.items()]
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                with sqlite3.connect(self.path) as db:
                    meta = dict(db.execute("SELECT key,value FROM metadata"))
                if meta.get("fingerprint") == fingerprint and meta.get(
                    "version"
                ) == str(VERSION):
                    self.sources = json.loads(meta["sources"])
                    self.ready = True
                    return
            temp = self.path.with_name(f"analysis-{uuid.uuid4().hex}.sqlite")
            db = sqlite3.connect(temp)
            try:
                db.executescript("""CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE variants(phenotype TEXT,ancestry TEXT,chromosome TEXT,position INTEGER,var_id TEXT,p_value REAL,beta REAL,std_err REAL,n REAL,reference TEXT,alt TEXT,source TEXT,source_row INTEGER);
                CREATE TABLE expression(gene TEXT,kind TEXT,statistic TEXT,tissue TEXT,value REAL,specificity REAL,record TEXT,source_row INTEGER);
                CREATE TABLE nearest(var_id TEXT,gene_id TEXT,source TEXT,source_row INTEGER);
                CREATE TABLE links(snp TEXT,gene TEXT,score REAL,record TEXT,source TEXT,source_row INTEGER);
                CREATE TABLE annotations(var_id TEXT,gene TEXT,record TEXT,source TEXT,source_row INTEGER);
                CREATE TABLE gene_map(gene TEXT,ensembl TEXT,record TEXT);
                """)
                sources = []
                for file in files:
                    rel = str(file.relative_to(self.root))
                    count = rejected = 0
                    if "gtx_tissue_expression" in rel:
                        kind = "rna" if "RNAseq" in file.name else "protein"
                        with file.open() as handle:
                            rows = csv.DictReader(handle)
                            batch = []
                            for i, row in enumerate(rows, 2):
                                gene = row.get("gene", "").upper()
                                batch.append(
                                    (
                                        gene,
                                        kind,
                                        row["tissue"] if kind == "rna" else None,
                                        row["tissue"] if kind == "protein" else None,
                                        finite(row.get("value")),
                                        finite(row.get("tissue_specificity")),
                                        json.dumps(row) if kind == "rna" else None,
                                        i,
                                    )
                                )
                                count += 1
                                if len(batch) >= 5000:
                                    db.executemany(
                                        "INSERT INTO expression VALUES(?,?,?,?,?,?,?,?)",
                                        batch,
                                    )
                                    batch = []
                            db.executemany(
                                "INSERT INTO expression VALUES(?,?,?,?,?,?,?,?)", batch
                            )
                    elif "gwas_genengine" in rel or "ancestry-specific" in rel:
                        import zstandard

                        if file.suffix == ".gz":
                            handle = gzip.open(file, "rt")
                            rows = csv.DictReader(handle, delimiter="\t")
                        else:
                            binary = file.open("rb")
                            handle = io.TextIOWrapper(
                                zstandard.ZstdDecompressor().stream_reader(binary)
                            )
                            rows = (json.loads(line) for line in handle if line.strip())
                        with handle:
                            batch = []
                            for i, row in enumerate(rows, 1):
                                pv = finite(row.get("pValue"))
                                pos = finite(row.get("position"))
                                beta = finite(row.get("beta"))
                                se = finite(row.get("stdErr"))
                                if (
                                    pv is None
                                    or not 0 <= pv <= 1
                                    or pos is None
                                    or pos <= 0
                                    or beta is None
                                ):
                                    rejected += 1
                                    continue
                                batch.append(
                                    (
                                        row["phenotype"],
                                        "EU",
                                        str(row["chromosome"]).removeprefix("chr"),
                                        int(pos),
                                        row["varId"],
                                        pv,
                                        beta,
                                        se,
                                        finite(row.get("n")),
                                        row.get("reference"),
                                        row.get("alt"),
                                        rel,
                                        i,
                                    )
                                )
                                count += 1
                                if len(batch) >= 10000:
                                    db.executemany(
                                        "INSERT INTO variants VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                        batch,
                                    )
                                    batch = []
                            db.executemany(
                                "INSERT INTO variants VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                batch,
                            )
                    elif "nearest_genes" in rel:
                        with file.open() as handle:
                            batch = []
                            for i, line in enumerate(handle, 1):
                                if not line.strip():
                                    continue
                                row = json.loads(line)
                                batch.append((row["varId"], row["nearestGene"], rel, i))
                                count += 1
                                if len(batch) >= 10000:
                                    db.executemany(
                                        "INSERT INTO nearest VALUES(?,?,?,?)", batch
                                    )
                                    batch = []
                            db.executemany("INSERT INTO nearest VALUES(?,?,?,?)", batch)
                    elif "cs2g_1000geur" in rel:
                        with gzip.open(file, "rt") as handle:
                            batch = []
                            for i, row in enumerate(
                                csv.DictReader(handle, delimiter="\t"), 2
                            ):
                                batch.append(
                                    (
                                        row["SNP"],
                                        row["GENE"].upper(),
                                        finite(row["cS2G"]),
                                        json.dumps(row),
                                        rel,
                                        i,
                                    )
                                )
                                count += 1
                                if len(batch) >= 10000:
                                    db.executemany(
                                        "INSERT INTO links VALUES(?,?,?,?,?,?)", batch
                                    )
                                    batch = []
                            db.executemany(
                                "INSERT INTO links VALUES(?,?,?,?,?,?)", batch
                            )
                    elif "topmed_burdenbinning" in rel:
                        with file.open() as handle:
                            batch = []
                            for i, line in enumerate(handle, 1):
                                if not line.strip():
                                    continue
                                row = json.loads(line)
                                batch.append(
                                    (
                                        row.get("varId"),
                                        str(
                                            row.get("geneSymbol") or row.get("gene", "")
                                        ).upper(),
                                        json.dumps(row),
                                        rel,
                                        i,
                                    )
                                )
                                count += 1
                            db.executemany(
                                "INSERT INTO annotations VALUES(?,?,?,?,?)", batch
                            )
                    elif "gene_id_map" in rel:
                        with file.open() as handle:
                            for line in handle:
                                if line.strip():
                                    row = json.loads(line)
                                    db.execute(
                                        "INSERT INTO gene_map VALUES(?,?,?)",
                                        (
                                            str(
                                                row.get("gene") or row.get("symbol", "")
                                            ).upper(),
                                            row.get("ensembl"),
                                            json.dumps(row),
                                        ),
                                    )
                                    count += 1
                    else:
                        continue
                    sources.append(
                        {
                            **source_identity[rel],
                            "accepted_records": count,
                            "rejected_records": rejected,
                        }
                    )
                db.executescript(
                    """CREATE INDEX variant_lookup ON variants(phenotype,ancestry,chromosome,position);CREATE INDEX variant_p ON variants(phenotype,p_value);CREATE INDEX variant_id ON variants(var_id);CREATE INDEX expression_gene ON expression(gene,kind);CREATE INDEX nearest_lookup ON nearest(var_id);CREATE INDEX links_gene ON links(gene);CREATE INDEX links_snp ON links(snp);CREATE INDEX annotation_var ON annotations(var_id);CREATE INDEX annotation_gene ON annotations(gene);CREATE INDEX gene_map_id ON gene_map(ensembl);"""
                )
                db.executemany(
                    "INSERT INTO metadata VALUES(?,?)",
                    [
                        ("fingerprint", fingerprint),
                        ("version", str(VERSION)),
                        ("sources", json.dumps(sources)),
                    ],
                )
                db.commit()
                db.close()
                temp.replace(self.path)
                self.sources = sources
                self.ready = True
            except Exception:
                db.close()
                temp.unlink(missing_ok=True)
                raise

    def connect(self):
        self.ensure()
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def catalog(self):
        with self.connect() as db:
            datasets = [
                dict(row)
                for row in db.execute(
                    "SELECT phenotype,ancestry,COUNT(*) AS count FROM variants GROUP BY phenotype,ancestry"
                )
            ]
        return {
            "gwas": datasets,
            "expression": ["rna", "protein"],
            "sources": self.sources,
            "limitations": [
                "Coverage is limited to supplied source files. Genome build, effect allele/scale and expression units are unconfirmed. No cross-build coordinate joins are performed."
            ],
        }

    def expression(self, gene: str, kind: str):
        with self.connect() as db:
            raw = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM expression WHERE gene=? AND kind=?",
                    (gene.upper(), kind),
                )
            ]
        records = []
        if kind == "rna":
            tissues = {}
            for row in raw:
                for tissue, value in json.loads(row["record"]).items():
                    if tissue not in {"gene", "tissue"}:
                        tissues.setdefault(tissue, {"tissue": tissue})[
                            row["statistic"]
                        ] = finite(value)
            records = list(tissues.values())
        else:
            records = [
                {
                    "tissue": r["tissue"],
                    "value": r["value"],
                    "tissue_specificity": r["specificity"],
                    "source_row": r["source_row"],
                }
                for r in raw
            ]
        sources = [
            s
            for s in self.sources
            if ("RNAseq" if kind == "rna" else "Proteomics") in s["source_file"]
        ]
        return {
            "gene": gene.upper(),
            "kind": kind,
            "records": records,
            "source_records": len(raw),
            "sources": sources,
            "limitations": [
                "Expression units and transformations are unconfirmed. RNA statistics are source summaries. Protein observations are preserved individually, with no inferred sample identity or aggregation. Expression is not disease-association evidence."
            ],
        }

    def gwas(
        self,
        phenotype: str,
        ancestry: str = "EU",
        threshold: float = 1,
        chromosome: str | None = None,
        start: int | None = None,
        end: int | None = None,
        points: int = 2000,
    ):
        where = "phenotype=? AND ancestry=?"
        params = [phenotype, ancestry]
        if chromosome is not None:
            where += " AND chromosome=?"
            params.append(chromosome.removeprefix("chr"))
        if start is not None:
            where += " AND position>=?"
            params.append(start)
        if end is not None:
            where += " AND position<=?"
            params.append(end)
        with self.connect() as db:
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM variants WHERE "
                    + where
                    + " ORDER BY CAST(chromosome AS INTEGER),position",
                    params,
                )
            ]
        n = len(rows)
        # QQ uses all valid p-values in the selected region, before significance filtering.
        values = np.sort(np.array([r["p_value"] for r in rows], dtype=float))
        indices = (
            np.unique(np.linspace(0, max(0, n - 1), min(n, points), dtype=int))
            if n
            else []
        )
        qq = (
            [
                {
                    "expected": float(-np.log10((i + 0.5) / n)),
                    "observed": float(-np.log10(max(values[i], 1e-300))),
                    "rank": int(i + 1),
                }
                for i in indices
            ]
            if n
            else []
        )
        offsets = {}
        offset = 0
        for row in rows:
            chromosome_code = row["chromosome"]
            if chromosome_code not in offsets:
                offsets[chromosome_code] = offset
                offset += (
                    max(
                        r["position"]
                        for r in rows
                        if r["chromosome"] == chromosome_code
                    )
                    + 1000000
                )
        filtered = [r for r in rows if r["p_value"] <= threshold]
        sample = (
            set(
                np.linspace(
                    0, max(0, len(filtered) - 1), min(len(filtered), points), dtype=int
                ).tolist()
            )
            if filtered
            else set()
        )
        # Preserve the strongest signals as well as a uniform sample.
        sample.update(
            sorted(range(len(filtered)), key=lambda i: filtered[i]["p_value"])[
                : min(200, points)
            ]
        )
        plotted = [
            {
                **filtered[i],
                "x": offsets[filtered[i]["chromosome"]] + filtered[i]["position"],
                "minus_log10_p": -math.log10(max(filtered[i]["p_value"], 1e-300)),
            }
            for i in sorted(sample)
        ]
        return {
            "phenotype": phenotype,
            "ancestry": ancestry,
            "total_records": n,
            "significant_records": len(filtered),
            "p_threshold": threshold,
            "variants": sorted(filtered, key=lambda r: r["p_value"])[:100],
            "manhattan": plotted,
            "qq": qq,
            "chromosome_offsets": offsets,
            "sources": [
                s
                for s in self.sources
                if s["source_file"] in {r["source"] for r in rows}
            ],
            "limitations": [
                "Supplied-file coverage, not guaranteed full-study coverage. Coordinates and effect-allele conventions are source-reported; genome build is unconfirmed. Plot points are sampled; QQ is computed before p-value filtering. Source p=0 is displayed at -log10(p)=300 (censored)."
            ],
        }

    def references(self, gene: str | None = None, variant: str | None = None):
        if not gene and not variant:
            raise ValueError("Provide a gene or variant identifier.")
        with self.connect() as db:
            links = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM links WHERE "
                    + ("gene=?" if gene else "snp=?")
                    + " ORDER BY score DESC LIMIT 200",
                    (gene.upper() if gene else variant,),
                )
            ]
            annotations = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM annotations WHERE "
                    + ("gene=?" if gene else "var_id=?")
                    + " LIMIT 200",
                    (gene.upper() if gene else variant,),
                )
            ]
            nearest = (
                [
                    dict(r)
                    for r in db.execute(
                        "SELECT n.*,g.gene FROM nearest n LEFT JOIN gene_map g ON g.ensembl=n.gene_id WHERE n.var_id=? LIMIT 200",
                        (variant,),
                    )
                ]
                if variant
                else []
            )
        return {
            "links": links,
            "annotations": annotations,
            "nearest_genes": nearest,
            "limitations": [
                "SNP-to-gene linking scores and nearest-gene proximity are annotations, not causal proof. rsIDs are not guessed from coordinates. Only supplied chromosome shards are covered. No cross-build coordinate joins are made."
            ],
        }
