"""Provider-agnostic hosted generation over any OpenAI-compatible Chat Completions API.

Presets cover common vendors (OpenAI, AIHubMix, DeepSeek, OpenRouter, Anthropic's
OpenAI-compatible endpoint, SiliconFlow, local Ollama/vLLM); ``custom`` accepts any
base URL. Every provider returns the same structured, claim-cited schema and is
validated identically, so evaluation results remain comparable across vendors.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from augmentation.schema import ContextPackage
from generation.schema import Claim, GeneratedAnswer

PROMPT_POLICY_VERSION = "1.1.0"


@dataclass(frozen=True)
class ProviderPreset:
    name: str
    base_url: str | None
    default_model: str
    requires_key: bool = True
    json_mode: bool = True
    label: str = ""


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset("openai", "https://api.openai.com/v1", "gpt-4o-mini", label="OpenAI"),
    "aihubmix": ProviderPreset("aihubmix", "https://aihubmix.com/v1", "gpt-4o-mini", label="AIHubMix"),
    "deepseek": ProviderPreset("deepseek", "https://api.deepseek.com/v1", "deepseek-chat", label="DeepSeek"),
    "openrouter": ProviderPreset("openrouter", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini", label="OpenRouter"),
    "anthropic": ProviderPreset("anthropic", "https://api.anthropic.com/v1/", "claude-sonnet-5-5",
                                json_mode=False, label="Anthropic (OpenAI-compatible endpoint)"),
    "siliconflow": ProviderPreset("siliconflow", "https://api.siliconflow.cn/v1", "Qwen/Qwen3-32B", label="SiliconFlow"),
    "ollama": ProviderPreset("ollama", "http://localhost:11434/v1", "qwen3:8b", requires_key=False,
                             label="Ollama (local)"),
    "custom": ProviderPreset("custom", None, "", requires_key=False, label="Custom OpenAI-compatible URL"),
}

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


class LLMGenerationError(RuntimeError):
    """Raised when the hosted provider cannot return a valid grounded answer."""


class LLMQuotaError(LLMGenerationError):
    """Raised when a provider returns an account quota notice instead of an answer."""


def validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("LLM base URL must be an http(s) URL")
    if parsed.scheme == "http" and parsed.hostname not in _LOCAL_HOSTS:
        raise ValueError("Plain http is only allowed for local model servers; use https")
    if parsed.username or parsed.password:
        raise ValueError("LLM base URL must not embed credentials")
    return base_url.strip()


def _json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        # Some reasoning models prepend <think> blocks or explanatory text even
        # when asked for JSON only. Extract the first object that matches the
        # answer schema instead of rejecting an otherwise usable response.
        decoder = json.JSONDecoder()
        value = None
        required_keys = {"status", "answer", "claims"}
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and required_keys.issubset(candidate):
                value = candidate
                break
        if value is None:
            raise LLMGenerationError("provider returned invalid JSON")
    if not isinstance(value, dict):
        raise LLMGenerationError("provider response must be a JSON object")
    return value


def _parse_answer(payload: dict[str, Any], context: ContextPackage, model: str,
                  provider: str = "llm") -> GeneratedAnswer:
    status = payload.get("status")
    if status not in {"answer", "qualified", "refuse"}:
        raise LLMGenerationError("provider returned an invalid answer status")
    answer_text = payload.get("answer")
    if not isinstance(answer_text, str) or not answer_text.strip():
        raise LLMGenerationError("provider returned an empty answer")

    raw_claims = payload.get("claims", [])
    if not isinstance(raw_claims, list):
        raise LLMGenerationError("claims must be a list")
    claims: list[Claim] = []
    for item in raw_claims:
        if not isinstance(item, dict):
            raise LLMGenerationError("each claim must be an object")
        text = item.get("text")
        citations = item.get("citations")
        if not isinstance(text, str) or not text.strip():
            raise LLMGenerationError("each claim must contain text")
        if not isinstance(citations, list) or not all(isinstance(cid, str) for cid in citations):
            raise LLMGenerationError("each claim must contain a citation list")
        claims.append(Claim(text=text.strip(), citations=list(dict.fromkeys(citations))))

    if status in {"answer", "qualified"} and not claims:
        raise LLMGenerationError("non-refusal answers must contain cited claims")
    if status == "refuse" and claims:
        raise LLMGenerationError("refusal answers must not contain factual claims")
    if context.evidence_status == "qualified" and status == "answer":
        status = "qualified"

    raw_limitations = payload.get("limitations", [])
    if not isinstance(raw_limitations, list) or not all(
        isinstance(item, str) for item in raw_limitations
    ):
        raise LLMGenerationError("limitations must be a list of strings")
    limitations = list(dict.fromkeys([*context.limitations, *raw_limitations]))

    cited_ids = list(dict.fromkeys(cid for claim in claims for cid in claim.citations))
    citations = [context.citation_registry[cid] for cid in cited_ids if cid in context.citation_registry]
    return GeneratedAnswer(
        status=status,
        # The displayed answer is constructed from cited claims, never an
        # independent unvalidated prose field from the provider.
        answer="\n\n".join(claim.text for claim in claims) if claims else
            "I cannot answer this question from the authorized approved corpus.",
        claims=claims,
        citations=citations,
        limitations=limitations,
        provider=provider,
        prompt_policy_version=PROMPT_POLICY_VERSION,
        diagnostics={"model": model, "claim_count": len(claims)},
    )


SYSTEM_PROMPT = """You are an evidence-grounded scientific assistant.
Use only the supplied evidence. Do not use outside knowledge.
Return JSON only with this exact structure:
{
  "status": "answer|qualified|refuse",
  "answer": "concise natural-language answer",
  "claims": [{"text": "one factual claim", "citations": ["exact chunk_id"]}],
  "limitations": ["limitation text"]
}
Every factual claim must cite one or more exact chunk_id values from the evidence.
Never invent a citation. If evidence is insufficient, return status "refuse" with no claims.
Preserve scientific numbers exactly and do not claim that association proves causality."""


def _messages(context: ContextPackage) -> list[dict[str, str]]:
    evidence = [
        {
            "chunk_id": passage.chunk_id,
            "collection": passage.collection,
            "title": passage.title,
            "content": passage.content,
            "metadata": ({"gene_symbol": passage.metadata.get("gene_symbol"), "units": None} if passage.collection == "gtex_tissue_expression" else passage.metadata),
        }
        for passage in context.passages
    ]
    user = json.dumps(
        {
            "question": context.question,
            "evidence_status": context.evidence_status,
            "known_limitations": context.limitations,
            "evidence": evidence,
        },
        ensure_ascii=False,
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def _is_quota_notice(content: str) -> bool:
    normalized = content.lower()
    return "can only try 10 times" in normalized or (
        "quota" in normalized and any(term in normalized for term in ("topup", "top up", "recharge", "exceeded"))
    )


def create_openai_client(api_key: str, base_url: str, timeout_s: float) -> Any:
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Hosted generation requires: pip install -r requirements/llm.txt"
        ) from exc
    # Local servers ignore the key, but the SDK requires a non-empty value.
    return OpenAI(api_key=api_key or "not-needed", base_url=base_url, timeout=timeout_s, max_retries=0)


@dataclass
class OpenAICompatibleGenerator:
    """Grounded generator for any OpenAI-compatible Chat Completions endpoint."""

    api_key: str = ""
    model: str = ""
    base_url: str | None = None
    provider_name: str = "custom"
    json_mode: bool | None = None
    max_tokens: int = 800
    timeout_s: float = 60.0
    repair_attempts: int = 1
    temperature: float | None = 0.0
    client: Any | None = None
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    usage_records: list[dict[str, Any]] = field(default_factory=list, init=False)

    prompt_policy_version = PROMPT_POLICY_VERSION

    def __post_init__(self) -> None:
        preset = PROVIDER_PRESETS.get(self.provider_name)
        if preset is None:
            raise ValueError(f"Unknown LLM provider '{self.provider_name}'. Choose one of {sorted(PROVIDER_PRESETS)}")
        self.base_url = validate_base_url(self.base_url or preset.base_url or "")
        self.model = (self.model or preset.default_model).strip()
        if not self.model:
            raise ValueError("An LLM model name is required for this provider")
        if self.json_mode is None:
            self.json_mode = preset.json_mode
        self.api_key = (self.api_key or "").strip()
        if preset.requires_key and not self.api_key:
            raise ValueError(f"An API key is required for provider '{self.provider_name}'")
        if self.client is None:
            self.client = create_openai_client(self.api_key, self.base_url, self.timeout_s)

    @property
    def provider(self) -> str:
        return self.provider_name

    def describe(self) -> dict[str, Any]:
        """Non-secret provider description for logs and responses."""
        return {"provider": self.provider_name, "model": self.model,
                "base_url_host": urlparse(self.base_url).hostname, "json_mode": self.json_mode}

    def usage_summary(self) -> dict[str, Any]:
        known = all(r.get("input_tokens") is not None and r.get("output_tokens") is not None for r in self.usage_records)
        inputs = sum(r["input_tokens"] for r in self.usage_records) if known else None
        outputs = sum(r["output_tokens"] for r in self.usage_records) if known else None
        priced = self.input_cost_per_million is not None and self.output_cost_per_million is not None
        cost = ((inputs * self.input_cost_per_million + outputs * self.output_cost_per_million) / 1_000_000) if known and priced else None
        return {"api_calls": len(self.usage_records), "input_tokens": inputs, "output_tokens": outputs,
                "estimated_cost_usd": cost, "pricing_configured": priced,
                "cost_note": "Estimate from configured per-million-token rates; not an invoice." if priced else "No model rates configured; cost unavailable."}

    def complete(self, messages: list[dict[str, str]], *, max_tokens: int | None = None,
                 json_mode: bool | None = None) -> str:
        """One raw chat completion; also used by the LLM support judge."""
        self.usage_records.append({"input_tokens": None, "output_tokens": None})
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages,
                                  "max_tokens": max_tokens or self.max_tokens, "stream": False}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.json_mode if json_mode is None else json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        usage = getattr(response, "usage", None)
        self.usage_records[-1] = {"input_tokens": getattr(usage, "prompt_tokens", None),
                                  "output_tokens": getattr(usage, "completion_tokens", None)}
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise LLMGenerationError("provider returned empty content")
        if _is_quota_notice(content):
            raise LLMQuotaError(
                f"{self.provider_name} reported an exhausted quota. Use a key from an "
                "account with available quota or top up the current account."
            )
        return content

    def generate(self, context: ContextPackage) -> GeneratedAnswer:
        if context.evidence_status == "refuse":
            return GeneratedAnswer(
                status="refuse",
                answer="I cannot answer this question from the authorized approved corpus.",
                claims=[],
                citations=[],
                limitations=context.limitations,
                provider=self.provider,
                prompt_policy_version=self.prompt_policy_version,
                diagnostics={"model": self.model, "api_called": False},
            )

        self.usage_records.clear()
        messages = _messages(context)
        last_error: Exception | None = None
        content = ""
        for attempt in range(self.repair_attempts + 1):
            try:
                content = self.complete(messages)
                answer = _parse_answer(_json_content(content), context, self.model, self.provider)
                answer.diagnostics["usage"] = self.usage_summary()
                answer.diagnostics["llm"] = self.describe()
                return answer
            except LLMQuotaError:
                raise
            except (LLMGenerationError, KeyError, IndexError, TypeError) as exc:
                last_error = exc
                if attempt >= self.repair_attempts:
                    break
                messages = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "The response was invalid. Return exactly one valid JSON object "
                            "matching the schema. Do not include reasoning, <think> tags, "
                            "Markdown fences, or any text before or after the JSON."
                        ),
                    },
                ]
            except Exception as exc:
                raise LLMGenerationError(f"{self.provider_name} request failed") from exc
        raise LLMGenerationError(f"{self.provider_name} returned no valid structured answer") from last_error


def _pricing(model: str, pricing_path=None) -> dict[str, Any]:
    from pathlib import Path

    path = Path(pricing_path) if pricing_path else Path(__file__).resolve().parents[2] / "config/model_pricing.json"
    try:
        table = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        table = {}
    return table.get(model, {}) if isinstance(table, dict) else {}


def build_llm_generator(provider: str | None = None, api_key: str | None = None, model: str | None = None,
                        base_url: str | None = None, **kwargs: Any) -> OpenAICompatibleGenerator:
    """Create a generator from explicit settings, falling back to environment variables.

    Environment: LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL. The legacy
    AIHUBMIX_* variables are still honoured when LLM_* are unset.
    """
    env = os.environ
    legacy = bool(env.get("AIHUBMIX_API_KEY")) and not env.get("LLM_API_KEY")
    provider = (provider or env.get("LLM_PROVIDER") or ("aihubmix" if legacy else "openai")).strip().lower()
    api_key = api_key if api_key is not None and api_key.strip() else (
        env.get("LLM_API_KEY") or (env.get("AIHUBMIX_API_KEY") if provider == "aihubmix" else "") or "")
    model = model or env.get("LLM_MODEL") or (env.get("AIHUBMIX_MODEL") if provider == "aihubmix" else None)
    base_url = base_url or env.get("LLM_BASE_URL") or (env.get("AIHUBMIX_BASE_URL") if provider == "aihubmix" else None)
    resolved_model = model or (PROVIDER_PRESETS[provider].default_model if provider in PROVIDER_PRESETS else "")
    rates = _pricing(resolved_model)
    kwargs.setdefault("input_cost_per_million", rates.get("input_usd_per_million"))
    kwargs.setdefault("output_cost_per_million", rates.get("output_usd_per_million"))
    return OpenAICompatibleGenerator(api_key=api_key, model=model or "", base_url=base_url,
                                     provider_name=provider, **kwargs)


def provider_catalog() -> list[dict[str, Any]]:
    return [{"id": p.name, "label": p.label or p.name, "base_url": p.base_url, "default_model": p.default_model,
             "requires_key": p.requires_key} for p in PROVIDER_PRESETS.values()]
