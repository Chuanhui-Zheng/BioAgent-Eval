"""Extract a deterministic, source-linked demonstration; never execute client code."""
import argparse, csv, hashlib, io, json, math, zipfile
from pathlib import Path

def prepare(archive, output):
    member = "Sample_Data/V001-20260826T154019Z-1-001.zip"
    source = "V001/df_table_demo_enrich.csv"
    with zipfile.ZipFile(archive) as outer:
        nested = outer.read(member)
    with zipfile.ZipFile(io.BytesIO(nested)) as inner:
        raw = inner.read(source)
        h_hash = hashlib.sha256(inner.read("V001/H_demo_enrich.csv")).hexdigest()
    traits = ["BMI", "HDL", "T2D", "TG"]
    by_gene = {}
    for line, row in enumerate(csv.DictReader(io.StringIO(raw.decode())), 2):
        if row["cluster"] != "0" or row["Trait"] not in traits:
            continue
        gene = row["genes"].strip().upper()
        if row["var_ID"].upper() != gene + "_0":
            raise ValueError("Unexpected gene-cluster identifier")
        beta, se, z = [float(row[k]) for k in ("beta_g", "StdErr", "Zscore")]
        if not all(math.isfinite(v) for v in (beta, se, z)) or se <= 0:
            continue
        if not math.isclose(beta / se, z, rel_tol=1e-5, abs_tol=1e-6):
            raise ValueError("Source beta / SE disagrees with Z")
        target = by_gene.setdefault(gene, {})
        if row["Trait"] in target:
            raise ValueError("Duplicate source gene-trait record")
        target[row["Trait"]] = {"gene": gene, "phenotype": row["Trait"], "beta": beta,
            "stdErr": se, "z": z, "p_value": None, "source_row": line,
            "source_cluster": 0, "source_var_id": row["var_ID"],
            "direction": "positive association" if beta > 0 else "negative association" if beta < 0 else "zero association"}
    eligible = sorted(g for g, values in by_gene.items() if set(values) == set(traits))
    if len(eligible) < 2:
        raise ValueError("No complete multi-trait sample")
    count = min(200, len(eligible))
    genes = [eligible[i * (len(eligible)-1) // (count-1)] for i in range(count)]
    records = [by_gene[g][t] for g in genes for t in traits]
    payload = {"version": "client-example-1", "genes": genes, "traits": traits, "records": records,
        "provenance": {"archive_name": Path(archive).name, "nested_member": member,
            "nested_sha256": hashlib.sha256(nested).hexdigest(), "source_file": source,
            "source_sha256": hashlib.sha256(raw).hexdigest(), "unpaired_h_sha256": h_hash,
            "source_cluster": 0, "eligible_complete_genes": len(eligible),
            "selection": "200 evenly spaced alphabetical complete-case genes; not top hits",
            "transform": "X[gene,trait] = abs(source Zscore); signed beta/SE/Z preserved separately; no imputation",
            "missing_input": "Matching W is absent; provided H is not paired or used. NMF is independently refitted."}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"genes": len(genes), "traits": traits, "records": len(records)}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data/reference/client_example/example.json")
    args = parser.parse_args()
    prepare(args.archive, args.output)
