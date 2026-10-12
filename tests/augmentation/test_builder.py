from __future__ import annotations

import pytest

from augmentation.builder import AugmentationConfig, ContextBuilder
from retrieval.service import RetrievalResponse
from tests.helpers import result


def response(question, results, effective=None):
    effective = effective or ["gene_info"]
    return RetrievalResponse(
        question=question,
        authorized_collections=effective,
        routed_collections=effective,
        effective_collections=effective,
        matched_rules=[],
        results=results,
        method="fixture",
        latency_s=0.0,
    )


def test_deduplicates_and_builds_resolvable_registry() -> None:
    item = result("gene:TCF7L2", "gene_info")
    context = ContextBuilder().build(response("function of TCF7L2", [item, item]))
    assert len(context.passages) == 1
    assert set(context.citation_registry) == {"gene:TCF7L2"}
    assert context.diagnostics["duplicates_removed"] == 1


def test_refuses_personal_medical_question() -> None:
    context = ContextBuilder().build(
        response("Is my glucose normal level?", [result("gene:X", "gene_info")])
    )
    assert context.evidence_status == "refuse"


def test_non_significant_evidence_is_qualified() -> None:
    item = result(
        "ldsc:2hrI:T2D",
        "ldsc_genetic_correlation",
        metadata={"mixed_rg": 0.1, "mixed_pvalue": 0.6, "is_significant_mixed": False},
    )
    context = ContextBuilder().build(
        response("Is 2-hour insulin genetically correlated with T2D?", [item], ["ldsc_genetic_correlation"])
    )
    assert context.evidence_status == "qualified"
    assert any("non-significant" in x for x in context.limitations)


def test_enforces_token_budget() -> None:
    items = [result(f"gene:{i}", "gene_info", rank=i + 1, content="x" * 100) for i in range(3)]
    context = ContextBuilder(AugmentationConfig(max_context_tokens=30, max_passages=5)).build(
        response("gene function", items)
    )
    assert context.estimated_tokens <= 30
    assert context.diagnostics["excluded_chunk_ids"]


def test_rejects_collection_leak() -> None:
    with pytest.raises(PermissionError, match="context isolation"):
        ContextBuilder().build(
            response("gene function", [result("ldsc:X:Y", "ldsc_genetic_correlation")])
        )
