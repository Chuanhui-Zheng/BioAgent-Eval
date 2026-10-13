# Review fixes — 2026-10-13

## Changes
- BM25 and dense retrieval apply authorized collections and metadata filters before top-k selection. This prevents global candidate starvation.
- Broad single-phenotype gene-list questions use a disclosed source-statistic overview: common BF > 1 descending and source-significant rare p-values ascending, interleaved without claiming a unified target ranking.
- Fixed target comparison's gene/symbol schema mismatch, explicit trait-pair context contamination, and function-intent routing.
- GTEx is part of the standard eight-collection rebuild. RNA 50% source summaries and derived protein medians retain separate assay provenance, row references, source hashes and transform version. Units remain unconfirmed; TPM is not assumed. Requested tissues are included even when outside the top-five summary.
- Hosted displayed text is constructed from cited claims. Validation rejects detached prose, unsupported citation IDs and numeric policy failures. Hosted validation/request failures fall back to local evidence and disclose fallback.
- Citation metadata carries source/corpus/chunk-file hashes. Old citation versions return HTTP 409. BM25 loading rejects changed chunk hashes and changed ID ordering.
- API runs are saved under artifacts/runs/<workspace>/, excluded from Git and Docker context. Logs contain question, evidence, response, validation, usage and index metadata; API keys and raw provider exceptions are not persisted.
- Hosted usage records include attempted calls and reported tokens. Set config/model_pricing.json entries by model with input_usd_per_million and output_usd_per_million (USD). Empty/missing rates mean unknown cost, never an invented price.
- X-Workspace-ID supports all, annotations and genetics. This is a simulated collection boundary, not authentication or production multi-tenancy. Evidence, analysis routes, gene associations and in-memory analysis-run access enforce the scope. Some mixed-source analysis endpoints require all underlying collections and return 403 for narrower scopes.
- Frontend adds workspace selection, clears state when switching, exposes run/usage information, separates transport errors from insufficient evidence, improves small-screen controls and splits chart dependencies.

## Reproduction
After source changes: python scripts/prepare_api_corpus.py; python scripts/build_bm25_index.py.
GTEx needs both supplied CSVs at the existing data/raw locations. Preparation validates source and output hashes.
Tests: TMPDIR=/private/tmp python -m pytest -q.
Frontend: cd frontend && npm run build.
Default end-to-end evaluation: python scripts/evaluate_rag_offline.py --output-dir artifacts/evaluation/review_e2e.
Historical oracle diagnostic only: add --oracle-collections.
Regression: python scripts/evaluate_annotated.py data/evaluation/integration_regression.jsonl --output artifacts/evaluation/integration_review/report.json.

## Verified
- 206 tests and 55 subtests passed, including FAISS, filtering, provenance, stale-index checks, simulated isolation, provider fallback and pricing mocks.
- Production frontend build passed; main JS approximately 287 KB and separate charts approximately 419 KB (uncompressed).
- Full corpus preparation and BM25 rebuild completed: 159,607 chunks across eight collections, including 16,630 GTEx chunks.
- Existing 100 questions, all-collection mode: answerable TargetHit@10 95.56%, status accuracy 99%, unanswerable refusal accuracy 100%. Citation structural checks pass; they do not measure semantic support.
- Added 16 maintainer regression questions covering eight collections: status accuracy 100%, gold retrieval hit rate 100%, citation precision 100%, citation recall 92.94%, deterministic fact/number policies 100%.
- Browser checks: broad 2hrG evidence query and PPARG/TCF7L2 comparison produce real source results.

## Remaining limits
One old benchmark case involving AM broad-intensity phenotype wording still refuses despite a gold record; alias semantics need confirmation rather than an invented mapping. The 16 new cases are regression checks based on supplied records, not a blind scientific evaluation; citation recall is not perfect. Real hosted model calls were not made, so hosted quality/latency/cost require separate measurement. Docker could not be executed on this host. Dense filtering is tested, but a fresh full dense/hybrid scientific benchmark was not run. Semantic entailment, clinical validity, source unit definitions and independent human gold annotations remain open. Simulated workspaces must not be presented as real authorization.

Client-provided raw data was preserved; derived GTEx chunks, manifest and BM25 index were regenerated.
