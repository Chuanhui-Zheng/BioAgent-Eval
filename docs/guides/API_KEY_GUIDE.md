# Hosted LLM Providers and API Keys

Hosted generation works with **any OpenAI-compatible Chat Completions API**.
AIHubMix is now one preset among several; the offline evidence engine remains
the default and needs no key.

| Preset (`LLM_PROVIDER`) | Default base URL | Default model | Key |
|---|---|---|---|
| `openai` | https://api.openai.com/v1 | gpt-4o-mini | required |
| `aihubmix` | https://aihubmix.com/v1 | gpt-4o-mini | required |
| `deepseek` | https://api.deepseek.com/v1 | deepseek-chat | required |
| `openrouter` | https://openrouter.ai/api/v1 | openai/gpt-4o-mini | required |
| `anthropic` | https://api.anthropic.com/v1/ (OpenAI-compatible endpoint) | claude-sonnet-5-5 | required |
| `siliconflow` | https://api.siliconflow.cn/v1 | Qwen/Qwen3-32B | required |
| `ollama` | http://localhost:11434/v1 | qwen3:8b | not needed |
| `custom` | set `LLM_BASE_URL` | set `LLM_MODEL` | optional |

`GET /api/llm/providers` returns the same list. The model and base URL can be
overridden for every preset. Plain `http://` is accepted only for local model
servers (localhost, 127.0.0.1, host.docker.internal); remote endpoints must use HTTPS.
Presets that do not support `response_format=json_object` (Anthropic) are called
without it; the parser extracts the answer JSON and validates it either way.

Every provider returns the same claim-cited schema and passes the same citation
and numeric validation. A provider error, quota notice or invalid answer falls
back to the offline engine and the response says so (`provider: offline_fallback`).

## React app

Open the assistant panel, click the key icon, choose a provider, optionally edit
model / base URL, and paste the key. **Gene MoA → Independent annotated evaluation**
has the same selector. Keys are sent with each request and never stored or logged.

## REST API

```json
POST /api/rag/query
{"question": "What is the function of TCF7L2?",
 "llm_provider": "deepseek", "api_key": "...", "model": "deepseek-chat"}
```

Omit `llm_provider` and `api_key` for offline generation. `base_url` overrides
the preset (required for `custom`).

## Command line and evaluation scripts

```bash
cp .env.example .env      # then edit LLM_PROVIDER / LLM_API_KEY / LLM_MODEL
python scripts/query_rag.py "What is the function of TCF7L2?" --provider llm
python scripts/evaluate_blind.py --label deepseek --llm-provider deepseek --limit 25 \
    --judge-provider openai --judge-model gpt-4o-mini
```

`JUDGE_API_KEY` is used for the support judge when it differs from `LLM_API_KEY`.
Legacy `AIHUBMIX_API_KEY` / `AIHUBMIX_MODEL` / `AIHUBMIX_BASE_URL` variables are
still honoured when `LLM_API_KEY` is empty. Cost estimates use per-million-token
rates from `config/model_pricing.json`, e.g.
`{"gpt-4o-mini": {"input_usd_per_million": 0.15, "output_usd_per_million": 0.6}}`;
without rates the cost is reported as unavailable, never as zero.

## Streamlit demo

Select **Hosted LLM**, choose the provider, then enter model, base URL and key.

## Security

- `.env` is ignored by Git and must never be committed.
- Never paste a key into documentation, source code, screenshots, chat or commits.
- Confirm client approval before sending non-public corpus passages to a hosted provider.
- Revoke and replace a key immediately if it is exposed.
