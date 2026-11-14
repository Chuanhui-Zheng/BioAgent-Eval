<p align="center">
  <img
    src="assets/dna-black.svg#gh-light-mode-only"
    width="100"
    alt="BioAgent-Eval Logo"
  />
  <img
    src="assets/dna-white.svg#gh-dark-mode-only"
    width="100"
    alt="BioAgent-Eval Logo"
  />
</p>

<h1 align="center">BioAgent-Eval</h1>

<p align="center">
  <strong>Scientific RAG × Agent Runtime × Reproducible Evaluation</strong><br>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Agent_Harness-Tool_Execution-6f42c1" alt="Agent Harness">
  <img src="https://img.shields.io/badge/Scientific_RAG-BM25%20%7C%20Hybrid-0a7" alt="Scientific RAG">
  <img src="https://img.shields.io/badge/Tests-282%20passed-2ea44f" alt="Tests">
</p>

<p align="center">
  A Python execution layer for reliable, traceable and measurable scientific agents.
</p>


BioAgent-Eval addresses a practical research workflow: scientists need to examine whether a candidate gene has evidence related to a disease or phenotype, but the evidence is distributed across heterogeneous collections and must remain traceable to its source. The project preserves the existing Scientific RAG foundation and adds a reusable Agent Harness that controls tool execution, state, recovery, observability and evaluation.

This is not a chatbot-first project. The primary deliverable is an execution and evaluation platform for evidence-grounded scientific agents.

## Why this project exists

<div align="center">
<pre>
┌──────────────────────────────────────────────┐
│              Research question               │
└──────────────────────────────────────────────┘
↓
┌──────────────────────────────────────────────┐
│     Gene / phenotype / variant evidence       │
│          across multiple collections          │
└──────────────────────────────────────────────┘
↓
┌──────────────────────────────────────────────┐
│        Retrieval must be relevant             │
│    citations must resolve; actions controlled │
└──────────────────────────────────────────────┘
↓
┌──────────────────────────────────────────────┐
│       BioAgent-Eval = Scientific RAG         │
│         Harness + Evaluation Harness         │
└──────────────────────────────────────────────┘
</pre>
</div>

Example workflow:

<table align="center" border="0" cellpadding="5" cellspacing="0">
  <tr>
    <td align="center"><table border="1" cellpadding="10" cellspacing="0"><tr><td align="center"><strong>Research question</strong><br><small>candidate-gene evidence</small></td></tr></table></td>
    <td align="center">→</td>
    <td align="center"><table border="1" cellpadding="10" cellspacing="0"><tr><td align="center"><strong>Scientific retrieval</strong><br><small>BM25 / evidence search</small></td></tr></table></td>
    <td align="center">→</td>
    <td align="center"><table border="1" cellpadding="10" cellspacing="0"><tr><td align="center"><strong>Evidence passages</strong><br><small>source IDs and metadata</small></td></tr></table></td>
    <td align="center">→</td>
    <td align="center"><table border="1" cellpadding="10" cellspacing="0"><tr><td align="center"><strong>Agent Harness</strong><br><small>bounded runtime loop</small></td></tr></table></td>
    <td align="center">→</td>
    <td align="center"><table border="1" cellpadding="10" cellspacing="0"><tr><td align="center"><strong>Controlled tools</strong><br><small>validate • authorize • execute</small></td></tr></table></td>
  </tr>
  <tr>
    <td colspan="2" align="center">→</td>
    <td align="center"><table border="1" cellpadding="10" cellspacing="0"><tr><td align="center"><strong>Context &amp; checkpoint</strong><br><small>state and recovery</small></td></tr></table></td>
    <td align="center">→</td>
    <td align="center"><table border="1" cellpadding="10" cellspacing="0"><tr><td align="center"><strong>LLM decision</strong><br><small>tool or final answer</small></td></tr></table></td>
    <td align="center">→</td>
    <td align="center"><table border="1" cellpadding="10" cellspacing="0"><tr><td align="center"><strong>Evidence-grounded response</strong><br><small>citations and limitations</small></td></tr></table></td>
    <td align="center">→</td>
    <td align="center"><table border="1" cellpadding="10" cellspacing="0"><tr><td align="center"><strong>Evaluation</strong><br><small>tokens • latency • cost</small></td></tr></table></td>
  </tr>
</table>

## Architecture

```mermaid
flowchart TB
    subgraph Domain[Scientific reference application]
        DATA[Gene / association / heritability / expression data]
        RAG[Scientific RAG\nchunking • BM25 • dense/hybrid adapters • citations]
        DATA --> RAG
    end

    subgraph Harness[Reusable Agent Harness]
        MODEL[Model Adapter]
        LOOP[Bounded Runtime Loop]
        REG[Tool Registry + Pydantic schemas]
        EXEC[Tool Executor]
        CTX[Context Budget + Evidence Ledger]
        STATE[Checkpoint + SQLite idempotency]
        OBS[JSONL tracing + usage metrics]
        MODEL --> LOOP
        LOOP --> CTX
        LOOP --> REG
        REG --> EXEC
        EXEC --> STATE
        LOOP --> OBS
    end

    RAG --> EXEC
    EXEC --> MODEL

    subgraph Eval[Evaluation Harness]
        BENCH[Benchmarks]
        QUALITY[Retrieval / citation / grounding]
        EFF[Token / latency / cost / tool calls]
        FAULT[Fault injection / recovery]
        BENCH --> QUALITY
        BENCH --> EFF
        BENCH --> FAULT
    end

    OBS --> Eval
    RAG --> Eval
```

## What the Harness contributes

| Capability | Engineering value |
|---|---|
| Bounded Agent Runtime | Prevents unbounded loops with step, timeout and tool-call budgets |
| Tool Registry / Executor | Gives every tool one validation, permission, timeout and error boundary |
| Context Engineering | Limits context growth while preserving task state and evidence IDs |
| Cache and deduplication | Reduces repeated external calls and makes execution measurable |
| Durable idempotency | Replays completed side-effect results instead of invoking the handler twice |
| Checkpoint recovery | Resumes interrupted read-heavy research tasks from persisted state |
| Structured tracing | Makes every decision, tool call, error, latency and usage record auditable |
| Evaluation Harness | Tests answer quality, trajectory quality, efficiency and recovery separately |

## Scientific RAG foundation

The active corpus contains **159,607 passages across 8 collections**, covering gene information, genetic correlation, common and rare gene associations, partitioned heritability, clumped variant associations, WES gene associations and GTEx tissue expression.

The scientific workflow is evidence-first:

```mermaid
graph LR
    G[Candidate gene] --> A[Association evidence]
    G --> X[Expression evidence]
    G --> H[Heritability / genetic evidence]
    A --> S[Source metadata]
    X --> S
    H --> S
    S --> C[Claim-linked citation]
    C --> O[Qualified answer or evidence-based refusal]
```

The system does not claim that a retrieved association proves a clinically effective drug target. It supports early-stage evidence review, candidate prioritisation and hypothesis generation with explicit sources and limitations.

## Verified results

### Scientific (offline) RAG regression

- 100 end-to-end queries;
- 99% status accuracy;
- 96.67% TargetHit@10 on answerable queries;
- 100% citation correctness;
- 100% citation completeness;
- 100% unanswerable-refusal accuracy.

These are deterministic regression results, not production-level scientific correctness guarantees.

### Agent Harness infrastructure benchmark

100 deterministic tasks comparing baseline and optimized execution:

| Metric | Baseline | Optimized | Change |
|---|---:|---:|---:|
| Estimated tokens/task | 3,226.69 | 2,277.62 | **−29.41%** |
| Mean latency | 0.386s | 0.199s | **−48.55%** |
| External tool calls/task | 2.0 | 1.0 | **−50%** |
| Completion rate | 100% | 100% | preserved |

The benchmark uses a deterministic fixture model, so these numbers measure Harness execution overhead rather than hosted-model scientific quality.

### Hosted scientific evaluation

An OpenRouter `openai/gpt-4o-mini` run over 16 annotated regression tasks achieved:

- Citation Precision: **100%**;
- Citation Recall: **92.75%**;
- Deterministic Claim-Grounding Check: **100%**;
- Status accuracy: **100%**;
- Fallback rate: **0%**;
- Mean latency: **4.88s**;
- Mean tokens/task: **2,533.62**;
- Estimated total cost: **US$0.00631**.

The grounding score is a deterministic evidence-consistency check, not a claim that scientific reasoning is 100% correct. The hosted set is a small annotated regression set, not a production-scale benchmark.

### Reliability and test quality

- Controlled fault injection recovered **1/1** transient tool failures;
- **282 tests passed**;
- **55 subtests passed**;
- 3 raw-fixture tests are skipped when the private data root is not mounted;
- Static JSON, JSONL, CSV and HTML evaluation outputs are supported.

## CLI demo

### Offline evidence-grounded run

After configuring `BIOAGENT_DATA_ROOT` in the private-data section above:

```bash
export BIOAGENT_DATA_ROOT=/Users/your-user/Desktop/BioAgent/private_data

PYTHONPATH=src python -m bioagent run \
  --query "Analyse TCF7L2 and 2-hour glucose evidence" \
  --trace-path artifacts/traces/demo.jsonl \
  --checkpoint-dir artifacts/checkpoints
```

### Hosted model run

Create a local `.env` file and keep it out of version control:

```dotenv
LLM_PROVIDER=openrouter
LLM_API_KEY=your_key_here
LLM_MODEL=openai/gpt-4o-mini
```

Then run:

```bash
PYTHONPATH=src python -m bioagent run \
  --hosted \
  --llm-provider openrouter \
  --model openai/gpt-4o-mini \
  --query "Analyse BRCA1 and breast cancer evidence"
```

### Inspect, evaluate and fault-test

```bash
PYTHONPATH=src python -m bioagent trace \
  --trace-path artifacts/traces/demo.jsonl

PYTHONPATH=src python -m bioagent evaluate \
  --dataset data/evaluation/integration_regression.jsonl \
  --output artifacts/evaluation/agent.json

PYTHONPATH=src python -m bioagent fault-test \
  --scenario tool_timeout

python scripts/evaluate_agent_harness.py
```

## Installation and corpus preparation

### Private client-data mode

The repository does not require client raw files to be stored inside the public project. For an authorized local deployment, keep the private data and generated retrieval artifacts outside the repository:

```text
/Users/your-user/Desktop/BioAgent/private_data/
├── data/raw/          # private source files
└── artifacts/         # private chunks, manifests and indexes
```

Point the runtime at that directory before building or querying:

```bash
export BIOAGENT_DATA_ROOT=/Users/your-user/Desktop/BioAgent/private_data
```

Then rebuild the private corpus and index:

```bash
PYTHONPATH=src python scripts/prepare_api_corpus.py
PYTHONPATH=src python scripts/build_bm25_index.py
PYTHONPATH=src python -m bioagent run \
  --query "Analyse BRCA1 and breast cancer evidence"
```

`BIOAGENT_DATA_ROOT` changes the data and artifact root only. The Python source, chunk schema, citation validation, Agent Harness and Evaluation Harness remain unchanged. Processed chunks and indexes may still contain derived client content, so they should remain private unless redistribution is explicitly approved.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/api.txt
python -m pip install transformers huggingface-hub
export BIOAGENT_DATA_ROOT=/Users/your-user/Desktop/BioAgent/private_data
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-Embedding-0.6B', allow_patterns=['*.json', '*.txt', '*.model'])"
python scripts/prepare_api_corpus.py
python scripts/build_bm25_index.py
```

Run the complete regression suite with:

```bash
python -m pytest -q
```

## Repository map

```text
src/bioagent/       reusable Agent Harness runtime
src/retrieval/      corpus, routing and retrieval backends
src/chunking/       scientific data chunking and normalization
src/rag/            retrieval-to-answer pipeline
src/generation/    offline and OpenAI-compatible model providers
scripts/            corpus, benchmark and report runners
data/evaluation/    annotated, blind and retrieval benchmark datasets
artifacts/          generated indexes, traces and evaluation outputs
docs/project/       audit, limitations, roadmap and resume material
tests/              unit, integration, provider and Harness tests
```

## Reports and documentation

- [Agent Harness benchmark report](artifacts/evaluation/agent_harness_v1/report.html)
- [Hosted OpenRouter evaluation](artifacts/evaluation/hosted_openrouter.json)
- [Evaluation methodology and limitations](docs/project/BIOAGENT_EVAL_GAPS_AND_NEXT_STEPS.md)
- [Repository audit](docs/project/BIOAGENT_REPOSITORY_AUDIT.md)
- [Resume-ready project description](docs/project/BIOAGENT_RESUME_CONTENT.md)

## Scope and limitations

BioAgent-Eval is a portfolio-grade and research-oriented Agent Infrastructure Platform. It is designed for evidence-grounded, read-heavy scientific workflows. It is not presented as an autonomous clinical decision system or as proof that a gene is an effective therapeutic target.

Important limitations:

- the 100-task Harness comparison uses a deterministic fixture model;
- the hosted evaluation contains 16 annotated tasks;
- semantic entailment and independent human citation review remain separate from deterministic grounding checks;
- production deployment would still require enterprise authentication, multi-tenant authorization, OpenTelemetry infrastructure, queueing, rate limits and broader red-team evaluation.

## License and data use

Check the repository's data provenance and licensing records before redistributing source data or generated indexes. Do not commit API keys, private research data or unapproved customer information.
