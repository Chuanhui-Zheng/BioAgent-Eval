# Hybrid RRF development evaluation

- queries: 20
- top_k: 10
- report_ks: [5, 10]
- candidate_k: 50
- rrf_k: 60
- weight_bm25: 1.0
- weight_dense: 1.0
- fusion: existing BM25 (title+content, identifier pin) + dense (content only); no new index
- labeling: TargetHit@k is 1 if any grade-2 gold chunk_id appears in the top-k results. This is not pooled corpus-level Recall.

## Routed retrieval

TargetHit@5: 1.0
TargetHit@10: 1.0
MRR@10: 0.95

### Router

exact_set_accuracy: 1.0
collection_precision: 1.0
collection_recall: 1.0

### By query type

common_association:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 1.0
  n: 4
cross_collection:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 1.0
  n: 2
gene_alias:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 0.75
  n: 2
gene_function:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 1.0
  n: 2
gene_identifier:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 1.0
  n: 2
ldsc_correlation:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 0.875
  n: 4
rare_association:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 1.0
  n: 4

## Oracle-collection diagnostic

TargetHit@5: 1.0
TargetHit@10: 1.0
MRR@10: 0.95

## Comparison (same 20 queries, same router)

| metric | BM25 | Dense | Hybrid |
| --- | --- | --- | --- |
| TargetHit@5 | 1.0 | 0.9 | 1.0 |
| TargetHit@10 | 1.0 | 0.9 | 1.0 |
| MRR@10 | 0.975 | 0.835 | 0.95 |

## Offline RRF grid (candidates retrieved once)

- weight_bm25: 1.0
  weight_dense: 1.0
  rrf_k: 60
  candidate_k: 50
  routed:
    TargetHit@5: 1.0
    TargetHit@10: 1.0
    MRR@10: 0.95
- weight_bm25: 1.2
  weight_dense: 0.8
  rrf_k: 60
  candidate_k: 50
  routed:
    TargetHit@5: 1.0
    TargetHit@10: 1.0
    MRR@10: 0.95
- weight_bm25: 0.8
  weight_dense: 1.2
  rrf_k: 60
  candidate_k: 50
  routed:
    TargetHit@5: 0.95
    TargetHit@10: 0.95
    MRR@10: 0.9

Grid results are diagnostic only; YAML defaults are not auto-updated.

