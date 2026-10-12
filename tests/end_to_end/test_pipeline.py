from __future__ import annotations

from augmentation.builder import ContextBuilder
from generation.offline import OfflineEvidenceGenerator
from rag.pipeline import RAGPipeline
from retrieval.service import RetrievalRequest, RetrieverService
from tests.helpers import FakeBackend, result


def test_supported_vertical_slice() -> None:
    pipeline = RAGPipeline(
        RetrieverService(FakeBackend([result("gene:TCF7L2", "gene_info")]), "fixture"),
        ContextBuilder(),
        OfflineEvidenceGenerator(),
    )
    run = pipeline.run(
        RetrievalRequest("What is the function of TCF7L2?", authorized_collections=("gene_info",))
    )
    assert run.answer.status == "answer"
    assert run.validation.valid
    assert run.latency_s["total"] >= 0


def test_unauthorized_evidence_is_never_used() -> None:
    backend = FakeBackend([result("gene:TCF7L2", "gene_info")])
    pipeline = RAGPipeline(
        RetrieverService(backend, "fixture"), ContextBuilder(), OfflineEvidenceGenerator()
    )
    run = pipeline.run(
        RetrievalRequest(
            "What is the function of TCF7L2?",
            authorized_collections=("gene_association_common",),
        )
    )
    assert run.answer.status == "refuse"
    assert run.context.passages == []
