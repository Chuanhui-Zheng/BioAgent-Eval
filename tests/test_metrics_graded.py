import unittest

from retrieval.metrics import aggregate_dev_metrics, ndcg_at_k, recall_at_k


class GradedMetricTests(unittest.TestCase):
    def test_recall_at_k_counts_all_grade_two_chunks(self):
        self.assertEqual(
            recall_at_k(
                ["a", "x", "b"],
                {"a": 2, "b": 2, "support": 1},
                3,
            ),
            1.0,
        )
        self.assertEqual(
            recall_at_k(["a", "x", "b"], {"a": 2, "b": 2}, 1),
            0.5,
        )

    def test_ndcg_at_k_uses_grade_one_as_partial_relevance(self):
        perfect = ndcg_at_k(["direct", "support"], {"direct": 2, "support": 1}, 2)
        reversed_order = ndcg_at_k(["support", "direct"], {"direct": 2, "support": 1}, 2)

        self.assertEqual(perfect, 1.0)
        self.assertLess(reversed_order, perfect)

    def test_aggregate_reports_recall_and_ndcg(self):
        rows = [
            {
                "example": {
                    "query_type": "gene_function",
                    "target_collections": ["gene_info"],
                    "relevance_judgments": [
                        {"chunk_id": "direct", "grade": 2},
                        {"chunk_id": "support", "grade": 1},
                    ],
                },
                "route": {"collections": ["gene_info"]},
                "routed": {
                    "results": [
                        {"chunk_id": "direct"},
                        {"chunk_id": "support"},
                    ]
                },
            }
        ]

        metrics = aggregate_dev_metrics(rows, (1, 3), "routed")["metrics"]

        self.assertEqual(metrics["Recall@1"], 1.0)
        self.assertEqual(metrics["Recall@3"], 1.0)
        self.assertEqual(metrics["nDCG@3"], 1.0)


if __name__ == "__main__":
    unittest.main()
