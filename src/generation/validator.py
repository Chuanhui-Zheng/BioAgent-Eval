from __future__ import annotations

from dataclasses import dataclass

from augmentation.schema import ContextPackage
from generation.schema import GeneratedAnswer


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]
    citation_correctness: float
    citation_completeness: float


def validate_answer(answer: GeneratedAnswer, context: ContextPackage) -> ValidationResult:
    allowed = set(context.citation_registry)
    errors: list[str] = []
    cited = [cid for claim in answer.claims for cid in claim.citations]
    invalid = sorted(set(cited) - allowed)
    if invalid:
        errors.append(f"citations outside context: {invalid}")
    uncited = [index for index, claim in enumerate(answer.claims) if not claim.citations]
    if uncited:
        errors.append(f"uncited claims: {uncited}")
    if answer.status == "refuse" and answer.claims:
        errors.append("refusal must not contain factual claims")
    correctness = 1.0 if not cited else sum(cid in allowed for cid in cited) / len(cited)
    completeness = 1.0 if not answer.claims else sum(bool(c.citations) for c in answer.claims) / len(answer.claims)
    return ValidationResult(not errors, errors, correctness, completeness)
