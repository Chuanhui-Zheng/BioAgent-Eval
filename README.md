# CS-46 Evidence-Grounded Scientific RAG Assistant

## Customer demonstration

This repository includes a local browser demonstration for Windows and macOS.
Python 3.10 or newer is the only prerequisite. From the repository folder run:

```text
python setup_demo.py
python run_demo.py
```

Windows users can replace `python` with `py`. Setup creates an isolated virtual
environment, installs the required packages, and builds the local BM25 index.
See [`DEMO_GUIDE.md`](DEMO_GUIDE.md) for operating-system instructions,
recommended questions, architecture, limitations, and troubleshooting.

Offline mode is the reliable default and requires no API key. AIHubMix is
optional. For the browser demo, paste a key into the password field after
selecting **AIHubMix**; it is kept only for the current app session. Command-line
use can read a key from a local `.env`. See [`API_KEY_GUIDE.md`](API_KEY_GUIDE.md).
Never commit `.env` or a real key.

This repository contains a reproducible offline RAG baseline for the approved
drug-discovery corpus. It covers corpus chunking, BM25/dense/hybrid retrieval,
context augmentation, deterministic evidence-grounded generation, claim-linked
citations, refusal, and end-to-end evaluation.

The default path requires no external LLM API and does not download an
embedding model. The development requirements include the FAISS library for
mock-vector tests, but not Torch or the Qwen model.

## Requirements

- Python 3.10 or newer (tested with Python 3.13.3)
- macOS, Linux, or Windows
- approximately 200 MB free space for the repository and BM25 index

## Reproduce the offline baseline

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
python scripts/build_bm25_index.py
python -m pytest -q
```

Windows PowerShell activation:

```powershell
.venv\Scripts\Activate.ps1
```

## Run the offline RAG demonstration

```bash
python scripts/query_rag_offline.py "What is the function of TCF7L2?"
```

The command prints the answer status, evidence-grounded answer, citation
records, limitations, validation result, and latency. It uses the deterministic
`OfflineEvidenceGenerator`; no API key is needed.

## Reproduce evaluation

```bash
python scripts/evaluate_bm25.py \
  --dev-set data/evaluation/retrieval_test.jsonl \
  --output-dir artifacts/evaluation/bm25_test_reproduced \
  --top-k 10 --report-ks 1 3 5 10
python scripts/build_rag_benchmark.py
python scripts/evaluate_rag_offline.py
```

Current local verification:

- 60 automated tests pass;
- answerable BM25 TargetHit@10: 87/90 (96.67%);
- answer/refuse status accuracy: 99%;
- unanswerable refusal accuracy: 10/10;
- structural citation correctness and completeness: 100%.

The citation figures validate references against supplied context. They are not
claims of 100% scientific or semantic answer correctness. See
[`docs/PROJECT_STATUS_AND_ROADMAP.md`](docs/PROJECT_STATUS_AND_ROADMAP.md).

## Optional dense and hybrid retrieval

Dense and hybrid retrieval are not required for the offline BM25 demonstration.
Install their larger dependencies separately:

```bash
python -m pip install -r requirements-embed.txt
python scripts/build_dense_index.py
python scripts/evaluate_dense.py \
  --dev-set data/evaluation/retrieval_test.jsonl \
  --output-dir artifacts/evaluation/dense_test_reproduced
python scripts/evaluate_hybrid.py \
  --dev-set data/evaluation/retrieval_test.jsonl \
  --output-dir artifacts/evaluation/hybrid_test_reproduced
```

The configured embedding model is `Qwen/Qwen3-Embedding-0.6B`. Building its
index can take a long time on a CPU or Apple laptop. Downloaded models and
generated indexes are intentionally excluded from Git.

## Optional AIHubMix generation

The default provider remains offline. The browser demo accepts an AIHubMix key
directly in its password field and does not save it. For command-line use,
install the hosted-generator requirements and create a local `.env`:

```bash
python -m pip install -r requirements-llm.txt
cp .env.example .env
```

Insert a newly generated key into the local `.env` file:

```env
AIHUBMIX_API_KEY=replace-with-a-new-key
AIHUBMIX_BASE_URL=https://aihubmix.com/v1
AIHUBMIX_MODEL=nemotron-3-ultra-550b-a55b-free
```

Run one grounded query:

```bash
python scripts/query_rag.py \
  "What is the function of TCF7L2?" \
  --provider aihubmix
```

The provider receives only the selected `ContextPackage`, must return
claim-level citations as structured JSON, and falls back to the deterministic
offline generator in the command-line pipeline if the API fails or the output
fails citation validation. The browser reports hosted-provider errors directly
so a failed API call cannot be mistaken for a successful online answer.
Replace a key later by changing only `AIHUBMIX_API_KEY` in `.env` and restarting
the command. Never commit `.env` or use a key that has been shared publicly.
Full browser and command-line instructions are in
[`API_KEY_GUIDE.md`](API_KEY_GUIDE.md).

The first live smoke test completed successfully on 2026-09-27 using a TCF7L2
function query: the hosted provider returned a cited answer, validation passed,
no offline fallback was used, and end-to-end latency was approximately 20.44 s.

## Repository guide

- Team update and file map: [`docs/TEAM_UPDATE_GUIDE.md`](docs/TEAM_UPDATE_GUIDE.md)
- Project status and roadmap: [`docs/PROJECT_STATUS_AND_ROADMAP.md`](docs/PROJECT_STATUS_AND_ROADMAP.md)
- Jira update guide: [`docs/JIRA_SUBTASK_UPDATE.md`](docs/JIRA_SUBTASK_UPDATE.md)
- Prioritised remaining work: [`docs/TODO.md`](docs/TODO.md)
- Stage reports: [`reports/`](reports/)
- Retrieval configuration: [`config/retrieval.yaml`](config/retrieval.yaml)
- Generation configuration: [`config/generation.yaml`](config/generation.yaml)

## Data and security

The prototype operates only on the approved repository corpus. Never commit
`.env` files, API keys, client secrets, downloaded model weights, or generated
indexes. Confirm client approval before sending any corpus passage to an
external LLM provider.
