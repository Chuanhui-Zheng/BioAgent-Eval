# Phase 4 Error Analysis

- Three answerable queries do not retrieve their grade-2 target in BM25 top 10. One is safely refused because the requested entity is absent from retrieved evidence; the other cases remain visible in per-query analysis. This produces 99% status accuracy rather than hiding the retrieval failure.
- The 100% citation and claim-support figures apply to the deterministic offline provider. A future LLM must be evaluated separately against human-reviewed claim support and cannot inherit these scores.
- No real workspace identity or authorization service exists. The measured isolation property is strict collection-boundary isolation inside the prototype.
- Tissue and cell evidence is not available as a dedicated corpus collection, so the system does not claim full coverage of those project requirements.
- Approximate financial cost is zero for the offline provider; hosted-model cost cannot be reported before a provider is approved.
