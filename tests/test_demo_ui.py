from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from generation.aihubmix import AIHubMixGenerator

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_aihubmix_uses_direct_generator() -> None:
    import app

    generator = app.generator_for("AIHubMix", "test-key")

    assert isinstance(generator, AIHubMixGenerator)


def test_aihubmix_selection_shows_session_key_input() -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()

    app.radio[0].set_value("AIHubMix").run()

    assert app.text_input[0].label == "AIHubMix API Key"


def test_aihubmix_requires_key_before_request() -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.radio[0].set_value("AIHubMix").run()

    app.button[0].click().run()

    assert any("API Key" in warning.value for warning in app.warning)
