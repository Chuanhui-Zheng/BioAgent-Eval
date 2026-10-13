"""Validated local client example, with no missing-cell imputation."""
import hashlib
import json
import math
import numpy as np

def load_example(root):
    path = root / "data/reference/client_example/example.json"
    if not path.exists():
        raise ValueError("Client example is not installed; run scripts/prepare_client_example.py.")
    raw = path.read_bytes()
    data = json.loads(raw)
    genes, traits = data["genes"], data["traits"]
    if not genes or not traits or len(set(genes)) != len(genes) or len(set(traits)) != len(traits):
        raise ValueError("Example labels must be unique and nonempty")
    if len(genes) * len(traits) > 250000:
        raise ValueError("Example exceeds the matrix limit")
    values = {}
    for row in data["records"]:
        key = (row["gene"], row["phenotype"])
        if key in values or key[0] not in genes or key[1] not in traits:
            raise ValueError("Unexpected or duplicate example record")
        if not all(math.isfinite(float(row[k])) for k in ("beta", "stdErr", "z")) or row["stdErr"] <= 0:
            raise ValueError("Invalid source effects")
        if not math.isclose(row["beta"] / row["stdErr"], row["z"], rel_tol=1e-5, abs_tol=1e-6):
            raise ValueError("Source beta/SE and Z disagree")
        values[key] = abs(row["z"])
    if len(values) != len(genes) * len(traits):
        raise ValueError("Incomplete example; missing effects must not become zero")
    x = np.array([[values[g,t] for t in traits] for g in genes])
    sources = {**data["provenance"], "example_sha256": hashlib.sha256(raw).hexdigest()}
    return genes, traits, x, data["records"], sources
