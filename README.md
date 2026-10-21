# CS46 Evidence-Grounded Scientific RAG Assistant

A simple chat interface for exploring the currently supplied scientific evidence. Ask about genes, phenotypes, variants, tissue expression or evidence gaps. The assistant retrieves source passages, gives cited answers where supported, and qualifies or refuses answers when the evidence is insufficient. The interface is a test surface for the RAG system, not a separate analysis portal.

## Evidence used by the chat

The active retrieval corpus has eight collections (159,607 passages): gene information, 2hrI genetic correlation, 2hrG common and rare gene associations, 2hrG LDSC partitioned heritability, 2hrG clumped variant associations, 2hrG WES gene associations, and GTEx RNA/protein expression. Seven come from the client's October 2026 `newdata` delivery; partitioned heritability comes from the earlier supplied files and is kept because the retrieval and end-to-end benchmarks (dev, test and blind) are labelled on all eight collections. The active collection list is in [`config/retrieval.yaml`](config/retrieval.yaml). 2hrFFA GWAS and nearest-gene files are not in the chat corpus.

The source files needed for the chat are included under `data/raw/` in the repository. You do not need to separately download or merge the client's ZIPs. A downloaded source ZIP does not contain the generated BM25 index; the first-time setup below builds it from the included sources. The workspace dropdown demonstrates retrieval isolation between all evidence, annotations/expression, and genetic associations. It is not user authentication.

## Download ZIP and run locally

Download the latest code from this branch or from `main` once these changes have been merged: **Code → Download ZIP**. Extract it, open a terminal in the directory containing `server.py`, and keep the original folder structure. This private repository requires GitHub access to download; Git and a token are not needed to run the ZIP.

Prerequisites: Python 3.12+ and Node.js 20+ with npm. First setup needs internet access to install dependencies and download tokenizer files, plus several GB of disk space. macOS with Python 3.13 has been tested. On Windows use `python` for `python3` below.

### 1. Prepare the backend

macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/api.txt transformers huggingface-hub
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-Embedding-0.6B', allow_patterns=['*.json', '*.txt', '*.model'])"
python scripts/prepare_api_corpus.py
python scripts/build_bm25_index.py
```

Windows PowerShell: create and activate the environment with `python -m venv .venv` and `.\.venv\Scripts\Activate.ps1`, then run the `python` commands above. Stop if preparation reports an error; a partial index cannot safely serve the chat. Tokenizer download does not fetch the model weights. Rebuild only if source files or processing rules change.

### 2. Start the backend

In the project root with `.venv` active:

```sh
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`. Open <http://127.0.0.1:8000/api/health> and check `status: healthy` with eight collections and `total_chunks: 159607`. Keep this terminal running.

### 3. Start the chat UI

In a second terminal, from the same project root:

```sh
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite, usually <http://127.0.0.1:5173>. On subsequent launches, start the backend and frontend; skip installation and corpus preparation. Press Ctrl+C in each terminal to stop.

## How to use the chat

Start with a suggested question or type your own. Example: “What evidence links ADCY5 to 2-hour glucose?” The first three cited claims appear as short evidence highlights; expand **Read full answer** for the complete response, and expand any source to inspect its indexed passage and metadata. Highlights are excerpts, not an additional scientific judgement. The answer shows its status, retrieved-passage count, provider and elapsed time; limitations are displayed separately. Choose an evidence scope before a question to demonstrate collection filtering. Changing scope shows that scope's separate chat history so responses from different scopes are not mixed.

The left sidebar saves up to 20 conversations per evidence scope in this browser. Use **New chat** to start another conversation, select a previous one to revisit its answers and citations, or use the trash icon to delete it. History is local to this browser and is not shared with teammates or the server. Your optional provider API key is not saved in conversation history.

Without an API key, generation uses local evidence excerpts. Open **Model settings** to use **AIHubMix**, **OpenAI**, **Anthropic (Claude)**, **Google (Gemini)** or **Custom (OpenAI-compatible URL)** with your own API key:

1. Install hosted-generation dependencies: `python -m pip install -r requirements/llm.txt` and restart the backend.
2. Select the provider and enter a key issued by that provider. Switching provider clears the previous key. For **Custom**, also enter the provider's OpenAI-compatible base URL (for example a relay such as `https://api.fenno.ai/v1`, or a local server such as `http://localhost:11434/v1`); you can type a model ID directly if the endpoint does not list models.
3. Click **Load models**, then select a model from the **Model ID** dropdown. No model is prefilled or automatically selected. Changing the provider or API key clears the list and selection; load models again. The returned list may be paginated and may include non-chat models; choose a text-generation model available to your account. Gemini's list is filtered to models supporting `generateContent`.
4. Click **Test connection**. This sends a small prompt, may incur API charges, and checks connectivity—not scientific quality. ChatGPT, Claude and Gemini chat subscriptions do not themselves configure API access here.
5. Ask a question. The app retrieves local evidence first, then sends the question and selected passages to your chosen provider for synthesis. Answers still pass the existing citation and numerical checks. Invalid or unavailable hosted answers fall back to local excerpts, visibly labelled `offline_fallback`.

Keys are kept only in page memory, sent through the backend for model discovery, connection tests and questions, and cleared on refresh. They are not written to conversation history or application run logs. Use HTTPS when deploying beyond localhost; do not commit keys to `.env` files. Preset providers use fixed hosts. **Custom** sends your key and the retrieved passages to the base URL you enter, so only use an endpoint you trust; the backend accepts only `https://` URLs (or `http://` on localhost) without embedded credentials. The native integrations use [OpenAI Responses](https://developers.openai.com/api/reference/python/resources/responses/methods/create), [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create) and [Gemini generateContent](https://ai.google.dev/api/generate-content). AIHubMix retains its existing OpenAI-compatible interface. Azure OpenAI and Vertex AI credentials are not supported by these direct-provider presets.

Provider payloads, failures, fallback and credential isolation have automated fixture tests; actual key validity, billing and model availability must be checked with your own account. Citation and numeric validation do not prove that a scientific interpretation is correct; verify claims against source passages.

## Tests and advanced work

```sh
python -m pip install -r requirements/dev.txt
python -m pytest -q
cd frontend
npm run test
npm run build
```

The repository retains research/evaluation scripts, benchmark questions and structured-analysis code for development. Keyword (BM25) retrieval is the default chat mode, selected on development questions only; see [Retrieval tuning](reports/phase_5_retrieval_tuning/README.md). Set `RAG_RETRIEVAL_METHOD` to `bm25_rerank` (BAAI/bge-reranker-base cross-encoder, tuned settings in `config/retrieval.yaml`), `dense`, `hybrid` or `hybrid_rerank` to try the alternatives; dense/hybrid need `requirements/embed.txt` and an index from `python scripts/build_dense_index.py --resume`, and missing components fall back to BM25 (reported by `/api/health` under `retrieval`). The API is documented at <http://127.0.0.1:8000/docs>.

For Docker, run `docker compose up --build`; its first API launch prepares the corpus and index. Docker startup has not been verified on every platform.

## Quality evaluation

- **Frozen blind benchmark:** `data/evaluation/blind/blind_e2e_v1.jsonl` (40 questions, SHA-256 in its manifest; never used for tuning). Run `python scripts/evaluate_blind.py --label offline`. For a hosted model put `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` (and `LLM_BASE_URL` for `custom`) in `.env`, then add `--llm-provider custom --limit 25 --judge-provider custom --judge-model <model>`. Reports, an LLM support-judge summary and a human review sheet are written to `reports/blind_v1/<label>/`; score them with [the rubric](reports/blind_v1/HUMAN_REVIEW_RUBRIC.md).
- **Metrics:** status/refusal accuracy, gold-citation precision and recall, required facts and exact numbers, claim grounding (every number and identifier in a claim must appear in its cited passage), optional LLM-judge support labels, fallback rate, latency and cost.
- **Retrieval tuning:** `python scripts/tune_retrieval.py --no-dense` (development sets only; refuses test/blind files) and `python scripts/evaluate_retrieval_methods.py --no-dense` (frozen test sets).

## Troubleshooting

- If port 8000 is occupied, choose another port for Uvicorn and set `VITE_API_TARGET=http://127.0.0.1:PORT` in `frontend/.env.local`, then restart Vite.
- If the backend reports a manifest or index mismatch, rerun `prepare_api_corpus.py` and `build_bm25_index.py` in that order from this source directory.
- If the tokenizer download fails, check internet access and rerun it before preparation.
- If the UI says “Backend unavailable”, keep the backend terminal open and check its error output.
