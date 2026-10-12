from __future__ import annotations

from augmentation.builder import ContextBuilder
from generation.offline import OfflineEvidenceGenerator
from generation.schema import Claim, GeneratedAnswer
from generation.validator import validate_answer
from retrieval.service import RetrievalResponse
from tests.helpers import result


def context_for(question="What is the function of TCF7L2?"):
    response = RetrievalResponse(
        question=question,
        authorized_collections=["gene_info"],
        routed_collections=["gene_info"],
        effective_collections=["gene_info"],
        matched_rules=[],
        results=[result("gene:TCF7L2", "gene_info")],
        method="fixture",
        latency_s=0.0,
    )
    return ContextBuilder().build(response)


def test_offline_generator_has_claim_linked_citation() -> None:
    context = context_for()
    answer = OfflineEvidenceGenerator().generate(context)
    validation = validate_answer(answer, context)
    assert answer.status == "answer"
    assert validation.valid
    assert validation.citation_correctness == 1.0
    assert validation.citation_completeness == 1.0


def test_validator_rejects_context_external_citation() -> None:
    context = context_for()
    answer = GeneratedAnswer(
        status="answer",
        answer="unsupported",
        claims=[Claim("unsupported", ["gene:OTHER"])],
        citations=[],
        limitations=[],
    )
    assert not validate_answer(answer, context).valid


def test_refusal_contains_no_factual_claims() -> None:
    context = context_for("Is my glucose normal level?")
    answer = OfflineEvidenceGenerator().generate(context)
    assert answer.status == "refuse"
    assert answer.claims == []
    assert validate_answer(answer, context).valid
