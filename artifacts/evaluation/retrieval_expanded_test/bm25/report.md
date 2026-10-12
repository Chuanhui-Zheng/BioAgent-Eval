# BM25 test evaluation

- queries: 100
- top_k: 10
- report_ks: [1, 3, 5, 10]
- labeling: TargetHit@k is 1 if any grade-2 gold chunk_id appears in the top-k results. Recall@k counts all grade-2 labels, while nDCG@k uses grades 0-2. Unpooled labels should not be interpreted as corpus-level Recall.

## Routed retrieval

TargetHit@1: 0.71
TargetHit@3: 0.74
TargetHit@5: 0.75
TargetHit@10: 0.78
Recall@1: 0.685
Recall@3: 0.74
Recall@5: 0.75
Recall@10: 0.78
nDCG@1: 0.71
nDCG@3: 0.7276
nDCG@5: 0.7315
nDCG@10: 0.7415
MRR@10: 0.7297

### Router

exact_set_accuracy: 1.0
collection_precision: 1.0
collection_recall: 1.0

### By query type

cross_collection:
  TargetHit@1: 1.0
  TargetHit@3: 1.0
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  Recall@1: 0.5
  Recall@3: 1.0
  Recall@5: 1.0
  Recall@10: 1.0
  nDCG@1: 1.0
  nDCG@3: 1.0
  nDCG@5: 1.0
  nDCG@10: 1.0
  MRR@10: 1.0
  n: 5
gene_association_wes:
  TargetHit@1: 0.95
  TargetHit@3: 0.975
  TargetHit@5: 0.975
  TargetHit@10: 1.0
  Recall@1: 0.95
  Recall@3: 0.975
  Recall@5: 0.975
  Recall@10: 1.0
  nDCG@1: 0.95
  nDCG@3: 0.9625
  nDCG@5: 0.9625
  nDCG@10: 0.9708
  MRR@10: 0.9619
  n: 40
ldsc_partitioned_heritability:
  TargetHit@1: 0.5789
  TargetHit@3: 0.6316
  TargetHit@5: 0.6579
  TargetHit@10: 0.6842
  Recall@1: 0.5789
  Recall@3: 0.6316
  Recall@5: 0.6579
  Recall@10: 0.6842
  nDCG@1: 0.5789
  nDCG@3: 0.6122
  nDCG@5: 0.6223
  nDCG@10: 0.6306
  MRR@10: 0.6138
  n: 38
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
variant_association_clumped:
  TargetHit@1: 0.8571
  TargetHit@3: 0.8571
  TargetHit@5: 0.8571
  TargetHit@10: 1.0
  Recall@1: 0.8571
  Recall@3: 0.8571
  Recall@5: 0.8571
  Recall@10: 1.0
  nDCG@1: 0.8571
  nDCG@3: 0.8571
  nDCG@5: 0.8571
  nDCG@10: 0.908
  MRR@10: 0.881
  n: 7

## Oracle-collection diagnostic

TargetHit@1: 0.71
TargetHit@3: 0.74
TargetHit@5: 0.75
TargetHit@10: 0.78
Recall@1: 0.685
Recall@3: 0.74
Recall@5: 0.75
Recall@10: 0.78
nDCG@1: 0.71
nDCG@3: 0.7276
nDCG@5: 0.7315
nDCG@10: 0.7415
MRR@10: 0.7297

