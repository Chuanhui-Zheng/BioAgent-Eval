# Dense test evaluation

- queries: 100
- top_k: 10
- report_ks: [1, 3, 5, 10]
- embedding field: content only
- identifier boost: disabled
- labeling: TargetHit@k is 1 if any grade-2 gold chunk_id appears in the top-k results. Recall@k counts all grade-2 labels, while nDCG@k uses grades 0-2. Unpooled labels should not be interpreted as corpus-level Recall.

## Routed retrieval

TargetHit@1: 0.67
TargetHit@3: 0.76
TargetHit@5: 0.8
TargetHit@10: 0.82
Recall@1: 0.635
Recall@3: 0.715
Recall@5: 0.76
Recall@10: 0.78
nDCG@1: 0.67
nDCG@3: 0.688
nDCG@5: 0.707
nDCG@10: 0.7137
MRR@10: 0.7169

### Router

exact_set_accuracy: 0.97
collection_precision: 0.9783
collection_recall: 1.0

### By query type

common_association:
  TargetHit@1: 0.85
  TargetHit@3: 0.9
  TargetHit@5: 0.9
  TargetHit@10: 0.95
  Recall@1: 0.85
  Recall@3: 0.9
  Recall@5: 0.9
  Recall@10: 0.95
  nDCG@1: 0.85
  nDCG@3: 0.875
  nDCG@5: 0.875
  nDCG@10: 0.8908
  MRR@10: 0.8729
  n: 20
cross_collection:
  TargetHit@1: 0.7
  TargetHit@3: 0.9
  TargetHit@5: 0.9
  TargetHit@10: 0.9
  Recall@1: 0.35
  Recall@3: 0.45
  Recall@5: 0.5
  Recall@10: 0.5
  nDCG@1: 0.7
  nDCG@3: 0.4905
  nDCG@5: 0.5169
  nDCG@10: 0.5169
  MRR@10: 0.7667
  n: 10
gene_alias:
  TargetHit@1: 0.6667
  TargetHit@3: 0.8333
  TargetHit@5: 0.8333
  TargetHit@10: 0.8333
  Recall@1: 0.6667
  Recall@3: 0.8333
  Recall@5: 0.8333
  Recall@10: 0.8333
  nDCG@1: 0.6667
  nDCG@3: 0.7718
  nDCG@5: 0.7718
  nDCG@10: 0.7718
  MRR@10: 0.75
  n: 6
gene_function:
  TargetHit@1: 0.8667
  TargetHit@3: 1.0
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  Recall@1: 0.8667
  Recall@3: 1.0
  Recall@5: 1.0
  Recall@10: 1.0
  nDCG@1: 0.8667
  nDCG@3: 0.9421
  nDCG@5: 0.9421
  nDCG@10: 0.9421
  MRR@10: 0.9222
  n: 15
gene_identifier:
  TargetHit@1: 0.5
  TargetHit@3: 0.5
  TargetHit@5: 0.5
  TargetHit@10: 0.5
  Recall@1: 0.5
  Recall@3: 0.5
  Recall@5: 0.5
  Recall@10: 0.5
  nDCG@1: 0.5
  nDCG@3: 0.5
  nDCG@5: 0.5
  nDCG@10: 0.5
  MRR@10: 0.5
  n: 2
gene_location:
  TargetHit@1: 0.5
  TargetHit@3: 0.5
  TargetHit@5: 0.5
  TargetHit@10: 0.5
  Recall@1: 0.5
  Recall@3: 0.5
  Recall@5: 0.5
  Recall@10: 0.5
  nDCG@1: 0.5
  nDCG@3: 0.5
  nDCG@5: 0.5
  nDCG@10: 0.5
  MRR@10: 0.5
  n: 2
ldsc_correlation:
  TargetHit@1: 0.55
  TargetHit@3: 0.65
  TargetHit@5: 0.85
  TargetHit@10: 0.9
  Recall@1: 0.55
  Recall@3: 0.65
  Recall@5: 0.85
  Recall@10: 0.9
  nDCG@1: 0.55
  nDCG@3: 0.6
  nDCG@5: 0.6818
  nDCG@10: 0.6996
  MRR@10: 0.6367
  n: 20
rare_association:
  TargetHit@1: 0.8667
  TargetHit@3: 0.9333
  TargetHit@5: 0.9333
  TargetHit@10: 0.9333
  Recall@1: 0.8667
  Recall@3: 0.9333
  Recall@5: 0.9333
  Recall@10: 0.9333
  nDCG@1: 0.8667
  nDCG@3: 0.9087
  nDCG@5: 0.9087
  nDCG@10: 0.9087
  MRR@10: 0.9
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

TargetHit@1: 0.67
TargetHit@3: 0.76
TargetHit@5: 0.8
TargetHit@10: 0.82
Recall@1: 0.635
Recall@3: 0.715
Recall@5: 0.76
Recall@10: 0.78
nDCG@1: 0.67
nDCG@3: 0.688
nDCG@5: 0.707
nDCG@10: 0.7137
MRR@10: 0.7169

## Comparison with BM25 (same 100 queries, same router)

| metric | BM25 | Dense |
| --- | --- | --- |
| TargetHit@5 | 0.86 | 0.8 |
| TargetHit@10 | 0.87 | 0.82 |
| Recall@10 | 0.87 | 0.78 |
| nDCG@10 | 0.8445 | 0.7137 |
| MRR@10 | 0.835 | 0.7169 |

Dense embeds `content` only and does not pin identifier exact matches. BM25 indexes title+content and can pin exact IDs.
