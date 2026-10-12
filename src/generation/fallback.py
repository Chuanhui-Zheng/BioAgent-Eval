from __future__ import annotations

from dataclasses import dataclass

from augmentation.schema import ContextPackage
from generation.provider import GeneratorProvider
from generation.schema import GeneratedAnswer
from generation.validator import validate_answer


@dataclass
class FallbackGenerator:
    primary: GeneratorProvider
    fallback: GeneratorProvider

    provider = "fallback"
    prompt_policy_version = "1.1.0"

    def generate(self, context: ContextPackage) -> GeneratedAnswer:
        try:
            answer = self.primary.generate(context)
            validation = validate_answer(answer, context)
            if answer.status == "error" or not validation.valid:
                raise ValueError("primary generator failed evidence validation")
            return answer
        except Exception as exc:
            answer = self.fallback.generate(context)
            answer.diagnostics = {
                **answer.diagnostics,
                "fallback_from": getattr(self.primary, "provider", type(self.primary).__name__),
                "fallback_error_type": type(exc).__name__,
            }
            return answer
