"""Backward-compatible AIHubMix entry point.

AIHubMix is now one preset of the provider-agnostic
``generation.llm_provider.OpenAICompatibleGenerator``; new code should use
``build_llm_generator(provider=...)`` instead of this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from generation.llm_provider import (  # noqa: F401  (re-exported for old imports)
    LLMGenerationError as AIHubMixGenerationError,
    LLMQuotaError as _AIHubMixQuotaError,
    OpenAICompatibleGenerator,
    _json_content,
    _messages,
    _parse_answer,
)


@dataclass
class AIHubMixGenerator(OpenAICompatibleGenerator):
    provider_name: str = "aihubmix"
