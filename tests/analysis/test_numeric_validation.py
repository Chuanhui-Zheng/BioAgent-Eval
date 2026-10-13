from generation.schema import GeneratedAnswer, Claim
from generation.validator import validate_answer
from augmentation.builder import ContextBuilder
from retrieval.service import RetrievalResponse
from tests.helpers import result


def context():
    hit = result(
        "rare:GENE",
        "gene_association_rare",
        metadata={"gene": "GENE", "beta": 0.123456, "pValue": 1e-8},
        content="Source beta=0.1235 and pValue=1e-8.",
    )
    return ContextBuilder().build(
        RetrievalResponse(
            question="association evidence",
            authorized_collections=["gene_association_rare"],
            routed_collections=["gene_association_rare"],
            effective_collections=["gene_association_rare"],
            matched_rules=[],
            results=[hit],
            method="fixture",
            latency_s=0,
        )
    )


def answer(text):
    return GeneratedAnswer("answer", text, [Claim(text, ["rare:GENE"])], [], [])


def test_numeric_fabrication_with_valid_citation_is_rejected():
    checked = validate_answer(answer("beta=99 and pValue=0.1."), context())
    assert not checked.valid
    assert any("unsupported numeric" in e for e in checked.errors)


def test_source_precision_and_display_rounding_are_accepted():
    checked = validate_answer(answer("beta=0.1235 and pValue=1e-8."), context())
    assert checked.valid and checked.numerical_fidelity_checked
    assert not checked.semantic_support_verified


def test_uncited_number_in_answer_is_checked_even_if_claim_is_valid():
    response = answer("beta=.123456")
    response.answer = "beta=99"
    assert not validate_answer(response, context()).valid
