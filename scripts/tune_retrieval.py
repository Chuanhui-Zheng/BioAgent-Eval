"""Select the serving retrieval method, hybrid weights and reranker on DEVELOPMENT sets only.

Grid (all evaluated on the same cached candidates):
  first stage : bm25, dense, hybrid RRF with (w_bm25, w_dense) in {(1,1), (1.2,0.8), (0.8,1.2)}
  reranker    : none, BAAI/bge-reranker-base, BAAI/bge-reranker-v2-m3
  candidate_k : 10, 20, 30, 50          alpha : 1.0, 0.75, 0.5, 0.25

Selection rule (fixed before looking at results): maximise mean nDCG@10 over all
development queries; among configurations within 0.005 of the best, choose the
lowest estimated latency. Held-out files (names containing "test" or "blind")
are rejected. ``--write-config`` stores the choice in config/retrieval.yaml.
"""

from __future__ import annotations

import argparse
import json
import re
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

DEV_SETS = [
    ROOT / "data/evaluation/retrieval_dev.jsonl",
    ROOT / "data/evaluation/retrieval_expanded_dev.jsonl",
    ROOT / "data/evaluation/retrieval_comparison_dev.jsonl",
]
WEIGHTS = [(1.0, 1.0), (1.2, 0.8), (0.8, 1.2)]
MODELS = ["BAAI/bge-reranker-base", "BAAI/bge-reranker-v2-m3"]
CANDIDATES = [10, 20, 30, 50]
ALPHAS = [1.0, 0.75, 0.5, 0.25]
TIE_MARGIN = 0.005
OUT = ROOT / "reports/phase_5_retrieval_tuning"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-set", type=Path, action="append", default=None)
    parser.add_argument("--models", nargs="+", default=MODELS)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--write-config", action="store_true")
    parser.add_argument("--no-dense", action="store_true",
                        help="Tune BM25 and BM25+reranker only (no dense index required)")
    return parser.parse_args()


def write_config(path: Path, selected: dict) -> None:
    text = path.read_text(encoding="utf-8")

    def set_key(section: str, key: str, value) -> None:
        nonlocal text
        pattern = re.compile(rf"(^{section}:\n(?:[ ]+.*\n)*?[ ]+{key}: ).*$", re.M)
        if not pattern.search(text):
            raise SystemExit(f"config key {section}.{key} not found")
        text = pattern.sub(lambda m: m.group(1) + str(value), text, count=1)

    set_key("pipeline", "default_method", selected["method"])
    if selected.get("weights"):
        set_key("hybrid", "weight_bm25", selected["weights"][0])
        set_key("hybrid", "weight_dense", selected["weights"][1])
    if selected.get("model"):
        set_key("reranker", "model", selected["model"])
        set_key("reranker", "candidate_k", selected["candidate_k"])
        set_key("reranker", "alpha", selected["alpha"])
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    examples = load_examples(args.dev_set or DEV_SETS, allow_held_out=False)
    config = load_retrieval_config(ROOT)
    corpus = load_corpus_from_config(config)
    components = _Components(config, corpus, None, None)
    bm25 = components.bm25()
    dense = None if args.no_dense else components.dense()
    print(f"dev queries: {len(examples)}; dense={'off' if dense is None else 'on'}", flush=True)

    stages = {"bm25": run_first_stage("bm25", bm25, examples)}
    if dense is not None:
        stages["dense"] = run_first_stage("dense", dense, examples)
    for weights in ([] if dense is None else WEIGHTS):
        name = f"hybrid_{weights[0]}_{weights[1]}"
        backend = HybridRetriever(bm25, dense, candidate_k=50, rrf_k=config.hybrid_rrf_k,
                                  weight_bm25=weights[0], weight_dense=weights[1])
        stages[name] = run_first_stage(name, backend, examples)
    stage_latency = {name: sum(run.latency_s.values()) / len(examples) for name, run in stages.items()}

    records_by_id = {record.chunk_id: record for record in corpus.records}
    pair_costs: dict[str, float] = {}
    grid = []
    for name, run in stages.items():
        metrics = score(ranked_lists(run, examples), run, examples)
        grid.append({"first_stage": name, "model": None, "candidate_k": 0, "alpha": None,
                     "est_latency_s": stage_latency[name], "metrics": metrics})
    for model in args.models:
        print(f"loading {model}", flush=True)
        cache = ScoreCache(CrossEncoderScorer(model, device=args.device), records_by_id)
        for name, run in stages.items():
            if name == "dense":
                continue
            for candidate_k in CANDIDATES:
                for alpha in ALPHAS:
                    ranked = ranked_lists(run, examples, cache=cache, candidate_k=candidate_k, alpha=alpha)
                    grid.append({"first_stage": name, "model": model, "candidate_k": candidate_k, "alpha": alpha,
                                 "est_latency_s": None, "metrics": score(ranked, run, examples)})
        for row in grid:
            if row["model"] == model:
                row["est_latency_s"] = stage_latency[row["first_stage"]] + row["candidate_k"] * cache.seconds_per_pair
        print(f"{model}: {cache.pairs_scored} pairs, {cache.seconds_per_pair * 1000:.1f} ms/pair", flush=True)
        pair_costs[model] = cache.seconds_per_pair

    best = max(row["metrics"]["metrics"]["nDCG@10"] for row in grid)
    eligible = [row for row in grid if row["metrics"]["metrics"]["nDCG@10"] >= best - TIE_MARGIN]
    chosen = min(eligible, key=lambda row: (row["est_latency_s"], -row["metrics"]["metrics"]["nDCG@10"]))
    stage = chosen["first_stage"]
    weights = None
    if stage.startswith("hybrid_"):
        weights = [float(v) for v in stage.split("_")[1:]]
    method = ("hybrid" if weights else stage) + ("_rerank" if chosen["model"] else "")
    selected = {"method": method, "weights": weights, "model": chosen["model"],
                "candidate_k": chosen["candidate_k"] or None, "alpha": chosen["alpha"],
                "dev_nDCG@10": chosen["metrics"]["metrics"]["nDCG@10"], "best_dev_nDCG@10": best,
                "est_latency_s": chosen["est_latency_s"]}

    OUT.mkdir(parents=True, exist_ok=True)
    tie_count = len(eligible)
    meta = {"created_at": datetime.now(timezone.utc).isoformat(), "dev_sets": sorted({e["_source"] for e in examples}),
            "dev_queries": len(examples), "selection_rule": f"max nDCG@10; ties within {TIE_MARGIN} -> lowest latency",
            "dense_index": None if dense is None else {k: v for k, v in dense.meta.items() if k != "chunk_hashes"},
            "rerank_seconds_per_pair": {}}
    meta["rerank_seconds_per_pair"] = pair_costs
    meta["configs_within_tie_margin"] = tie_count
    (OUT / "dev_grid.json").write_text(json.dumps({"meta": meta, "grid": grid}, indent=2) + "\n")
    reranked = [row for row in grid if row["model"]]
    best_reranker = None
    if reranked:
        top_rr = max(row["metrics"]["metrics"]["nDCG@10"] for row in reranked)
        pick = min((row for row in reranked if row["metrics"]["metrics"]["nDCG@10"] >= top_rr - TIE_MARGIN),
                   key=lambda row: row["est_latency_s"])
        best_reranker = {"first_stage": pick["first_stage"], "model": pick["model"],
                         "candidate_k": pick["candidate_k"], "alpha": pick["alpha"],
                         "dev_nDCG@10": pick["metrics"]["metrics"]["nDCG@10"], "est_latency_s": pick["est_latency_s"]}
    (OUT / "selected.json").write_text(json.dumps({"meta": meta, "selected": selected,
                                                   "best_reranker": best_reranker}, indent=2) + "\n")
    print("best reranker on dev:", json.dumps(best_reranker))
    print(json.dumps(selected, indent=2))
    top = sorted(grid, key=lambda r: -r["metrics"]["metrics"]["nDCG@10"])[:12]
    for row in top:
        m = row["metrics"]["metrics"]
        print(f"{row['first_stage']:18} {str(row['model']).split('/')[-1]:22} k={row['candidate_k']:<3} a={row['alpha']} "
              f"nDCG@10={m['nDCG@10']:.4f} MRR={m['MRR@10']:.4f} Hit@10={m['TargetHit@10']:.4f} "
              f"All@10={row['metrics']['AllTargets@10']} lat={row['est_latency_s']:.3f}s")
    if args.write_config:
        write_config(ROOT / "config/retrieval.yaml", selected)
        print("config/retrieval.yaml updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
