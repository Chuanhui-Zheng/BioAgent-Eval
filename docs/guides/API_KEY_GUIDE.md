# Hosted LLM Providers and API Keys

The offline evidence engine is the default and needs no key. Hosted generation is
available in the chat UI and API through:

| `provider` | Interface | Endpoint |
|---|---|---|
| `aihubmix` | OpenAI-compatible chat | https://aihubmix.com/v1 |
| `openai` | OpenAI Responses | https://api.openai.com/v1 |
| `anthropic` | Anthropic Messages | https://api.anthropic.com/v1 |
| `gemini` | Gemini generateContent | https://generativelanguage.googleapis.com/v1beta |
| `custom` | OpenAI-compatible chat | **base URL you supply** (relays, DeepSeek, OpenRouter, Ollama, vLLM…) |

`custom` URLs must be `https://`, or `http://` on localhost/127.0.0.1/host.docker.internal,
and must not embed credentials. Your key and the retrieved passages are sent to that URL,
so use only endpoints you trust. Every provider returns the same claim-cited schema and
passes the same citation and numeric validation; failures fall back to the offline engine
(`provider: offline_fallback`).

## Chat UI

Open **Model settings**, choose the provider, paste the key, click **Load models** (for
Custom, enter the base URL first; you can also type a model ID), then **Test connection**.
Keys stay in page memory only.

## REST API

```json
POST /api/rag/query
{"question": "What is the function of TCF7L2?", "provider": "custom",
 "base_url": "https://api.example-relay.com/v1", "api_key": "...", "model": "gpt-4o-mini"}
```

`POST /api/llm/models` and `POST /api/llm/test` take the same `provider`, `api_key`,
`model` and `base_url` fields. Omit `api_key` for offline generation.

## Command line and evaluation scripts

```bash
cp .env.example .env      # then edit LLM_PROVIDER / LLM_API_KEY / LLM_MODEL
python scripts/query_rag.py "What is the function of TCF7L2?" --provider llm
python scripts/evaluate_blind.py --label deepseek --llm-provider deepseek --limit 25 \
    --judge-provider openai --judge-model gpt-4o-mini
```

Scripts use `generation.llm_provider` presets (`openai`, `aihubmix`, `deepseek`,
`openrouter`, `anthropic` via its OpenAI-compatible endpoint, `siliconflow`, `ollama`,
`custom`). `LLM_*` values apply only to `LLM_PROVIDER`; they are never sent to another
provider. `JUDGE_API_KEY` is used for the support judge when it differs from `LLM_API_KEY`.
Legacy `AIHUBMIX_API_KEY` / `AIHUBMIX_MODEL` / `AIHUBMIX_BASE_URL` variables are
still honoured when `LLM_API_KEY` is empty. Cost estimates use per-million-token
rates from `config/model_pricing.json`, e.g.
`{"gpt-4o-mini": {"input_usd_per_million": 0.15, "output_usd_per_million": 0.6}}`;
without rates the cost is reported as unavailable, never as zero.

## Streamlit demo

Select **Hosted LLM**, choose the preset, then enter model, base URL and key.

## Security

- `.env` is ignored by Git and must never be committed.
- Never paste a key into documentation, source code, screenshots, chat or commits.
- Confirm client approval before sending non-public corpus passages to a hosted provider.
- Revoke and replace a key immediately if it is exposed.
