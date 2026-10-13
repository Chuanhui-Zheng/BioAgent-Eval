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

## Local setup

Python 3.10+ (Python 3.13 validated) and Node.js 20+ are required.

### Data and generated files

Existing versioned datasets and baseline artifacts remain in this repository.
This update excludes additional local raw data, generated indexes, databases,
run logs, dependencies and client-example data.

Before running preparation commands, ensure that all required source files
are present under `data/raw/` with their original directory structure.
Obtain any missing project data through the team's agreed channel.

The optional client example requires
`data/reference/client_example/example.json`.
Restore it locally or regenerate it with
`python scripts/prepare_client_example.py /path/to/mainSample_Data.zip`.
Client-example integration tests are skipped when this file is absent.
Never commit API keys or local `.env` files.

### 1. First-time Setup (Run Once)

Set up the virtual environment, install dependencies, and build local scientific corpora and structured indices:

```sh
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# 2. Install backend dependencies & fetch embedding model files
python -m pip install -r requirements/api.txt transformers huggingface-hub
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-Embedding-0.6B', allow_patterns=['*.json', '*.txt', '*.model'])"

# 3. Build offline scientific evidence corpora & structured database (~714 MB)
python scripts/prepare_api_corpus.py
python scripts/build_bm25_index.py
python scripts/prepare_analysis.py
```

### 2. Routine Running (Two Terminals Required)

Run the backend and frontend in **two separate terminal windows**:

#### Terminal 1 — Backend (FastAPI API)
```sh
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```
> API will be available at `http://127.0.0.1:8000` (Interactive API documentation at `http://127.0.0.1:8000/docs`).

#### Terminal 2 — Frontend (React Interface)
Open a **new** terminal window:
```sh
cd frontend
npm install                     # Or npm ci
npm run dev
```
> Open **`http://localhost:5173`** in your browser.

Public reference libraries are versioned under `data/reference/gene_sets` with checksums. The rebuildable SQLite cache is approximately 714 MB and excluded from Git. Optional library refresh: `python scripts/prepare_analysis.py --download-libraries` (downloads only public sets; user gene lists are never transmitted).

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

206 tests and 55 subtests passed during the final implementation checks. Full FAISS tests are now included. The existing 100-question offline benchmark, now evaluated over all eight collections without oracle collection labels, reports 95.56% answerable TargetHit@10 and 99% status accuracy; it is not a new blind evaluation.

Docker packaging: `docker compose up --build`. The first API launch downloads tokenizer files and prepares its corpus/index. Docker was not executable on the development host, so container startup remains unverified. GitHub Actions configuration runs tests and the frontend build; no remote workflow run was triggered.

Independent evaluation: `python scripts/evaluate_annotated.py questions.jsonl --output reports/review.json`. Add `--hosted` with AIHUBMIX_API_KEY in the environment to test hosted generation. Real hosted calls were not made during this work.

## Scientific limits

Citation structure and explicitly labelled scientific numbers are checked. This is not a semantic entailment or scientific correctness guarantee. Effect scale, allele convention, genome build and some source definitions remain unconfirmed. Invalid standard errors are excluded from z-based selection. No agonist/antagonist or clinical recommendation is inferred from effect sign. Blind annotations, human review and Bayesian convergence assessment require qualified reviewers.

Historical design/evaluation material remains in docs/, reports/ and artifacts/evaluation/. The simple Streamlit demo remains available through setup_demo.py and run_demo.py.

Current review changes, scope controls, run logging and reproducible checks: [Review fixes](docs/guides/REVIEW_FIXES_2026-10-13.md).

## Client example and analysis explanations

In Gene MoA, use **Load client example** for a traceable 200-gene, four-trait demonstration. The embedded question box explains the current run and filters with source records and approved gene-function citations. The original W matrix is missing; this demo independently refits NMF and does not reproduce the client factors. See [workflow and limitations](docs/guides/CLIENT_EXAMPLE_WORKFLOW.md). Current full test suite: 211 tests and 55 subtests.
