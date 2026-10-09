# Hybrid RRF development evaluation

- queries: 25
- top_k: 10
- report_ks: [1, 3, 5, 10]
- candidate_k: 50
- rrf_k: 60
- weight_bm25: 1.0
- weight_dense: 1.0
- fusion: existing BM25 (title+content, identifier pin) + dense (content only); no new index
- labeling: TargetHit@k is 1 if any grade-2 gold chunk_id appears in the top-k results. Recall@k counts all grade-2 labels, while nDCG@k uses grades 0-2. Unpooled labels should not be interpreted as corpus-level Recall.

## Routed retrieval

TargetHit@1: 0.92
TargetHit@3: 1.0
TargetHit@5: 1.0
TargetHit@10: 1.0
Recall@1: 0.92
Recall@3: 1.0
Recall@5: 1.0
Recall@10: 1.0
nDCG@1: 0.92
nDCG@3: 0.9705
nDCG@5: 0.9705
nDCG@10: 0.9705
MRR@10: 0.96

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
  TargetHit@1: 0.8333
  TargetHit@3: 1.0
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  Recall@1: 0.8333
  Recall@3: 1.0
  Recall@5: 1.0
  Recall@10: 1.0
  nDCG@1: 0.8333
  nDCG@3: 0.9385
  nDCG@5: 0.9385
  nDCG@10: 0.9385
  MRR@10: 0.9167
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

TargetHit@1: 0.92
TargetHit@3: 1.0
TargetHit@5: 1.0
TargetHit@10: 1.0
Recall@1: 0.92
Recall@3: 1.0
Recall@5: 1.0
Recall@10: 1.0
nDCG@1: 0.92
nDCG@3: 0.9705
nDCG@5: 0.9705
nDCG@10: 0.9705
MRR@10: 0.96

## Comparison (same 25 queries, same router)

| metric | BM25 | Dense | Hybrid |
| --- | --- | --- | --- |
| TargetHit@5 | 1.0 | 0.84 | 1.0 |
| TargetHit@10 | 1.0 | 0.92 | 1.0 |
| Recall@10 | 1.0 | 0.92 | 1.0 |
| nDCG@10 | 1.0 | 0.6917 | 0.9705 |
| MRR@10 | 1.0 | 0.6198 | 0.96 |

## Offline RRF grid (candidates retrieved once)

- weight_bm25: 1.0
  weight_dense: 1.0
  rrf_k: 60
  candidate_k: 50
  routed:
    TargetHit@1: 0.92
    TargetHit@3: 1.0
    TargetHit@5: 1.0
    TargetHit@10: 1.0
    Recall@1: 0.92
    Recall@3: 1.0
    Recall@5: 1.0
    Recall@10: 1.0
    nDCG@1: 0.92
    nDCG@3: 0.9705
    nDCG@5: 0.9705
    nDCG@10: 0.9705
    MRR@10: 0.96
- weight_bm25: 1.2
  weight_dense: 0.8
  rrf_k: 60
  candidate_k: 50
  routed:
    TargetHit@1: 0.92
    TargetHit@3: 1.0
    TargetHit@5: 1.0
    TargetHit@10: 1.0
    Recall@1: 0.92
    Recall@3: 1.0
    Recall@5: 1.0
    Recall@10: 1.0
    nDCG@1: 0.92
    nDCG@3: 0.9705
    nDCG@5: 0.9705
    nDCG@10: 0.9705
    MRR@10: 0.96
- weight_bm25: 0.8
  weight_dense: 1.2
  rrf_k: 60
  candidate_k: 50
  routed:
    TargetHit@1: 0.88
    TargetHit@3: 0.96
    TargetHit@5: 1.0
    TargetHit@10: 1.0
    Recall@1: 0.88
    Recall@3: 0.96
    Recall@5: 1.0
    Recall@10: 1.0
    nDCG@1: 0.88
    nDCG@3: 0.9305
    nDCG@5: 0.9459
    nDCG@10: 0.9459
    MRR@10: 0.928

Grid results are diagnostic only; YAML defaults are not auto-updated.
