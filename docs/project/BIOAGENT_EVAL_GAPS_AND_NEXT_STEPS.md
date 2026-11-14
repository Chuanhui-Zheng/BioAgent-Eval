# BioAgent-Eval Evaluation and Interview Readiness

## Verified results

- Scientific corpus: 159,607 chunks across eight collections.
- Existing RAG evaluation: 100-query end-to-end run with 99% status accuracy, 96.67% answerable retrieval TargetHit@10, 100% citation correctness, and 100% citation completeness.
- Harness infrastructure benchmark: 100 deterministic tasks; Optimized configuration reduced estimated fixture-model tokens/task from 3,226.69 to 2,277.62 (29.41%), mean latency from 0.386s to 0.199s (48.55%), and external tool calls/task from 2.0 to 1.0 (50%). Cache hit rate was 50%; all 100 tasks completed.
- Controlled fault test: one injected transient failure recovered successfully (1/1). This is a smoke test, not a production reliability confidence interval.
- Hosted OpenRouter evaluation: 16 annotated tasks, 0% fallback, 100% status accuracy, 100% citation precision, 92.75% citation recall, 100% claim grounding, 4.88s mean latency, 2,533.62 mean tokens/task and US$0.00631 estimated total cost.
- Regression suite: 282 tests and 55 subtests passed.

## Claims that remain explicitly limited

- The 100-task Harness comparison uses a deterministic fixture model and estimated tokens; it is infrastructure evidence, not hosted-model answer-quality evidence.
- The hosted evaluation is 16 tasks, not a 100-task hosted Agent quality benchmark.
- No production claim is made for prompt-injection resistance, long-term memory, multi-tenant authorization, distributed execution, or side-effecting tool safety.

## Interview-readiness gap list

The highest-value remaining interview topics are trajectory-level evaluation with repeated trials (pass@k/pass^k), calibrated human/LLM judges, red-team prompt-injection cases, approval and permission policies, OpenTelemetry-style spans, concurrency/queueing, circuit breakers/rate limits, long-term memory, and a 100+ task hosted benchmark with reproducible pricing.
