from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from retrieval.benchmark_runner import all_targets_at_k, load_examples
from tests.helpers import result

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "data/evaluation"
BLIND = EVAL / "blind/blind_e2e_v1.jsonl"
DEV = [EVAL / "retrieval_dev.jsonl", EVAL / "retrieval_expanded_dev.jsonl", EVAL / "retrieval_comparison_dev.jsonl"]


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def gold(row):
    return {j["chunk_id"] for j in row.get("relevance_judgments", []) if j.get("grade", 0) >= 2} | set(
        row.get("gold_citations", []))


def test_blind_benchmark_matches_frozen_manifest():
    manifest = json.loads(BLIND.with_name("blind_e2e_v1.manifest.json").read_text())
    assert hashlib.sha256(BLIND.read_bytes()).hexdigest() == manifest["sha256"]
    assert manifest["questions"] == len(rows(BLIND)) == 40


def test_blind_labels_are_well_formed_and_disjoint_from_development_sets():
    blind = rows(BLIND)
    assert len({r["query_id"] for r in blind}) == len(blind)
    for row in blind:
        assert row["accepted_statuses"]
        assert bool(row["gold_citations"]) == row["answerable"]
    blind_gold = set().union(*(gold(r) for r in blind))
    dev_gold = set().union(*(gold(r) for path in DEV for r in rows(path)))
    dev_assessed = {cid for path in DEV for r in rows(path) for cid in r.get("assessed_chunk_ids", [])}
    assert not blind_gold & dev_gold
    assert not blind_gold & dev_assessed


def test_comparison_dev_set_never_reuses_test_targets():
    held_out = set().union(*(gold(r) for path in EVAL.glob("*test*.jsonl") for r in rows(path)))
    for row in rows(EVAL / "retrieval_comparison_dev.jsonl"):
        assert not gold(row) & held_out
        assert len(gold(row)) >= 2


def test_tuning_refuses_held_out_files():
    with pytest.raises(SystemExit, match="held-out"):
        load_examples([EVAL / "retrieval_test.jsonl"], allow_held_out=False)
    with pytest.raises(SystemExit, match="held-out"):
        load_examples([BLIND], allow_held_out=False)
    assert load_examples(DEV, allow_held_out=False)


def test_all_targets_metric_requires_every_comparison_target():
    examples = [{"query_id": "q", "relevance_judgments": [{"chunk_id": "a", "grade": 2}, {"chunk_id": "b", "grade": 2}]},
                {"query_id": "single", "relevance_judgments": [{"chunk_id": "a", "grade": 2}]}]
    assert all_targets_at_k({"q": [result("a", "gene_info"), result("b", "gene_info")], "single": []}, examples) == 1.0
    assert all_targets_at_k({"q": [result("a", "gene_info")], "single": []}, examples) == 0.0
