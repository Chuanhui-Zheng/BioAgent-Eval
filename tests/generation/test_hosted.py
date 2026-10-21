import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

import server
from generation import hosted
from generation.fallback import FallbackGenerator
from generation.offline import OfflineEvidenceGenerator
from generation.validator import validate_answer
from tests.generation.test_aihubmix import context_for, payload
from tests.test_review_regressions import pipeline
from tests.helpers import result


def adapter(provider, text=None, complete=True):
    text = payload() if text is None else text
    if provider == "openai":
        client = SimpleNamespace(responses=SimpleNamespace(create=Mock(return_value=SimpleNamespace(
            status="completed" if complete else "incomplete", output_text=text,
            usage=SimpleNamespace(input_tokens=20, output_tokens=10),
        ))))
        generator = hosted.OpenAIGenerator("secret-fixture", model="account-model", client=client, repair_attempts=0)
        return generator, client.responses.create
    if provider == "anthropic":
        data = {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn" if complete else "max_tokens",
                "usage": {"input_tokens": 20, "output_tokens": 10}}
        cls = hosted.AnthropicGenerator
    else:
        data = {"candidates": [{"finishReason": "STOP" if complete else "SAFETY",
                               "content": {"parts": [{"text": "hidden reasoning", "thought": True}, {"text": text}]}}],
                "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 8, "thoughtsTokenCount": 2}}
        cls = hosted.GeminiGenerator
    response = httpx.Response(200, json=data, request=httpx.Request("POST", "https://fixture.invalid"))
    client = SimpleNamespace(post=Mock(return_value=response))
    return cls("secret-fixture", model="account-model", client=client, repair_attempts=0), client.post


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_native_provider_citations_usage_and_protocol(provider):
    generator, request = adapter(provider)
    answer = generator.generate(context_for())
    assert answer.provider == provider
    assert validate_answer(answer, context_for()).valid
    assert answer.claims[0].citations == ["gene:TCF7L2"]
    assert answer.diagnostics["usage"]["output_tokens"] == 10
    assert answer.diagnostics["usage"]["estimated_cost_usd"] is None
    assert "secret-fixture" not in repr(generator)
    assert "secret-fixture" not in json.dumps(asdict(answer))
    args, kwargs = request.call_args
    if provider == "openai":
        assert kwargs["store"] is False
        assert kwargs["input"][0]["role"] == "system"
    else:
        assert args[0].startswith(hosted.PROVIDER_URLS[provider])
        assert "secret-fixture" not in args[0]
        assert kwargs["follow_redirects"] is False
        if provider == "gemini":
            assert kwargs["headers"] == {"x-goog-api-key": "secret-fixture"}
            assert kwargs["json"]["generationConfig"]["responseMimeType"] == "application/json"
            assert "evidence" in kwargs["json"]["contents"][0]["parts"][0]["text"]
        else:
            assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
            assert all(m["role"] != "system" for m in kwargs["json"]["messages"])


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
@pytest.mark.parametrize("failure", ["bad_citation", "incomplete", "bad_json"])
def test_native_provider_invalid_answers_fall_back(provider, failure):
    text = payload("invented") if failure == "bad_citation" else "not json" if failure == "bad_json" else payload()
    generator, _ = adapter(provider, text, complete=failure != "incomplete")
    context = context_for()
    answer = FallbackGenerator(generator, OfflineEvidenceGenerator()).generate(context)
    assert answer.diagnostics["fallback_from"] == provider
    assert validate_answer(answer, context).valid


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_no_provider_request_when_evidence_insufficient(provider):
    generator, request = adapter(provider)
    context = context_for()
    context.evidence_status = "refuse"
    assert generator.generate(context).status == "refuse"
    request.assert_not_called()


def test_gemini_models_use_header_and_filter_generation(monkeypatch):
    fake = Mock(return_value=httpx.Response(200, json={"models": [
        {"name": "models/gemini-example", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/embedding-example", "supportedGenerationMethods": ["embedContent"]},
    ]}, request=httpx.Request("GET", "https://fixture.invalid")))
    monkeypatch.setattr(hosted.httpx, "get", fake)
    assert hosted.list_models("gemini", "private-key") == ["gemini-example"]
    args, kwargs = fake.call_args
    assert args[0] == hosted.PROVIDER_URLS["gemini"] + "/models"
    assert kwargs["headers"] == {"x-goog-api-key": "private-key"}
    assert kwargs["follow_redirects"] is False


def test_probe_errors_and_validation_do_not_echo_key(monkeypatch):
    client = TestClient(server.app)
    def fail(*args):
        raise RuntimeError("private-key")
    monkeypatch.setattr(server, "hosted_generator", fail)
    request = {"provider": "gemini", "api_key": "private-key", "model": "fixture"}
    response = client.post("/api/llm/test", json=request)
    assert response.status_code == 502
    assert "private-key" not in response.text
    response = client.post("/api/llm/test", json={**request, "api_key": {"secret": "private-key"}})
    assert response.status_code == 422
    assert "private-key" not in response.text
    assert "input" not in response.json()["detail"][0]
    for missing in ["", "  "]:
        assert client.post("/api/llm/models", json={**request, "api_key": missing}).status_code == 422
    assert client.post("/api/llm/test", json={**request, "provider": "arbitrary-url"}).status_code == 422


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_query_routes_selected_provider_without_logging_credentials(monkeypatch, tmp_path, provider):
    generator, _ = adapter(provider)
    factory = Mock(return_value=generator)
    monkeypatch.setattr(server, "hosted_generator", factory)
    monkeypatch.setattr(server, "get_pipeline", lambda: pipeline([result("gene:TCF7L2", "gene_info")]))
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    client = TestClient(server.app)
    response = client.post("/api/rag/query", json={
        "question": "What is the function of TCF7L2?", "api_key": "secret-fixture",
        "provider": provider, "model": "account-model",
    })
    assert response.status_code == 200
    assert response.json()["provider"] == provider
    assert response.json()["model"] == "account-model"
    factory.assert_called_once_with(provider, "secret-fixture", "account-model")
    for path in (tmp_path / "artifacts/runs").rglob("*.json"):
        assert "secret-fixture" not in path.read_text()
    assert "secret-fixture" not in response.text


def test_probe_uses_no_corpus_and_reports_selected_model(monkeypatch):
    generator, request = adapter("gemini", '{"ok": true}')
    monkeypatch.setattr(server, "hosted_generator", lambda *args: generator)
    response = TestClient(server.app).post("/api/llm/test", json={
        "provider": "gemini", "api_key": "secret-fixture", "model": "account-model",
    })
    assert response.status_code == 200 and response.json()["ok"]
    body = request.call_args.kwargs["json"]
    assert "evidence" not in json.dumps(body).lower()
