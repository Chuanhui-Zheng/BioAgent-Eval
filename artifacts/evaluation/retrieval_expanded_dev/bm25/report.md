# BM25 development evaluation

- queries: 25
- top_k: 10
- report_ks: [1, 3, 5, 10]
- labeling: TargetHit@k is 1 if any grade-2 gold chunk_id appears in the top-k results. Recall@k counts all grade-2 labels, while nDCG@k uses grades 0-2. Unpooled labels should not be interpreted as corpus-level Recall.

## Routed retrieval

TargetHit@1: 1.0
TargetHit@3: 1.0
TargetHit@5: 1.0
TargetHit@10: 1.0
Recall@1: 1.0
Recall@3: 1.0
Recall@5: 1.0
Recall@10: 1.0
nDCG@1: 1.0
nDCG@3: 1.0
nDCG@5: 1.0
nDCG@10: 1.0
MRR@10: 1.0

### Router

exact_set_accuracy: 1.0
collection_precision: 1.0
collection_recall: 1.0

### By query type

gene_association_wes:
  TargetHit@1: 1.0
  TargetHit@3: 1.0
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  Recall@1: 1.0
  Recall@3: 1.0
  Recall@5: 1.0
  Recall@10: 1.0
  nDCG@1: 1.0
  nDCG@3: 1.0
  nDCG@5: 1.0
  nDCG@10: 1.0
  MRR@10: 1.0
  n: 6
ldsc_partitioned_heritability:
  TargetHit@1: 1.0
  TargetHit@3: 1.0
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  Recall@1: 1.0
  Recall@3: 1.0
  Recall@5: 1.0
  Recall@10: 1.0
  nDCG@1: 1.0
  nDCG@3: 1.0
  nDCG@5: 1.0
  nDCG@10: 1.0
  MRR@10: 1.0
  n: 12
variant_association_clumped:
  TargetHit@1: 1.0
  TargetHit@3: 1.0
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  Recall@1: 1.0
  Recall@3: 1.0
  Recall@5: 1.0
  Recall@10: 1.0
  nDCG@1: 1.0
  nDCG@3: 1.0
  nDCG@5: 1.0
  nDCG@10: 1.0
  MRR@10: 1.0
  n: 7

## Oracle-collection diagnostic

TargetHit@1: 1.0
TargetHit@3: 1.0
TargetHit@5: 1.0
TargetHit@10: 1.0
Recall@1: 1.0
Recall@3: 1.0
Recall@5: 1.0
Recall@10: 1.0
nDCG@1: 1.0
nDCG@3: 1.0
nDCG@5: 1.0
nDCG@10: 1.0
MRR@10: 1.0
