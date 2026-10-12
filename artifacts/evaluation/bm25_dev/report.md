# BM25 development evaluation

- queries: 20
- top_k: 10
- report_ks: [5, 10]
- labeling: TargetHit@k is 1 if any grade-2 gold chunk_id appears in the top-k results. This is not pooled corpus-level Recall.

## Routed retrieval

TargetHit@5: 1.0
TargetHit@10: 1.0
MRR@10: 0.975

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
  MRR@10: 1.0
  n: 4
rare_association:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 1.0
  n: 4

## Oracle-collection diagnostic

TargetHit@5: 1.0
TargetHit@10: 1.0
MRR@10: 0.975

