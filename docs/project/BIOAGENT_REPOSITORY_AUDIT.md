# BioAgent-Eval Repository Audit

**Audit date:** 2026-11-13  
**Scope:** existing repository before Agent Harness migration

## Current implementation

| Module | Observed implementation | Decision | Next change |
|---|---|---|---|
| Scientific RAG | `src/chunking`, `src/retrieval`, `src/augmentation`, `src/rag/pipeline.py`; BM25 is available and Dense/Hybrid/Rerank implementations are present | Keep | Expose retrieval through Agent tools without changing corpus or index formats |
| LLM API | `src/generation` supports offline evidence generation plus AIHubMix, OpenAI, Anthropic, Gemini and OpenAI-compatible providers | Keep | Add a provider-neutral Model Adapter boundary |
| Evaluation Harness | Retrieval benchmarks and metrics in `src/retrieval`; annotated answer evaluation and grounding checks in `src/analysis/evaluation.py`; runners under `scripts/` | Keep and integrate | Consume Agent traces and report execution/efficiency metrics |
| Agent Harness | No independent runtime, tool registry, checkpoint, retry or trace package existed | Add | `src/bioagent/` provides the first minimal, mockable runtime |
| Frontend | `frontend/` is a React/Vite chat app; Compose and CI build it | Remove | Keep the API and test imports; use Python CLI and static reports |
| Deployment | Python API Docker image and Compose API service exist; CI runs pytest | Keep | Remove web service and Node setup; use `bioagent` container user |

## Existing evaluation capabilities

- Retrieval: TargetHit, Recall, nDCG, MRR and routing precision/recall.
- Answer evaluation: expected status, gold citation precision/recall, required facts and numbers, prohibited phrases, deterministic claim grounding and optional LLM support judging.
- Operational data: retrieval method, latency, provider, fallback usage and configured-token cost estimates when provider usage is available.
- Current limitation: there was no standard Agent execution trace schema, tool-call metric, checkpoint format or controlled fault-injection runner.

## Migration boundary

The first Harness implementation deliberately wraps the existing retrieval service and context builder. It does not replace the RAG pipeline, change corpus data, claim new benchmark results, or require a real API key. The default CLI demo uses a deterministic offline model adapter and is a smoke/demo path, not an LLM quality benchmark.

## Risks and follow-up

1. RAG index startup is comparatively heavy; CLI and service entry points should share a lazy factory rather than duplicate loading logic.
2. Provider usage is authoritative only when the provider returns usage metadata; estimates must remain explicitly marked.
3. Checkpoint resume needs idempotency policies before side-effecting tools are enabled.
4. Agent metrics require an independently annotated dataset; existing RAG labels must not be treated as Agent ground truth.
