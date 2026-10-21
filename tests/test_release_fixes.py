from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from augmentation.builder import ContextBuilder
from generation.offline import OfflineEvidenceGenerator
from generation.validator import validate_answer
from rag.pipeline import RAGPipeline
from retrieval.router import SUPPORTED_COLLECTIONS
from retrieval.service import RetrievalRequest, RetrieverService
from tests.helpers import FakeBackend, result
import server


class ReleaseFixTests(unittest.TestCase):
    def setUp(self):
        saving = patch.object(RAGPipeline, "save_run")
        saving.start()
        self.addCleanup(saving.stop)

    def pipeline(self, hits):
        return RAGPipeline(RetrieverService(FakeBackend(hits), "fixture"), ContextBuilder(), OfflineEvidenceGenerator())

    def test_all_new_collections_are_reachable_with_citations(self):
        cases = [
            ("WES evidence for PPARG", "gene_association_wes", {"gene": "PPARG"}),
            ("Partitioned heritability for 2hrG", "ldsc_partitioned_heritability", {"phenotype": "2hrG"}),
            ("Clumped lead SNP evidence", "variant_association_clumped", {}),
        ]
        for question, collection, metadata in cases:
            with self.subTest(collection=collection):
                hit = result("source:" + collection, collection, metadata=metadata, content="Source pValue=0.0123; beta=-0.42. Field definitions unconfirmed.")
                run = self.pipeline([hit]).run(RetrievalRequest(question))
                self.assertEqual(run.retrieval.effective_collections, [collection])
                self.assertNotEqual(run.answer.status, "refuse")
                self.assertIn("pValue=0.0123; beta=-0.42", run.answer.answer)
                self.assertEqual(run.answer.claims[0].citations, [hit.chunk_id])
                self.assertTrue(run.validation.valid)

    def test_restriction_still_excludes_new_collections(self):
        backend = FakeBackend([result("wes:PPARG", "gene_association_wes", metadata={"gene": "PPARG"})])
        response = RetrieverService(backend, "fixture").retrieve(RetrievalRequest("WES PPARG", authorized_collections=("gene_info",)))
        self.assertEqual(response.results, [])
        self.assertEqual(backend.calls, [])

    def test_empty_authorization_is_not_expanded_by_api(self):
        pipeline = self.pipeline([result("gene:PPARG", "gene_info")])
        with patch.object(server, "get_pipeline", return_value=pipeline):
            response = server.query_rag(server.QueryRequest(question="Function of PPARG", authorized_collections=[]))
        self.assertEqual(response.retrieved_count, 0)
        self.assertEqual(response.status, "refuse")

    def test_bad_query_is_a_client_error(self):
        with patch.object(server, "get_pipeline", return_value=self.pipeline([])):
            for params in ({"question": "   "}, {"question": "question", "authorized_collections": ["private"]}):
                with self.subTest(params=params), self.assertRaises(HTTPException) as caught:
                    server.query_rag(server.QueryRequest(**params))
                self.assertEqual(caught.exception.status_code, 422)

    def test_provider_initialization_failure_has_visible_fallback(self):
        pipeline = self.pipeline([result("gene:PPARG", "gene_info")])
        with patch.object(server, "get_pipeline", return_value=pipeline), patch.object(server, "build_llm_generator", side_effect=RuntimeError("missing provider")):
            response = server.query_rag(server.QueryRequest(question="Function of PPARG", api_key="test-key"))
        self.assertEqual(response.provider, "offline_fallback")
        self.assertTrue(any("unavailable" in note for note in response.limitations))
        self.assertEqual(response.validation["scope"], "citation_structure")
        self.assertFalse(response.validation["semantic_support_verified"])

    def test_missing_scores_remain_missing_and_zero_is_preserved(self):
        genes = {"NO_DATA": {"title": "No association evidence"}, "ZERO": {"title": "Zero evidence"}}
        common = {"ZERO": [{"metadata": {"phenotype": "2hrG", "bf_common": 0.0}}]}
        rare = {"ZERO": [{"metadata": {"phenotype": "2hrG", "bf_rare": 5.0, "pValue": 0.0}}]}
        with patch.object(server, "_GENE_INDEX", genes), patch.object(server, "_COMMON_ASSOC", common), patch.object(server, "_RARE_ASSOC", rare):
            missing = server.get_gene_details("NO_DATA")
            zero = server.get_gene_details("ZERO")
        self.assertIsNone(missing["huge_score"])
        self.assertEqual(missing["associations"], [])
        self.assertEqual(zero["huge_score"], 0)
        self.assertEqual(zero["associations"][0]["p_value"], 0)

    def test_partial_comparison_reports_missing_entity(self):
        run = self.pipeline([result("gene:PPARG", "gene_info")]).run(RetrievalRequest("Compare PPARG and TCF7L2"))
        self.assertEqual(run.answer.status, "qualified")
        self.assertTrue(any("TCF7L2" in limitation for limitation in run.answer.limitations))

    def test_association_sign_does_not_infer_drug_action(self):
        hit = result("rare:PPARG", "gene_association_rare", metadata={"gene": "PPARG", "beta": -0.42, "pValue": 0.01})
        run = self.pipeline([hit]).run(RetrievalRequest("Rare variant PPARG"))
        self.assertNotIn("inhibitor", run.answer.answer)
        self.assertNotIn("agonist", run.answer.answer)

    def test_evidence_endpoint_has_not_found_response(self):
        record = type("Record", (), {"chunk_id": "gene:PPARG", "collection": "gene_info", "to_dict": lambda self: {"content": "Evidence", "citation": {"chunk_id": self.chunk_id}}})()
        pipeline = self.pipeline([])
        pipeline.retriever.backend.records = [record]
        with patch.object(server, "get_pipeline", return_value=pipeline):
            self.assertEqual(server.get_evidence("gene:PPARG")["content"], "Evidence")
            with self.assertRaises(HTTPException) as caught:
                server.get_evidence("unknown")
            self.assertEqual(caught.exception.status_code, 404)

    def test_supported_collection_set_has_eight_members(self):
        self.assertEqual(len(SUPPORTED_COLLECTIONS), 8)
        self.assertEqual(len(set(SUPPORTED_COLLECTIONS)), 8)

    def test_entity_evidence_is_selected_before_passage_limit(self):
        hits = [result("gene:OTHER" + str(i), "gene_info", rank=i + 1) for i in range(6)]
        hits.append(result("gene:PPARG", "gene_info", rank=7))
        run = self.pipeline(hits).run(RetrievalRequest("Function of PPARG"))
        self.assertEqual(run.answer.status, "answer")
        self.assertEqual([p.chunk_id for p in run.context.passages], ["gene:PPARG"])

    def test_comparison_reserves_room_for_both_requested_genes(self):
        hits = [result("source:" + str(i), "gene_association_common", metadata={"gene": "PPARG"}) for i in range(6)]
        hits.append(result("source:TCF7L2", "gene_association_common", metadata={"gene": "TCF7L2"}))
        run = self.pipeline(hits).run(RetrievalRequest("Compare PPARG and TCF7L2 evidence tiers"))
        self.assertEqual({p.metadata["gene"] for p in run.context.passages}, {"PPARG", "TCF7L2"})
        self.assertIn("Evidence comparison", run.answer.answer)
