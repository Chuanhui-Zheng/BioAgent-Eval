# Phase 1 Error Analysis

- Three of 90 answerable queries miss the grade-2 target at top 10. Existing sliced analysis identifies rare-association and LDSC cases as priorities.
- Dense and Hybrid serialized indexes were absent from the supplied folder. The Qwen model was downloaded and its revision fixed, but a full local encoding attempt projected roughly 80 minutes on Apple MPS and was stopped without saving a partial index.
- Dense/Hybrid numbers in this report are therefore the supplied frozen results, not a new local run. Their per-query results, hashes, and configuration snapshots remain in `artifacts/evaluation/dense_test` and `hybrid_test`.
- Collection filtering is an application-level evidence boundary, not enterprise authentication or tenant authorization.
