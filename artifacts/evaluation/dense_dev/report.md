# Dense development evaluation

- queries: 20
- top_k: 10
- report_ks: [5, 10]
- embedding field: content only
- identifier boost: disabled
- labeling: TargetHit@k is 1 if any grade-2 gold chunk_id appears in the top-k results. This is not pooled corpus-level Recall.

## Routed retrieval

TargetHit@5: 0.9
TargetHit@10: 0.9
MRR@10: 0.835

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
  TargetHit@5: 0.5
  TargetHit@10: 0.5
  MRR@10: 0.5
  n: 2
gene_function:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 0.75
  n: 2
gene_identifier:
  TargetHit@5: 0.5
  TargetHit@10: 0.5
  MRR@10: 0.5
  n: 2
ldsc_correlation:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 0.8
  n: 4
rare_association:
  TargetHit@5: 1.0
  TargetHit@10: 1.0
  MRR@10: 1.0
  n: 4

## Oracle-collection diagnostic

TargetHit@5: 0.9
TargetHit@10: 0.9
MRR@10: 0.835

## Comparison with BM25 (same 20 queries, same router)

| metric | BM25 | Dense |
| --- | --- | --- |
| TargetHit@5 | 1.0 | 0.9 |
| TargetHit@10 | 1.0 | 0.9 |
| MRR@10 | 0.975 | 0.835 |

Dense embeds `content` only and does not pin identifier exact matches. BM25 indexes title+content and can pin exact IDs.

Misses on this set: `dev-gene-002` (Ensembl ID `ENSG00000148737`) and `dev-gene-003` (alias `TCF4`/`TCF-4` retrieved `gene:TCF4` instead of gold `gene:TCF7L2`). Routed and oracle scores match because the router was exact.

