from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from chunking.utils import file_sha256, load_jsonl
from retrieval.bm25_retriever import load_bm25_index
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.dense_retriever import load_dense_index, load_encoder_from_config
from retrieval.evaluation import BenchmarkMetadata, benchmark_metadata, load_matching_metrics
from retrieval.hybrid_retriever import HybridRetriever, rrf_fuse
from retrieval.metrics import aggregate_dev_metrics
from retrieval.router import route_query
from retrieval.schema import SearchResult

GRID = [
    {"weight_bm25": 1.0, "weight_dense": 1.0, "rrf_k": 60, "candidate_k": 50},
    {"weight_bm25": 1.2, "weight_dense": 0.8, "rrf_k": 60, "candidate_k": 50},
    {"weight_bm25": 0.8, "weight_dense": 1.2, "rrf_k": 60, "candidate_k": 50},
]


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate routed hybrid RRF on the development set.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--dev-set", type=Path, default=None)
    parser.add_argument("--bm25-eval-dir", type=Path, default=None)
    parser.add_argument("--dense-eval-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--report-ks", nargs="+", type=int, default=None)
    return parser.parse_args()


def serialize_results(results: list[SearchResult]) -> list[dict]:
    return [
        {
            "rank": item.rank,
            "chunk_id": item.chunk_id,
            "collection": item.collection,
            "score": item.score,
            "component_scores": item.component_scores,
        }
        for item in results
    ]


def hits_from_dicts(rows: list[dict]) -> list[SearchResult]:
    return [
        SearchResult(
            chunk_id=item["chunk_id"],
            collection=item["collection"],
            rank=item["rank"],
            score=item["score"],
            method=item.get("method", "component"),
            component_scores=item.get("component_scores") or {},
        )
        for item in rows
    ]


def render_report(
    metrics: dict,
    report_ks: list[int],
    top_k: int,
    comparisons: dict[str, dict],
    benchmark: BenchmarkMetadata,
) -> str:
    lines = [
        f"# Hybrid RRF {benchmark.label} evaluation",
        "",
        f"- queries: {metrics['routed']['n']}",
        f"- top_k: {top_k}",
        f"- report_ks: {report_ks}",
        f"- candidate_k: {metrics['hybrid']['candidate_k']}",
        f"- rrf_k: {metrics['hybrid']['rrf_k']}",
        f"- weight_bm25: {metrics['hybrid']['weight_bm25']}",
        f"- weight_dense: {metrics['hybrid']['weight_dense']}",
        "- fusion: existing BM25 (title+content, identifier pin) + dense (content only); no new index",
        f"- labeling: {metrics['routed']['labeling_note']}",
        "",
        "## Routed retrieval",
        "",
        yaml.safe_dump(metrics["routed"]["metrics"], sort_keys=False).strip(),
        "",
        "### Router",
        "",
        yaml.safe_dump(metrics["routed"]["router"], sort_keys=False).strip(),
        "",
        "### By query type",
        "",
        yaml.safe_dump(metrics["routed"]["by_query_type"], sort_keys=False).strip(),
        "",
        "## Oracle-collection diagnostic",
        "",
        yaml.safe_dump(metrics["oracle"]["metrics"], sort_keys=False).strip(),
        "",
        f"## Comparison ({benchmark.comparison_label})",
        "",
        "| metric | BM25 | Dense | Hybrid |",
        "| --- | --- | --- | --- |",
    ]
    hybrid_m = metrics["routed"]["metrics"]
    bm25_m = (comparisons.get("bm25") or {}).get("routed", {}).get("metrics", {})
    dense_m = (comparisons.get("dense") or {}).get("routed", {}).get("metrics", {})
    lines.extend(
        [
            f"| TargetHit@5 | {bm25_m.get('TargetHit@5', '-')} | {dense_m.get('TargetHit@5', '-')} | {hybrid_m.get('TargetHit@5')} |",
            f"| TargetHit@10 | {bm25_m.get('TargetHit@10', '-')} | {dense_m.get('TargetHit@10', '-')} | {hybrid_m.get('TargetHit@10')} |",
            f"| Recall@10 | {bm25_m.get('Recall@10', '-')} | {dense_m.get('Recall@10', '-')} | {hybrid_m.get('Recall@10')} |",
            f"| nDCG@10 | {bm25_m.get('nDCG@10', '-')} | {dense_m.get('nDCG@10', '-')} | {hybrid_m.get('nDCG@10')} |",
            f"| MRR@10 | {bm25_m.get('MRR@10', '-')} | {dense_m.get('MRR@10', '-')} | {hybrid_m.get('MRR@10')} |",
            "",
            "## Offline RRF grid (candidates retrieved once)",
            "",
            yaml.safe_dump(metrics.get("grid", []), sort_keys=False).strip(),
            "",
            "Grid results are diagnostic only; YAML defaults are not auto-updated.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    config = load_retrieval_config(PROJECT_ROOT, args.config)
    report_ks = tuple(args.report_ks) if args.report_ks else config.report_ks
    top_k = args.top_k or max(config.top_k, max(report_ks))
    bm25_dir = config.index_dir
    dense_dir = config.dense_index_dir
    dev_set = args.dev_set or config.dev_set
    output_dir = args.output_dir or config.hybrid_eval_output_dir

    if not (bm25_dir / "index_meta.json").exists():
        raise FileNotFoundError(f"BM25 index not found at {bm25_dir}")
    if not (dense_dir / "index_meta.json").exists():
        raise FileNotFoundError(
            f"Dense index not found at {dense_dir}. Run: python scripts/build_dense_index.py"
        )

    corpus = load_corpus_from_config(config)
    bm25_index = load_bm25_index(bm25_dir, corpus.records)
    encoder = load_encoder_from_config(config)
    dense_index = load_dense_index(dense_dir, corpus.records, encoder)
    retriever = HybridRetriever(
        bm25=bm25_index,
        dense=dense_index,
        candidate_k=config.hybrid_candidate_k,
        rrf_k=config.hybrid_rrf_k,
        weight_bm25=config.hybrid_weight_bm25,
        weight_dense=config.hybrid_weight_dense,
    )

    examples = list(load_jsonl(dev_set))
    if not examples:
        raise ValueError(f"Benchmark is empty: {dev_set}")
    benchmark = benchmark_metadata(dev_set, query_count=len(examples))

    gold_ids = {
        item["chunk_id"]
        for example in examples
        for item in example.get("relevance_judgments", [])
    }
    known_ids = {record.chunk_id for record in corpus.records}
    missing = sorted(gold_ids - known_ids)
    if missing:
        raise ValueError(f"Development gold chunk_id missing from corpus: {missing}")

    rows = []
    latencies = []
    candidate_k = retriever.candidate_k
    for example in examples:
        query = example["query"]
        route = route_query(query, available_collections=[s.collection for s in config.chunk_sources])
        started = time.perf_counter()
        routed_bm25 = bm25_index.search(query, top_k=candidate_k, collections=route.collections)
        routed_dense = dense_index.search(query, top_k=candidate_k, collections=route.collections)
        routed_results = rrf_fuse(
            routed_bm25,
            routed_dense,
            rrf_k=retriever.rrf_k,
            weight_bm25=retriever.weight_bm25,
            weight_dense=retriever.weight_dense,
            top_k=top_k,
        )
        latencies.append(time.perf_counter() - started)
        oracle_bm25 = bm25_index.search(
            query, top_k=candidate_k, collections=example.get("target_collections") or None
        )
        oracle_dense = dense_index.search(
            query, top_k=candidate_k, collections=example.get("target_collections") or None
        )
        oracle_results = rrf_fuse(
            oracle_bm25,
            oracle_dense,
            rrf_k=retriever.rrf_k,
            weight_bm25=retriever.weight_bm25,
            weight_dense=retriever.weight_dense,
            top_k=top_k,
        )
        for item in routed_results:
            if item.collection not in route.collections:
                raise ValueError(f"Routed result escaped collections: {item.chunk_id}")
        rows.append(
            {
                "query_id": example["query_id"],
                "example": example,
                "route": route.to_dict(),
                "routed": {
                    "latency_s": latencies[-1],
                    "results": serialize_results(routed_results),
                    "bm25_candidates": serialize_results(routed_bm25),
                    "dense_candidates": serialize_results(routed_dense),
                },
                "oracle": {
                    "results": serialize_results(oracle_results),
                    "bm25_candidates": serialize_results(oracle_bm25),
                    "dense_candidates": serialize_results(oracle_dense),
                },
            }
        )

    grid = []
    for spec in GRID:
        fused_rows = []
        for row in rows:
            fused = rrf_fuse(
                hits_from_dicts(row["routed"]["bm25_candidates"]),
                hits_from_dicts(row["routed"]["dense_candidates"]),
                rrf_k=spec["rrf_k"],
                weight_bm25=spec["weight_bm25"],
                weight_dense=spec["weight_dense"],
                top_k=top_k,
            )
            fused_rows.append(
                {
                    "example": row["example"],
                    "route": row["route"],
                    "routed": {"results": serialize_results(fused)},
                }
            )
        grid.append({**spec, "routed": aggregate_dev_metrics(fused_rows, report_ks, "routed")["metrics"]})

    metrics = {
        "method": "hybrid_rrf",
        "top_k": top_k,
        "report_ks": list(report_ks),
        "hybrid": {
            "candidate_k": retriever.candidate_k,
            "rrf_k": retriever.rrf_k,
            "weight_bm25": retriever.weight_bm25,
            "weight_dense": retriever.weight_dense,
        },
        "latency_s": {
            "mean": round(sum(latencies) / len(latencies), 4),
            "median": round(sorted(latencies)[len(latencies) // 2], 4),
        },
        "routed": aggregate_dev_metrics(rows, report_ks, "routed"),
        "oracle": aggregate_dev_metrics(rows, report_ks, "oracle"),
        "grid": grid,
    }

    comparisons = {}
    for name, path in (
        ("bm25", args.bm25_eval_dir or config.eval_output_dir),
        ("dense", args.dense_eval_dir or config.dense_eval_output_dir),
    ):
        comparison_metrics = load_matching_metrics(path, dev_set, benchmark)
        if comparison_metrics is not None:
            comparisons[name] = comparison_metrics

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config.config_file, output_dir / "config.snapshot.yaml")
    (output_dir / "chunk_hashes.json").write_text(
        json.dumps(corpus.chunk_hashes, indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "per_query_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(
        render_report(metrics, list(report_ks), top_k, comparisons, benchmark),
        encoding="utf-8",
    )
    (output_dir / benchmark.hash_filename).write_text(file_sha256(dev_set) + "\n", encoding="utf-8")

    print(json.dumps(metrics["routed"]["metrics"], indent=2))
    print(f"Wrote evaluation -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
