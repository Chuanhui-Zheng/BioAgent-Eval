# Retrieval Performance Summary

Latency values are extracted from the existing final per-query evaluation outputs; no retriever was rerun.

| Method | Mean (s) | Median (s) | P95 (s) | Serialized index size |
|---|---:|---:|---:|---:|
| bm25 | 0.0409 | 0.0334 | 0.0993 | 33.61 MiB |
| dense | 0.1596 | 0.1361 | 0.1579 | 163.85 MiB |
| hybrid | 0.2214 | 0.1954 | 0.2807 | 197.46 MiB |

Build time, document encoding time, cold-start load time, and separately isolated search-only/end-to-end timings were not recorded in the existing runs.
