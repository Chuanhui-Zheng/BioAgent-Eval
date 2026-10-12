# Raw source data (read-only)

Place client-provided source files here. Do not modify files in this directory.
Record stored client sources in the [client data inventory](../../docs/Client_Sample_Data_Inventory.md). Update `config/paths.yaml` when adding or relocating a source used by the configured pipeline; storage alone does not enable ingestion or indexing.

## Layout (by data type)

- `gene_info/genes_function_info.json` — gene function and annotation (T2D Knowledge Portal)
- `reference/gene_id_map/genes.jsonl` — gene symbol / Ensembl ↔ genomic coordinates (HuGE export)
- `ldsc/genetic_correlation/2hrI/2hrI.json` — LDSC genetic correlation (anchor phenotype 2hrI)
- `gene_association/common/2hrG/2hrG.common.jsonl` — common-variant gene–phenotype evidence for 2hrG (HuGE)
- `gene_association/rare/2hrG/2hrG.rare.jsonl` — rare-variant gene-level association for 2hrG (HuGE)

HuGE refers to the T2D Portal export module; paths here are organized by analysis type, not portal folder names.

## Additional stored client sources

The following originals are stored for reference or future ingestion design. None is currently configured for chunk generation or retrieval indexing; detailed checks, uncertainties and scope decisions are in the client data inventory.

| Directory | Contents / use |
|---|---|
| `gtx_tissue_expression/` | GTEx RNA and protein tissue-expression tables; directory spelling retained intentionally |
| `gwas_genengine/EU/` | 2hrFFA variant-level GWAS summary statistics; structured-query candidate |
| `reference/topmed_burdenbinning/` | TOPMed variant annotations and burden-bin assignments |
| `reference/cs2g_1000geur/` | cS2G SNP-to-gene score mappings |
| `reference/nearest_genes/` | Variant-to-nearest-gene mapping |
| `ldsc/partitioned_heritability/2hrG/` | Partitioned-heritability results; separate from genetic correlation |
| `metaanalysis/bottom-line/` | Clumped regional results and compressed ancestry-specific variant statistics |
| `wes/2hrG/` | Gene-level association results with mask detail; overlaps existing rare evidence |

Retain original filenames and compressed formats. Raw storage is not evidence-ingestion completion. Results examples and V001 application materials remain deferred according to the inventory; they are not added to this pipeline.

Pipeline outputs are written to `artifacts/`.
