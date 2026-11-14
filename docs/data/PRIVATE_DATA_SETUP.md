# Private Data Setup

Client-provided raw files must not be committed to the public repository. Keep the source data and its derived retrieval artifacts in a private data root, for example:

```text
BioAgent/
├── BioAgent-Eval/       # public code repository
└── private_data/        # private, local or controlled storage
    ├── data/raw/
    └── artifacts/
```

Set the runtime root before corpus preparation or querying:

```bash
export BIOAGENT_DATA_ROOT=/Users/your-user/Desktop/BioAgent/private_data
```

Build the private processed corpus and BM25 index:

```bash
PYTHONPATH=src python scripts/prepare_api_corpus.py
PYTHONPATH=src python scripts/build_bm25_index.py
```

The current pipeline produces eight validated collections and preserves the existing chunk schema, citation metadata, manifests and index validation. The private build should report 159,607 chunks for the current corpus.

When the private data root is mounted, the data-dependent chunking tests can be run against the authorized files. Without that private root, those tests are intentionally skipped so the public repository never needs to contain the client raw data.

Important:

- A processed chunk can still contain client-derived text and is not automatically public.
- Keep raw files, chunks, manifests containing source hashes and indexes under the same access policy unless redistribution is approved.
- Do not put API keys or private data paths containing sensitive identifiers into committed files.
- Before publishing a repository, inspect both the current tree and Git history for raw and derived data.
