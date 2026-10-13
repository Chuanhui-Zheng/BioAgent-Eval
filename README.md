# CS46 Scientific Evidence Assistant

React + FastAPI application for evidence retrieval and structured scientific analysis.

## Implemented functionality

- Eight-collection RAG with cited claims, visible limitations, hosted-provider fallback and source-passage inspection.
- Gene function, identifiers, source associations, GO/pathway membership, target comparison and dossier export.
- Actual RNA tissue summaries and individual protein observations; source units remain unconfirmed.
- Actual GWAS Manhattan/QQ plots, significance filtering and exact interval queries for supplied 2hrG and 2hrFFA EU files. QQ uses all selected-region p-values before significance filtering.
- Exact supplied nearest-gene, cS2G and burden annotation lookups. Coordinate builds are not silently joined.
- Upload matrix.csv or W.csv + H.csv, with optional associations.csv and GMT. Calculate reproducible NMF or Bayesian NMF, select component genes, filter signed association z, calculate local hypergeometric enrichment with BH correction and export factors/results/provenance.
- Independently annotated offline or AIHubMix evaluation with gold citation, required fact/number policies, fallback rate and an exported human-review rubric.

## Download ZIP and run locally

You only need **Code → Download ZIP** from the
`feature/scientific-analysis-update` branch (or a later version containing these
instructions). Selecting `main` before downloading may give an older version.
Unzip it, open a terminal and `cd` into the directory containing `server.py`.
Git, a GitHub token, and the Release runtime ZIP are not needed after downloading.
Repository access is required to download this private project.

The source ZIP includes `data/raw/`, public gene-set libraries, and the real
200-gene/four-trait client example at
`data/reference/client_example/example.json`. Do not merge a second data ZIP.
Database, chunks and BM25 index are generated during first-time setup below.
Keep the original relative paths and retain `data/raw/`.

### 1. Check prerequisites

Install Python 3.12+ (3.13 recommended) and Node.js 20+ (npm included). The pinned
NumPy dependencies require Python 3.12 or newer. macOS with Python 3.13 has
been tested; Windows commands are provided but have not been validated on Windows.
First setup requires internet access for dependencies and tokenizer files, and
several GB of free disk space for the environment and generated data.

```sh
python3 --version
node --version
npm --version
```

On Windows, use `python` instead of `python3`.

### 2. First-time backend setup — from the project root

macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

With the virtual environment active, run each command in order. Stop if any
command reports an error; do not start the application with a partial index.

```sh
python -m pip install -r requirements/api.txt transformers huggingface-hub
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-Embedding-0.6B', allow_patterns=['*.json', '*.txt', '*.model'])"
python scripts/prepare_api_corpus.py
python scripts/build_bm25_index.py
python scripts/prepare_analysis.py
```

These commands rebuild all eight collections (159,607 chunks), BM25 retrieval
and the structured database. Allow several minutes, depending on your computer
and network. The tokenizer download does not download the model weights;
a warning that PyTorch is unavailable is harmless for this tokenizer-only step.
Run preparation again only when source data or processing rules change.

### 3. Start the backend — terminal 1

In the project root with `.venv` active:

```sh
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`. Keep this terminal running.
Check <http://127.0.0.1:8000/api/health>: expect `healthy` and `total_chunks: 159607`.

### 4. Start the frontend — terminal 2

Open another terminal, `cd` into the **same project root**, then:

```sh
cd frontend
npm ci
npm run dev
```

Open the **Local** URL printed by Vite, normally <http://127.0.0.1:5173>.
Keep both terminals running. On subsequent launches, activate `.venv` and start
the backend, then run `npm run dev` in `frontend`; skip installation and data
preparation. Press Ctrl+C in each terminal to stop.

### 5. Try the application

- Gene Search: search `ADCY5` and inspect source evidence.
- Phenotype Search: select `2hrG` to view GWAS/QQ and gene associations.
- Gene Region: inspect a region covered by the supplied variant statistics.
- Gene MoA: click **Load client example** to load 200 genes and four traits,
  explore the signed heatmap, then explain the selection. No extra file is needed.
- Gene MoA also supports the corpus matrix, matrix/factor uploads, NMF/Bayesian
  NMF, local enrichment and result export; follow the input formats below.
- Ask RAG Assistant: ask which genes are associated with 2-hour glucose and open
  the returned citations. Default generation is local/offline and needs no API key.

Not every gene or phenotype has supplied evidence. Empty results can reflect
coverage, not an installation failure. This setup enables the default BM25 app;
optional hosted generation/evaluation requires your own provider API key, and
standalone Dense/Hybrid retrieval requires its additional dependencies, model
weights and a newly built matching Dense index. Do not mix old Release indexes
with this corpus. Docker and other operating systems remain separately unverified.

### Troubleshooting

- **Port 8000 already in use:** stop the other backend, or use another port:
  `python -m uvicorn server:app --host 127.0.0.1 --port 8016`.
  Put `VITE_API_TARGET=http://127.0.0.1:8016` in `frontend/.env.local`, then
  restart Vite. Frontend and backend must use matching ports.
- **Manifest mismatch or missing index:** run all three preparation commands in
  step 2, in order, using this source directory.
- **Tokenizer download failed:** check internet access and rerun the download
  command before corpus preparation. Do not skip a failed preparation step.
- **Client example missing:** confirm `data/reference/client_example/example.json`
  exists. Older ZIPs omitted it; download the branch version containing this README.
- **API connection failure:** keep terminal 1 running and check its error output.

Public gene-set libraries and checksums are included. Refreshing them with
`python scripts/prepare_analysis.py --download-libraries` is optional.
The [prebuilt runtime package](docs/guides/RUNTIME_RELEASE.md) is an alternative
for skipping preparation, not a requirement for Download ZIP setup.
Never commit real API keys or local `.env` files.

## Analysis input formats

- X CSV: first column gene, subsequent columns phenotype names; finite nonnegative values, unique labels.
- W CSV: gene rows and component columns. H CSV: component rows and phenotype columns. Component labels must match; order is aligned explicitly.
- Associations CSV: gene,phenotype,beta plus z or positive stdErr; optional pValue. Inconsistent z versus beta/stdErr is rejected.
- GMT: term,description,gene1,gene2... separated by tabs. The enrichment background is all measured matrix genes; all testable terms enter BH correction.

Download format templates in Gene MoA. The templates are synthetic format examples and are not biological reference datasets. Bayesian sampling exposes its likelihood/priors, seed, posterior intervals and trace; a single chain does not establish convergence. Uploaded files and at most eight analysis runs remain in server memory, expire after eviction/restart and are exportable as JSON.

## Tests and delivery

```sh
python -m pip install -r requirements/dev.txt
TMPDIR=/private/tmp python -m pytest -q
cd frontend
npm run build
```

Earlier implementation checks passed 206 tests and 55 subtests; run the commands above for the current checkout. Full FAISS tests are now included. The existing 100-question offline benchmark, now evaluated over all eight collections without oracle collection labels, reports 95.56% answerable TargetHit@10 and 99% status accuracy; it is not a new blind evaluation.

Docker packaging: `docker compose up --build`. The first API launch downloads tokenizer files and prepares its corpus/index. Docker was not executable on the development host, so container startup remains unverified. GitHub Actions configuration runs tests and the frontend build; no remote workflow run was triggered.

Independent evaluation: `python scripts/evaluate_annotated.py questions.jsonl --output reports/review.json`. Add `--hosted` with AIHUBMIX_API_KEY in the environment to test hosted generation. Real hosted calls were not made during this work.

## Scientific limits

Citation structure and explicitly labelled scientific numbers are checked. This is not a semantic entailment or scientific correctness guarantee. Effect scale, allele convention, genome build and some source definitions remain unconfirmed. Invalid standard errors are excluded from z-based selection. No agonist/antagonist or clinical recommendation is inferred from effect sign. Blind annotations, human review and Bayesian convergence assessment require qualified reviewers.

Historical design/evaluation material remains in docs/, reports/ and artifacts/evaluation/. The simple Streamlit demo remains available through setup_demo.py and run_demo.py.

Current review changes, scope controls, run logging and reproducible checks: [Review fixes](docs/guides/REVIEW_FIXES_2026-10-13.md).

## Client example and analysis explanations

In Gene MoA, use **Load client example** for a traceable 200-gene, four-trait demonstration. The embedded question box explains the current run and filters with source records and approved gene-function citations. The original W matrix is missing; this demo independently refits NMF and does not reproduce the client factors. See [workflow and limitations](docs/guides/CLIENT_EXAMPLE_WORKFLOW.md). The bundled-example integration tests run with the source ZIP; missing example data is a test failure.
