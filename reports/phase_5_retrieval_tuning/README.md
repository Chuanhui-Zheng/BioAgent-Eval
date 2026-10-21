# Phase 5 — Retrieval Tuning: Hybrid Switch and Cross-Encoder Reranker

Date: 2026-10-21. Corpus: 8 collections, 159,607 chunks.

## What was built

- **Configurable serving method** (`src/retrieval/factory.py`): `bm25`, `dense`, `hybrid`,
  `bm25_rerank`, `hybrid_rerank`, chosen by `pipeline.default_method` in
  `config/retrieval.yaml` or `RAG_RETRIEVAL_METHOD`. Missing dense index, model or
  dependencies degrade step by step (`hybrid_rerank → hybrid → bm25_rerank → bm25`);
  the reason is logged and returned by `GET /api/health` under `retrieval`.
- **Cross-encoder reranker** (`src/retrieval/reranker.py`): BAAI/bge-reranker-base or
  bge-reranker-v2-m3 over the first stage's `candidate_k` passages, fused with the
  first-stage rank: `alpha/(rrf_k+rerank_rank) + (1-alpha)/(rrf_k+first_rank)`.
  Reranking only reorders already-authorised candidates, so it cannot widen access.
- **Dense index build** is resumable and can split work between MPS and CPU workers
  (`scripts/build_dense_index.py --resume [--worker helper]`). Dense search now runs as
  exact numpy inner product, because torch and faiss each load their own OpenMP
  runtime on macOS and crash or deadlock when they run in the same process.
- **Dev-only tuning** (`scripts/tune_retrieval.py`) refuses any file whose name contains
  `test` or `blind`. A new 16-query comparison dev set
  (`data/evaluation/retrieval_comparison_dev.jsonl`) is disjoint from every test and blind
  grade-2 target.

## Decision on dense / hybrid

Building the Qwen3-Embedding-0.6B index for 159,607 chunks on the available Apple M4
runs at ~5–7 chunks/s (each chunk ≈ 240 GFLOP), i.e. 5–7 hours. Before investing that,
BM25's candidate ceiling was measured on the dev sets: all grade-2 targets are already
in BM25's top 10 for 60 of 61 dev queries (20/20, 25/25, 15/16), and the one miss is not
in the top 50 either. Dense retrieval therefore could not change the dev-based decision,
and the build was stopped (one shard is checkpointed; `--resume` continues it). Hybrid
code, configuration, fallback and tests remain in place for when an index is built on
GPU hardware.

## Dev tuning (61 queries; rule fixed in advance)

Rule: maximise mean nDCG@10; configurations within 0.005 of the best are ties, broken
by lowest estimated latency. Grid: reranker ∈ {none, bge-reranker-base, bge-reranker-v2-m3}
× candidate_k ∈ {10, 20, 30, 50} × alpha ∈ {1, 0.75, 0.5, 0.25}.

| Configuration | nDCG@10 | MRR@10 | Est. latency |
|---|---|---|---|
| **BM25 (selected)** | **0.9843** | 0.9918 | 0.04 s |
| BM25 + bge-reranker-base, k=10, α=0.25 (best reranker) | 0.9811 | 0.9918 | 0.56 s |
| BM25 + bge-reranker-v2-m3, k=10, α=0.25 | 0.9808 | 0.9918 | 1.93 s |
| BM25 + bge-reranker-v2-m3, k=50, α=0.25 | 0.9739 | 0.9836 | 9.5 s |

Cross-encoder cost on M4/MPS: 52 ms per pair (base) and 189 ms per pair (v2-m3). Pure reranking
(α = 1) was worse than fusion in every setting: the general-domain rerankers do not
reliably prefer the exact ancestry/mask/field record in templated scientific text.

## Frozen test evaluation (run once, no tuning)

`scripts/evaluate_retrieval_methods.py --no-dense`; full output in `test_results.json`.
Hit@10 is computed over all queries, so sets that include unanswerable queries cap below 1.

| Set | n | BM25 Hit@10 | BM25 nDCG@10 | +reranker nDCG@10 | AllTargets@10 |
|---|---|---|---|---|---|
| retrieval_test | 100 (10 unanswerable) | 0.860 (95.6 % answerable) | 0.839 | 0.840 | – |
| retrieval_expanded_test | 100 (10 unanswerable) | 0.900 (100 % answerable) | 0.883 | 0.882 | – |
| retrieval_comparison_test | 50 | 1.000 | 0.977 | 0.963 | 0.96 (both) |
| blind_e2e_v1 | 40 (6 unanswerable) | 0.850 (100 % answerable) | 0.722 | **0.751** | 1.00 |
| Mean latency | | 0.04 s | | 0.55 s | |

Interpretation: the current BM25 (with the improved partitioned/WES chunk text) already
reaches 0.96 AllTargets@10 on comparison queries, above the historical hybrid result
(0.84 on the earlier corpus). The reranker helps ranking only on the more natural-language
blind questions (+0.03 nDCG@10) and costs about 14 times the latency, so BM25 stays the default.
`RAG_RETRIEVAL_METHOD=bm25_rerank` enables the tuned reranker.

## Caveats

- Dev sets are near-saturated for BM25, so they cannot discriminate between methods. A
  harder, natural-language development set (blind-style, disjoint entities) is the main
  prerequisite for meaningful future tuning.
- Test labels were pooled from earlier BM25/dense/hybrid runs; chunks newly surfaced by
  the reranker may be unjudged and count as non-relevant.
- Dense/hybrid were not re-measured on the current corpus.
