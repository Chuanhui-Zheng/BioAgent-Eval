# Phase 1 Report — Formal Retrieval

## Outcome

Phase 1 is complete for the production offline baseline. The project is installable, the 41,103-chunk corpus validates, BM25 has been rebuilt locally, a typed authorization-aware retrieval service is available, and the frozen 100-query BM25 evaluation was reproduced without changing labels.

## Delivered

- `RetrievalRequest`, `RetrievalResponse`, and `RetrieverService`.
- Authorization/router intersection: routing may narrow but never expand caller access.
- Isolation violation detection.
- Environment and index diagnostics.
- Installable `pyproject.toml` with retrieval, embedding, and test extras.
- Rebuilt BM25 index under `artifacts/indexes/bm25_title_content`.
- Reproduced evaluation under `artifacts/evaluation/bm25_test_reproduced`.

## Results

The reproduced BM25 run achieved Recall@10 0.8700, nDCG@10 0.8496, and MRR@10 0.8417. This meets the agreed thresholds and slightly exceeds the supplied nDCG/MRR baseline. Router collection recall remains 1.00 in the supplied frozen evaluation.

The supplied Hybrid result remains the best top-10 recall at 0.88. BM25 remains the default end-to-end method because it has stronger ranking quality, lower latency, and is reproducible on this machine.

## Verdict

**PASS**, with the Dense/Hybrid local-index caveat documented in `error_analysis.md`.
