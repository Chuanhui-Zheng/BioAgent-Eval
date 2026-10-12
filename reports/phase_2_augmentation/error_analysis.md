# Phase 2 Error Analysis

- Entity narrowing is deliberately conservative and identifier-oriented. A future LLM query planner or approved ontology expansion may improve natural-language entity resolution.
- Current token accounting uses a deterministic character-based estimate, not a provider-specific tokenizer. It guarantees the configured estimate but must be replaced or calibrated when a generation model is selected.
- Provenance warnings cannot manufacture missing source versions; upstream association and LDSC citations should receive explicit release/version metadata when the client supplies it.
