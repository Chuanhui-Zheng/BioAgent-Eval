# Remaining Work and Delivery Plan

## Current baseline

The project currently provides a reproducible BM25-based RAG pipeline with
context augmentation, deterministic offline generation, an experimental
AIHubMix generator, claim-linked citations, validation, refusal/qualification,
and automatic offline fallback. All 55 automated tests pass. One live AIHubMix
smoke test has passed, but this is not yet broad scientific validation.

## P0 — Scientific quality and final evaluation

- [ ] Create a frozen blind test set of 30–50 new questions from the approved
  corpus. Split questions and labels, not the searchable corpus.
- [ ] Have a team member who did not tune the retriever annotate expected
  status, gold chunk IDs, required facts, exact numerical values, and prohibited
  claims.
- [ ] Score citations against gold evidence IDs instead of only checking that
  they exist in the supplied context.
- [ ] Enforce required-field and numerical-fidelity checks for p-values, beta,
  Bayes factors, genetic correlations, identifiers, and genomic coordinates.
- [ ] Run the AIHubMix provider on a representative 20–30 question sample and
  report answer quality, refusal accuracy, citation support, latency, fallback
  rate, errors, and approximate cost/quota use separately from the offline
  baseline.
- [ ] Add a human review rubric for correctness, relevance, completeness,
  citation support, and clarity.

## P1 — Retrieval optimisation and comparison

- [ ] Fix the three known BM25 misses: numeric p-value lookup for `PHLDA1`,
  additive-model naming for `AMD_add`, and phenotype normalisation for
  `AM_broad_int`.
- [ ] Add regression tests for aliases, underscores, phenotype/model names, and
  numeric field lookup.
- [ ] Build the dense index once in a controlled environment and record model
  revision, hardware, index time, index size, and latency.
- [ ] Reproduce BM25, dense, and hybrid results on the same frozen benchmark.
- [ ] Tune hybrid RRF or an optional reranker only on development questions;
  keep the blind test frozen.

## P2 — Required question types

- [ ] Add intent-specific answers for gene identifiers and GRCh37 locations.
- [ ] Add structured comparisons between targets, variants, and phenotypes.
- [ ] Add evidence summary, conflicting-evidence, limitation, and evidence-gap
  response formats.
- [ ] Add target-dossier summarisation when suitable approved dossier data are
  available.
- [ ] Do not claim tissue/cell support until dedicated approved evidence is
  supplied and evaluated.

## P3 — Product packaging

- [ ] Add FastAPI health and query endpoints with documented request/response
  schemas.
- [ ] Add a simple demonstration interface showing retrieved evidence, final
  answer, citations, limitations, provider, fallback state, and latency.
- [ ] Add structured response logging without storing API keys or sensitive
  client data.
- [ ] Add Docker configuration and a CI workflow that runs the offline tests.
- [ ] Add provider timeout, rate-limit, retired-model, quota, and malformed-JSON
  integration tests.
- [ ] Confirm client approval before sending any non-public corpus passage to a
  hosted provider.

## P4 — Final project delivery

- [ ] Agree final acceptance thresholds with the team/client. Suggested minimum
  targets are at least 95% gold-citation correctness/completeness, at least 90%
  refusal accuracy, zero accepted context-external citations, and exact required
  numerical values on the blind set.
- [ ] Produce the final architecture, retrieval comparison, evaluation, risk,
  limitation, and reproducibility report.
- [ ] Prepare a short repeatable demonstration covering one supported question,
  one qualified answer, one refusal, citation traceability, and provider
  fallback.
- [ ] Complete Jira evidence links, team review, pull request review, and final
  release tagging.

## Data decision

The current approved corpus is sufficient for retrieval, citation, refusal,
and hosted-generation evaluation. Keep the full corpus searchable and split the
question set into development, regression, and blind test groups. Additional
data are only required to claim support for missing areas such as tissue/cell
evidence, richer multi-omics comparisons, or realistic target dossiers.
