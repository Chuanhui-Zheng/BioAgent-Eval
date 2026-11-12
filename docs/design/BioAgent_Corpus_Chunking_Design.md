# BioAgent-Eval Corpus Chunking Design

**Project:** BioAgent-Eval: An Evidence-Grounded Scientific Agent Harness and Automated Evaluation Platform for Drug Discovery  
**Document version:** v1.2

**Date:** 2026-09-16  
**Last updated:** 2026-10-10
**Scope:** Structured JSON corpora under `data/raw/` (Gene Info, LDSC genetic correlation and partitioned heritability, HuGE Gene Association, clumped variant regions and WES; reference `gene_id_map` is not chunked)

---

## 1. Purpose

This document defines how the BioAgent-Eval scientific RAG foundation **splits, textifies, annotates with metadata, cites, and routes** multiple JSON source types in the current sample corpus. Goals:

1. Support **entity-aware retrieval** (gene, phenotype/trait)
2. Ensure **citations trace back to a specific source and version**
3. Avoid semantic breakage from fixed token-window splits on structured records
4. Provide a single specification for the ingestion pipeline, embedding, and evaluation benchmarks

---

## 2. Data Sources Overview

### 2.1 Baseline File Inventory

| File path | Format | Entity type | Scale (measured) |
|-----------|--------|-------------|------------------|
| `data/raw/gene_info/genes_function_info.json` | Single JSON object | Gene | **24,825** gene records |
| `data/raw/ldsc/genetic_correlation/2hrI/2hrI.json` | JSONL | Phenotype pair (genetic correlation) | **1,646** rows → **781** unique pairs |
| `data/raw/reference/gene_id_map/genes.jsonl` | JSONL | Gene locus lookup | **10,422** rows (**not chunked**) |
| `data/raw/gene_association/common/2hrG/2hrG.common.jsonl` | JSONL | Gene × phenotype (common) | **11,383** rows |
| `data/raw/gene_association/rare/2hrG/2hrG.rare.jsonl` | JSONL | Gene × phenotype (rare) | **4,114** rows |

> Baseline LDSC genetic correlation uses anchor `2hrI`; HuGE gene association uses `2hrG`. The added partitioned, clumped and WES sources use `2hrG`. Indexing and citations must use the source `phenotype` field value.

The active seven-collection corpus adds 7,924 partitioned-heritability chunks, seven clumped-region chunks and 93,943 WES summary/mask chunks to the 41,103-record baseline, giving 142,977 total. Their source paths, evidence units and validation rules are specified in Sections 5.14-5.16.

### 2.2 Semantic Layers

These corpora belong to the same domain (T2D Knowledge Portal / metabolic genetics) but describe different layers:

```
Gene Info                 →  Molecular entity layer (function, coordinates, standard IDs)
LDSC rg results           →  Population genetics layer (shared genetic architecture between traits)
HuGE gene association     →  Population genetics layer (gene–phenotype GWAS / rare-variant evidence)
reference/gene_id_map     →  Pipeline reference table (not indexed in RAG)
```

**There is no single join key for merged chunks.** Link evidence after retrieval via `gene` symbol / `ensembl`. **Do not** put gene annotation and association statistics in the same chunk.

### 2.3 Mapping to BioAgent-Eval Requirements

| Project requirement | This design |
|---------------------|-------------|
| Entity-aware retrieval (gene, phenotype/disease) | Separate collections + entity metadata |
| Comparison questions | LDSC pair-level chunks |
| Traceable citations | Unified `citation` block + `chunk_id` |
| Abstention / qualification | `data_quality`, `is_significant`, etc. in metadata |
| Reproducible pipeline | Deterministic chunk rules, no random overlap |

---

## 3. Design Principles

### 3.1 Semantic Units, Not Token Windows

Sample records are structured, short, and self-contained. **Do not** split whole files with fixed 512/1024 token sliding windows.

| Source | Chunk unit |
|--------|------------|
| Gene Info | 1 gene = 1 chunk |
| LDSC | 1 `(phenotype, other_phenotype)` pair = 1 chunk (merge ancestries) |
| Gene association common | 1 JSONL row = 1 chunk (1 gene × anchor phenotype) |
| Gene association rare | 1 JSONL row = 1 chunk |
| `gene_id_map` | **Not chunked** |

### 3.2 Embeddable Text vs Filterable Metadata

* **`content` (embeddable text):** Natural language, synonyms, readable phenotype names—for dense retrieval
* **`metadata` (structured fields):** Gene symbol, phenotype code, ancestry, p-values—for exact match / hybrid filter / rerank
* Raw JSON must not be embedded directly

### 3.3 Citation Granularity = Chunk Granularity

Each chunk must answer one question independently and be citable on its own.  
Citations point to: **source file + `chunk_id` + (if applicable) ancestry sub-record**.

### 3.4 Explicit Evidence Boundaries

LDSC results are **population-level genetics**, not individual lab values or causal claims. Chunk text and metadata must include interpretation guardrails for the generation stage.

### 3.5 Separate Collections, Unified Schema

Collections share the same chunk envelope schema for API, evaluation harness, and future GenEngine integration. (From v1.1: **four embed collections** + one reference source.)

---

## 4. Collection A: Gene Info

### 4.1 Source Structure

Top-level source file shape:

```json
{
  "source_base_url": "https://t2d.hugeamp.org/gene.html",
  "genes": {
    "TCF7L2": {
      "gene": "TCF7L2",
      "function_summary": "...",
      "info": {
        "alternative_names": ["TCF-4", "TCF4"],
        "coding_sequence": "10:114710009-114927437",
        "length_bp": 217429,
        "assembly": "GRCh37",
        "gene_sources": ["Ensembl", "HGNC", "NCBI Gene"],
        "ensembl_gene_id": "ENSG00000148737",
        "hgnc_id": "11641",
        "entrezgene": "6934"
      },
      "extracted_at_unix": 1767895499,
      "uniprot_accession": "Q9NQB0"
    }
  }
}
```

### 4.2 Data Quality Tiers (measured)

| Category | Count | Notes |
|----------|-------|-------|
| Has `function_summary` | 14,583 | Usual functional annotation; preferred for QA |
| `function_summary = null`, no error | 2,711 | IDs/coordinates only; missing function text |
| Has `error` field | 7,531 | e.g. miRNA not found in MyGene.info |

### 4.3 Chunk Rules

**Rule G-1:** Each `genes.<symbol>` entry produces exactly one chunk.  
**Rule G-2:** Do not merge multiple genes into one chunk.  
**Rule G-3:** Do not split one gene’s `info` and `function_summary` into multiple chunks (not needed at current sizes).  
**Rule G-4:** Parse `coding_sequence` into `chromosome`, `start`, `end` in metadata (format: `chr:start-end`).

### 4.4 Chunk ID

```
gene:{GENE_SYMBOL}
```

Example: `gene:TCF7L2`

### 4.5 Embeddable Text Template (`content`)

```text
Gene: {gene_symbol}
Alternative names: {alternative_names_joined_or_NA}
Function: {function_summary_or_NOT_AVAILABLE_IN_CORPUS}
Genomic location: chr{chromosome}:{start}-{end} ({assembly_or_unknown})
Gene length: {length_bp} bp
Database identifiers: Ensembl {ensembl_gene_id}, HGNC {hgnc_id}, Entrez {entrezgene}, UniProt {uniprot_accession_or_NA}
Data sources: {gene_sources_joined}
Provenance: Extracted from T2D Knowledge Portal ({source_base_url}), extracted_at={extracted_at_iso8601}
```

**Template constraints:**

* If `function_summary` is empty: `Function: Not available in the approved corpus.`
* If `error` exists, append: `Data quality note: {error}`
* Empty alias list → `N/A`

### 4.6 Metadata Fields

| Field | Type | Required | Use |
|-------|------|----------|-----|
| `entity_type` | string | ✓ | Always `"gene"` |
| `gene_symbol` | string | ✓ | Exact match / filter |
| `alternative_names` | string[] | ✓ | Alias search |
| `ensembl_gene_id` | string | ○ | ID search |
| `hgnc_id` | string | ○ | ID search |
| `entrezgene` | string | ○ | ID search |
| `uniprot_accession` | string | ○ | Protein link |
| `chromosome` | string | ○ | Region filter |
| `start` | int | ○ | Region filter |
| `end` | int | ○ | Region filter |
| `assembly` | string | ○ | Genome build |
| `length_bp` | int | ○ | Sort / display |
| `has_function_summary` | bool | ✓ | Abstention / qualification |
| `data_quality` | enum | ✓ | `complete` / `partial` / `error` |
| `source_base_url` | string | ✓ | Citation |
| `extracted_at_unix` | int | ✓ | Version / provenance |
| `source_file` | string | ✓ | Relative path |

**`data_quality` rules:**

* `complete`: has `function_summary`, no `error`
* `partial`: no `function_summary`, no `error` (IDs/coordinates still present)
* `error`: `error` field present

### 4.7 Full Chunk Example

```json
{
  "chunk_id": "gene:TCF7L2",
  "collection": "gene_info",
  "entity_type": "gene",
  "title": "Gene TCF7L2",
  "content": "Gene: TCF7L2\nAlternative names: TCF-4, TCF4\nFunction: Participates in the Wnt signaling pathway...\nGenomic location: chr10:114710009-114927437 (GRCh37)\n...",
  "metadata": {
    "entity_type": "gene",
    "gene_symbol": "TCF7L2",
    "alternative_names": ["TCF-4", "TCF4"],
    "ensembl_gene_id": "ENSG00000148737",
    "has_function_summary": true,
    "data_quality": "complete",
    "source_file": "data/raw/gene_info/genes_function_info.json"
  },
  "citation": {
    "source_name": "T2D Knowledge Portal",
    "source_url": "https://t2d.hugeamp.org/gene.html",
    "source_file": "data/raw/gene_info/genes_function_info.json",
    "chunk_id": "gene:TCF7L2",
    "extracted_at_unix": 1767895499
  }
}
```

---

## 5. Collection B: LDSC Genetic Correlation

### 5.1 Source Structure

JSONL, one record per line:

```json
{
  "rg": 0.1816782310225735,
  "stdErr": 0.28868386110307526,
  "pValue": 0.5291311831551757,
  "phenotype": "2hrI",
  "other_phenotype": "T2D",
  "ancestry": "Mixed",
  "project": "portal"
}
```

### 5.2 Field Semantics

| Field | Meaning |
|-------|---------|
| `phenotype` | Anchor trait; in this file always `2hrI` (OGTT 2-hour insulin) |
| `other_phenotype` | Trait correlated with the anchor |
| `rg` | Genetic correlation (LDSC) |
| `stdErr` | Standard error |
| `pValue` | Significance |
| `ancestry` | Stratum: `EU` / `HS` / `Mixed` |
| `project` | Source project id; here `portal` |

**Semantic boundaries:**

* `2hrI` is a **quantitative metabolic trait** from population GWAS of OGTT measures—not an individual lab value
* `rg` reflects **shared genetic architecture**, not causality
* This file only covers pairwise correlations anchored on `2hrI`

### 5.3 Source Statistics (measured)

| Metric | Value |
|--------|-------|
| Total rows | 1,646 |
| Unique `other_phenotype` | 781 |
| Unique `(phenotype, other_phenotype)` pairs | 781 |
| Ancestry counts | Mixed: 781, EU: 735, HS: 130 |
| Mixed ancestry p < 0.05 (unique `other_phenotype`) | 7 |

### 5.4 Chunk Rules

**Rule L-1:** Aggregate by `(phenotype, other_phenotype)` → one chunk.  
**Rule L-2:** Different `ancestry` rows for the same pair go in one chunk as a **results list**.  
**Rule L-3:** No fixed-token splitting.  
**Rule L-4:** Content must include **readable phenotype labels** (Section 5.5 glossary).  
**Rule L-5:** Content must include **interpretation guardrails** (population genetics, non-causal, not individual labs).

**Why not one row = one chunk:**

* Users ask at trait-pair level (“Is 2hrI genetically correlated with T2D?”), not per ancestry slice
* 1,646 rows would redundant-recall the same pair across EU/Mixed
* Merged design: 781 chunks with pair-level citations

### 5.5 Phenotype Glossary

Natural language helps embedding. Maintain `config/phenotype_glossary.json` and lookup at ingestion.

**Initial mappings (anchor + frequent comparators):**

| Code | Label | Category |
|------|-------|----------|
| `2hrI` | 2-hour insulin (OGTT) | quantitative_trait |
| `2hrG` | 2-hour glucose (OGTT) | quantitative_trait |
| `2hrGadjBMI` | 2-hour glucose adjusted for BMI | quantitative_trait |
| `2hrFFA` | 2-hour free fatty acids (OGTT) | quantitative_trait |
| `T2D` | Type 2 Diabetes | disease |
| `BMI` | Body Mass Index | quantitative_trait |
| `AD` | Alzheimer's Disease | disease |
| `Asthma` | Asthma | disease |
| `AF` | Atrial Fibrillation | disease |

**Glossary extension:**

1. Known code → curated label  
2. Unknown code → heuristic label (camelCase split + abbreviations), `label_confidence: inferred`  
3. Later: replace/extend with client ontology (e.g. Genovah)

### 5.6 Chunk ID

```
ldsc:{phenotype}:{other_phenotype}
```

Example: `ldsc:2hrI:T2D`

### 5.7 Embeddable Text Template (`content`)

```text
Genetic correlation analysis (LDSC): {phenotype_label} ({phenotype_code}) vs {other_phenotype_label} ({other_phenotype_code})
Analysis type: Linkage Disequilibrium Score Regression (LDSC)
Anchor trait: 2-hour insulin from oral glucose tolerance test (OGTT), a quantitative metabolic trait studied at population level via GWAS summary statistics.

Results by ancestry:
{for each ancestry in pair_results}
- {ancestry_label}: rg={rg}, SE={stdErr}, p={pValue}{significance_tag}
{end for}

Summary (Mixed ancestry, if available): rg={mixed_rg}, p={mixed_pValue}, significant={is_significant_mixed}

Interpretation boundaries:
- rg reflects shared genetic architecture between traits, not causal effect.
- Results describe population-level GWAS evidence, not individual lab test values.
- Non-significant p-values indicate insufficient evidence for shared genetic basis under this analysis.

Source: T2D Knowledge Portal LDSC results (project={project})
Provenance: {source_file}
```

**`significance_tag`:**

* p < 0.05 → `(statistically significant at p<0.05)`  
* else → `(not significant)`

**`ancestry_label`:**

| Code | Label |
|------|-------|
| `EU` | European |
| `HS` | Hispanic/South Asian |
| `Mixed` | Mixed ancestry |

### 5.8 Metadata Fields

| Field | Type | Required | Use |
|-------|------|----------|-----|
| `entity_type` | string | ✓ | `"genetic_correlation"` |
| `phenotype` | string | ✓ | Anchor code |
| `phenotype_label` | string | ✓ | Readable name |
| `other_phenotype` | string | ✓ | Comparator code |
| `other_phenotype_label` | string | ✓ | Readable name |
| `other_phenotype_category` | enum | ○ | `disease` / `quantitative_trait` / `other` |
| `results` | object[] | ✓ | Per-ancestry rg/stdErr/pValue |
| `mixed_rg` | float | ○ | Mixed rg |
| `mixed_pvalue` | float | ○ | Mixed p |
| `is_significant_mixed` | bool | ✓ | mixed p < 0.05 |
| `available_ancestries` | string[] | ✓ | Ancestries present for pair |
| `project` | string | ✓ | `portal` |
| `method` | string | ✓ | `LDSC` |
| `source_file` | string | ✓ | Relative path |

### 5.9 Full Chunk Example

See implementation output in `artifacts/chunks/ldsc_2hrI.chunks.jsonl` (example id `ldsc:2hrI:T2D`).

### 5.10 Optional: Significant Pairs Summary

**Purpose:** Broad questions such as “Which traits are significantly genetically correlated with 2hrI?”

| Attribute | Value |
|-----------|-------|
| Chunk type | `ldsc_summary` |
| Scope | Mixed ancestry, p < 0.05 |
| Measured entries | 7 `other_phenotype` values |
| Relation to pair chunks | Recall aid only; answers should still cite `ldsc:2hrI:{X}` |

Summary chunks **do not replace** pair-level chunks.

---

## 5.11 Reference: `gene_id_map` (not chunked)

| Attribute | Description |
|-----------|-------------|
| Source path | `data/raw/reference/gene_id_map/genes.jsonl` |
| Purpose | HuGE pipeline gene coordinate lookup; hash recorded in manifest |
| RAG | **No chunks, no embedding** |
| Rationale | Overlaps `gene_info` symbols/coordinates; association rows already include locus fields |

---

## 5.12 Collection C: `gene_association_common`

### 5.12.1 Split Rule

**1 JSONL row = 1 chunk** (`gene` × anchor `phenotype`, currently `2hrG`).

### 5.12.2 Chunk ID

```
gassoc_common:{phenotype}:{gene}
```

When the same `gene` symbol appears multiple times (different Ensembl loci):

```
gassoc_common:{phenotype}:{gene}:{ensembl}
```

Examples: `gassoc_common:2hrG:ADCY5`; ambiguous symbol `gassoc_common:2hrG:AC004233.4:ENSG00000289281`

### 5.12.3 Collection / `entity_type`

| Field | Value |
|-------|-------|
| `collection` | `gene_association_common` |
| `entity_type` | `gene_phenotype_association` |
| `metadata.variant_class` | `common` |

### 5.12.4 `content` Highlights

* Natural language + `phenotype_label` (glossary)
* Summarize `bf_common`; if `varIdCausal` present, include causal/GWAS block
* **Interpretation boundaries** (population GWAS, not individual labs, not individual causality)
* Rows with `bf_common=1` and no causal fields still produce chunks; text marks baseline inclusion

### 5.12.5 Metadata Highlights

| Field | Use |
|-------|-----|
| `gene`, `ensembl`, `chromosome`, `start`, `end` | Exact match / filter |
| `phenotype`, `phenotype_label` | Routing / filter |
| `bf_common`, `has_causal_annotation`, `evidence_tier` | Rerank / filter |
| `evidence_tier` | `baseline` / `annotated` / `strong` (e.g. causal + bf_common ≥ 10) |
| Optional causal fields | Exact values and flags |

### 5.12.6 Output

`artifacts/chunks/gene_association_common_2hrG.chunks.jsonl` (**11,383** chunks)

---

## 5.13 Collection D: `gene_association_rare`

### 5.13.1 Split Rule

**1 row = 1 chunk**.

### 5.13.2 Chunk ID

```
gassoc_rare:{phenotype}:{gene}
```

### 5.13.3 `content` / Metadata

* `content`: summarize `pValue`, `beta`, `z`, `bf_rare` + `significance_tag`
* **`stdErr`, `v` in metadata only** (some source rows have anomalous `stdErr`)
* `is_significant`: `pValue < 0.05`
* `method`: `HuGE_rare`

### 5.13.4 Output

`artifacts/chunks/gene_association_rare_2hrG.chunks.jsonl` (**4,114** chunks)

---

## 5.14 Collection E: `ldsc_partitioned_heritability` (2026-10-09 extension)

Source: `data/raw/ldsc/partitioned_heritability/2hrG/2hrG.json`. This extension is prepared for indexing; it does not change the four-collection baseline results.

**Split rule:** one `phenotype + annotation + tissue + biosample + ancestry` record per chunk. The supplied file produces 7,924 chunks, grouped into 1,981 annotation/tissue/biosample units. Do not combine this evidence with genetic-correlation chunks or merge distinct biosamples.

**Readable ID:**

```text
ldsc_partitioned:{phenotype}:{annotation}:{tissue}:{biosample}:{ancestry}
ldsc_partitioned_group:{phenotype}:{annotation}:{tissue}:{biosample}
```

Each source string is UTF-8 percent-encoded using `urllib.parse.quote` with `safe="-_."`; unreserved characters remain readable. Colon, percent, brackets and whitespace are escaped. Null and absent biosample use unescaped `[null]` and `[missing]` markers; a literal source string `[null]` is `%5Bnull%5D`, so the identities remain distinct. Duplicate identities fail validation. IDs are independent of row order and numeric estimates; source version is recorded separately in citation hashes. `group_id` is metadata only and does not implement automatic group retrieval.

**Content and provenance:** all ten source statistics appear in content to four significant digits; complete original fields and parsed numeric precision remain in `metadata.raw_record`. Citation retains source file, physical source row, SHA-256 and chunk ID. All final content is token-checked without truncation against the configured 512-token limit. No significance label, ancestry expansion or causal interpretation is inferred while field definitions and release remain unconfirmed.

**Retrieval text correction (2026-10-10):** content starts with ancestry code and phenotype, followed by annotation, tissue and biosample. Annotation, tissue and provided underscore-containing biosample values include their space-separated spelling, for example `vein_endothelial_cell (vein endothelial cell)`. These are literal spelling variants, not biological definitions. Null/missing markers have no added spelling variant. All ten statistics retain four-significant-digit display; complete parsed values and provenance remain in metadata and citation. IDs and titles remain unchanged. After rebuilding, the 7,924 chunks span 222–270 tokens (median 237), with no truncation at the 512-token limit. BM25 must be rebuilt when content changes; changed Dense records must be re-encoded. See Retrieval Evaluation Design Section 10.4 for the updated 100-query regression results.

**Output:** `artifacts/chunks/ldsc_partitioned_2hrG.chunks.jsonl`. Register the raw path in `config/paths.yaml`; run `python scripts/chunk_corpus.py --partitioned-only` to build only this collection. Validation/build records stay under `artifacts/ingestion_dev/ldsc_partitioned/`. The active seven-collection manifest is `artifacts/manifest_partitioned.json`; `artifacts/manifest.json` remains the four-collection baseline. Explicit `--include-partitioned` rebuilds the baseline too and is not used for this migration. The existing default command retains its baseline behavior.

---

## 5.15 Collection F: `variant_association_clumped` (2026-10-09 extension)

Source: the 2hrG `ancestry=EU` JSONL under `data/raw/metaanalysis/bottom-line/ancestry-clumped/`. The supplied 68 variant records form seven chromosome/clump groups. This is regional association evidence, distinct from gene-level common association and from un-clumped GWAS summary statistics.

**Unit and identity:** one supplied phenotype/ancestry/chromosome/clump region per chunk; `entity_type=variant_association_region`. ID format: `clumped:<phenotype>:<ancestry>:<chromosome>:<clump>:<start>-<end>`, using the same percent-encoding convention as Section 5.14. Bounds come from the export; genome build and interval conventions remain unconfirmed. Ancestry comes from the directory, explicitly recorded as such. Source versions belong in citation hashes; simultaneous different releases require a separate identity/version decision.

**Ranking text:** phenotype, ancestry code, chromosome, source clump and bounds, supplied member count, the source-designated lead variant and its beta/stdErr/pValue/n/alignment (four significant digits), and interpretation limitations. Lead status is not causal proof. Do not flip beta from alignment or infer clumping thresholds/reference panels. This summary supports region/lead questions; it does not support indexed lookup of non-lead member IDs or statistics.

**Metadata and citation:** all original member records and parsed numeric precision in `metadata.members`, in deterministic position/varId order; matching physical `source_rows`, member count, source hash and region identifiers. Citation retains file, all source rows, hash and chunk ID. Member n values may differ; no region-wide n is inferred. Genome build, effect scale/allele, n, alignment, clumping rules, meta selection and release remain explicitly unconfirmed. Metadata is returned with retrieved evidence but is not embedded; no structured member-query or answer-generation adapter is added here.

**Validation and publication:** strict JSON, required types, finite statistics, positive SE/n, pValue bounds, varId/coordinate consistency, unique variants, consistent group context/bounds and exactly one source lead with minimum supplied pValue. Run `python scripts/chunk_corpus.py --clumped-only`; existing five chunk files remain unchanged. Output: `artifacts/chunks/metaanalysis_clumped_2hrG_EU.chunks.jsonl`. All seven final contents are 313-322 Qwen tokens, with special tokens and no truncation, below 512. Separate build/validation records live in `artifacts/ingestion_dev/clumped/`; cross-collection metadata collisions are rejected before writing. The active expanded manifest/config covers seven collections, 142,977 chunks, including WES; this chunking command does not rebuild indexes.

---

## 5.16 Collection G: `gene_association_wes` (2026-10-09 extension)

Source: `data/raw/wes/2hrG/part-00000.json`. Retain every valid gene's source-reported top-level summary and every supplied mask result, including numeric overlap with existing rare evidence. The source has 15,361 rows: 15,360 valid gene identities and one invalid bare NaN gene on physical row 1,845. The invalid row is excluded from chunks and preserved verbatim as a string with its physical row/reason in the validation report; raw remains unchanged.

**Units:** 15,360 gene-summary chunks (`entity_type=gene_phenotype_summary`) and 78,583 gene-mask chunks (`entity_type=gene_mask_association`), total 93,943. Empty masks still produce a summary explicitly noting absent supplied detail; an empty list is not proof of no association/analysis. Do not collapse differently named masks just because values match.

**IDs:** `wes:<phenotype>:<gene>:summary` and `wes:<phenotype>:<gene>:mask:<mask>`, with UTF-8 percent encoding as in Section 5.14. Source records are sorted by phenotype/gene; summary precedes masks sorted by raw mask label. The metadata/citation mask index retains the original zero-based source position, not the sorted position. Same-input builds are deterministic. Source release is unconfirmed; concurrent releases require a separate versioned identity decision.

**Content/metadata:** summary text displays source top-level pValue/beta and supplied mask count; mask text displays original mask label and pValue/beta/stdErr/n/combinedAF/singleVariants/passingVariants, at four significant digits. Exact parsed originals live in summary `metadata.raw_record` (including all masks), and mask `metadata.raw_parent` plus `metadata.raw_mask`. Citation retains physical source row, original mask index where applicable, file hash and ID. Extra supplied fields remain preserved. Top-level test/aggregation is unconfirmed: do not treat it as the minimum mask pValue or borrow a mask SE. No inferred significance, units, effect direction interpretation or mask-selection definitions.

**Overlap:** link same gene/phenotype to old rare via `related_baseline_chunk_id`; `top_level_matches_baseline` separately compares pValue/beta. All 4,113 numerically matching gene summaries remain in WES. `baseline_reference` records compared fields and old chunk-file hash. A same-identity reference does not imply numeric equality, and equality does not establish the same study/version. Links are provenance only; no automatic retrieval expansion, deduplication or score adjustment is implemented. Summary/mask results and repeated exports must not be counted as independent corroboration.

**Validation/output:** finite statistics, pValue bounds, positive SE and integer n, nonnegative count/frequency fields, unique valid gene/phenotype and mask names. Known invalid gene records are quarantined; malformed JSON or invalid statistics in valid genes fail the build. Unconfirmed semantics are explicitly listed in metadata. Reuse `python scripts/chunk_corpus.py --wes-only`, with source/validation paths in paths.yaml. Output: `artifacts/chunks/wes_2hrG.chunks.jsonl`; reports in `artifacts/ingestion_dev/wes/`. Every final content is 132-245 Qwen tokens, no truncation, below 512. The WES chunking step preserves the other six chunk files and raw inputs. Expanded manifest/config covers seven collections, 142,977 chunks. Matching BM25/Dense indexes have subsequently been rebuilt and verified at artifacts/indexes/bm25_title_content/ and artifacts/indexes/dense_qwen3_06b/. New index release packaging and publication remain pending.

---

## 6. Unified Chunk Envelope Schema

All collections emit the same JSON shape for indexing, API, and evaluation:

```json
{
  "chunk_id": "string, globally unique",
  "collection": "gene_info | ldsc_genetic_correlation | gene_association_common | gene_association_rare | ldsc_partitioned_heritability | variant_association_clumped | gene_association_wes | ldsc_summary",
  "entity_type": "gene | genetic_correlation | gene_phenotype_association | partitioned_heritability | variant_association_region | gene_mask_association | gene_phenotype_summary | genetic_correlation_summary",
  "title": "human-readable short title",
  "content": "embedding + generation context text",
  "metadata": { },
  "citation": {
    "source_name": "string",
    "source_url": "string, optional",
    "source_file": "string",
    "chunk_id": "string",
    "extracted_at_unix": "int, optional",
    "method": "string, optional"
  }
}
```

**Constraints:**

* `chunk_id` globally unique across all collections
* `content` is plain text (no markdown tables)
* Precise numeric values live in metadata (e.g. `metadata.results`) to reduce hallucination at generation time

---

## 7. Ingestion Pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Raw JSON/JSONL │ ──► │  Chunk Builder   │ ──► │  Normalized     │
│  source files   │     │  (rules G/L/A)   │     │  chunks.jsonl   │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                        ┌──────────────────┐              │
                        │ Phenotype        │ ◄────────────┤
                        │ Glossary lookup  │              │
                        └──────────────────┘              │
                                                          ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │  Embedder        │ ◄── │  Index Writer   │
                        │  (dense vector)  │     │  (vector + BM25)│
                        └──────────────────┘     └─────────────────┘
```

### 7.1 Steps

1. **Validate source:** schema checks, record source hash  
2. **Build chunks:** Sections 4–5 rules (including HuGE association)  
3. **Enrich labels:** glossary + inferred labels  
4. **Quality flags:** `data_quality`, `is_significant_mixed`, etc.  
5. **Write normalized chunks.jsonl:** one envelope per line  
6. **Index:** hybrid vector + keyword; metadata filters  
7. **Log provenance:** source hashes, pipeline version, timestamp  

**CLI:** `python scripts/chunk_corpus.py` (paths from `config/paths.yaml`).

### 7.2 Outputs

| Artifact | Description |
|----------|-------------|
| `artifacts/chunks/gene_info.chunks.jsonl` | 24,825 chunks |
| `artifacts/chunks/ldsc_2hrI.chunks.jsonl` | 781 chunks |
| `artifacts/chunks/gene_association_common_2hrG.chunks.jsonl` | 11,383 chunks |
| `artifacts/chunks/gene_association_rare_2hrG.chunks.jsonl` | 4,114 chunks |
| `artifacts/chunks/ldsc_2hrI_significant_summary.chunk.json` | 1 optional summary chunk |
| `artifacts/manifest.json` | Source hashes, chunk counts, pipeline version (includes `gene_id_map` not-chunked flag) |

---

## 8. Retrieval and Query Routing

### 8.1 Entity Recognition → Collection

| Query signal | Preferred collection(s) |
|--------------|-------------------------|
| Gene symbol / Ensembl / “gene function” | `gene_info` |
| 2hrI / OGTT insulin / genetic correlation / LDSC / trait vs trait | `ldsc_genetic_correlation` |
| Gene + 2hrG / 2-hour glucose / GWAS / rare variant / HuGE | `gene_association_common` / `gene_association_rare` |
| Gene + phenotype mechanism (e.g. “Why does TCF7L2 support T2D?”) | Corpus may be insufficient → multi-collection retrieval + separate evidence types; **do not merge chunks** |

### 8.2 Hybrid Retrieval (recommended)

| Stage | Gene Info | LDSC | Gene association |
|-------|-----------|------|------------------|
| Exact match | `gene_symbol`, IDs | `phenotype`, `other_phenotype` | `gene`, `phenotype` |
| BM25 | `content` | `content` | `content` |
| Dense | `content` | `content` | `content` |
| Filter | `data_quality` | ancestry | `evidence_tier`, `is_significant`, `variant_class` |
| Rerank | `has_function_summary=true` | exact pair | prefer strong / significant |

### 8.3 Top-k

| Collection | Retrieval top-k | Chunks to LLM |
|------------|-----------------|---------------|
| `gene_info` | 10 | 3–5 |
| `ldsc` | 10 | 3–5 |
| `gene_association_*` | 10 | 3–5 |

---

## 9. Generation and Abstention

### 9.1 Wording Boundaries

| Scenario | System behavior |
|----------|-----------------|
| LDSC p ≥ 0.05 | State insufficient evidence for significant shared genetic basis |
| Individual lab values | Refuse: corpus is population GWAS/LDSC, not personal data |
| Gene → disease causality | Qualify: need MR/GWAS/association layers; cite per collection |
| HuGE rare p ≥ 0.05 | State insufficient rare-variant association evidence |
| Gene `data_quality=error` | Refuse or note incomplete evidence for symbol |
| Gene without `function_summary` | Answer IDs/coordinates only; do not infer function |

### 9.2 User-Facing Citation Format

```
[T2D Knowledge Portal | gene:TCF7L2 | extracted 2026-01-08]
[T2D Knowledge Portal | LDSC 2hrI vs T2D | Mixed rg=0.18, p=0.53 | ldsc:2hrI:T2D]
```

---

## 10. Evaluation Alignment

### 10.1 Suggested Benchmark Types

| Type | Example question | Expected chunk |
|------|------------------|----------------|
| Gene lookup | What is the function of TCF7L2? | `gene:TCF7L2` |
| Gene ID | Which gene is ENSG00000148737? | `gene:TCF7L2` |
| Trait correlation | Is 2-hour insulin genetically correlated with T2D? | `ldsc:2hrI:T2D` |
| Gene–trait GWAS | Common-variant evidence for ADCY5 and 2-hour glucose? | `gassoc_common:2hrG:ADCY5` |
| Rare variant | Rare-variant association for LPCAT2 and 2hrG? | `gassoc_rare:2hrG:LPCAT2` |
| Abstention | Why is TCF7L2 a causal target for T2D? | Refuse / qualify (missing layer) |
| Abstention | My 2-hour insulin is 85—is that normal? | Refuse (out of corpus scope) |

### 10.2 Metrics Mapping

| BioAgent-Eval metric | Supported by |
|--------------|--------------|
| Retrieval relevance | `chunk_id` hit rate |
| Citation correctness | `citation.chunk_id` matches expected |
| Factual support | Numbers from metadata, not LLM-generated |
| Abstention | `data_quality` / `is_significant` / missing-layer rules |

---

## 11. MVP and Extensions

### 11.1 MVP (phase 1)

* [x] Gene: 1 gene = 1 chunk  
* [x] LDSC: 1 pair = 1 chunk (merged ancestries)  
* [x] Unified chunk envelope  
* [x] Baseline phenotype glossary  
* [x] Gene association common/rare (2hrG)  
* [x] `gene_id_map` manifest provenance only  
* [ ] Hybrid retrieval (BM25 + vector)  
* [ ] Benchmark 10–20 questions  

### 11.2 Future Corpora

| New source | Suggested chunk unit |
|------------|----------------------|
| More LDSC (other anchors) | `ldsc:{anchor}:{other}` |
| More HuGE phenotypes (e.g. T2D) | `gassoc_{common\|rare}:{phenotype}:{gene}` |
| GWAS locus → gene | `gwas_locus:{trait}:{locus_id}` |
| MR results | `mr:{exposure}:{outcome}` |
| Target dossier PDF | Section-aware chunks by heading |

---

## 12. Anti-Patterns (Forbidden)

1. **Whole-file token splitting** — breaks entities and citations  
2. **Merging Gene + LDSC chunks** — mixed entity types, wrong citations  
3. **Merging gene info + association chunks** — blurred evidence boundaries  
4. **LDSC one row per chunk without aggregation** — redundant recall  
5. **Embedding raw JSON only** — poor semantic match for natural questions  
6. **Missing significance / `data_quality` flags** — overclaiming  
7. **Describing rg or GWAS association as individual causality or lab results** — violates evidence boundary  
8. **Embedding `gene_id_map`** — duplicates `gene_info` and hurts ranking  

---

## 13. Appendix: Chunk Counts

| Collection | Source records | Output chunks |
|------------|----------------|---------------|
| `gene_info` | 24,825 genes | **24,825** |
| `ldsc_2hrI` | 1,646 rows → 781 pairs | **781** |
| `gene_association_common_2hrG` | 11,383 rows | **11,383** |
| `gene_association_rare_2hrG` | 4,114 rows | **4,114** |
| `ldsc_2hrI_summary` (optional) | 7 significant mixed pairs | **1** |
| **Total** | | **41,104** (with summary) |

---

## 14. Revision History

| Version | Date | Notes |
|---------|------|-------|
| v1.0 | 2026-09-11 | Initial release from sample JSON measurements and BioAgent-Eval requirements |
| v1.1 | 2026-09-16 | HuGE gene association (common/rare 2hrG); `gene_id_map` not chunked; raw layout scheme A |
| v1.2 | 2026-10-10 | Documented Partitioned ranking text, biosample space-separated spelling and matching index rebuild |
