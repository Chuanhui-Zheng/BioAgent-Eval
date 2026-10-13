import copy
import json
import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from analysis.client_example import load_example
from analysis.routes import create_router
from retrieval.access import workspace_id
from tests.test_review_regressions import pipeline
from tests.helpers import result

ROOT = Path(__file__).resolve().parents[1]

def client(tmp_path):
    target = tmp_path / "data/reference/client_example"
    target.mkdir(parents=True)
    shutil.copyfile(ROOT / "data/reference/client_example/example.json", target / "example.json")
    p = pipeline([result("gene:AADACL3", "gene_info",
                         metadata={"gene_symbol": "AADACL3", "function_summary": "Source gene function."})])
    app = FastAPI()
    app.include_router(create_router(tmp_path, lambda: p, lambda g: {}, lambda: None))
    return TestClient(app)


def test_client_example_complete_cases_provenance_and_reproducibility(tmp_path):
    c = client(tmp_path)
    genes, traits, x, effects, sources = load_example(tmp_path)
    assert x.shape == (200, 4)
    assert len(effects) == 800 and traits == ["BMI", "HDL", "T2D", "TG"]
    assert sources["eligible_complete_genes"] == 4562
    assert all(e["source_row"] >= 2 and e["source_cluster"] == 0 for e in effects)
    a = c.post("/api/analysis/matrix/client-example").json()
    b = c.post("/api/analysis/matrix/client-example").json()
    assert a["w"] == b["w"] and a["h"] == b["h"]
    assert a["run_id"] != b["run_id"]
    assert a["diagnostics"]["not_client_original_factors"]
    assert any("Matching W is absent" in s for s in a["limitations"])


def test_example_missing_cells_rejected_not_imputed(tmp_path):
    client(tmp_path)
    p = tmp_path / "data/reference/client_example/example.json"
    d = json.loads(p.read_text())
    d["records"].pop()
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="Incomplete"):
        load_example(tmp_path)


def test_selection_question_exact_filters_snapshot_and_sources(tmp_path):
    c = client(tmp_path)
    run = c.post("/api/analysis/matrix/client-example").json()
    rid = run["run_id"]
    r = c.post(f"/api/analysis/runs/{rid}/question", json={
        "question": "Why were these genes selected?", "trait": "T2D", "z_cutoff": 1})
    assert r.status_code == 200, r.text
    answer = r.json()
    assert answer["status"] == "qualified" and answer["validation"]["valid"]
    assert answer["analysis_run_id"] == rid
    assert answer["filters"]["trait"] == "T2D"
    assert any(c["title"] == "Source association record" and c["evidence"]["source_row"] >= 2 for c in answer["citations"])
    for cite in answer["citations"]:
        if cite.get("title") == "Source association record":
            assert cite["evidence"]["phenotype"] == "T2D"
    changed = c.post(f"/api/analysis/runs/{rid}/question", json={
        "question": "Explain selected genes", "weight": 1e9}).json()
    assert changed["snapshot_sha256"] != answer["snapshot_sha256"]
    assert "selects 0" in changed["answer"]
    assert len(list((tmp_path/"artifacts/runs/all").glob("analysis-*.json"))) == 2


def test_run_question_refuses_treatment_and_expired_or_other_workspace(tmp_path):
    c = client(tmp_path)
    rid = c.post("/api/analysis/matrix/client-example").json()["run_id"]
    response = c.post(f"/api/analysis/runs/{rid}/question", json={"question": "Which agonist should cure diabetes?"}).json()
    assert response["status"] == "refuse" and response["claims"] == []
    token = workspace_id.set("annotations")
    try:
        assert c.post(f"/api/analysis/runs/{rid}/question", json={"question": "Explain selection"}).status_code == 404
    finally:
        workspace_id.reset(token)
    assert c.post("/api/analysis/runs/missing/question", json={"question": "Explain selection"}).status_code == 404


def test_unknown_trait_filters_out_genes_even_without_z_threshold(tmp_path):
    c = client(tmp_path)
    rid = c.post("/api/analysis/matrix/client-example").json()["run_id"]
    response = c.get(f"/api/analysis/runs/{rid}/selection", params={"trait": "unknown_trait"})
    assert response.status_code == 200
    assert response.json()["total"] == 0
