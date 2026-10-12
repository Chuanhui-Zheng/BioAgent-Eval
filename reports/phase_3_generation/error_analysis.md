# Phase 3 Error Analysis

- The offline generator is intentionally extractive and template-based. It provides a safe reproducible baseline but does not offer the synthesis fluency of a selected LLM.
- Structural claim support proves that generated claims originate from cited passage fields; independent scientific or human review is still required.
- A future provider adapter must return the same structured contract and pass the existing validator. Provider-specific token counting and one controlled repair attempt should be added with that adapter.
