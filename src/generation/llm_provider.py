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
from generation.aihubmix import AIHubMixGenerationError, _json_content, _messages, _parse_answer
from generation.schema import GeneratedAnswer

PROMPT_POLICY_VERSION = "1.1.0"  # same prompt as generation.aihubmix


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


class LLMGenerationError(AIHubMixGenerationError):
    """Raised when an OpenAI-compatible provider cannot return a valid grounded answer.

    Subclasses the shared hosted-generation error so callers catch one type.
    """


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

    def _request(self, messages: list[dict[str, str]]) -> str:
        """Interface shared with generation.hosted adapters (used by /api/llm/test)."""
        return self.complete(messages)

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
                answer = _parse_answer(_json_content(content), context, self.model)
                answer.provider = self.provider
                answer.diagnostics["usage"] = self.usage_summary()
                answer.diagnostics["llm"] = self.describe()
                return answer
            except LLMQuotaError:
                raise
            except (AIHubMixGenerationError, KeyError, IndexError, TypeError) as exc:
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
    env_provider = (env.get("LLM_PROVIDER") or ("aihubmix" if legacy else "openai")).strip().lower()
    provider = (provider or env_provider).strip().lower()
    # LLM_* settings describe LLM_PROVIDER only; never send its key or URL to another provider.
    use_env = provider == env_provider
    legacy_aihubmix = provider == "aihubmix" and legacy
    api_key = api_key if api_key is not None and api_key.strip() else (
        (env.get("LLM_API_KEY") if use_env else None) or (env.get("AIHUBMIX_API_KEY") if legacy_aihubmix else "") or "")
    model = model or (env.get("LLM_MODEL") if use_env else None) or (
        env.get("AIHUBMIX_MODEL") if legacy_aihubmix else None)
    base_url = base_url or (env.get("LLM_BASE_URL") if use_env else None) or (
        env.get("AIHUBMIX_BASE_URL") if legacy_aihubmix else None)
    resolved_model = model or (PROVIDER_PRESETS[provider].default_model if provider in PROVIDER_PRESETS else "")
    rates = _pricing(resolved_model)
    kwargs.setdefault("input_cost_per_million", rates.get("input_usd_per_million"))
    kwargs.setdefault("output_cost_per_million", rates.get("output_usd_per_million"))
    return OpenAICompatibleGenerator(api_key=api_key, model=model or "", base_url=base_url,
                                     provider_name=provider, **kwargs)


def provider_catalog() -> list[dict[str, Any]]:
    return [{"id": p.name, "label": p.label or p.name, "base_url": p.base_url, "default_model": p.default_model,
             "requires_key": p.requires_key} for p in PROVIDER_PRESETS.values()]
