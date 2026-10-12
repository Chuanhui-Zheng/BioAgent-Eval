# Team Update Guide

## Summary

The original repository completed corpus preparation and BM25, dense, and
hybrid retrieval experiments. This update adds the formal offline RAG path:

```text
question -> retrieval -> context augmentation -> offline generation
         -> citation validation -> evaluation
```

The update keeps the existing history and data while adding reproducibility,
tests, phase reports, and a no-API demonstration.

## What changed and where

| Update | Location | Purpose |
|---|---|---|
| Installable project configuration | `pyproject.toml` | Makes `src/` packages installable |
| Reproducible base dependencies | `requirements.txt` | BM25 and offline RAG runtime |
| Test dependencies | `requirements-dev.txt` | Automated test environment |
| Optional embedding dependencies | `requirements-embed.txt` | Dense and hybrid retrieval only |
| Unified retrieval request/response service | `src/retrieval/service.py` | Typed retrieval and access boundaries |
| Retrieval diagnostics | `src/retrieval/diagnostics.py` | Corpus/index/environment checks |
| Portable dense device selection | `src/retrieval/dense_retriever.py` | CUDA, Apple MPS, or CPU fallback |
| Augmentation configuration | `config/augmentation.yaml` | Passage and context limits |
| Context package and evidence policy | `src/augmentation/` | Deduplication, entity narrowing, refusal |
| Generation configuration | `config/generation.yaml` | Offline provider and citation policy |
| Provider-neutral generation interface | `src/generation/provider.py` | Future LLM adapter boundary |
| Offline evidence generator | `src/generation/offline.py` | Deterministic evidence-only answers |
| Answer and claim schema | `src/generation/schema.py` | Structured output contract |
| Citation validator | `src/generation/validator.py` | Rejects missing/external citations |
| End-to-end pipeline | `src/rag/pipeline.py` | Runs and records the full RAG flow |
| Offline query demonstration | `scripts/query_rag_offline.py` | One-command local demo |
| RAG benchmark builder | `scripts/build_rag_benchmark.py` | Adds generation expectations |
| End-to-end evaluator | `scripts/evaluate_rag_offline.py` | Produces repeatable RAG metrics |
| End-to-end benchmark | `data/evaluation/rag_e2e.jsonl` | 100 evaluation questions |
| Automated tests | `tests/augmentation/`, `tests/generation/`, `tests/retrieval/`, `tests/end_to_end/` | New unit and integration coverage |
| Stage reports | `reports/phase_1_retrieval/` through `phase_4_evaluation/` | Results and error analysis |
| Project roadmap | `docs/PROJECT_STATUS_AND_ROADMAP.md` | Remaining tasks and priorities |

## Current verified results

- Remote baseline: 35 automated tests passed.
- Updated local version: 55 automated tests passed.
- Answerable BM25 TargetHit@10: 87/90 (96.67%).
- End-to-end answer/refusal status accuracy: 99%.
- Unanswerable refusal accuracy: 10/10.
- Structural citation correctness and completeness: 100%.

The citation scores check whether claims cite passages supplied in the context.
They do not yet prove semantic entailment or scientific correctness.

## How to reproduce

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
python scripts/build_bm25_index.py
python -m pytest -q
python scripts/query_rag_offline.py "What is the function of TCF7L2?"
```

Run the formal evaluations:

```bash
python scripts/evaluate_bm25.py \
  --dev-set data/evaluation/retrieval_test.jsonl \
  --output-dir artifacts/evaluation/bm25_test_reproduced \
  --top-k 10 --report-ks 1 3 5 10
python scripts/build_rag_benchmark.py
python scripts/evaluate_rag_offline.py
```

## Dense and hybrid decision

Dense and hybrid are not required to run the current offline demonstration.
They should be reproduced once before final delivery because the project asks
for comparison of at least two retrieval approaches. Dense index construction
is the expensive step; hybrid reuses both BM25 and dense indexes.

Historical benchmark artifacts are retained, but the current machine has not
completed a fresh dense encoding run. Do not describe those historical numbers
as newly reproduced results.

## Known limitations

- The offline generator is template-based rather than a fluent LLM.
- Citation evaluation is currently structural rather than semantic.
- Required fact fields and gold citation IDs are recorded but not fully scored.
- Gene identifier and location questions need intent-specific answer templates.
- Three answerable BM25 cases miss the grade-2 target at top 10.
- Tissue and cell evidence are not dedicated corpus collections.
- Collection filtering is simulated; it is not production authentication.
- Source release/version metadata are incomplete for some records.
- AIHubMix generation is available as an experimental provider with offline fallback.
- REST API, browser UI, Docker, CI, and broad hosted-model evaluation are pending.

## Next work by priority

1. Strengthen evaluation: score gold citations, required fields, numerical
   fidelity, answer relevance, blind questions, and human review.
2. Improve offline templates for identifiers, locations, comparisons,
   summaries, limitations, and evidence gaps.
3. Fix the three retrieval misses with numeric-field and phenotype/model-name
   normalisation; retune hybrid RRF only on development data.
4. Rebuild and reproduce dense/hybrid evaluation in a controlled environment.
5. Add an approved structured-output LLM adapter while retaining the offline
   provider as fallback.
6. Add FastAPI, a simple demo interface, Docker, CI, response logging, API
   documentation, and the final report.

## Suggested team ownership

| Workstream | Suggested focus |
|---|---|
| Evaluation | Gold citations, required fields, blind set, human rubric |
| Retrieval | Three misses, aliases, numeric lookup, dense/hybrid reproduction |
| Generation | Intent templates, LLM provider, structured repair and validation |
| Platform | API, demo UI, Docker, CI, logging and documentation |

## Repository hygiene

Never commit `.env`, API keys, `.venv`, caches, `*.egg-info`, downloaded models,
or generated indexes. Evaluation summaries may be committed when they include
the benchmark hash and configuration snapshot needed for reproducibility.
