# BM25 test evaluation

- queries: 100
- top_k: 10
- report_ks: [1, 3, 5, 10]
- labeling: TargetHit@k is 1 if any grade-2 gold chunk_id appears in the top-k results. Recall@k counts all grade-2 labels, while nDCG@k uses grades 0-2. Unpooled labels should not be interpreted as corpus-level Recall.

## Routed retrieval

TargetHit@1: 0.81
TargetHit@3: 0.86
TargetHit@5: 0.86
TargetHit@10: 0.87
Recall@1: 0.765
Recall@3: 0.855
Recall@5: 0.86
Recall@10: 0.87
nDCG@1: 0.81
nDCG@3: 0.8383
nDCG@5: 0.8409
nDCG@10: 0.8445
MRR@10: 0.835

### Router

exact_set_accuracy: 0.97
collection_precision: 0.9783
collection_recall: 1.0

### By query type

common_association:
  TargetHit@1: 0.95
  TargetHit@3: 0.95
  TargetHit@5: 0.95
  TargetHit@10: 1.0
  Recall@1: 0.95
  Recall@3: 0.95
  Recall@5: 0.95
  Recall@10: 1.0
  nDCG@1: 0.95
  nDCG@3: 0.95
  nDCG@5: 0.95
  nDCG@10: 0.9678
  MRR@10: 0.9583
  n: 20
cross_collection:
  TargetHit@1: 0.9
  TargetHit@3: 1.0
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  Recall@1: 0.45
  Recall@3: 0.95
  Recall@5: 1.0
  Recall@10: 1.0
  nDCG@1: 0.9
  nDCG@3: 0.9307
  nDCG@5: 0.9571
  nDCG@10: 0.9571
  MRR@10: 0.9333
  n: 10
gene_alias:
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
gene_function:
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
  n: 15
gene_identifier:
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
  n: 2
gene_location:
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
  n: 2
ldsc_correlation:
  TargetHit@1: 0.7
  TargetHit@3: 0.9
  TargetHit@5: 0.9
  TargetHit@10: 0.9
  Recall@1: 0.7
  Recall@3: 0.9
  Recall@5: 0.9
  Recall@10: 0.9
  nDCG@1: 0.7
  nDCG@3: 0.8262
  nDCG@5: 0.8262
  nDCG@10: 0.8262
  MRR@10: 0.8
  n: 20
rare_association:
  TargetHit@1: 0.9333
  TargetHit@3: 0.9333
  TargetHit@5: 0.9333
  TargetHit@10: 0.9333
  Recall@1: 0.9333
  Recall@3: 0.9333
  Recall@5: 0.9333
  Recall@10: 0.9333
  nDCG@1: 0.9333
  nDCG@3: 0.9333
  nDCG@5: 0.9333
  nDCG@10: 0.9333
  MRR@10: 0.9333
  n: 15
unanswerable:
  TargetHit@1: 0.0
  TargetHit@3: 0.0
  TargetHit@5: 0.0
  TargetHit@10: 0.0
  Recall@1: 0.0
  Recall@3: 0.0
  Recall@5: 0.0
  Recall@10: 0.0
  nDCG@1: 0.0
  nDCG@3: 0.0
  nDCG@5: 0.0
  nDCG@10: 0.0
  MRR@10: 0.0
  n: 10

## Oracle-collection diagnostic

TargetHit@1: 0.81
TargetHit@3: 0.86
TargetHit@5: 0.86
TargetHit@10: 0.87
Recall@1: 0.765
Recall@3: 0.855
Recall@5: 0.86
Recall@10: 0.87
nDCG@1: 0.81
nDCG@3: 0.8383
nDCG@5: 0.8409
nDCG@10: 0.8445
MRR@10: 0.835
