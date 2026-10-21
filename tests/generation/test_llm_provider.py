from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from generation.aihubmix import AIHubMixGenerator
from generation.llm_provider import (
    PROVIDER_PRESETS,
    LLMGenerationError,
    OpenAICompatibleGenerator,
    build_llm_generator,
    provider_catalog,
    validate_base_url,
)


class RecordingClient:
    def __init__(self, content: str) -> None:
        self.calls: list[dict] = []
        self.content = content
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
                               usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL",
                 "AIHUBMIX_API_KEY", "AIHUBMIX_MODEL", "AIHUBMIX_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("name", sorted(set(PROVIDER_PRESETS) - {"custom"}))
def test_every_preset_resolves_url_and_model(name):
    generator = build_llm_generator(provider=name, api_key="k", client=RecordingClient("{}"))
    assert generator.provider == name
    assert generator.base_url == PROVIDER_PRESETS[name].base_url
    assert generator.model == PROVIDER_PRESETS[name].default_model


def test_custom_provider_requires_base_url_and_model():
    with pytest.raises(ValueError):
        build_llm_generator(provider="custom", model="m", client=RecordingClient("{}"))
    generator = build_llm_generator(provider="custom", model="my-model", base_url="https://llm.example.org/v1",
                                    client=RecordingClient("{}"))
    assert generator.describe() == {"provider": "custom", "model": "my-model",
                                    "base_url_host": "llm.example.org", "json_mode": True}


def test_key_required_for_hosted_presets_but_not_local():
    with pytest.raises(ValueError, match="API key"):
        build_llm_generator(provider="openai", client=RecordingClient("{}"))
    assert build_llm_generator(provider="ollama", client=RecordingClient("{}")).api_key == ""


def test_unknown_provider_rejected():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        build_llm_generator(provider="nope", api_key="k", client=RecordingClient("{}"))


@pytest.mark.parametrize("url", ["ftp://x/v1", "http://remote.example.org/v1", "https://u:p@host/v1", "not a url"])
def test_unsafe_base_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_local_http_allowed():
    assert validate_base_url("http://127.0.0.1:8001/v1") == "http://127.0.0.1:8001/v1"


def test_environment_configuration_and_legacy_aihubmix(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY", "env-key")
    monkeypatch.setenv("LLM_MODEL", "deepseek-reasoner")
    generator = build_llm_generator(client=RecordingClient("{}"))
    assert (generator.provider, generator.api_key, generator.model) == ("deepseek", "env-key", "deepseek-reasoner")

    for name in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name)
    monkeypatch.setenv("AIHUBMIX_API_KEY", "legacy-key")
    legacy = build_llm_generator(client=RecordingClient("{}"))
    assert (legacy.provider, legacy.api_key) == ("aihubmix", "legacy-key")


def test_json_mode_follows_preset_and_temperature_is_zero():
    from tests.generation.test_aihubmix import context_for

    payload = json.dumps({"status": "answer", "answer": "x",
                          "claims": [{"text": "Claim.", "citations": ["gene:PPARG"]}]})
    anthropic_client = RecordingClient(payload)
    answer = build_llm_generator(provider="anthropic", api_key="k", client=anthropic_client).generate(context_for())
    assert answer.provider == "anthropic"
    assert "response_format" not in anthropic_client.calls[0]
    assert anthropic_client.calls[0]["temperature"] == 0.0
    assert answer.diagnostics["llm"]["base_url_host"] == "api.anthropic.com"

    openai_client = RecordingClient(payload)
    build_llm_generator(provider="openai", api_key="k", client=openai_client).generate(context_for())
    assert openai_client.calls[0]["response_format"] == {"type": "json_object"}


def test_generic_quota_notice_is_not_retried():
    from tests.generation.test_aihubmix import context_for

    client = RecordingClient("Your quota has been exceeded, please recharge.")
    generator = build_llm_generator(provider="openrouter", api_key="k", client=client, repair_attempts=2)
    with pytest.raises(LLMGenerationError, match="exhausted quota"):
        generator.generate(context_for())
    assert len(client.calls) == 1


def test_legacy_class_is_generic_preset():
    generator = AIHubMixGenerator("k", client=RecordingClient("{}"))
    assert isinstance(generator, OpenAICompatibleGenerator)
    assert generator.provider == "aihubmix" and generator.base_url == "https://aihubmix.com/v1"


def test_catalog_contains_no_secrets():
    catalog = provider_catalog()
    assert {item["id"] for item in catalog} == set(PROVIDER_PRESETS)
    assert all("key" not in json.dumps(item).lower().replace("requires_key", "") for item in catalog)
