# Formal RAG Phases 1–4 Design

**Project:** CS-46 Evidence-Grounded Scientific RAG Assistant
**Date:** 2026-09-22
**Status:** Approved design, pending written-spec review
**Scope:** Formal retrieval, augmentation, generation, and end-to-end evaluation

## 1. Objective

Extend the existing chunking and retrieval experiment into a reproducible, evidence-grounded RAG pipeline. The implementation must preserve collection boundaries, attach every factual claim to approved evidence, qualify or refuse unsupported questions, and produce reproducible metrics and a report for every phase.

The implementation will not select or require a hosted generation API. Generation will use a provider-neutral interface and an offline evidence generator that works without credentials. A future approved local model or hosted API can be added without changing retrieval, augmentation, validation, or evaluation contracts.

## 2. Current Baseline

The supplied project contains:

- 41,103 unique chunks across four collections;
- BM25, Qwen3-Embedding-0.6B dense retrieval, and RRF hybrid retrieval;
- 20 development queries and a frozen 100-query retrieval test set;
- 100 manual review decisions;
- retrieval-only evaluation reports.

The recorded test baseline is:

| Method | Recall@10 | nDCG@10 | MRR@10 | Mean latency |
|---|---:|---:|---:|---:|
| BM25 | 0.870 | 0.8445 | 0.8350 | 0.0409 s |
| Dense | 0.780 | 0.7137 | 0.7169 | 0.1596 s |
| Hybrid RRF | 0.880 | 0.8272 | 0.8195 | 0.2214 s |

The local copy does not contain serialized indexes and the active Python environment lacks some retrieval dependencies. There is no context builder, generator, end-to-end pipeline, packaging metadata, API, UI, or container configuration.

## 3. Architecture

The pipeline is divided into four independently testable stages:

```text
Question
  -> Retrieve: route, isolate, search, normalize passages
  -> Augment: deduplicate, enforce budget, classify evidence, build context
  -> Generate: produce structured claims and citations, validate output
  -> Evaluate: score retrieval, support, citations, abstention, isolation, latency
```

Each stage communicates through typed data contracts rather than unlabelled text. Collection restrictions are checked at retrieval and checked again during context construction. Generation may cite only passage identifiers included in the context package.

## 4. Project Layout

```text
config/
  retrieval.yaml
  augmentation.yaml
  generation.yaml
  evaluation.yaml
src/
  retrieval/
  augmentation/
  generation/
  rag/
tests/
  retrieval/
  augmentation/
  generation/
  end_to_end/
reports/
  phase_1_retrieval/
  phase_2_augmentation/
  phase_3_generation/
  phase_4_evaluation/
artifacts/
  indexes/
  evaluation/
  runs/
```

Every phase report directory contains:

```text
README.md
metrics.json
test_results.txt
error_analysis.md
config_snapshot/
```

## 5. Phase 1 — Formal Retrieve

### 5.1 Responsibilities

- Preserve the existing BM25, dense, and hybrid implementations.
- Add typed `RetrievalRequest`, `RetrievalResponse`, and `RetrieverService` contracts.
- Separate caller-authorized collections from router-suggested collections. The effective search boundary is their intersection; routing can narrow authorization but can never expand it.
- Return normalized passages with rank, score, component scores, route decision, source metadata, citation data, latency, and retrieval configuration.
- Validate chunk hashes, index metadata, dense dimensions, document counts, and embedding model revision at startup.
- Provide explicit diagnostics for missing dependencies, indexes, or model files.
- Make the project installable and provide stable commands for tests, index checks, retrieval evaluation, and smoke queries.

### 5.2 Retrieval Policy

BM25 remains the precision-oriented baseline for identifiers and highly specific terms. Hybrid remains the recall-oriented option for cross-collection and semantic queries. The system will not declare one method universally best; method comparisons are reported by query type.

Automatic fallback is disabled by default. If an explicitly configured fallback occurs, it must be included in the response diagnostics and run manifest.

### 5.3 Acceptance Criteria

- Frozen 100-query Hybrid Recall@10 is at least 0.88.
- Frozen 100-query BM25 nDCG@10 is at least 0.8445.
- Router collection recall is 1.00.
- Unauthorized collection results are zero.
- All chunk and index validation checks pass.
- Existing tests and new service tests pass in the documented environment.

## 6. Phase 2 — Augmentation

### 6.1 Context Contract

`ContextBuilder` consumes a `RetrievalResponse` and returns a structured `ContextPackage` containing:

- normalized question;
- authorized and routed collections;
- retrieval configuration and run identifiers;
- ordered evidence passages;
- a citation registry keyed by chunk ID;
- an evidence-status recommendation;
- detected limitations and evidence gaps;
- token-budget accounting;
- augmentation diagnostics.

### 6.2 Context Construction

The builder will:

- reject passages outside the authorized collection boundary;
- remove exact duplicate chunk IDs;
- retain rank and provenance;
- select evidence under a configured token budget;
- retain exact numeric values from metadata;
- keep conflicting evidence when it is relevant;
- avoid inferring unavailable biological causality;
- expose missing source-version fields as provenance warnings.

### 6.3 Evidence Status

The builder recommends one of:

- `answer`: sufficient in-scope supporting evidence exists;
- `qualified`: evidence is partial, conflicting, non-significant, or limited;
- `refuse`: the request is outside corpus scope or lacks the required evidence layer.

The policy includes the documented guardrails for individual medical values, non-significant LDSC and rare-variant results, missing function summaries, and unsupported causal claims.

### 6.4 Acceptance Criteria

- Unauthorized passages in context: zero.
- Citation registry resolvability: 100%.
- Token-budget violations: zero.
- Duplicate chunk IDs: zero.
- Numeric metadata preservation on evaluation fixtures: 100%.
- Evidence-status policy tests pass for supported, partial, conflicting, and out-of-scope examples.

## 7. Phase 3 — Generation

### 7.1 Provider-Neutral Interface

`GeneratorProvider` accepts a `ContextPackage` and returns a structured draft. No vendor SDK is imported by the core pipeline. Provider-specific adapters can be added later behind this contract.

The initial implementation includes `OfflineEvidenceGenerator`, which creates evidence summaries and claim-linked citations entirely from the supplied context. It is a reproducible offline baseline, not a substitute presented as a large language model.

### 7.2 Answer Contract

The answer object contains:

- `status`: `answer`, `qualified`, `refuse`, or `error`;
- answer text;
- structured claims;
- cited chunk IDs for every material factual claim;
- limitations and evidence gaps;
- model/provider and prompt-policy version;
- validation diagnostics.

### 7.3 Validation

The validator will ensure:

- every cited chunk exists in the context package;
- every cited chunk belongs to an authorized collection;
- material factual claims have at least one citation;
- structured output conforms to the answer schema;
- unsafe unsupported causal or individual medical interpretations are rejected or qualified.

A provider output may receive one controlled repair attempt. If it remains invalid, the pipeline returns a safe error or refusal and never displays fabricated citations.

### 7.4 Acceptance Criteria

- Invalid displayed citations: zero.
- Uncited material claims: zero on the evaluation fixtures.
- Structured output validity: 100%.
- Offline-baseline factual support: at least 95%.
- `answer`/`qualified`/`refuse` status accuracy: at least 90%.

## 8. Phase 4 — End-to-End Evaluation

### 8.1 Benchmark Separation

The existing 20-query development set is used for threshold and policy tuning. The existing 100-query retrieval test set remains frozen and is not used for tuning.

Generation evaluation extends the benchmark schema with:

- expected evidence status;
- allowed citation chunk IDs;
- required facts or exact numeric values;
- prohibited unsupported claims;
- workspace or collection constraints.

These annotations are maintained separately from the existing retrieval labels.

### 8.2 Metrics

The end-to-end harness reports:

- retrieval Recall, nDCG, MRR, and routing metrics;
- context coverage and token-budget compliance;
- citation correctness, completeness, and resolvability;
- claim factual support;
- evidence-status confusion matrix and accuracy;
- workspace/collection isolation failures;
- latency by stage and end to end;
- provider, model, prompt-policy, configuration, and corpus versions.

Results are reported overall and sliced by query type. Every aggregate report links to per-query results and an error analysis.

### 8.3 Acceptance Criteria

- Citation correctness: at least 95%.
- Citation completeness: at least 95%.
- Workspace/collection isolation: 100%.
- The complete evaluation is reproducible from documented commands.
- Every run writes an immutable run manifest and per-query JSONL output.
- BM25 and Hybrid end-to-end results are compared without selecting a winner from one aggregate metric.

## 9. Testing Strategy

Unit tests cover schemas, routing boundaries, filter behavior, context selection, evidence rules, offline generation, citation validation, and metrics. Integration tests exercise each adjacent stage boundary. End-to-end tests cover representative supported, qualified, refused, conflicting, cross-collection, and isolation cases.

Regression tests preserve all cases that expose a bug. Test fixtures are small and deterministic; full-corpus evaluation is a separate command. Tests must not require a network connection or API credential unless explicitly marked as optional provider tests.

## 10. Failure Handling

- Missing index, dependency, or incompatible metadata: fail at startup with an actionable error.
- Empty authorized collection intersection: return refusal without searching other collections.
- Missing or malformed provenance: retain the passage only when allowed by policy, attach a warning, and prevent a falsely complete citation.
- Context budget exhausted: return the highest-priority valid evidence and record excluded passage IDs.
- Provider unavailable: return a typed error unless an explicit fallback is configured.
- Invalid provider citation: attempt one controlled repair, then fail safely.
- Isolation violation: terminate the answer, record the violation, and fail the relevant test/evaluation run.

## 11. Reporting and Reproducibility

Each phase report records scope, implementation summary, commands, environment, configuration snapshot, tests, metrics, threshold results, failed cases, limitations, and the next phase's dependencies. Metrics are generated from evaluation artifacts rather than manually copied where practical.

Quality thresholds are gates, not targets to be achieved by modifying the frozen test set. Any unmet threshold remains visible with an explanation and remediation plan.

## 12. Explicit Non-Goals for These Four Phases

- Selecting a production generation vendor.
- Uploading approved corpus content to an unapproved external service.
- Building a web interface or production REST API.
- Implementing enterprise authentication or production authorization.
- Claiming tissue or cell support without corresponding corpus data.
- Treating association or genetic correlation as proven causality.
- Training or fine-tuning a foundation model.

## 13. Repository Note

The supplied project directory is not currently a Git repository. This design can be versioned as a project artifact, but a Git commit cannot be created until the project is restored inside its repository or initialized under the team's agreed source-control workflow.
