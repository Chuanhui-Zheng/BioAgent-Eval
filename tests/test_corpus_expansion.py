from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT
for directory in (ROOT, ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(directory))

import json
import tempfile
import unittest
import yaml
from chunking.utils import file_sha256
from retrieval.config import ChunkSource, load_retrieval_config
from retrieval.corpus import load_corpus, load_corpus_from_config, load_manifest_counts
from retrieval.router import ALL_COLLECTIONS, route_query
from argparse import Namespace
from unittest.mock import patch
from prepare_partitioned_retrieval import prepare_manifest
from retrieval.router import ALL_COLLECTIONS
import chunk_corpus
from tests.test_ldsc_partitioned import sample
from tests.test_ldsc_partitioned import TokenizerStub


NEW = "ldsc_partitioned_heritability"

EXPANDED = [*ALL_COLLECTIONS, NEW]

class PartitionedRetrievalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chunks = self.root / "partitioned.chunks.jsonl"
        record = {"chunk_id": "partitioned:example", "collection": NEW,
                  "entity_type": "partitioned_heritability", "title": "Partitioned heritability",
                  "content": "LDSC partitioned heritability: 2hrG adipose_tissue EA",
                  "metadata": {"ancestry": "EA"}, "citation": {"source_file": "raw.jsonl"}}
        self.chunks.write_text(json.dumps(record) + "\n", encoding="utf-8")
        self.manifest = self.root / "manifest.json"
        self.entry = {"collection": NEW, "path": self.chunks.name, "chunks": 1,
                      "sha256": file_sha256(self.chunks)}
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps({"outputs": {self.chunks.name: self.entry}}))

    def test_manifest_supports_explicit_collection_and_new_filename(self):
        self.assertEqual(load_manifest_counts(self.manifest), {NEW: 1})

    def test_clumped_region_intent_routes_to_new_collection(self):
        name = "variant_association_clumped"
        for query in ("Clumped GWAS association regions for 2hrG", "leadSNP for clump 3",
                      "2hrG 的关联区域和先导变异", "Which source lead variant is in clumped region 3?"):
            with self.subTest(query=query):
                self.assertEqual(route_query(query, available_collections=[*EXPANDED, name]).collections, [name])

    def test_unavailable_clumped_intent_does_not_route_to_gene_association(self):
        self.assertEqual(route_query("Clumped GWAS association region", available_collections=EXPANDED).collections, [])

    def test_compare_gene_association_and_clumped_evidence_routes_both(self):
        self.assertEqual(route_query("Compare common gene association with clumped regions",
                                     available_collections=[*EXPANDED, "variant_association_clumped"]).collections,
                         ["gene_association_common", "variant_association_clumped"])

    def test_unclassified_gene_association_comparison_keeps_both_classes(self):
        for query in ("Compare gene association with clumped regions",
                      "Compare clumped lead variants and gene-based association evidence"):
            with self.subTest(query=query):
                self.assertEqual(route_query(query, available_collections=[*EXPANDED, "variant_association_clumped"]).collections,
                                 ["gene_association_common", "gene_association_rare", "variant_association_clumped"])

    def test_config_uses_manifest_total_instead_of_baseline_constant(self):
        config_file = self.root / "retrieval.yaml"
        config_file.write_text(yaml.safe_dump({"chunks": [{"collection": NEW, "path": self.chunks.name}],
                                               "manifest": self.manifest.name}))
        corpus = load_corpus_from_config(load_retrieval_config(self.root, config_file))
        self.assertEqual(len(corpus.records), 1)
        self.assertEqual(corpus.collection_counts, {NEW: 1})

    def test_modified_chunk_hash_is_rejected_even_if_count_unchanged(self):
        record = json.loads(self.chunks.read_text())
        record["content"] += " changed"
        self.chunks.write_text(json.dumps(record) + "\n")
        with self.assertRaisesRegex(ValueError, "hash"):
            load_corpus([ChunkSource(NEW, self.chunks)], manifest_file=self.manifest, expected_total=1)

    def test_configured_manifest_cannot_be_missing(self):
        self.manifest.unlink()
        with self.assertRaises(FileNotFoundError):
            load_corpus([ChunkSource(NEW, self.chunks)], manifest_file=self.manifest, expected_total=1)

    def test_manifest_path_cannot_point_to_a_different_artifact(self):
        self.entry["path"] = "different.chunks.jsonl"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "path"):
            load_corpus([ChunkSource(NEW, self.chunks)], manifest_file=self.manifest, expected_total=1)

    def test_manifest_collection_set_must_match_loaded_sources(self):
        self.entry["collection"] = "gene_info"
        self.write_manifest()
        with self.assertRaises(ValueError):
            load_corpus([ChunkSource(NEW, self.chunks)], manifest_file=self.manifest, expected_total=1)

    def test_partitioned_intent_is_separate_from_genetic_correlation(self):
        for query in ("LDSC partitioned heritability for 2hrG in adipose tissue",
                      "GWAS-based heritability enrichment in accessible_chromatin",
                      "2hrG 的分区遗传力结果", "enrichment_beta in fat_cell",
                      "partitioned heritability for 2hrI", "partition heritability for 2hrG"):
            with self.subTest(query=query):
                self.assertEqual(route_query(query, available_collections=EXPANDED).collections, [NEW])

    def test_explicit_correlation_stays_in_old_collection(self):
        self.assertEqual(route_query("LDSC genetic correlation between 2hrI and T2D",
                                     available_collections=EXPANDED).collections, ["ldsc_genetic_correlation"])

    def test_cross_ldsc_question_routes_to_both(self):
        decision = route_query("Compare partitioned heritability and genetic correlation",
                               available_collections=EXPANDED)
        self.assertEqual(decision.collections, ["ldsc_genetic_correlation", NEW])

    def test_unmatched_uses_configured_collections_only(self):
        self.assertEqual(route_query("unmatched question").collections, ALL_COLLECTIONS)
        self.assertEqual(route_query("unmatched question", available_collections=EXPANDED).collections, EXPANDED)
        self.assertEqual(route_query("unmatched question", available_collections=[NEW]).collections, [NEW])

    def test_bare_ldsc_is_ambiguous_across_two_evidence_types(self):
        self.assertEqual(route_query("LDSC results", available_collections=EXPANDED).collections,
                         ["ldsc_genetic_correlation", NEW])

    def test_unavailable_intent_does_not_return_wrong_evidence_class(self):
        decision = route_query("partitioned heritability", available_collections=ALL_COLLECTIONS)
        self.assertEqual(decision.collections, [])


class PreparePartitionedRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.dev = self.root / "artifacts/ingestion_dev/ldsc_partitioned"
        self.dev.mkdir(parents=True)
        self.sources = []
        outputs = {}
        for collection in [*ALL_COLLECTIONS, "ldsc_partitioned_heritability"]:
            folder = self.dev if collection == "ldsc_partitioned_heritability" else self.root / "artifacts/chunks"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (collection + ".chunks.jsonl")
            path.write_text(json.dumps({"chunk_id": collection + ":1", "collection": collection,
                                       "entity_type": "test", "title": "Test", "content": "Evidence",
                                       "metadata": {"ancestry": "EA"},
                                       "citation": {"source_file": "raw.jsonl"}}) + "\n", encoding="utf-8")
            relative = path.relative_to(self.root).as_posix()
            self.sources.append({"collection": collection, "path": relative})
            outputs[path.name] = {"collection": collection, "path": relative,
                                  "chunks": 1, "sha256": file_sha256(path)}
        self.new_chunks = self.root / self.sources[-1]["path"]
        self.baseline_manifest = self.root / "artifacts/manifest.json"
        self.baseline_manifest.write_text(json.dumps({"pipeline_version": "1.1.0", "sources": {},
                                                      "outputs": dict(list(outputs.items())[:-1])}), encoding="utf-8")
        baseline_config = {"chunks": self.sources[:-1], "manifest": "artifacts/manifest.json"}
        (self.root / "config/retrieval.yaml").write_text(yaml.safe_dump(baseline_config), encoding="utf-8")
        self.config = self.dev / "retrieval_dev.yaml"
        self.destination = self.dev / "retrieval_manifest.json"
        self.write_config(self.destination)
        self.build_manifest = self.dev / "manifest.json"
        self.build_manifest.write_text(json.dumps({"partial": False, "created_at": "run-1",
                                                  "output": outputs[self.new_chunks.name],
                                                  "dense_config_snapshot": {"model": "Qwen/Qwen3-Embedding-0.6B",
                                                                            "max_seq_length": 512},
                                                  "source": {"path": "raw.jsonl"}, "glossary": {}}), encoding="utf-8")
        self.report = self.dev / "validation_report.json"
        self.report.write_text(json.dumps({"partial": False, "created_at": "run-1", "status": "passed",
                                          "chunk_sha256": file_sha256(self.new_chunks)}), encoding="utf-8")

    def write_config(self, destination):
        self.config.write_text(yaml.safe_dump({"chunks": self.sources,
                                              "manifest": destination.relative_to(self.root).as_posix()}), encoding="utf-8")

    def assert_collision_rejected(self, path):
        self.write_config(path)
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite|input|collision"):
            prepare_manifest(self.config, project_root=self.root)
        self.assertEqual(path.read_bytes(), before)

    def test_chunk_input_cannot_be_manifest_destination(self):
        self.assert_collision_rejected(self.new_chunks)

    def test_build_manifest_cannot_be_destination(self):
        self.assert_collision_rejected(self.build_manifest)

    def test_validation_report_cannot_be_destination(self):
        self.assert_collision_rejected(self.report)

    def test_config_input_cannot_be_destination(self):
        self.assert_collision_rejected(self.config)

    def test_main_config_can_select_expanded_corpus_with_separate_baseline_manifest(self):
        cfg = yaml.safe_load(self.config.read_text())
        cfg["baseline_manifest"] = self.baseline_manifest.relative_to(self.root).as_posix()
        primary = self.root / "config/retrieval.yaml"
        primary.write_text(yaml.safe_dump(cfg))
        before = self.baseline_manifest.read_bytes()
        result = prepare_manifest(primary, project_root=self.root)
        self.assertEqual(result["total"], 5)
        self.assertEqual(self.baseline_manifest.read_bytes(), before)
        self.assertEqual(len(json.loads(self.destination.read_text())["outputs"]), 5)

    def test_merged_main_config_still_rejects_baseline_reordering(self):
        cfg = yaml.safe_load(self.config.read_text())
        cfg["baseline_manifest"] = self.baseline_manifest.relative_to(self.root).as_posix()
        cfg["chunks"][0], cfg["chunks"][1] = cfg["chunks"][1], cfg["chunks"][0]
        primary = self.root / "config/retrieval.yaml"
        primary.write_text(yaml.safe_dump(cfg))
        with self.assertRaisesRegex(ValueError, "order"):
            prepare_manifest(primary, project_root=self.root)
        self.assertFalse(self.destination.exists())

    def test_success_preserves_inputs_and_loads_five_collections(self):
        protected = [self.new_chunks, self.build_manifest, self.report, self.baseline_manifest, self.config]
        before = {path: path.read_bytes() for path in protected}
        result = prepare_manifest(self.config, project_root=self.root)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["collections"]), 5)
        self.assertTrue(self.destination.exists())
        self.assertEqual({path: path.read_bytes() for path in protected}, before)

    def test_changed_chunks_rejected_without_publishing(self):
        self.new_chunks.write_text(self.new_chunks.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash"):
            prepare_manifest(self.config, project_root=self.root)
        self.assertFalse(self.destination.exists())

    def test_changed_dense_model_or_limit_requires_new_validation(self):
        for changes in ({"model": "different-model"}, {"max_seq_length": 128}):
            with self.subTest(changes=changes):
                self.write_config(self.destination)
                config = yaml.safe_load(self.config.read_text())
                config["dense"] = changes
                self.config.write_text(yaml.safe_dump(config))
                with self.assertRaisesRegex(ValueError, "dense|token|model"):
                    prepare_manifest(self.config, project_root=self.root)
                self.assertFalse(self.destination.exists())

    def add_clumped_fixture(self):
        directory = self.root / "artifacts/ingestion_dev/clumped"
        directory.mkdir()
        chunk_file = directory / "metaanalysis_clumped_2hrG_EU.chunks.jsonl"
        record = {"chunk_id": "clumped:2hrG:EU:10:3:100-201", "collection": "variant_association_clumped",
                  "entity_type": "variant_association_region", "title": "Clumped region",
                  "content": "Source-designated lead variant in clumped association region",
                  "metadata": {"member_count": 2}, "citation": {"source_file": "clumped.jsonl"}}
        chunk_file.write_text(json.dumps(record) + '\n')
        built = {"partial": False, "created_at": "clumped-run", "collection": "variant_association_clumped",
                 "dense_config_snapshot": {"model": "Qwen/Qwen3-Embedding-0.6B", "max_seq_length": 512},
                 "output": {"path": chunk_file.relative_to(self.root).as_posix(), "chunks": 1,
                            "sha256": file_sha256(chunk_file)},
                 "source": {"path": "clumped.jsonl"}, "glossary": {}}
        (directory / "manifest.json").write_text(json.dumps(built))
        (directory / "validation_report.json").write_text(json.dumps({"status": "passed", "partial": False,
            "created_at": "clumped-run", "chunk_sha256": file_sha256(chunk_file)}))
        config = yaml.safe_load(self.config.read_text())
        config["chunks"].append({"collection": "variant_association_clumped", "path": built["output"]["path"]})
        config["clumped_build_manifest"] = (directory / "manifest.json").relative_to(self.root).as_posix()
        config["clumped_validation_report"] = (directory / "validation_report.json").relative_to(self.root).as_posix()
        self.config.write_text(yaml.safe_dump(config))
        return directory

    def test_seven_collection_manifest_includes_wes_and_checks_baseline_link(self):
        self.add_clumped_fixture()
        directory = self.root / "artifacts/ingestion_dev/wes"
        directory.mkdir()
        chunk_file = directory / "wes_2hrG.chunks.jsonl"
        chunk_file.write_text(json.dumps({"chunk_id":"wes:2hrG:A:summary", "collection":"gene_association_wes",
            "entity_type":"gene_phenotype_summary", "title":"WES A", "content":"WES gene summary",
            "metadata":{}, "citation":{"source_file":"wes.jsonl"}})+'\n')
        rare = self.root / self.sources[3]["path"]
        built = {"partial":False, "created_at":"wes-run", "collection":"gene_association_wes",
            "output":{"path":chunk_file.relative_to(self.root).as_posix(), "chunks":1, "sha256":file_sha256(chunk_file)},
            "source":{"path":"wes.jsonl"}, "glossary":{},
            "baseline_reference":{"path":rare.relative_to(self.root).as_posix(), "sha256":file_sha256(rare)},
            "dense_config_snapshot":{"model":"Qwen/Qwen3-Embedding-0.6B", "max_seq_length":512}}
        (directory/"manifest.json").write_text(json.dumps(built))
        (directory/"validation_report.json").write_text(json.dumps({"status":"passed", "partial":False,
            "created_at":"wes-run", "chunk_sha256":file_sha256(chunk_file)}))
        cfg=yaml.safe_load(self.config.read_text())
        cfg["chunks"].append({"collection":"gene_association_wes", "path":built["output"]["path"]})
        cfg["wes_build_manifest"]=(directory/"manifest.json").relative_to(self.root).as_posix()
        cfg["wes_validation_report"]=(directory/"validation_report.json").relative_to(self.root).as_posix()
        self.config.write_text(yaml.safe_dump(cfg))
        self.assertEqual(prepare_manifest(self.config,project_root=self.root)["total"],7)
        built["baseline_reference"]["sha256"]="invalid"
        (directory/"manifest.json").write_text(json.dumps(built))
        with self.assertRaisesRegex(ValueError,"baseline"):
            prepare_manifest(self.config,project_root=self.root)

    def test_six_collection_manifest_validates_both_additions(self):
        self.add_clumped_fixture()
        baseline = self.baseline_manifest.read_bytes()
        result = prepare_manifest(self.config, project_root=self.root)
        self.assertEqual(result["total"], 6)
        self.assertEqual(result["collections"]["variant_association_clumped"], 1)
        self.assertEqual(self.baseline_manifest.read_bytes(), baseline)

    def test_failed_clumped_build_cannot_be_published_in_expanded_manifest(self):
        directory = self.add_clumped_fixture()
        report = json.loads((directory / "validation_report.json").read_text())
        report["status"] = "failed"
        (directory / "validation_report.json").write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "failed"):
            prepare_manifest(self.config, project_root=self.root)
        self.assertFalse(self.destination.exists())

    def configure_canonical(self):
        final = self.root / "artifacts/chunks/ldsc_partitioned_2hrG.chunks.jsonl"
        self.new_chunks.replace(final)
        self.sources[-1]["path"] = final.relative_to(self.root).as_posix()
        built = json.loads(self.build_manifest.read_text())
        built["output"]["path"] = self.sources[-1]["path"]
        self.build_manifest.write_text(json.dumps(built))
        paths_config = self.root / "config/paths.yaml"
        paths_config.write_text(yaml.safe_dump({
            "raw": {"gene_info": "unused", "ldsc_2hri": "unused", "gene_id_map": "unused",
                    "gene_association_common_2hrg": "unused", "gene_association_rare_2hrg": "unused",
                    "ldsc_partitioned_2hrg": "raw.jsonl"},
            "artifacts": {"chunks_dir": "artifacts/chunks", "manifest": "artifacts/manifest.json",
                          "partitioned_manifest": "artifacts/manifest_partitioned.json"},
            "config": {"phenotype_glossary": "glossary.json"},
        }))
        config = {"chunks": self.sources, "manifest": "artifacts/manifest_partitioned.json",
                  "paths_config": "config/paths.yaml",
                  "partitioned_build_manifest": self.build_manifest.relative_to(self.root).as_posix(),
                  "partitioned_validation_report": self.report.relative_to(self.root).as_posix()}
        self.config.write_text(yaml.safe_dump(config))
        return final

    def test_canonical_chunks_use_explicit_build_metadata_and_registered_manifest(self):
        final = self.configure_canonical()
        before = {p: p.read_bytes() for p in (final, self.baseline_manifest, self.build_manifest, self.report)}
        result = prepare_manifest(self.config, project_root=self.root)
        self.assertEqual(result["total"], 5)
        self.assertTrue((self.root / "artifacts/manifest_partitioned.json").exists())
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_existing_pipeline_can_build_only_partitioned_collection(self):
        final = self.configure_canonical()
        (self.root / "raw.jsonl").write_text(json.dumps(sample()) + "\n")
        (self.root / "glossary.json").write_text(json.dumps({"2hrG": {"label": "2-hour glucose (OGTT)"}}))
        baseline_config_path = self.root / "config/retrieval.yaml"
        baseline_config = yaml.safe_load(baseline_config_path.read_text())
        baseline_config["dense"] = {"model": "cached-model", "max_seq_length": 512}
        baseline_config_path.write_text(yaml.safe_dump(baseline_config))
        expanded = yaml.safe_load(self.config.read_text())
        expanded["dense"] = baseline_config["dense"]
        self.config.write_text(yaml.safe_dump(expanded))
        build_config = self.root / "config/ldsc_partitioned_dev.yaml"
        build_config.write_text(yaml.safe_dump({"paths_config": "config/paths.yaml",
                                               "raw_file": "raw.jsonl", "glossary_file": "glossary.json",
                                               "retrieval_config": "config/retrieval.yaml",
                                               "output_dir": self.dev.relative_to(self.root).as_posix()}))
        protected = [self.baseline_manifest, *(self.root / s["path"] for s in self.sources[:-1])]
        before = {p: p.read_bytes() for p in protected}
        args = Namespace(paths_config=self.root / "config/paths.yaml", gene_file=None,
                         ldsc_file=None, glossary_file=None, output_dir=None, manifest_file=None,
                         dry_run=0, partitioned_only=True, include_partitioned=False,
                         partitioned_config=build_config, partitioned_retrieval_config=self.config)
        with patch.object(chunk_corpus, "PROJECT_ROOT", self.root), \
                patch.object(chunk_corpus, "parse_args", return_value=args), \
                patch("chunk_ldsc_partitioned.load_tokenizer", return_value=TokenizerStub()):
            self.assertEqual(chunk_corpus.main(), 0)
        self.assertEqual(json.loads(final.read_text())["collection"], "ldsc_partitioned_heritability")
        self.assertEqual({p: p.read_bytes() for p in protected}, before)


if __name__ == "__main__":
    unittest.main()
