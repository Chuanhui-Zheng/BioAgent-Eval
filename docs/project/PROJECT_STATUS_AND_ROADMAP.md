# Project Status and Roadmap

## Status at this release

The project has a working, tested offline vertical slice:

```text
BM25 -> RetrieverService -> ContextBuilder
     -> OfflineEvidenceGenerator -> Citation Validator
```

Completed baseline capabilities:

- approved corpus ingestion, chunking, and metadata preservation;
- BM25, dense, and hybrid retrieval implementations and historical comparison;
- entity-aware routing and collection-boundary filtering;
- duplicate-free, budgeted, citation-resolvable context construction;
- deterministic evidence-only answers, limitations, qualification, and refusal;
- claim-linked citation validation;
- repeatable 100-query retrieval and end-to-end evaluation;
- automated unit/integration tests and four phase reports.

## Quality boundary

Current 100% citation metrics validate citation structure against supplied
context. They do not establish that every answer is relevant, complete, or
scientifically correct. The existing end-to-end evaluator does not yet enforce
all recorded gold citation IDs or required fact fields.

## Immediate quality work

1. Score citations against `allowed_citation_chunk_ids`.
2. Enforce `required_fact_fields` for each query type.
3. Check numerical fidelity for p-values, beta, Bayes factors, and correlations.
4. Add intent-specific relevance checks for function, identifier, location,
   association, correlation, comparison, and summary questions.
5. Add independent blind questions and a human scientific review rubric.
6. Expand adversarial refusal and collection-isolation cases.

## Retrieval optimisation

The answerable BM25 evaluation misses three targets:

- `test-rare-003`: numeric p-value lookup for `PHLDA1`;
- `test-ldsc-018`: additive-model naming for `AMD_add`;
- `test-ldsc-020`: phenotype normalisation for `AM_broad_int`.

Planned work includes numeric-field retrieval, identifier/alias normalisation,
tokenisation tests, development-only tuning, and fresh dense/hybrid index and
benchmark reproduction with recorded hardware and model revision.

## Generation roadmap

An experimental AIHubMix adapter now returns the existing structured schema,
requires claim citations, supports a controlled JSON repair attempt, and falls
back to the offline provider. A live TCF7L2 smoke test passed on 2026-09-27 with
validated citations, no fallback, and approximately 20.44 s end-to-end latency.
The next work is separate hosted-provider evaluation, provider-specific token
counting, and improved deterministic templates for identifiers, locations,
comparisons, summaries, conflicting evidence, limitations, and evidence gaps.

## Platform roadmap

- FastAPI query and health endpoints;
- simple browser or command-line demonstration interface;
- response/run logging with reproducibility metadata;
- Docker image and CI test workflow;
- API and deployment documentation;
- client-approved source/version metadata;
- final report and recorded demonstration.

## Dense and hybrid release gate

Dense and hybrid are optional for this initial v2 repository release but are
recommended before final submission. Run them once in a controlled environment
because the project requires comparison of at least two retrieval approaches.
Do not block normal team setup or the offline BM25 demo on the large model.
