from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from retrieval.hybrid_retriever import HybridRetriever, rrf_fuse
from retrieval.schema import SearchResult


def hit(chunk_id: str, collection: str, rank: int, score: float = 1.0, method: str = "bm25") -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        collection=collection,
        rank=rank,
        score=score,
        method=method,
        component_scores={},
        chunk={"chunk_id": chunk_id},
    )


class StubIndex:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results

    def search(self, query, top_k=10, collections=None, filters=None):
        items = self.results
        if collections is not None:
            items = [item for item in items if item.collection in collections]
        return items[:top_k]


class RrfTests(unittest.TestCase):
    def test_formula_and_union(self) -> None:
        bm25 = [hit("a", "gene_info", 1, 9.0), hit("b", "gene_info", 2, 3.0)]
        dense = [hit("b", "gene_info", 1, 0.9, "dense"), hit("c", "gene_info", 2, 0.8, "dense")]
        fused = rrf_fuse(bm25, dense, rrf_k=60, weight_bm25=1.0, weight_dense=1.0, top_k=10)
        scores = {item.chunk_id: item.score for item in fused}
        self.assertAlmostEqual(scores["a"], 1.0 / 61)
        self.assertAlmostEqual(scores["c"], 1.0 / 62)
        self.assertAlmostEqual(scores["b"], 1.0 / 62 + 1.0 / 61)
        self.assertEqual([item.chunk_id for item in fused], ["b", "a", "c"])
        self.assertEqual(fused[0].method, "hybrid_rrf")
        self.assertEqual(fused[0].component_scores["bm25_rank"], 2)
        self.assertEqual(fused[0].component_scores["dense_rank"], 1)

    def test_missing_method_contributes_zero(self) -> None:
        fused = rrf_fuse(
            [hit("only-bm25", "gene_info", 1)],
            [],
            rrf_k=60,
            top_k=5,
        )
        self.assertEqual(len(fused), 1)
        self.assertAlmostEqual(fused[0].score, 1.0 / 61)
        self.assertIsNone(fused[0].component_scores["dense_rank"])

    def test_tie_break_best_rank_then_chunk_id(self) -> None:
        bm25 = [hit("gene:z", "gene_info", 1), hit("gene:a", "gene_info", 1)]
        dense = [hit("gene:z", "gene_info", 5, method="dense"), hit("gene:a", "gene_info", 5, method="dense")]
        fused = rrf_fuse(bm25, dense, rrf_k=60, top_k=2)
        # equal RRF and equal best rank 1 -> lexical chunk_id
        self.assertEqual([item.chunk_id for item in fused], ["gene:a", "gene:z"])

        left = rrf_fuse([hit("x", "gene_info", 3)], [hit("y", "gene_info", 1, method="dense")], rrf_k=60, top_k=2)
        self.assertEqual(left[0].chunk_id, "y")

    def test_hybrid_respects_collection_filter(self) -> None:
        retriever = HybridRetriever(
            bm25=StubIndex(
                [
                    hit("gene:INS", "gene_info", 1),
                    hit("gassoc_common:2hrG:ADCY5", "gene_association_common", 2),
                ]
            ),
            dense=StubIndex(
                [
                    hit("gassoc_common:2hrG:ADCY5", "gene_association_common", 1, method="dense"),
                    hit("gene:INS", "gene_info", 2, method="dense"),
                ]
            ),
            candidate_k=10,
        )
        results = retriever.search("ADCY5", top_k=5, collections=["gene_association_common"])
        self.assertTrue(results)
        self.assertTrue(all(item.collection == "gene_association_common" for item in results))
        self.assertEqual(results[0].chunk_id, "gassoc_common:2hrG:ADCY5")


if __name__ == "__main__":
    unittest.main()
