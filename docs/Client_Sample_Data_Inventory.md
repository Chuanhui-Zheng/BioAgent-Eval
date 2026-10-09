# Client Sample Data Inventory

The trees retain the client delivery layout; Status records actual repository raw locations. Stored files are not automatically chunked or indexed. The unpacked T2D TSV and preview are omitted; its compressed source remains listed.

Labels: ✅ EXISTING = included in the current corpus and indexes; 🟡 PENDING = candidate evidence, not yet indexed; 📊 Structured query = prioritize exact lookup/filtering, query interface not yet implemented; 📎 Supporting material = reference only; 🌐 Application & integration = app/integration work; 📖 Glossary = vocabulary; ⬜ No data = empty/temporary files.

## Client directory trees

```text
Sample_Data-20260929T151459Z-1-001/
└── Sample_Data/
    ├── burdenbinning/
    │   └── gene/
    │       └── TOPMed/
    │           ├── part-00002-22364f34-a15a-4bb8-aae1-2390d54e9c5c-c000.json  [📊 Structured query]
    │           │       Description: A JSONL shard containing 16,593 variant annotation records. Each record identifies a variant, its gene/transcript, functional consequences, prediction values, frequency fields and assigned burden bin. These are annotation and grouping records, not phenotype association-test results.
    │           │       Status: Stored in repository data/raw/reference/topmed_burdenbinning/ as structured reference data; Not configured for chunking or retrieval indexing; not yet registered in the generated manifest. Dataset coverage, genome build, prediction versions/codes, frequency population, bin rules and linkage to WES inputs remain unconfirmed.
    │           └── part-00107-22364f34-a15a-4bb8-aae1-2390d54e9c5c-c000.json  [📊 Structured query]
    │                   Description: A JSONL shard containing 18,981 variant annotation records. Each record identifies a variant, its gene/transcript, functional consequences, prediction values, frequency fields and assigned burden bin. These are annotation and grouping records, not phenotype association-test results.
    │                   Status: Stored in repository data/raw/reference/topmed_burdenbinning/ as structured reference data; Not configured for chunking or retrieval indexing; not yet registered in the generated manifest. Dataset coverage, genome build, prediction versions/codes, frequency population, bin rules and linkage to WES inputs remain unconfirmed.
    ├── cS2G/
    │   └── cS2G_1000GEUR/
    │       ├── cS2G.1.SGscore.gz  [📊 Structured query]
    │       │       Description: A gzip-compressed TSV named for chromosome 1, containing 229,378 SNP-to-gene linking records. SNP is an rsID, GENE is a gene symbol, cS2G is the combined linking score, and INFO records individual functional-strategy scores. One SNP may link to multiple genes; these are mapping scores, not disease-association test results.
    │       │       Status: Stored in repository data/raw/reference/cs2g_1000geur/ as structured reference mapping; not configured for chunking or RAG indexing. Exact source release and rsID-to-coordinate mapping remain unconfirmed; preserve all SNP-gene links. Only files named for chromosomes 1, 10 and 2 were supplied; genome-wide coverage is incomplete.
    │       ├── cS2G.10.SGscore.gz  [📊 Structured query]
    │       │       Description: A gzip-compressed TSV named for chromosome 10, containing 119,843 SNP-to-gene linking records. SNP is an rsID, GENE is a gene symbol, cS2G is the combined linking score, and INFO records individual functional-strategy scores. One SNP may link to multiple genes; these are mapping scores, not disease-association test results.
    │       │       Status: Stored in repository data/raw/reference/cs2g_1000geur/ as structured reference mapping; not configured for chunking or RAG indexing. Exact source release and rsID-to-coordinate mapping remain unconfirmed; preserve all SNP-gene links. Only files named for chromosomes 1, 10 and 2 were supplied; genome-wide coverage is incomplete.
    │       └── cS2G.2.SGscore.gz  [📊 Structured query]
    │               Description: A gzip-compressed TSV named for chromosome 2, containing 183,721 SNP-to-gene linking records. SNP is an rsID, GENE is a gene symbol, cS2G is the combined linking score, and INFO records individual functional-strategy scores. One SNP may link to multiple genes; these are mapping scores, not disease-association test results.
    │               Status: Stored in repository data/raw/reference/cs2g_1000geur/ as structured reference mapping; not configured for chunking or RAG indexing. Exact source release and rsID-to-coordinate mapping remain unconfirmed; preserve all SNP-gene links. Only files named for chromosomes 1, 10 and 2 were supplied; genome-wide coverage is incomplete.
    ├── Gene_Info/
    │   └── genes_function_info.json  [✅ EXISTING]
    │           RAG: Included in gene_info: 24,825 one-gene chunks, represented in the current BM25 and Dense mappings; ACTR1B function lookup checked in BM25, Dense and Hybrid.
    │           Description: A JSON object containing 24,825 gene annotation records from the stated T2D Knowledge Portal source. Each gene may include a function summary, aliases, genomic location/build, database identifiers and extraction metadata. This is a gene reference, not a gene-disease association-test table.
    │           Status: Already stored at data/raw/gene_info/genes_function_info.json and included in the baseline RAG corpus. No duplicate import or rebuild is needed for this file.
    ├── GTX_Tissue_Expression/
    │   ├── ALL_GENES_GTEx_Proteomics.csv  [📊 Structured query]
    │   │       RAG: Not indexed; prioritize structured gene-tissue lookup. Query interface not yet implemented.
    │   │       Description: Protein-expression observations across 32 tissues for 11,094 genes (1,479,446 rows). Each row contains gene, tissue, value and tissue_specificity. A gene-tissue pair may have 1-13 observations; no sample identifier is supplied. These are expression records, not gene-disease association results.
    │   │       Status: Stored at data/raw/gtx_tissue_expression/; not configured for chunking or RAG indexing. Prioritize structured gene-tissue lookup; query interface not yet implemented. measurement scale/transformation, observation identity, tissue_specificity calculation and source release remain unconfirmed. Do not deduplicate, average or embed each observation before resolving their meaning.
    │   └── ALL_GENES_GTEx_RNAseq.csv  [📊 Structured query]
    │           RAG: Not indexed; prioritize structured gene-tissue lookup. Query interface not yet implemented.
    │           Description: RNA-expression summary statistics for 16,613 genes across 54 tissues (132,904 rows). Each gene has count, mean, std, min, 25%, 50%, 75% and max rows. The first column named tissue actually identifies the statistic; tissue names are the measurement columns. These are expression summaries, not eight independent gene records.
    │           Status: Stored at data/raw/gtx_tissue_expression/; not configured for chunking or RAG indexing. Prioritize structured gene-tissue summary lookup; query interface not yet implemented. Future RAG summaries require a separate ingestion decision. Expression units/normalization, count definition and source release remain unconfirmed; do not label the values TPM or infer disease association from expression. Define query coverage and field semantics before implementing lookup or any future indexing.
    ├── GWAS_GenEngine/
    │   └── EU/
    │       └── 2hrFFA.sumstats.tsv.gz  [📊 Structured query]
    │               Description: A gzip-compressed TSV containing 448,162 variant-level GWAS association records for 2-hour free fatty acids (OGTT; phenotype 2hrFFA). Columns contain variant coordinates/alleles, beta, stdErr, pValue and n; all recorded n values are 9565. These are variant-trait association statistics, not gene-level results or SNP-to-gene mappings.
    │               Status: Stored at data/raw/gwas_genengine/EU/2hrFFA.sumstats.tsv.gz as structured association data; not configured for chunking or RAG indexing. Intended for exact variant/region queries rather than per-row embedding. Genome build, beta units/effect allele, n definition, source release and full-study coverage remain unconfirmed.
    ├── Huge/
    │   ├── common/
    │   │   ├── 2hrG/
    │   │   │   └── part-00000-dd32156d-ef29-4ed2-9d4b-7187bc0b569c-c000.json  [✅ EXISTING]
    │   │   │           Description: 11,383 gene-level common-variant association records for 2hrG (two-hour glucose), with gene/locus identifiers, bf_common and optional variant annotations. Baseline records are not necessarily positive association evidence.
    │   │   │           Status: Already stored at data/raw/gene_association/common/2hrG/2hrG.common.jsonl and included in the baseline RAG corpus. No duplicate import or rebuild is needed for this file.
    │   │   └── T2D/  [EMPTY DIRECTORY]
    │   ├── geneidmap/
    │   │   └── genes/
    │   │       └── part-00000-6ba5dfbf-6dd4-4fb8-b481-e1589c93e4f1-c000.json  [📊 Structured query]
    │   │               Description: 10,422 gene lookup records: symbol, ensembl, chromosome, start and end. Supports gene-ID and locus lookup; contains no phenotype association results.
    │   │               Status: Already stored at data/raw/reference/gene_id_map/genes.jsonl and recorded in the manifest as reference-only. The existing design creates no chunks or embeddings for this source; no duplicate import is needed.
    │   ├── nearest genes/
    │   │   └── Copy of part-00000-6b1f9194-a149-4e7d-ab11-3fb9c60755f6-c000.json  [📊 Structured query]
    │   │           Description: 324,437 unique variant-to-nearest-gene mappings. Fields: varId (coordinate-style variant ID) and nearestGene (Ensembl gene ID); 40,921 distinct gene IDs. Supports exact variant lookup, not disease association testing.
    │   │           Status: Stored in repository data/raw/reference/nearest_genes/ as structured reference data. Not configured for chunking or retrieval indexing. Genome build, annotation version and nearest-gene selection rule remain unconfirmed; existing gene_id_map covers only part of these IDs. Proximity is not causal evidence.
    │   └── rare/
    │       ├── 2hrG/
    │       │   └── part-00000-07e2fb6f-3814-4ac6-93a3-d14d5813d6d5-c000.json  [✅ EXISTING]
    │       │           Description: 4,114 gene-level rare-variant association records for 2hrG, with pValue, beta, z, stdErr, v and bf_rare; existing gene_association_rare evidence.
    │       │           Status: Already stored at data/raw/gene_association/rare/2hrG/2hrG.rare.jsonl and included in the baseline RAG corpus. No duplicate import or rebuild is needed for this file. Includes an existing quoted NaN gene identifier; overlapping WES top-level results are not independent evidence.
    │       └── T2D/  [EMPTY DIRECTORY]
    ├── ldsc/
    │   ├── genetic_correlation/
    │   │   ├── 2hrG/
    │   │   │   └── 2hrG.json  [⬜ No data]
    │   │   │           Description: Zero-byte file; no genetic-correlation records supplied.
    │   │   │           Status: No ingestion.
    │   │   ├── 2hrI/
    │   │   │   └── 2hrI.json  [✅ EXISTING]
    │   │   │           Description: 1,646 genetic-correlation results between 2hrI (two-hour insulin) and 781 other phenotypes, stratified by EU, HS and Mixed ancestry. Measures shared genetic architecture, not causality.
    │   │   │           Status: Already stored at data/raw/ldsc/genetic_correlation/2hrI/2hrI.json and included as 781 pair-level chunks in the baseline RAG corpus. No duplicate import is needed. New glossary labels have not been propagated to existing chunks/indexes.
    │   │   └── T2D/  [EMPTY DIRECTORY]
    │   └── partitioned_heritability/
    │       ├── 2hrG/
    │       │   ├── 2hrG.json  [✅ EXISTING]
    │       │   │       Description: 7,924 partitioned-heritability results for 2hrG (two-hour glucose): 1,981 annotation/tissue/biosample units, each with EA, EU, HS and Mixed strata. Contains SNPs, h2, enrichment, coefficient, diff estimates and standard errors, plus pValue; not trait-pair genetic correlation.
    │       │   │       Status: 7,924 chunks validated (265–294 tokens) at artifacts/chunks/ldsc_partitioned_2hrG.chunks.jsonl; readable IDs and routing prepared. Expanded corpus now has seven collections (142,977 total). Included in the current 142,977-record BM25 and Dense indexes; loading and queries verified. New index release not yet published. Scientific field definitions and source release remain unconfirmed. Separate from genetic_correlation.
    │       │   └── _SUCCESS  [⬜ No data]
    │       │           Description: Empty pipeline completion marker.
    │       │           Status: No scientific evidence to ingest.
    │       └── T2D/  [EMPTY DIRECTORY]
    ├── metaanalysis/
    │   └── bottom-line/
    │       ├── ancestry-clumped/
    │       │   ├── 2hrG/
    │       │   │   └── ancestry=EU/
    │       │   │       ├── _SUCCESS  [⬜ No data]
    │       │   │       │       Description: Empty pipeline completion marker.
    │       │   │       │       Status: No scientific evidence to ingest.
    │       │   │       └── part-00000-ddaf2613-61d9-48db-b24e-3c0a67a82ad8-c000.json  [✅ EXISTING]
    │       │   │               Description: 68 common-variant association records for 2hrG, supplied under ancestry=EU, grouped into 7 chromosome-clump regions. Each group has one leadSNP with the lowest supplied pValue, plus member variants, bounds, effect estimates and pipeline-selection fields. Lead status is not causal proof.
    │       │   │               Status: Stored in repository data/raw/metaanalysis/bottom-line/ancestry-clumped/2hrG/ancestry=EU/. Seven regional chunks validated (313-322 tokens) at artifacts/chunks/metaanalysis_clumped_2hrG_EU.chunks.jsonl; all 68 original members retained in metadata. Included in the current seven-collection BM25 and Dense indexes (142,977 total); loading and queries verified. New index release not yet published. Non-lead member IDs/statistics are not indexed. Genome build, clumping rules/reference panel, effect scale/allele, n, alignment and meta-selection definitions remain unconfirmed; clump ID is not a cross-source global identifier.
    │       │   └── T2D/  [EMPTY DIRECTORY]
    │       └── ancestry-specific/
    │           └── 2hrG/
    │               └── ancestry=EU/
    │                   └── part-00000-72dc06b7-0335-4bcb-9163-2a462300a726-c000.json.zst  [📊 Structured query]
    │                           Review: Streaming decompression of the first 1,000 records only; not a full-file audit.
    │                           Description: Zstandard-compressed JSONL containing variant-level 2hrG association statistics, supplied under ancestry=EU. Fields: varId, chromosome, position, reference, alt, phenotype, pValue, beta, stdErr and n. No gene, clump or leadSNP fields in the inspected sample.
    │                           Status: Stored in repository data/raw/metaanalysis/bottom-line/ancestry-specific/2hrG/ancestry=EU/. Not configured for chunking or retrieval indexing. Retain the compressed original for structured variant/region queries; avoid per-row embedding. Full-file quality/coverage, genome build, effect scale/allele, n, release and its exact relationship to the clumped file remain unconfirmed.
    ├── Results/
    │   ├── chr1/
    │   │   └── ACAP3/
    │   │       └── N_snps_1000/
    │   │           ├── BIC_Convergence.png  [📎 Supporting material]
    │   │           │       Description: BIC plotted against number of clusters (1-9); a model-comparison diagnostic, not an iteration trace or gene-trait evidence table.
    │   │           │       Status: Retained as client model-result reference material; no corpus ingestion or indexing planned at this stage.
    │   │           ├── GENE.csv  [📎 Supporting material]
    │   │           │       Description: 34 ACAP3-trait model-result rows, all cluster=0, with beta_g, StdErr, Zscore, cluster summaries, Log_pvalue, WES comparator fields and cpu_time. WES fields are absent for 19 traits (57 empty cells).
    │   │           │       Status: Retained as client model-result reference material; no corpus ingestion or indexing planned at this stage.
    │   │           ├── Gene_N_snps_15_cl_0.csv  [📎 Supporting material]
    │   │           │       Description: 34 ACAP3-trait model-result rows, all cluster=0. All nine shared columns match GENE.csv after joining by Trait; mean_cluster also matches GENE.csv mean_bg. No WES comparator or cpu_time columns.
    │   │           │       Status: Retained as client model-result reference material; no corpus ingestion or indexing planned at this stage.
    │   │           ├── likelihood_Convergence.png  [📎 Supporting material]
    │   │           │       Description: Log-likelihood plotted against iteration (0-12); visual optimization diagnostic.
    │   │           │       Status: Retained as client model-result reference material; no corpus ingestion or indexing planned at this stage.
    │   │           ├── raw_N_snps_15_cl_0.csv  [📎 Supporting material]
    │   │           │       Description: 510 trait-SNP model-detail rows: 34 traits x the same 15 rsIDs, all cluster=0. Contains observed/fitted/scaled beta-related fields, psi, PIP, StdErr, N and pval. Position, standard_beta_hat, beta_hat and pval are jointly absent in 196 rows (784 empty cells).
    │   │           │       Status: Retained as client model-result reference material; no corpus ingestion or indexing planned at this stage.
    │   │           └── RMSE_Err.png  [📎 Supporting material]
    │   │                   Description: RMSE of BG plotted against iteration (1-8); visual fitting diagnostic, not a retrieval benchmark.
    │   │                   Status: Retained as client model-result reference material; no corpus ingestion or indexing planned at this stage.
    │   ├── chr10/  [EMPTY DIRECTORY]
    │   └── chr3/  [EMPTY DIRECTORY]
    ├── Software Dev/
    │   ├── 18-12-2025 meeting voice recoding/
    │   │   ├── Voice 251218_153807.m4a  [📎 Supporting material]
    │   │   │       Review: Filename/metadata only.
    │   │   │       Description: Client meeting audio; not transcribed.
    │   │   │       Status: Contents unconfirmed; inspect only for a concrete unresolved requirement.
    │   │   ├── Voice 251218_160639.m4a  [📎 Supporting material]
    │   │   │       Review: Filename/metadata only.
    │   │   │       Description: Client meeting audio; not transcribed.
    │   │   │       Status: Contents unconfirmed; inspect only for a concrete unresolved requirement.
    │   │   └── Voice 251218_165957.m4a  [📎 Supporting material]
    │   │           Review: Filename/metadata only.
    │   │           Description: Client meeting audio; not transcribed.
    │   │           Status: Contents unconfirmed; inspect only for a concrete unresolved requirement.
    │   └── development/
    │       ├── 01.data_exploration.xlsx  [🌐 Application & integration]
    │       │       Review: Workbook field-reference review.
    │       │       Description: Frontend/backend development reference listing client module data fields; supports data handoff and schema cross-checks.
    │       │       Status: Web integration reference, not scientific corpus input. Consult only for relevant data handoff requirements; field names/types do not establish scientific meanings or approved APIs.
    │       └── 02.database_design.xlsx  [🌐 Application & integration]
    │               Review: Workbook field-reference review.
    │               Description: Frontend/backend database-design reference: draft tables, columns, types, ranges and nullable constraints.
    │               Status: Web/backend database reference, not scientific corpus input. Business database implementation is not added to the data/retrieval scope by this file; draft constraints remain unconfirmed.
    ├── WES/
    │   ├── 2hrG/
    │   │   ├── _SUCCESS  [⬜ No data]
    │   │   │       Description: Empty pipeline completion marker.
    │   │   │       Status: No scientific evidence to ingest.
    │   │   └── part-00000.json  [✅ EXISTING]
    │   │           Description: JSONL with 15,361 source rows (15,360 valid gene identifiers; one bare NaN gene at source line 1,845) and 78,583 mask-level association results for 2hrG, with source labelled AMP T2D-GENES. Each gene has top-level pValue/beta and a nested masks list; seven mask names occur, and 935 rows have empty mask lists (934 valid genes plus the invalid-gene row). Contains association results, not raw exome reads or per-variant genotypes.
    │   │           Status: Stored in repository data/raw/wes/2hrG/part-00000.json and included in the current corpus and indexes. 93,943 WES chunks validated at artifacts/chunks/wes_2hrG.chunks.jsonl: 15,360 gene summaries plus 78,583 mask results, all content 132-245 tokens. All 4,113 matching rare summaries retained with provenance links. Invalid gene row 1,845 quarantined in validation report; raw unchanged. Included in the current seven-collection BM25 and Dense indexes (142,977 total); loading and queries verified. New index release not yet published. The invalid-gene row is excluded from chunks and retained in the validation report; raw is unchanged. Mask rules, n/cohort, combinedAF/count definitions, effect scale, top-level aggregation and release remain unconfirmed. Existing rare results overlap for 4,113 genes; preserve provenance and avoid duplicate evidence.
    │   └── T2D/  [EMPTY DIRECTORY]
    ├── Copy of Web App Detail Deployment.docx  [🌐 Application & integration]
    │       Review: Document body reviewed; embedded screenshots not checked.
    │       Description: Client workflows, input/output dependencies and plotting requirements.
    │       Status: Shared reference: Web implements page flows and plots; data work supplies validated inputs/query outputs. Exact ownership is unconfirmed; plots alone do not require RAG ingestion.
    ├── Page4_web_genovah.mov  [🌐 Application & integration]
    │       Review: Filename/metadata only.
    │       Description: Client demo/screen recording; not watched.
    │       Status: No full media processing; targeted review only if needed.
    ├── Phenotypes_group.xlsx  [📖 Glossary]
    │       RAG: Auxiliary vocabulary updated; used when building the three new collections. The original four chunk files retain their earlier text. Not a standalone evidence collection.
    │       Review: Exact matching + glossary validation.
    │       Description: 769 new Portal labels plus 11 retained definitions/categories; 780 of 782 corpus codes covered. Added mappings retain source group/dichotomous in provenance.
    │       Status: SerumUrea/Testosterone unresolved. Full 1,603-code Portal dictionary not imported; Trangs aliases not enabled. Baseline chunks were not regenerated with the expanded glossary; current indexes contain those preserved baseline chunks plus the three new collections.
    ├── Screen Recording 2025-11-23 at 6.43.04 PM.mov  [🌐 Application & integration]
    │       Review: Filename/metadata only.
    │       Description: Client demo/screen recording; not watched.
    │       Status: No full media processing; targeted review only if needed.
    ├── Updated_Web_layout.png  [🌐 Application & integration]
    │       Review: Filename/metadata only.
    │       Description: Web page layout and visual interface reference.
    │       Status: Web work: page layout and visual interface reference; not scientific evidence for RAG.
    ├── Updated_Web_layout.vsdx  [🌐 Application & integration]
    │       Review: Filename/metadata only.
    │       Description: Web page layout and visual interface reference.
    │       Status: Web work: page layout and visual interface reference; not scientific evidence for RAG.
    ├── V001-20260826T154019Z-1-001.zip  [🌐 Application & integration]
    │       Review: Member listing + bounded reads.
    │       Description: Application/Demo package containing 11 files: scripts, notebook, analysis references and input/result tables.
    │       Status: Assigned to application & integration work for current scope tracking; deferred from current data/corpus/index work. User-extracted copy is available at V001-20260826T154019Z-1-001/V001/. No raw import, further analysis or indexing planned at this stage.
    └── WebAppLayout.png  [🌐 Application & integration]
            Review: Filename/metadata only.
            Description: Web page layout and visual interface reference.
            Status: Web work: page layout and visual interface reference; not scientific evidence for RAG.

Sample_Data-20260929T151459Z-1-002/
└── Sample_Data/
    └── GWAS_GenEngine/
        └── EU/
            └── T2D.sumstats.tsv.gz  [📊 Structured query]
                    Review: Same-source relationship confirmed by user.
                    Description: Compressed counterpart of extracted TSV.
                    Status: Import one representation only; latest review did not independently decompress/compare both files.

```
