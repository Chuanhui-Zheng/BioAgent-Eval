from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from retrieval.corpus import LoadedCorpus
from retrieval.dense_retriever import (
    MockEncoder,
    build_dense_index,
    embedding_model_is_cached,
    load_dense_index,
    save_dense_index,
)
from retrieval.schema import ChunkRecord


def make_record(chunk_id: str, collection: str, content: str) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        collection=collection,
        entity_type="gene",
        title=chunk_id,
        content=content,
        metadata={"gene_symbol": chunk_id.split(":")[-1]},
        citation={"chunk_id": chunk_id},
    )


class DenseRetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            make_record("gene:TCF7L2", "gene_info", "Wnt signaling transcription factor TCF7L2"),
            make_record("gene:INS", "gene_info", "Insulin decreases blood glucose"),
            make_record(
                "gassoc_common:2hrG:ADCY5",
                "gene_association_common",
                "Common variant ADCY5 2hrG evidence",
            ),
        ]
        self.corpus = LoadedCorpus(self.records, chunk_hashes={}, collection_counts={})
        self.encoder = MockEncoder(dimension=8)
        self.index = build_dense_index(self.corpus, self.encoder, batch_size=2, progress=None)

    def test_index_shape(self) -> None:
        self.assertEqual(self.index.faiss_index.ntotal, 3)
        self.assertEqual(self.index.faiss_index.d, 8)

    def test_collection_filter(self) -> None:
        results = self.index.search(
            "ADCY5 common variant",
            top_k=5,
            collections=["gene_association_common"],
        )
        self.assertTrue(results)
        self.assertTrue(all(item.collection == "gene_association_common" for item in results))

    def test_save_and_load_preserves_ranks(self) -> None:
        query = "Insulin decreases blood glucose"
        before = [item.chunk_id for item in self.index.search(query, top_k=3)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dense"
            save_dense_index(self.index, path)
            loaded = load_dense_index(path, self.records, self.encoder)
        after = [item.chunk_id for item in loaded.search(query, top_k=3)]
        self.assertEqual(before, after)
        self.assertEqual(loaded.faiss_index.ntotal, 3)
        self.assertEqual(loaded.faiss_index.d, 8)

    def test_unknown_hub_repo_is_not_cached(self) -> None:
        self.assertFalse(embedding_model_is_cached("cs46-test/missing-embedding-model"))


if __name__ == "__main__":
    unittest.main()
