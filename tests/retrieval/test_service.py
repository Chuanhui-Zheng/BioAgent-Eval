from __future__ import annotations

import pytest

from retrieval.service import RetrievalRequest, RetrieverService
from tests.helpers import FakeBackend, result


def test_authorization_intersects_router_scope() -> None:
    backend = FakeBackend([result("gene:TCF7L2", "gene_info")])
    service = RetrieverService(backend, "fixture")
    response = service.retrieve(
        RetrievalRequest(
            "What is the function of TCF7L2?",
            authorized_collections=("gene_association_common",),
        )
    )
    assert response.effective_collections == []
    assert response.results == []
    assert backend.calls == []


def test_router_never_expands_authorization() -> None:
    backend = FakeBackend(
        [
            result("gene:TCF7L2", "gene_info"),
            result("gassoc_common:2hrG:TCF7L2", "gene_association_common"),
        ]
    )
    response = RetrieverService(backend, "fixture").retrieve(
        RetrievalRequest(
            "What common-variant association is available?",
            authorized_collections=("gene_association_common",),
        )
    )
    assert response.effective_collections == ["gene_association_common"]
    assert {r.collection for r in response.results} == {"gene_association_common"}


def test_invalid_collection_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown authorized"):
        RetrievalRequest("question", authorized_collections=("private_workspace",))
