# Artifact map

These files preserve reproducibility evidence. Directory names identify different evaluations; they are not interchangeable copies.

| Location | Meaning |
| --- | --- |
| `chunks/` | Committed baseline chunks; rebuild for the active expanded corpus |
| `manifest.json` | Baseline corpus manifest |
| `manifest_partitioned.json` | Expanded corpus manifest |
| `evaluation/*_dev/` | Development-set results used during experimentation |
| `evaluation/*_test/` | Recorded test-set results for the named retriever |
| `evaluation/bm25_test_reproduced/` | Separate reproduction of the baseline BM25 run |
| `evaluation/retrieval_comparison_test/` | BM25/dense/hybrid comparison on a shared test set |
| `evaluation/retrieval_expanded_dev/` | Expanded-corpus development comparison |
| `evaluation/retrieval_expanded_test/` | Expanded-corpus test comparison |
| `evaluation/rag_e2e/` | Offline end-to-end RAG evaluation |
| `evaluation/test_pool/` | Candidate relevance pool |
| `evaluation/performance/` | Performance measurements |

Read each run's metrics, configuration snapshot and dataset hashes together. Old scores should not be presented as measurements of a rebuilt corpus. Do not move these folders without updating the scripts and references that use them.

`indexes/` and `ingestion_dev/` are generated locally and ignored by Git. Prepare the current runtime using the root [README](../README.md).
