# CS46 Scientific RAG Assistant

Retrieve scientific evidence, build context, generate an answer and show source citations. The current application has a React frontend and a FastAPI backend. Offline generation is available; AIHubMix is optional. Some charts and MoA panels still use prototype data.

## Run the current application

Python 3.10+ and Node.js 20+ are required. Create and activate a virtual environment first:

```sh
python -m venv .venv
```

macOS/Linux: `source .venv/bin/activate`

Windows PowerShell: `.venv\Scripts\Activate.ps1`

Prepare the corpus and index once on a fresh checkout:

```sh
python -m pip install -r requirements/api.txt transformers huggingface-hub
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-Embedding-0.6B', allow_patterns=['*.json', '*.txt', '*.model'])"
python scripts/prepare_api_corpus.py
python scripts/build_bm25_index.py
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. See [frontend instructions](frontend/README.md) for API behaviour and limitations.

### Key UI Features

| Module | Description |
|:---|:---|
| **Ask Assistant** | Submit scientific queries; returns verified evidence-grounded answers with claim citations and latency tracking. |
| **Gene Explorer** | Search and view genes (e.g., PPARG, TCF7L2) with HuGE Scores, UniProt functional annotations, and GWAS phenotype associations. |
| **Phenotype Browser** | Explore and filter 1,658 standardized phenotypes across biological categories with reactive GWAS Manhattan/QQ charts. |
| **Mechanism of Action** | Interactive bNMF factoring, Z-cutoff gene selection, and multi-gene pathway mechanism analysis. |

### Optional AIHubMix Generation

By default, the assistant runs in deterministic offline mode requiring **no API keys**.

To enable fluent generative answers with AIHubMix:
1. Click the **🔑 AIHubMix Key** button in the top right of the Ask Assistant panel.
2. Enter your API key (`sk-...`).
3. Keys are stored only in memory for the active browser session and never committed to disk.


## Simple Streamlit demonstration

After preparing the corpus and index above:

```sh
python setup_demo.py
python run_demo.py
```

See the [demo guide](docs/guides/DEMO_GUIDE.md) and [API key guide](docs/guides/API_KEY_GUIDE.md). Keep keys in the session input or a local `.env` file.

## Where things belong

| Directory | Purpose |
| --- | --- |
| `frontend/` | React interface |
| `src/` | Reusable data processing, retrieval and generation code |
| `scripts/` | Corpus preparation, indexing, queries and evaluation commands |
| `config/` | Pipeline settings and phenotype glossary |
| `data/` | Source datasets and evaluation questions |
| `artifacts/` | Versioned corpus manifests, baseline chunks and evaluation outputs |
| `reports/` | Four historical RAG phase reports |
| `requirements/` | Optional API, demo, test, embedding and LLM dependencies |
| `docs/` | Guides, project notes, design and archived plans |
| `tests/` | Automated regression tests |

`server.py` starts the API; `app.py`, `setup_demo.py` and `run_demo.py` support the simple demo. Core runtime dependencies remain in `requirements.txt`.

## Verify and evaluate

```sh
python -m pip install -r requirements/dev.txt
python -m pytest -q
cd frontend
npm run build
```

On macOS, if a test compares `/var` with `/private/var`, run `TMPDIR=/private/tmp python -m pytest -q`.

The merged version was checked with 152 tests, 50 subtests, a frontend build and an offline API query. Historical benchmark scores belong to their recorded corpus/configuration; they do not establish scientific correctness of current generated answers. See the [documentation index](docs/README.md) for evaluation designs and archived results.

Generated indexes, caches, model downloads, virtual environments and secrets are excluded from Git. Keep source data and evaluation evidence versioned, and do not add local build outputs with `git add -f`.
