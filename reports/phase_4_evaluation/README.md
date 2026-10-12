# Phase 4 Report — End-to-End Evaluation

## Outcome

Phase 4 is complete. The executable vertical slice is:

```text
BM25 -> RetrieverService -> ContextBuilder -> OfflineEvidenceGenerator -> Citation Validator
```

The evaluation uses a separate 100-row `rag_e2e.jsonl` derived from the frozen retrieval benchmark. It adds expected evidence status, allowed citations, required fact-field policies, and prohibited claim classes without modifying retrieval labels.

## Results

- answerable TargetHit@10: 96.67% (87/90);
- status accuracy: 99%;
- unanswerable refusal accuracy: 100%;
- citation correctness/completeness: 100% / 100%;
- claim-support contract: 100%;
- collection isolation: 100%;
- context budget, duplicate, and citation-registry checks: 100%;
- mean end-to-end latency: approximately 11.3 ms on the final recorded run.

The retrieval rate is reported over answerable queries; the historical all-query TargetHit@10 remains 0.87 because the ten intentionally unanswerable queries have no positive target.

## Artifacts

- `data/evaluation/rag_e2e.jsonl`
- `artifacts/evaluation/rag_e2e/metrics.json`
- `artifacts/evaluation/rag_e2e/per_query_results.jsonl`

## Verdict

**PASS** for the offline formal RAG baseline.
