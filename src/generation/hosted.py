"""Direct provider adapters sharing the existing evidence prompt and answer parser."""
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

import httpx

from generation.aihubmix import AIHubMixGenerator, AIHubMixGenerationError

# "custom" is any OpenAI-compatible endpoint (relay or local server) whose base URL
# the user supplies; see generation.llm_provider.validate_base_url for the URL policy.
Provider = Literal["aihubmix", "openai", "anthropic", "gemini", "custom"]
PROVIDER_URLS = {
    "aihubmix": "https://aihubmix.com/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}


@dataclass
class OpenAIGenerator(AIHubMixGenerator):
    base_url: str = PROVIDER_URLS["openai"]
    max_tokens: int = 4096
    provider = "openai"

    def _request(self, messages):
        self.usage_records.append({"input_tokens": None, "output_tokens": None})
        response = self.client.responses.create(
            model=self.model, input=messages, max_output_tokens=self.max_tokens,
            store=False,
        )
        usage = getattr(response, "usage", None)
        self.usage_records[-1] = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }
        if response.status != "completed" or not response.output_text.strip():
            raise AIHubMixGenerationError("OpenAI response was incomplete or empty")
        return response.output_text


@dataclass
class AnthropicGenerator(AIHubMixGenerator):
    base_url: str = PROVIDER_URLS["anthropic"]
    max_tokens: int = 4096
    provider = "anthropic"

    def __post_init__(self):
        if not self.api_key.strip():
            raise ValueError("An Anthropic API key is required")
        if self.client is None:
            self.client = httpx

    def _request(self, messages):
        self.usage_records.append({"input_tokens": None, "output_tokens": None})
        response = self.client.post(
            f"{self.base_url}/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": self.model, "max_tokens": self.max_tokens,
                "system": "\n".join(m["content"] for m in messages if m["role"] == "system"),
                "messages": [m for m in messages if m["role"] != "system"],
            },
            timeout=self.timeout_s, follow_redirects=False,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage", {})
        self.usage_records[-1] = {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        }
        content = "\n".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
        if data.get("stop_reason") != "end_turn" or not content.strip():
            raise AIHubMixGenerationError("Claude response was incomplete or empty")
        return content


@dataclass
class GeminiGenerator(AIHubMixGenerator):
    base_url: str = PROVIDER_URLS["gemini"]
    max_tokens: int = 8192
    provider = "gemini"

    def __post_init__(self):
        if not self.api_key.strip():
            raise ValueError("A Gemini API key is required")
        if self.client is None:
            self.client = httpx

    def _request(self, messages):
        self.usage_records.append({"input_tokens": None, "output_tokens": None})
        model = quote(self.model.removeprefix("models/"), safe="")
        response = self.client.post(
            f"{self.base_url}/models/{model}:generateContent",
            headers={"x-goog-api-key": self.api_key},
            json={
                "systemInstruction": {"parts": [{"text": "\n".join(
                    m["content"] for m in messages if m["role"] == "system"
                )}]},
                "contents": [
                    {"role": "model" if m["role"] == "assistant" else "user",
                     "parts": [{"text": m["content"]}]}
                    for m in messages if m["role"] != "system"
                ],
                "generationConfig": {
                    "maxOutputTokens": self.max_tokens,
                    "responseMimeType": "application/json",
                },
            },
            timeout=self.timeout_s, follow_redirects=False,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usageMetadata", {})
        output_tokens = usage.get("candidatesTokenCount")
        self.usage_records[-1] = {
            "input_tokens": usage.get("promptTokenCount"),
            "output_tokens": (output_tokens + usage.get("thoughtsTokenCount", 0)
                              if output_tokens is not None else None),
        }
        candidate = next(iter(data.get("candidates", [])), {})
        content = "\n".join(
            part["text"] for part in candidate.get("content", {}).get("parts", [])
            if isinstance(part.get("text"), str) and not part.get("thought")
        )
        if candidate.get("finishReason") != "STOP" or not content.strip():
            raise AIHubMixGenerationError("Gemini response was blocked, incomplete or empty")
        return content


def list_models(provider: Provider, api_key: str, base_url: str | None = None):
    # Preset providers use fixed hosts. "custom" uses the caller's validated base URL,
    # chosen explicitly by the user for their own key.
    if provider == "custom":
        if not base_url:
            raise ValueError("custom provider requires a base URL")
        response = httpx.get(f"{base_url.rstrip('/')}/models", headers={"Authorization": f"Bearer {api_key}"},
                             timeout=20, follow_redirects=False)
        response.raise_for_status()
        return sorted({m["id"] for m in response.json().get("data", []) if isinstance(m.get("id"), str)})
    headers = ({"x-goog-api-key": api_key} if provider == "gemini" else
               {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
               if provider == "anthropic" else {"Authorization": f"Bearer {api_key}"})
    response = httpx.get(f"{PROVIDER_URLS[provider]}/models", headers=headers,
                         timeout=20, follow_redirects=False)
    response.raise_for_status()
    data = response.json()
    if provider == "gemini":
        return sorted({m["name"].removeprefix("models/") for m in data.get("models", [])
                       if isinstance(m.get("name"), str)
                       and "generateContent" in m.get("supportedGenerationMethods", [])})
    return sorted({m["id"] for m in data.get("data", []) if isinstance(m.get("id"), str)})


def connection_error(exc: Exception) -> str:
    # Do not expose provider response bodies, request headers or credentials.
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in {401, 403}:
        return "Authentication failed. Check this provider's API key and account permissions."
    if status == 429:
        return "The provider reported a rate or quota limit. Check your account and retry later."
    if status in {400, 404, 422}:
        return "The model or request is unavailable. Check the model ID and API compatibility."
    return "The provider could not complete the request. Check the model, account quota and connection."
