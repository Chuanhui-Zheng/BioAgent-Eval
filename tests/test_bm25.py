from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from retrieval.bm25_retriever import build_bm25_index, load_bm25_index, save_bm25_index
from retrieval.corpus import LoadedCorpus
from retrieval.identifiers import record_identifier_keys
from retrieval.schema import ChunkRecord
from retrieval.tokenizer import tokenize, tokenize_query


def make_record(
    chunk_id: str,
    collection: str,
    title: str,
    content: str,
    metadata: dict | None = None,
) -> ChunkRecord:
    payload = {"gene_symbol": title.split()[-1]}
    if metadata:
        payload.update(metadata)
    return ChunkRecord(
        chunk_id=chunk_id,
        collection=collection,
        entity_type="gene",
        title=title,
        content=content,
        metadata=payload,
        citation={"chunk_id": chunk_id},
    )


class TokenizerTests(unittest.TestCase):
    def test_identifier_tokens_are_preserved(self) -> None:
        text = "TCF7L2 ENSG00000148737 2hrI 2hrG AC004233.4 ldsc:2hrI:T2D"
        tokens = tokenize(text)
        for expected in [
            "tcf7l2",
            "ensg00000148737",
            "2hri",
            "2hrg",
            "ac004233.4",
            "ldsc:2hri:t2d",
        ]:
            self.assertIn(expected, tokens)

    def test_query_stopwords_are_dropped(self) -> None:
        tokens = tokenize_query("What is the function of INS?")
        self.assertEqual(tokens, ["ins"])
        self.assertNotIn("function", tokens)


class BM25RetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            make_record(
                "gene:TCF7L2",
                "gene_info",
                "Gene TCF7L2",
                "Function: Wnt signaling gene TCF7L2",
                {"gene_symbol": "TCF7L2", "ensembl_gene_id": "ENSG00000148737", "alternative_names": ["TCF-4", "TCF4"]},
            ),
            make_record(
                "gene:INS",
                "gene_info",
                "Gene INS",
                "Function: Insulin decreases blood glucose concentration.",
                {"gene_symbol": "INS"},
            ),
            make_record(
                "gene:ADCK5",
                "gene_info",
                "Gene ADCK5",
                "Function: AarF domain containing kinase 5.",
                {"gene_symbol": "ADCK5"},
            ),
            make_record(
                "gassoc_common:2hrG:ADCY5",
                "gene_association_common",
                "Common-variant ADCY5",
                "Common variant evidence ADCY5 2hrG",
                {"gene": "ADCY5"},
            ),
            make_record(
                "ldsc:2hrI:T2D",
                "ldsc_genetic_correlation",
                "LDSC 2hrI vs T2D",
                "LDSC genetic correlation 2-hour insulin Type 2 Diabetes",
                {"other_phenotype": "T2D", "other_phenotype_label": "Type 2 Diabetes"},
            ),
            make_record(
                "ldsc:2hrI:T2D_insulin-deficient",
                "ldsc_genetic_correlation",
                "LDSC 2hrI vs T2D_insulin-deficient",
                "LDSC genetic correlation 2-hour insulin T2D insulin deficient",
                {
                    "other_phenotype": "T2D_insulin-deficient",
                    "other_phenotype_label": "T2D insulin deficient",
                },
            ),
        ]
        self.corpus = LoadedCorpus(self.records, chunk_hashes={}, collection_counts={})
        self.index = build_bm25_index(self.corpus, ("title", "content"))

    def test_search_ranks_exact_identifier_first(self) -> None:
        results = self.index.search("function of TCF7L2", top_k=3)
        self.assertEqual(results[0].chunk_id, "gene:TCF7L2")

    def test_short_gene_symbol_is_pinned(self) -> None:
        results = self.index.search("What is the function of INS?", top_k=3)
        self.assertEqual(results[0].chunk_id, "gene:INS")

    def test_ensembl_id_is_pinned(self) -> None:
        results = self.index.search("Which gene is identified by ENSG00000148737?", top_k=3)
        self.assertEqual(results[0].chunk_id, "gene:TCF7L2")

    def test_ldsc_other_phenotype_is_pinned(self) -> None:
        results = self.index.search(
            "Is 2-hour insulin genetically correlated with T2D according to LDSC?",
            top_k=3,
            collections=["ldsc_genetic_correlation"],
        )
        self.assertEqual(results[0].chunk_id, "ldsc:2hrI:T2D")

    def test_collection_filter(self) -> None:
        results = self.index.search("ADCY5 2hrG", top_k=3, collections=["gene_association_common"])
        self.assertTrue(results)
        self.assertTrue(all(item.collection == "gene_association_common" for item in results))

    def test_save_and_load_is_deterministic(self) -> None:
        query = "LDSC genetic correlation 2hrI T2D"
        before = [item.chunk_id for item in self.index.search(query, top_k=3)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bm25"
            save_bm25_index(self.index, path)
            loaded = load_bm25_index(path, self.records)
        after = [item.chunk_id for item in loaded.search(query, top_k=3)]
        self.assertEqual(before, after)

    def test_partitioned_ancestry_is_not_an_exact_identifier(self) -> None:
        for ancestry in ("EA", "EU", "HS", "Mixed"):
            with self.subTest(ancestry=ancestry):
                record = ChunkRecord(
                    chunk_id=f"ldsc_partitioned:2hrG:accessible_chromatin:bile_duct:cholangiocyte:{ancestry}",
                    collection="ldsc_partitioned_heritability",
                    entity_type="partitioned_heritability",
                    title="LDSC partitioned heritability",
                    content=f"Bile duct cholangiocyte ancestry {ancestry}",
                    metadata={"ancestry": ancestry}, citation={},
                )
                self.assertNotIn(ancestry.lower(), record_identifier_keys(record))

    def test_partitioned_tissue_ranking_survives_index_reload(self) -> None:
        records = [
            ChunkRecord(
                chunk_id=f"ldsc_partitioned:2hrG:accessible_chromatin:{tissue}:{biosample}:EA",
                collection="ldsc_partitioned_heritability",
                entity_type="partitioned_heritability",
                title=f"LDSC partitioned heritability {tissue} {biosample}",
                content=f"2hrG accessible_chromatin tissue {tissue} biosample {biosample} ancestry EA",
                metadata={"ancestry": "EA", "tissue": tissue, "biosample": biosample},
                citation={},
            )
            for tissue, biosample in [("adipose_tissue", "[null]"), ("bile_duct", "cholangiocyte")]
        ]
        index = build_bm25_index(LoadedCorpus(records, {}, {}), ("title", "content"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bm25"
            save_bm25_index(index, path)
            loaded = load_bm25_index(path, records)
            for searcher in (index, loaded):
                hits = searcher.search("2hrG bile_duct cholangiocyte ancestry EA", top_k=2)
                self.assertEqual(hits[0].chunk_id, records[1].chunk_id)
                self.assertEqual(hits[0].component_scores["exact_match"], 0)


if __name__ == "__main__":
    unittest.main()
