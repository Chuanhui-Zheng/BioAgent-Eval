# Dense test evaluation

- queries: 50
- top_k: 10
- report_ks: [1, 3, 5, 10]
- embedding field: content only
- identifier boost: disabled
- labeling: TargetHit@k is 1 if any grade-2 gold chunk_id appears in the top-k results. Recall@k counts all grade-2 labels, while nDCG@k uses grades 0-2. Unpooled labels should not be interpreted as corpus-level Recall.

## Routed retrieval

TargetHit@1: 0.54
TargetHit@3: 0.68
TargetHit@5: 0.8
TargetHit@10: 0.92
Recall@1: 0.2533
Recall@3: 0.4533
Recall@5: 0.5817
Recall@10: 0.765
nDCG@1: 0.54
nDCG@3: 0.4691
nDCG@5: 0.5349
nDCG@10: 0.6092
MRR@10: 0.6475

### Router

exact_set_accuracy: 1.0
collection_precision: 1.0
collection_recall: 1.0

### By query type

comparison_clumped:
  TargetHit@1: 1.0
  TargetHit@3: 1.0
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  Recall@1: 0.4583
  Recall@3: 1.0
  Recall@5: 1.0
  Recall@10: 1.0
  nDCG@1: 1.0
  nDCG@3: 1.0
  nDCG@5: 1.0
  nDCG@10: 1.0
  MRR@10: 1.0
  n: 4
comparison_partitioned:
  TargetHit@1: 0.5667
  TargetHit@3: 0.6667
  TargetHit@5: 0.7667
  TargetHit@10: 0.9333
  Recall@1: 0.2667
  Recall@3: 0.45
  Recall@5: 0.5694
  Recall@10: 0.725
  nDCG@1: 0.5667
  nDCG@3: 0.474
  nDCG@5: 0.5365
  nDCG@10: 0.6021
  MRR@10: 0.6597
  n: 30
comparison_wes:
  TargetHit@1: 0.375
  TargetHit@3: 0.625
  TargetHit@5: 0.8125
  TargetHit@10: 0.875
  Recall@1: 0.1771
  Recall@3: 0.3229
  Recall@5: 0.5
  Recall@10: 0.7812
  nDCG@1: 0.375
  nDCG@3: 0.3273
  nDCG@5: 0.4157
  nDCG@10: 0.5248
  MRR@10: 0.5365
  n: 16

## Oracle-collection diagnostic

TargetHit@1: 0.54
TargetHit@3: 0.68
TargetHit@5: 0.8
TargetHit@10: 0.92
Recall@1: 0.2533
Recall@3: 0.4533
Recall@5: 0.5817
Recall@10: 0.765
nDCG@1: 0.54
nDCG@3: 0.4691
nDCG@5: 0.5349
nDCG@10: 0.6092
MRR@10: 0.6475

