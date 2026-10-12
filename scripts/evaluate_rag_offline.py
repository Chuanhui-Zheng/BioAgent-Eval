from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from augmentation.builder import ContextBuilder
from generation.offline import OfflineEvidenceGenerator
from rag.pipeline import RAGPipeline
from retrieval.bm25_retriever import load_bm25_index
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.service import RetrievalRequest, RetrieverService


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate the offline evidence-grounded RAG pipeline.")
    parser.add_argument("--benchmark", type=Path, default=PROJECT_ROOT / "data/evaluation/rag_e2e.jsonl")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "artifacts/evaluation/rag_e2e")
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args()


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    args = parse_args()
    config = load_retrieval_config(PROJECT_ROOT)
    corpus = load_corpus_from_config(config)
    bm25 = load_bm25_index(config.index_dir, corpus.records)
    pipeline = RAGPipeline(
        RetrieverService(bm25, "bm25"),
        ContextBuilder(),
        OfflineEvidenceGenerator(),
    )
    rows = []
    for item in load_jsonl(args.benchmark):
        gold = {
            judgment["chunk_id"]
            for judgment in item.get("relevance_judgments", [])
            if int(judgment.get("grade", 0)) == 2
        }
        run = pipeline.run(
            RetrievalRequest(
                item["query"],
                authorized_collections=tuple(item["target_collections"]),
                top_k=args.top_k,
            )
        )
        retrieved = [hit.chunk_id for hit in run.retrieval.results]
        answerable = bool(item["answerable"])
        status_correct = (
            run.answer.status in {"answer", "qualified"}
            if answerable
            else run.answer.status == "refuse"
        )
        rows.append(
            {
                "query_id": item["query_id"],
                "query_type": item["query_type"],
                "answerable": answerable,
                "expected_status": "answer_or_qualified" if answerable else "refuse",
                "observed_status": run.answer.status,
                "status_correct": status_correct,
                "target_hit_at_10": bool(gold.intersection(retrieved[:10])) if answerable else None,
                "retrieved_chunk_ids": retrieved,
                "context_chunk_ids": [p.chunk_id for p in run.context.passages],
                "context_budget_pass": run.context.estimated_tokens <= run.context.max_context_tokens,
                "context_duplicate_free": len({p.chunk_id for p in run.context.passages}) == len(run.context.passages),
                "context_citations_resolvable": all(
                    p.chunk_id in run.context.citation_registry for p in run.context.passages
                ),
                "citation_correctness": run.validation.citation_correctness,
                "citation_completeness": run.validation.citation_completeness,
                "claim_support_contract": 1.0 if run.validation.valid else 0.0,
                "isolation_pass": all(
                    p.collection in item["target_collections"] for p in run.context.passages
                ),
                "latency_s": run.latency_s,
                "limitations": run.answer.limitations,
            }
        )
    answerable_rows = [row for row in rows if row["answerable"]]
    metrics = {
        "pipeline": "bm25 -> context_builder -> offline_evidence_generator -> validator",
        "queries": len(rows),
        "retrieval_target_hit_at_10": sum(r["target_hit_at_10"] for r in answerable_rows) / len(answerable_rows),
        "status_accuracy": sum(r["status_correct"] for r in rows) / len(rows),
        "unanswerable_refusal_accuracy": sum(r["status_correct"] for r in rows if not r["answerable"]) / sum(not r["answerable"] for r in rows),
        "citation_correctness": statistics.mean(r["citation_correctness"] for r in rows),
        "citation_completeness": statistics.mean(r["citation_completeness"] for r in rows),
        "claim_support_contract": statistics.mean(r["claim_support_contract"] for r in rows),
        "isolation": statistics.mean(r["isolation_pass"] for r in rows),
        "context_budget_compliance": statistics.mean(r["context_budget_pass"] for r in rows),
        "context_duplicate_free": statistics.mean(r["context_duplicate_free"] for r in rows),
        "context_citation_resolvability": statistics.mean(r["context_citations_resolvable"] for r in rows),
        "latency_s": {
            key: statistics.mean(r["latency_s"][key] for r in rows)
            for key in ("retrieval", "augmentation", "generation_and_validation", "total")
        },
        "interpretation": {
            "citation_metrics": "Deterministic structural validation against the supplied context.",
            "claim_support_contract": "Offline generator claims are produced only from cited passage metadata/content; this is not an LLM-judge score.",
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "per_query_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
