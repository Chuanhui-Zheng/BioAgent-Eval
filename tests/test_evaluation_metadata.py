import unittest
from pathlib import Path

from retrieval.evaluation import benchmark_metadata


class EvaluationMetadataTests(unittest.TestCase):
    def test_development_benchmark_keeps_legacy_output_name(self):
        metadata = benchmark_metadata(Path("data/evaluation/retrieval_dev.jsonl"), query_count=20)

        self.assertEqual(metadata.label, "development")
        self.assertEqual(metadata.hash_filename, "dev_set.sha256.txt")
        self.assertEqual(metadata.comparison_label, "same 20 queries, same router")

    def test_test_benchmark_uses_test_output_name_and_query_count(self):
        metadata = benchmark_metadata(Path("data/evaluation/retrieval_test_draft.jsonl"), query_count=100)

        self.assertEqual(metadata.label, "test")
        self.assertEqual(metadata.hash_filename, "test_set.sha256.txt")
        self.assertEqual(metadata.comparison_label, "same 100 queries, same router")


if __name__ == "__main__":
    unittest.main()
