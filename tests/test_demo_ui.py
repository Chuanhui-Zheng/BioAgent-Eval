from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from generation.llm_provider import OpenAICompatibleGenerator

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_hosted_llm_uses_generic_generator() -> None:
    import app

    generator = app.generator_for("Hosted LLM", "test-key", llm_provider="deepseek")

    assert isinstance(generator, OpenAICompatibleGenerator)
    assert generator.provider == "deepseek"
    assert generator.base_url == "https://api.deepseek.com/v1"


def test_hosted_llm_selection_shows_provider_and_key_inputs() -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()

    app.radio[0].set_value("Hosted LLM").run()

    assert app.selectbox[0].label == "LLM provider"
    assert [item.label for item in app.text_input][-1] == "API Key"


def test_hosted_llm_requires_key_before_request() -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.radio[0].set_value("Hosted LLM").run()
    app.selectbox[0].set_value("openai").run()

    app.button[0].click().run()

    assert any("API key" in warning.value for warning in app.warning)
