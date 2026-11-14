# BioAgent-Eval: Scientific Agent Harness & Evaluation Platform

BioAgent-Eval is an evidence-grounded Scientific Agent Harness and automated Evaluation Platform for drug-discovery research workflows. It preserves the existing Scientific RAG, LLM providers and evaluation assets, and adds a reusable execution layer for tool calling, context handling, retries, checkpoints and structured traces.

The Harness includes structured tool selection, Pydantic argument validation, async/sync execution, timeout/retry/cache handling, durable SQLite idempotency for side-effecting tools, permission checks, tool-call budgets, checkpoint persistence and resume, evidence-aware context compression, JSONL tracing, execution metrics, and a provider-neutral adapter for the existing OpenAI-compatible LLM provider.

## Scientific RAG foundation

The active retrieval corpus has eight collections (159,607 passages): gene information, 2hrI genetic correlation, 2hrG common and rare gene associations, 2hrG LDSC partitioned heritability, 2hrG clumped variant associations, 2hrG WES gene associations, and GTEx RNA/protein expression. Seven come from the client's October 2026 `newdata` delivery; partitioned heritability comes from the earlier supplied files and is kept because the retrieval and end-to-end benchmarks (dev, test and blind) are labelled on all eight collections. The active collection list is in [`config/retrieval.yaml`](config/retrieval.yaml). 2hrFFA GWAS and nearest-gene files are not in the chat corpus.

The source files needed for the scientific retrieval tools are included under `data/raw/` in the repository. You do not need to separately download or merge the client's ZIPs. A downloaded source ZIP does not contain the generated BM25 index; the first-time setup below builds it from the included sources. Authorized collection selection demonstrates retrieval isolation; it is not user authentication.

## CLI quick start

Prerequisites: Python 3.10+. Install the Python dependencies with `python -m pip install -r requirements/dev.txt`. Retrieval indexes and corpus preparation remain available through the existing scripts.

### 1. Prepare the backend

macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/api.txt transformers huggingface-hub
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-Embedding-0.6B', allow_patterns=['*.json', '*.txt', '*.model'])"
python scripts/prepare_api_corpus.py
python scripts/build_bm25_index.py
```

Windows PowerShell: create and activate the environment with `python -m venv .venv` and `.\.venv\Scripts\Activate.ps1`, then run the `python` commands above. Stop if preparation reports an error; a partial index cannot safely serve the chat. Tokenizer download does not fetch the model weights. Rebuild only if source files or processing rules change.

### 2. Run the Agent Harness

From the project root:

```sh
PYTHONPATH=src python -m bioagent run \
  --query "Analyse TCF7L2 and 2-hour glucose evidence" \
  --trace-path artifacts/traces/demo.jsonl \
  --checkpoint-dir artifacts/checkpoints
```

This deterministic offline adapter exercises the real approved corpus and tool execution path without claiming LLM answer quality. The retained API can be started with `python -m uvicorn server:app --host 127.0.0.1 --port 8000` for integrations and automated tests.

Additional CLI commands are available for the execution lifecycle:

```sh
PYTHONPATH=src python -m bioagent trace --trace-path artifacts/traces/demo.jsonl
PYTHONPATH=src python -m bioagent evaluate --dataset data/evaluation/integration_regression.jsonl --output artifacts/evaluation/agent.json
PYTHONPATH=src python -m bioagent fault-test --scenario tool_timeout
PYTHONPATH=src python -m bioagent report --input artifacts/traces/demo.jsonl --output artifacts/reports/demo.html
```

`compare` reports configuration differences only; performance claims still require running the same benchmark against both configurations.

Hosted generation remains available for CLI/API integrations through the existing provider adapters. Install `requirements/llm.txt`, configure the provider through the existing request or environment settings, and keep credentials out of source control. Provider usage metadata is recorded when supplied; otherwise cost and token values remain explicitly unavailable or estimated.

Provider payloads, failures, fallback and credential isolation have automated fixture tests; actual key validity, billing and model availability must be checked with your own account. Citation and numeric validation do not prove that a scientific interpretation is correct; verify claims against source passages.

## Tests and advanced work

```sh
python -m pytest -q
```

The repository retains research/evaluation scripts, benchmark questions and structured-analysis code for development. Keyword (BM25) retrieval is the default chat mode, selected on development questions only; see [Retrieval tuning](reports/phase_5_retrieval_tuning/README.md). Set `RAG_RETRIEVAL_METHOD` to `bm25_rerank` (BAAI/bge-reranker-base cross-encoder, tuned settings in `config/retrieval.yaml`), `dense`, `hybrid` or `hybrid_rerank` to try the alternatives; dense/hybrid need `requirements/embed.txt` and an index from `python scripts/build_dense_index.py --resume`, and missing components fall back to BM25 (reported by `/api/health` under `retrieval`). The API is documented at <http://127.0.0.1:8000/docs>.

For Docker, run `docker compose up --build`; its first API launch prepares the corpus and index. Docker startup has not been verified on every platform.

## Quality evaluation

### Verified BioAgent-Eval results

- Existing RAG regression: 100 queries, 99% status accuracy, 96.67% TargetHit@10, 100% citation correctness and 100% citation completeness.
- Agent Harness infrastructure benchmark: 100 deterministic tasks. The optimized configuration reduced estimated fixture-model tokens/task from 3,226.69 to 2,277.62 (**29.41%**), mean latency from 0.386s to 0.199s (**48.55%**), and external tool executions/task from 2.0 to 1.0 (**50%**); completion remained 100%.
- Fault injection smoke test: **1/1** transient tool failures recovered.
- Hosted OpenRouter integration run: **16** annotated tasks, 0% fallback, 100% status accuracy, 100% citation precision, 92.75% citation recall, 100% claim grounding, 4.88s mean latency, 2,533.62 mean tokens/task and **US$0.00631 estimated total cost**. This is a small regression set, not a statistically conclusive production benchmark.

The full methodology, limitations and interview-readiness gap list are in [`docs/project/BIOAGENT_EVAL_GAPS_AND_NEXT_STEPS.md`](docs/project/BIOAGENT_EVAL_GAPS_AND_NEXT_STEPS.md). Resume-ready wording is in [`docs/project/BIOAGENT_RESUME_CONTENT.md`](docs/project/BIOAGENT_RESUME_CONTENT.md).

- **Frozen blind benchmark:** `data/evaluation/blind/blind_e2e_v1.jsonl` (40 questions, SHA-256 in its manifest; never used for tuning). Run `python scripts/evaluate_blind.py --label offline`. For a hosted model put `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` (and `LLM_BASE_URL` for `custom`) in `.env`, then add `--llm-provider custom --limit 25 --judge-provider custom --judge-model <model>`. Reports, an LLM support-judge summary and a human review sheet are written to `reports/blind_v1/<label>/`; score them with [the rubric](reports/blind_v1/HUMAN_REVIEW_RUBRIC.md).
- **Metrics:** status/refusal accuracy, gold-citation precision and recall, required facts and exact numbers, claim grounding (every number and identifier in a claim must appear in its cited passage), optional LLM-judge support labels, fallback rate, latency and cost.
- **Retrieval tuning:** `python scripts/tune_retrieval.py --no-dense` (development sets only; refuses test/blind files) and `python scripts/evaluate_retrieval_methods.py --no-dense` (frozen test sets).

## Troubleshooting

- If port 8000 is occupied, choose another port for Uvicorn and use that port for API clients.
- If the backend reports a manifest or index mismatch, rerun `prepare_api_corpus.py` and `build_bm25_index.py` in that order from this source directory.
- If the tokenizer download fails, check internet access and rerun it before preparation.
- If the API reports an unavailable backend or retrieval index, keep the API process running and inspect its error output.
