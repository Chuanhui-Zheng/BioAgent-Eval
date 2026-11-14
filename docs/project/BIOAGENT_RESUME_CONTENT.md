# Resume Content — BioAgent-Eval

## One-line project description

**BioAgent-Eval — Scientific Agent Harness & Evaluation Platform:** Built a reusable, evidence-grounded Agent Runtime around a scientific RAG system for drug-discovery research workflows, with structured tool execution, context budgeting, retry/recovery, checkpointing, tracing and automated evaluation.

## Resume bullets

- Architected a Python Agent Harness with structured tool calling, Pydantic argument validation, sync/async execution, bounded loops, timeouts, retry policies, cache-backed duplicate detection, permission controls, durable SQLite idempotency for side-effecting tools, checkpoint save/resume and JSONL execution traces.
- Integrated an eight-collection Scientific RAG corpus containing **159,607 chunks**, preserving BM25/Dense/Hybrid retrieval, evidence metadata, citation resolution and deterministic grounding validation.
- Built an Evaluation Harness spanning retrieval quality, answer status, citation precision/recall, required-fact and numeric policies, claim grounding, latency, token usage and fallback tracking.
- Ran a 100-task deterministic infrastructure benchmark: context budgeting and caching reduced estimated fixture-model token consumption by **29.41%**, mean latency by **48.55%**, and external tool executions by **50%**, while maintaining a **100% completion rate**.
- Implemented controlled fault injection with retry and recovery measurement; the current smoke benchmark recovered **1/1 injected transient failures**.
- Validated a real OpenRouter hosted run over 16 annotated scientific tasks with **0% fallback**, **100% status accuracy**, **100% citation precision**, **92.75% citation recall**, **100% claim grounding**, **4.88s mean latency**, **2,533.62 mean tokens/task**, and **US$0.00631 estimated total cost**.
- Added permission and idempotency guards for side-effecting tools, explicit treatment of tool output as untrusted data, and regression coverage; the Python suite passes **282 tests and 55 subtests**.

## Interview-safe wording

Say “deterministic infrastructure benchmark” for the 29.41% token and 48.55% latency improvements. Say “16-task hosted evaluation” for the OpenRouter results. Do not present either result as a statistically conclusive production-agent quality improvement.
