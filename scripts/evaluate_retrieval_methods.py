"""Evaluate BM25, dense, hybrid and the dev-selected configuration on frozen TEST sets.

Nothing is tuned here: the reranker/hybrid settings come from
reports/phase_5_retrieval_tuning/selected.json. Test labels were pooled from
earlier BM25/dense/hybrid runs, so chunks newly surfaced by the reranker may be
unjudged and are counted as non-relevant (a conservative bias against new methods).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from retrieval.benchmark_runner import ScoreCache, load_examples, ranked_lists, run_first_stage, score  # noqa: E402
from retrieval.config import load_retrieval_config  # noqa: E402
from retrieval.corpus import load_corpus_from_config  # noqa: E402
from retrieval.factory import _Components  # noqa: E402
from retrieval.hybrid_retriever import HybridRetriever  # noqa: E402
from retrieval.reranker import CrossEncoderScorer  # noqa: E402

TEST_SETS = [
    ROOT / "data/evaluation/retrieval_test.jsonl",
    ROOT / "data/evaluation/retrieval_expanded_test.jsonl",
    ROOT / "data/evaluation/retrieval_comparison_test.jsonl",
    ROOT / "data/evaluation/blind/blind_e2e_v1.jsonl",
]
OUT = ROOT / "reports/phase_5_retrieval_tuning"


def main() -> int:
    selected = json.loads((OUT / "selected.json").read_text())["selected"]
    examples = load_examples(TEST_SETS, allow_held_out=True)
    config = load_retrieval_config(ROOT)
    corpus = load_corpus_from_config(config)
    components = _Components(config, corpus, None, None)
    bm25 = components.bm25()
    no_dense = "--no-dense" in sys.argv
    dense = None if no_dense else components.dense()
    weights = selected.get("weights") or [1.0, 1.0]
    runs = {"bm25": run_first_stage("bm25", bm25, examples)}
    if dense is not None:
        runs["dense"] = run_first_stage("dense", dense, examples)
        runs["hybrid_1.0_1.0"] = run_first_stage("hybrid", HybridRetriever(bm25, dense, candidate_k=50), examples)
    if dense is not None and weights != [1.0, 1.0]:
        runs["hybrid_selected"] = run_first_stage(
            "hybrid", HybridRetriever(bm25, dense, candidate_k=50, weight_bm25=weights[0], weight_dense=weights[1]),
            examples)
    results = {}
    for name, run in runs.items():
        results[name] = {"metrics": score(ranked_lists(run, examples), run, examples),
                         "mean_latency_s": sum(run.latency_s.values()) / len(examples)}
    rerank = selected.get("model") and selected.get("candidate_k")
    # Always also report the best dev reranker so the comparison has a reranked arm.
    rerank_spec = selected if rerank else json.loads((OUT / "selected.json").read_text()).get("best_reranker")
    if rerank_spec:
        selected = {**selected, **{k: rerank_spec[k] for k in ("model", "candidate_k", "alpha")}}
        if not rerank:
            selected["method"] = selected["method"] + "_rerank (best dev reranker; not selected)"
    if selected.get("model"):
        base_name = ("hybrid_selected" if "hybrid_selected" in runs else "hybrid_1.0_1.0") \
            if selected["method"].startswith("hybrid") else "bm25"
        cache = ScoreCache(CrossEncoderScorer(selected["model"]), {r.chunk_id: r for r in corpus.records})
        run = runs[base_name]
        ranked = ranked_lists(run, examples, cache=cache, candidate_k=selected["candidate_k"], alpha=selected["alpha"])
        results[selected["method"] if not rerank else f"{selected['method']} (selected)"] = {
            "metrics": score(ranked, run, examples),
            "mean_latency_s": results[base_name]["mean_latency_s"] + selected["candidate_k"] * cache.seconds_per_pair,
        }
    payload = {"created_at": datetime.now(timezone.utc).isoformat(), "selected_config": selected,
               "test_sets": [p.name for p in TEST_SETS], "queries": len(examples), "results": results,
               "caveat": __doc__.strip().splitlines()[-3:]}
    (OUT / "test_results.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"{'method':28} {'set':34} n   Hit@10  nDCG@10 MRR@10  All@10")
    for name, item in results.items():
        for source, m in item["metrics"]["by_source"].items():
            all10 = "-" if m["AllTargets@10"] is None else f"{m['AllTargets@10']:.3f}"
            print(f"{name:28} {source:34} {m['n']:<3} {m['TargetHit@10']:.3f}  {m['nDCG@10']:.3f}   "
                  f"{m['MRR@10']:.3f}  {all10}")
        print(f"{name:28} {'ALL':34} {len(examples):<3} lat={item['mean_latency_s']:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
