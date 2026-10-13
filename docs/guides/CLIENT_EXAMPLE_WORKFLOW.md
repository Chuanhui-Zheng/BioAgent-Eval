# Client example and analysis-context questions

The source branch includes `data/reference/client_example/example.json`, so
**Code → Download ZIP** needs no separate client archive to use this example.
The preparation script is retained only for reproducing it from the original archive.

## Try it
Open Gene MoA, then Load client example. In Explore genes, select T2D under Phenotype and set Minimum |Z-score| to 2. Component and W filters are under Advanced. With component C1 and W >= 0, the bundled example selects 75 of 200 genes. Run enrichment with a local library if desired, inspect directional effects, then choose Explain results and ask “Why were these genes selected?” in the embedded question box. The question uses server-owned run data and current filters. A named measured gene can also be explained, including why it was excluded.

The global chat still answers fixed-corpus questions. The embedded MoA question box is the entry point for analysis-context questions. It is a local extractive explanation plus approved gene-function retrieval; it does not call an external model or infer drug action. Enrichment results are exported in the dossier but are not interpreted by this question endpoint.

## Dataset and transformation
Source: Sample_Data/V001-20260826T154019Z-1-001.zip -> V001/df_table_demo_enrich.csv.
The supplied H_demo_enrich.csv has no matching supplied W; the app never pairs it with invented factors.
Choose source cluster 0 and traits BMI, HDL, T2D, TG. There are 4,562 genes with valid complete records for these four traits. Select 200 evenly spaced genes in alphabetical order (not the strongest hits). The bundled example preserves 800 original signed beta_g, StdErr and Zscore records, original CSV row numbers and gene-cluster IDs.
X = absolute source Zscore; no missing-cell imputation. NMF uses two components, 500 iterations and seed 46. These newly calculated factors do not reproduce the original client model. Source cluster IDs and new component IDs have different meanings. Log_pvalue is not silently converted to a p-value; its definition remains unconfirmed.
Enrichment is conditional on the 200 measured demo genes, not a genome-wide test. No significant result is guaranteed.

Regenerate from the client ZIP:
    python scripts/prepare_client_example.py /path/to/Sample_Data-20260929T151459Z-1-001.zip

The script reads client files, never executes client scripts. It validates duplicate IDs and beta/SE versus Z consistency, checks finite values and selects complete cases. Source CSV and nested ZIP hashes plus selection policy are stored in data/reference/client_example/example.json.

## API and evidence
POST /api/analysis/matrix/client-example returns a normal analysis run, factors, source effects, diagnostics and limitations.
POST /api/analysis/runs/{run_id}/question takes question, component, weight, z_cutoff and trait. It reconstructs the selection on the server, refuses missing/expired/other-workspace runs, and never trusts client-supplied result text. The example endpoint is limited to workspaces with common and rare genetic evidence access.
Each response carries analysis_run_id, query_run_id, filters and snapshot_sha256. Claims reference separate computed-selection, source-association or approved-corpus evidence. Validation checks citations and labelled numbers, not scientific entailment.
Question records are persisted under artifacts/runs/<workspace>/analysis-<query_run_id>.json. They include the snapshot and source hashes. Analysis runs themselves remain in memory and expire after eviction/restart; export the dossier to preserve factors, selection, enrichment and the explanation.
Changing run or filters clears the old explanation; a late response from an old selection is discarded.
Unsupported treatment questions are refused. Detailed summaries cover at most three genes and three source effects per gene.

## Verification
211 tests and 55 subtests passed, including deterministic example factors, complete-case validation, source row provenance, filters/snapshot changes, unknown-trait filtering, treatment refusal and workspace/expired-run isolation.
Frontend production build passed.
Real-data API and browser checks loaded the example, selected 75 genes for T2D with |Z| >= 2, retrieved function citations and ran local WikiPathways enrichment (282 tested sets, zero passing BH q <= 0.05 for this selection).
No hosted model call, client-code execution or external gene-list submission was made.

## Guided UI and heatmaps
The interface shows three stages, with upload/algorithm configuration, enrichment, source tables and evaluation collapsed by default. The signed heatmap uses current selection records: traits as rows, genes ordered by component W as columns. Z-score/Beta switching, 6/12/24 displayed genes, value annotations and keyboard-accessible cell details are supported. Missing/nonfinite/ambiguous cells are N/A, never zero. Red/blue represent positive/negative source association only. The nonnegative H-weight heatmap remains available under its own disclosure. The old teammate UI used generated demo numbers; those numbers and its agonist/antagonist rule are not used.
Verification: production build and three matrix-alignment tests passed. Browser checks verified data loading, metric switching, source-cell detail and transition to the explanation stage. Screenshots do not establish full accessibility compliance.
