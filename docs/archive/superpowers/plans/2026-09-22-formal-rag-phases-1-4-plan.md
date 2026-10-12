# Formal RAG Phases 1–4 Implementation Plan

## Phase 1 — Formal Retrieve

1. Add installable project metadata and stable configuration loading.
2. Add typed request/response contracts and a `RetrieverService` enforcing authorization intersection.
3. Add index/environment diagnostics and regression tests.
4. Run retrieval tests and capture existing frozen benchmark metrics without modifying labels.
5. Write the Phase 1 report bundle.

## Phase 2 — Augmentation

1. Add augmentation configuration and typed context contracts.
2. Implement context isolation, deduplication, token budgeting, citation registry, and evidence-policy classification.
3. Add supported, qualified, refused, conflicting, and isolation tests.
4. Run the augmentation evaluation fixtures and write the Phase 2 report bundle.

## Phase 3 — Generation

1. Add provider-neutral generation contracts.
2. Implement the deterministic offline evidence generator.
3. Implement citation, collection, schema, and claim-support validation.
4. Add safe failure behavior and optional provider-adapter boundary.
5. Run generation evaluation fixtures and write the Phase 3 report bundle.

## Phase 4 — End-to-End Evaluation

1. Add the orchestrating RAG pipeline and immutable run-manifest output.
2. Add a separate end-to-end benchmark with expected status, facts, citations, and collection boundaries.
3. Implement stage and end-to-end metrics with per-query JSONL output.
4. Compare BM25 and Hybrid from the frozen retrieval artifacts and evaluate the executable offline vertical slice.
5. Run all tests and write the Phase 4 report bundle and top-level handoff instructions.

## Quality Rules

- Do not tune on or edit the frozen 100-query retrieval test set.
- Generate report metrics from artifacts or executable fixtures.
- Preserve all failed cases in error-analysis reports.
- Never count a citation outside the supplied context as valid.
- Never allow routing to expand the caller-authorized collection set.
