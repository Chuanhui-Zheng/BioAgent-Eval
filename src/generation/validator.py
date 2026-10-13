from __future__ import annotations

from dataclasses import dataclass

from augmentation.schema import ContextPackage
from generation.schema import GeneratedAnswer
from generation.numeric_validation import numeric_errors


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]
    citation_correctness: float
    citation_completeness: float
    scope: str = "citation_structure"
    semantic_support_verified: bool = False
    numerical_fidelity_checked: bool = True


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
    if answer.status in {"answer", "qualified"} and not answer.claims:
        errors.append("non-refusal answer must contain cited claims")
    # Offline summaries may have only these fixed, non-factual headings.
    body = answer.answer
    for prefix in ("The available evidence is limited. ",
                   "Evidence comparison by retrieved source; missing evidence is not evidence of absence.\n"):
        if body.startswith(prefix):
            body = body[len(prefix):]
    expected_body = "\n\n".join(claim.text for claim in answer.claims)
    if answer.claims and body.strip() != expected_body.strip():
        errors.append("answer body must consist of the cited claims")
    if answer.status == "refuse" and answer.answer != "I cannot answer this question from the authorized approved corpus.":
        errors.append("refusal must use the non-factual refusal message")
    errors.extend(numeric_errors(answer, context))
    correctness = 1.0 if not cited else sum(cid in allowed for cid in cited) / len(cited)
    completeness = 1.0 if not answer.claims else sum(bool(c.citations) for c in answer.claims) / len(answer.claims)
    return ValidationResult(not errors, errors, correctness, completeness)
