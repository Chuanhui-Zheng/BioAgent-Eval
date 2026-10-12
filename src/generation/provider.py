from __future__ import annotations

from typing import Protocol

from augmentation.schema import ContextPackage
from generation.schema import GeneratedAnswer


class GeneratorProvider(Protocol):
    provider: str
    prompt_policy_version: str

    def generate(self, context: ContextPackage) -> GeneratedAnswer: ...
