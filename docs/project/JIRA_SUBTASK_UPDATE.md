# Jira Subtask Update

Implementation is maintained on branch `feature/offline-rag-phases-1-4`.

## Recommended status

| Issue | Status | Reason |
|---|---|---|
| CS46-10 Design the Core RAG Workflow | Done | The typed Retrieve → Augment → Generate → Validate pipeline is implemented and tested. |
| CS46-11 Implement Prompt and Context Construction | Done for MVP | Context selection, evidence budgets, prompt policy, structured evidence payloads, and refusal context are implemented. Provider-specific token counting remains a later optimisation. |
| CS46-12 Implement Grounded Answer Generation | Done for MVP | Offline generation and an AIHubMix structured-output provider with automatic offline fallback are implemented. |
| CS46-13 Implement Source Citation Generation | Done for MVP | Claim-linked chunk citations, citation registry resolution, and context-external citation rejection are implemented. Full semantic citation judging remains future evaluation work. |
| CS46-14 Support Required Question Types | In Progress | Function and association queries have a working baseline, but comparison, dossier summary, identifier, genomic-location, conflict, and evidence-gap answers still need specialised evaluation and templates. |
| CS46-15 Implement Refusal and Qualification Mechanism | Done | Missing evidence, entity mismatch, personal medical questions, non-significant evidence, invalid hosted output, and provider failure are handled through refusal, qualification, validation, or offline fallback. |

## Shared verification note

```text
Implementation branch: feature/offline-rag-phases-1-4

Current verification:
- 55 automated tests pass.
- BM25 retrieval, context augmentation, offline generation and citation validation pass.
- AIHubMix structured-output parsing, invalid-citation rejection and offline fallback pass with mocked API tests.
- A live TCF7L2 AIHubMix smoke test returned a cited answer with validation pass and no fallback.
- Observed live smoke-test latency was approximately 20.44 seconds.

External API scope:
- The real key is loaded only from the local .env file.
- The key is never stored in source code or Git.
- The real key is kept only in the ignored local .env file and can be rotated without code changes.
```

## Suggested CS46-14 follow-up subtasks

1. Add intent-specific answers for gene identifiers and GRCh37 locations.
2. Add structured comparison and evidence-conflict summaries.
3. Add target-dossier and evidence-gap response formats.
4. Add gold required-field, numerical-fidelity and semantic citation scoring.
5. Evaluate the hosted provider separately from the offline baseline.
