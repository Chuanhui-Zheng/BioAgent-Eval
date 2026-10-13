# React frontend and RAG API

Run both processes from the same checkout. Python 3.10+ and Node.js 20+ are required.

For a fresh checkout, rebuild the seven-collection corpus and matching BM25 index first. The tokenizer validation requires a locally cached `Qwen/Qwen3-Embedding-0.6B` tokenizer; download its tokenizer files from Hugging Face before this step. No embedding model inference is needed for BM25.

```sh
python -m pip install -r requirements/api.txt transformers huggingface-hub
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-Embedding-0.6B', allow_patterns=['*.json', '*.txt', '*.model'])"
python scripts/prepare_api_corpus.py
python scripts/build_bm25_index.py
```

The preparation script builds all added collections before publishing the shared manifest, avoiding missing intermediate manifests on a clean checkout. Generated chunks and manifests are local build outputs; existing retrieval evaluation scores refer to their original corpus versions.

From the repository root:

```sh
python -m pip install -r requirements/api.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite forwards `/api` requests to the local Python server. The assistant uses retrieved evidence offline by default; entering an AIHubMix key enables hosted generation. Hosted failures fall back to offline evidence and include a limitation message. Keys must not be committed. Prototype analysis is labelled on each affected page. File selection does not parse matrices and enrichment is a sample preview. Gene fields and scores are shown as unavailable when missing, while zero scores are preserved. The seven-collection query service displays limitations, provider fallback and expandable source passages. Citation validation checks reference structure only, not scientific entailment.

`npm run build` checks TypeScript and builds the frontend. Production serving requires routing `/api` to the Python server separately.
