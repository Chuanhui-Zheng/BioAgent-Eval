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
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.dense_retriever import load_dense_index, load_encoder_from_config
from retrieval.evaluation import BenchmarkMetadata, benchmark_metadata, load_matching_metrics
from retrieval.metrics import aggregate_dev_metrics
from retrieval.router import route_query
from retrieval.schema import SearchResult


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate routed dense retrieval on the development set.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--index-dir", type=Path, default=None)
    parser.add_argument("--dev-set", type=Path, default=None)
    parser.add_argument("--bm25-eval-dir", type=Path, default=None)
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
        }
        for item in results
    ]


def render_report(
    metrics: dict,
    report_ks: list[int],
    top_k: int,
    bm25_metrics: dict | None = None,
    benchmark: BenchmarkMetadata | None = None,
) -> str:
    benchmark = benchmark or benchmark_metadata(Path("retrieval_dev.jsonl"), metrics["routed"]["n"])
    lines = [
        f"# Dense {benchmark.label} evaluation",
        "",
        f"- queries: {metrics['routed']['n']}",
        f"- top_k: {top_k}",
        f"- report_ks: {report_ks}",
        "- embedding field: content only",
        "- identifier boost: disabled",
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
    ]
    if bm25_metrics:
        dense_routed = metrics["routed"]["metrics"]
        bm25_routed = bm25_metrics["routed"]["metrics"]
        lines.extend(
            [
                f"## Comparison with BM25 ({benchmark.comparison_label})",
                "",
                "| metric | BM25 | Dense |",
                "| --- | --- | --- |",
                f"| TargetHit@5 | {bm25_routed.get('TargetHit@5')} | {dense_routed.get('TargetHit@5')} |",
                f"| TargetHit@10 | {bm25_routed.get('TargetHit@10')} | {dense_routed.get('TargetHit@10')} |",
                f"| Recall@10 | {bm25_routed.get('Recall@10')} | {dense_routed.get('Recall@10')} |",
                f"| nDCG@10 | {bm25_routed.get('nDCG@10')} | {dense_routed.get('nDCG@10')} |",
                f"| MRR@10 | {bm25_routed.get('MRR@10')} | {dense_routed.get('MRR@10')} |",
                "",
                "Dense embeds `content` only and does not pin identifier exact matches. "
                "BM25 indexes title+content and can pin exact IDs.",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    config = load_retrieval_config(PROJECT_ROOT, args.config)
    report_ks = tuple(args.report_ks) if args.report_ks else config.report_ks
    top_k = args.top_k or max(config.top_k, max(report_ks))
    index_dir = args.index_dir or config.dense_index_dir
    dev_set = args.dev_set or config.dev_set
    output_dir = args.output_dir or config.dense_eval_output_dir

    if not (index_dir / "index_meta.json").exists():
        raise FileNotFoundError(
            f"Dense index not found at {index_dir}. Run: python scripts/build_dense_index.py"
        )

    corpus = load_corpus_from_config(config)
    encoder = load_encoder_from_config(config)
    index = load_dense_index(index_dir, corpus.records, encoder)

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
    for example in examples:
        query = example["query"]
        route = route_query(query, available_collections=[s.collection for s in config.chunk_sources])
        started = time.perf_counter()
        routed_results = index.search(query, top_k=top_k, collections=route.collections)
        latencies.append(time.perf_counter() - started)
        oracle_results = index.search(
            query,
            top_k=top_k,
            collections=example.get("target_collections") or None,
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
                },
                "oracle": {"results": serialize_results(oracle_results)},
            }
        )

    metrics = {
        "method": "dense",
        "top_k": top_k,
        "report_ks": list(report_ks),
        "latency_s": {
            "mean": round(sum(latencies) / len(latencies), 4),
            "median": round(sorted(latencies)[len(latencies) // 2], 4),
        },
        "routed": aggregate_dev_metrics(rows, report_ks, "routed"),
        "oracle": aggregate_dev_metrics(rows, report_ks, "oracle"),
    }

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
    bm25_metrics = load_matching_metrics(
        args.bm25_eval_dir or config.eval_output_dir,
        dev_set,
        benchmark,
    )
    (output_dir / "report.md").write_text(
        render_report(
            metrics,
            list(report_ks),
            top_k,
            bm25_metrics=bm25_metrics,
            benchmark=benchmark,
        ),
        encoding="utf-8",
    )
    (output_dir / benchmark.hash_filename).write_text(file_sha256(dev_set) + "\n", encoding="utf-8")

    print(json.dumps(metrics["routed"]["metrics"], indent=2))
    print(f"Wrote evaluation -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
