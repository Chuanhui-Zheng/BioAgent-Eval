from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT
for directory in (ROOT, ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(directory))

import hashlib
import json
import tempfile
import unittest
from chunking.ldsc_partitioned_chunker import chunk_ldsc_partitioned
from chunking.phenotype_glossary import PhenotypeGlossary
from unittest.mock import patch
import yaml
from chunk_ldsc_partitioned import build_partitioned


def sample(**changes):
    row = {
        "phenotype": "2hrG", "annotation": "accessible_chromatin",
        "tissue": "adipose_tissue", "biosample": "adipose_tissue",
        "ancestry": "EA", "SNPs": 0.021517342075613042,
        "h2_beta": 1.5451070814667924, "h2_stdErr": 10.145319523038026,
        "enrichment_beta": 71.80752511333449,
        "enrichment_stdErr": 471.49501492270065,
        "coefficient_beta": -9.332735785701083e-6,
        "coefficient_stdErr": 8.040282127843968e-6,
        "diff_beta": -8.868266378196636e-6,
        "diff_stdErr": 5.789584180791003e-6,
        "pValue": 0.12716134501704568,
    }
    row.update(changes)
    return row

class PartitionedChunkingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "data" / "partitioned.jsonl"
        self.source.parent.mkdir()
        self.glossary = PhenotypeGlossary({
            "2hrG": {"label": "2-hour glucose (OGTT)", "category": "quantitative_trait"}
        })

    def chunks(self, rows):
        self.source.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        return list(chunk_ldsc_partitioned(self.source, self.glossary, self.root))

    def test_ancestries_are_separate_but_share_group(self):
        rows = [sample(ancestry=a) for a in ("EA", "EU", "HS", "Mixed")]
        chunks = self.chunks(rows)
        self.assertEqual(len(chunks), 4)
        self.assertEqual(len({c.chunk_id for c in chunks}), 4)
        self.assertEqual(len({c.metadata["group_id"] for c in chunks}), 1)
        self.assertEqual({c.metadata["ancestry"] for c in chunks}, {"EA", "EU", "HS", "Mixed"})
        for c in chunks:
            self.assertEqual(c.collection, "ldsc_partitioned_heritability")
            self.assertEqual(c.entity_type, "partitioned_heritability")
            self.assertIn("2-hour glucose (OGTT)", c.content)

    def test_ids_are_readable_composite_keys(self):
        chunk = self.chunks([sample()])[0]
        self.assertEqual(chunk.chunk_id,
                         "ldsc_partitioned:2hrG:accessible_chromatin:adipose_tissue:adipose_tissue:EA")
        self.assertEqual(chunk.metadata["group_id"],
                         "ldsc_partitioned_group:2hrG:accessible_chromatin:adipose_tissue:adipose_tissue")

    def test_ranking_text_frontloads_identity_without_guessing_definitions(self):
        chunks = self.chunks([sample(ancestry="EA"), sample(ancestry="EU")])
        for chunk in chunks:
            self.assertTrue(chunk.content.startswith(
                f"LDSC partitioned heritability. Ancestry code: {chunk.metadata['ancestry']}."))
            self.assertIn("accessible_chromatin (accessible chromatin)", chunk.content)
            self.assertIn("adipose_tissue (adipose tissue)", chunk.content)
            self.assertIn("not causal evidence or individual measurements", chunk.content)
            self.assertIn("ancestry-code meanings, pValue test and source release are unconfirmed", chunk.content)
            statistics = [line for line in chunk.content.splitlines() if line.startswith("- ")]
            self.assertEqual(len(statistics), 10)
            self.assertEqual(chunk.metadata["raw_record"]["enrichment_beta"], 71.80752511333449)

    def test_reserved_missing_markers_and_percent_escapes_are_distinct(self):
        missing = sample()
        del missing["biosample"]
        chunks = self.chunks([missing, sample(biosample=None), sample(biosample="[null]"),
                              sample(biosample="[missing]"), sample(biosample="a:b"),
                              sample(biosample="a%3Ab")])
        identifiers = {c.chunk_id for c in chunks}
        self.assertEqual(len(identifiers), 6)
        self.assertTrue(any(":[null]:EA" in value for value in identifiers))
        self.assertTrue(any(":%5Bnull%5D:EA" in value for value in identifiers))
        self.assertTrue(any(":a%3Ab:EA" in value for value in identifiers))
        self.assertTrue(any(":a%253Ab:EA" in value for value in identifiers))

    def test_biosample_supports_spaced_and_source_tokens(self):
        from retrieval.tokenizer import tokenize

        row = sample(biosample="vein_endothelial_cell")
        chunk = self.chunks([row])[0]
        self.assertIn("Biosample: vein_endothelial_cell (vein endothelial cell).", chunk.content)
        tokens = set(tokenize(chunk.content))
        self.assertTrue(set(tokenize("vein endothelial cell")).issubset(tokens))
        self.assertIn("vein_endothelial_cell", tokens)
        self.assertEqual(chunk.metadata["raw_record"], row)
        self.assertEqual(chunk.metadata["biosample"], "vein_endothelial_cell")
        self.assertTrue(chunk.chunk_id.endswith(":vein_endothelial_cell:EA"))

    def test_biosample_without_underscores_or_value_has_no_redundant_alias(self):
        missing = sample()
        del missing["biosample"]
        chunks = self.chunks([missing, sample(biosample=None), sample(biosample="cell")])
        for chunk in chunks:
            expected = {"missing": "[missing]", "null": "[null]", "provided": "cell"}[
                chunk.metadata["biosample_status"]]
            self.assertIn(f"Biosample: {expected}.", chunk.content)
            self.assertNotIn(f"Biosample: {expected} (", chunk.content)

    def test_complete_raw_record_and_precision_are_preserved(self):
        row = sample(extra={"release": None, "codes": ["a", "b"]})
        chunk = self.chunks([row])[0]
        self.assertEqual(chunk.metadata["raw_record"], row)
        self.assertEqual(chunk.to_dict()["metadata"]["raw_record"], row)
        self.assertEqual(chunk.metadata["raw_record"]["h2_beta"], 1.5451070814667924)
        self.assertIn("h2_beta=1.545", chunk.content)
        self.assertIn("4 significant digits", chunk.content)

    def test_source_citation_points_to_original_line_and_hash(self):
        rows = [sample(), sample(ancestry="EU")]
        chunks = self.chunks(rows)
        expected_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        for c in chunks:
            line = c.citation["source_row"]
            self.assertEqual(c.metadata["raw_record"], rows[line - 1])
            self.assertEqual(c.citation["source_file"], "data/partitioned.jsonl")
            self.assertEqual(c.citation["source_sha256"], expected_hash)
            self.assertEqual(c.metadata["source_sha256"], expected_hash)
            self.assertEqual(c.citation["chunk_id"], c.chunk_id)

    def test_biosamples_are_not_merged(self):
        chunks = self.chunks([sample(), sample(biosample="fat_cell")])
        self.assertEqual(len({c.metadata["group_id"] for c in chunks}), 2)

    def test_missing_null_and_literal_null_biosamples_stay_distinct(self):
        missing = sample()
        del missing["biosample"]
        chunks = self.chunks([missing, sample(biosample=None), sample(biosample="null")])
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len({c.metadata["group_id"] for c in chunks}), 3)
        self.assertEqual({c.metadata["biosample_status"] for c in chunks}, {"missing", "null", "provided"})

    def test_duplicate_identity_reports_both_source_rows(self):
        with self.assertRaisesRegex(ValueError, r"[Dd]uplicate.*1.*2"):
            self.chunks([sample(), sample(h2_beta=0.5)])

    def test_negative_and_large_estimates_are_not_clipped(self):
        row = sample(h2_beta=-2.5, enrichment_beta=1500, coefficient_beta=-0.4)
        chunk = self.chunks([row])[0]
        self.assertEqual(chunk.metadata["raw_record"], row)
        self.assertIn("h2_beta=-2.5", chunk.content)
        self.assertIn("enrichment_beta=1500", chunk.content)
        self.assertNotIn("is_significant", chunk.metadata)
        self.assertNotIn("not significant", chunk.content.lower())
        self.assertIn("unconfirmed", chunk.content)
        self.assertIn("pValue", chunk.metadata["unconfirmed_definitions"])
        self.assertNotIn("European", chunk.content)

    def test_invalid_statistics_are_rejected_with_source_line(self):
        for field, value in [("pValue", -0.1), ("pValue", 1.1), ("pValue", True),
                             ("h2_beta", float("nan")), ("diff_beta", float("inf")),
                             ("h2_stdErr", -1), ("SNPs", "0.2")]:
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, rf"line 1.*{field}"):
                    self.chunks([sample(**{field: value})])

    def test_missing_statistics_and_empty_identity_are_rejected(self):
        row = sample()
        del row["diff_stdErr"]
        with self.assertRaisesRegex(ValueError, "diff_stdErr"):
            self.chunks([row])
        with self.assertRaisesRegex(ValueError, "phenotype"):
            self.chunks([sample(phenotype=" ")])

    def test_ids_and_content_are_stable_after_reordering(self):
        rows = [sample(ancestry="EU"), sample(), sample(biosample="fat_cell")]
        first = self.chunks(rows)
        second = self.chunks(list(reversed(rows)))
        self.assertEqual([c.chunk_id for c in first], [c.chunk_id for c in second])
        self.assertEqual([c.content for c in first], [c.content for c in second])
        self.assertEqual([c.metadata["group_id"] for c in first], [c.metadata["group_id"] for c in second])

    def test_separator_characters_do_not_cause_identity_collision(self):
        chunks = self.chunks([sample(tissue="a:b", biosample="c"), sample(tissue="a", biosample="b:c")])
        self.assertNotEqual(chunks[0].chunk_id, chunks[1].chunk_id)

    def test_bom_and_blank_lines_preserve_physical_line_numbers(self):
        self.source.write_text("\ufeff\n" + json.dumps(sample()) + "\n", encoding="utf-8")
        chunk = list(chunk_ldsc_partitioned(self.source, self.glossary, self.root))[0]
        self.assertEqual(chunk.citation["source_row"], 2)

    def test_malformed_and_non_object_json_report_line(self):
        for text in ("{oops}\n", "[]\n"):
            with self.subTest(text=text):
                self.source.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "line 1"):
                    list(chunk_ldsc_partitioned(self.source, self.glossary, self.root))


class TokenizerStub:
    def __init__(self, length=250):
        self.length = length
        self.calls = []

    def __call__(self, text, **kwargs):
        self.calls.append(kwargs)
        return {"input_ids": [0] * self.length}

class PartitionedPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw.jsonl"
        self.raw.write_text(json.dumps(sample()) + "\n" + json.dumps(sample(ancestry="EU")) + "\n")
        (self.root / "glossary.json").write_text(json.dumps({"2hrG": {"label": "2-hour glucose (OGTT)"}}))
        (self.root / "retrieval.yaml").write_text(yaml.safe_dump({"dense": {"model": "cached-model", "max_seq_length": 512}}))
        self.config = self.root / "dev.yaml"
        self.output = self.root / "artifacts/ingestion_dev/ldsc_partitioned"
        self.config_data = {
            "raw_file": "raw.jsonl", "glossary_file": "glossary.json",
            "retrieval_config": "retrieval.yaml", "output_dir": "artifacts/ingestion_dev/ldsc_partitioned",
        }
        self.save_config()

    def save_config(self):
        self.config.write_text(yaml.safe_dump(self.config_data))

    def build(self, **kwargs):
        return build_partitioned(self.config, project_root=self.root, **kwargs)

    def configure_canonical_paths(self, chunks_dir="artifacts/chunks"):
        paths_config = self.root / "paths.yaml"
        paths_config.write_text(yaml.safe_dump({
            "raw": {"gene_info": "unused", "ldsc_2hri": "unused", "gene_id_map": "unused",
                    "gene_association_common_2hrg": "unused", "gene_association_rare_2hrg": "unused",
                    "ldsc_partitioned_2hrg": "raw.jsonl"},
            "artifacts": {"chunks_dir": chunks_dir, "manifest": "artifacts/manifest.json"},
            "config": {"phenotype_glossary": "glossary.json"},
        }))
        self.config_data["paths_config"] = "paths.yaml"
        self.save_config()
        return self.root / chunks_dir / "ldsc_partitioned_2hrG.chunks.jsonl"

    def test_canonical_output_uses_paths_config_and_preserves_old_chunks(self):
        final_chunks = self.configure_canonical_paths()
        final_chunks.parent.mkdir(parents=True)
        old_chunk = final_chunks.parent / "ldsc_2hrI.chunks.jsonl"
        old_chunk.write_bytes(b"baseline bytes")
        # Canonical source/glossary must come from paths.yaml, not stale duplicated entries.
        self.config_data["raw_file"] = "not-the-canonical-source.jsonl"
        self.save_config()
        report = self.build(tokenizer=TokenizerStub())
        self.assertEqual(report["status"], "passed")
        self.assertTrue(final_chunks.exists())
        self.assertFalse((self.output / final_chunks.name).exists())
        self.assertEqual(old_chunk.read_bytes(), b"baseline bytes")
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["output"]["path"], "artifacts/chunks/ldsc_partitioned_2hrG.chunks.jsonl")

    def test_canonical_output_cannot_be_partial(self):
        final_chunks = self.configure_canonical_paths()
        with self.assertRaisesRegex(ValueError, "partial|limit"):
            self.build(tokenizer=TokenizerStub(), limit=1)
        self.assertFalse(final_chunks.exists())

    def test_canonical_chunks_directory_cannot_point_to_raw(self):
        self.configure_canonical_paths("data/raw")
        with self.assertRaisesRegex(ValueError, "chunks"):
            self.build(tokenizer=TokenizerStub())

    def test_canonical_publication_cannot_replace_registered_baseline_inputs(self):
        for section, field in (("artifacts", "manifest"), ("raw", "gene_info"),
                               ("raw", "gene_association_common_2hrg")):
            with self.subTest(field=field):
                final = self.configure_canonical_paths()
                final.parent.mkdir(parents=True, exist_ok=True)
                final.write_bytes(b"protected baseline")
                paths_config = self.root / "paths.yaml"
                data = yaml.safe_load(paths_config.read_text())
                data[section][field] = final.relative_to(self.root).as_posix()
                paths_config.write_text(yaml.safe_dump(data))
                with self.assertRaisesRegex(ValueError, "input|baseline|overwrite"):
                    self.build(tokenizer=TokenizerStub())
                self.assertEqual(final.read_bytes(), b"protected baseline")

    def test_metadata_publication_cannot_replace_baseline_manifest(self):
        self.configure_canonical_paths()
        paths_config = self.root / "paths.yaml"
        data = yaml.safe_load(paths_config.read_text())
        data["artifacts"]["manifest"] = "artifacts/ingestion_dev/ldsc_partitioned/validation_report.json"
        paths_config.write_text(yaml.safe_dump(data))
        self.output.mkdir(parents=True)
        protected = self.output / "validation_report.json"
        protected.write_bytes(b"protected baseline")
        with self.assertRaisesRegex(ValueError, "input|baseline|overwrite"):
            self.build(tokenizer=TokenizerStub())
        self.assertEqual(protected.read_bytes(), b"protected baseline")

    def test_canonical_manifest_failure_restores_old_new_collection(self):
        final_chunks = self.configure_canonical_paths()
        self.build(tokenizer=TokenizerStub())
        old_chunks = final_chunks.read_bytes()
        old_manifest = (self.output / "manifest.json").read_bytes()
        original_replace = Path.replace

        def locked_manifest(path, target):
            if path.name == "manifest.json":
                raise PermissionError("manifest is locked")
            return original_replace(path, target)

        with patch.object(Path, "replace", locked_manifest):
            report = self.build(tokenizer=TokenizerStub())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(final_chunks.read_bytes(), old_chunks)
        self.assertEqual((self.output / "manifest.json").read_bytes(), old_manifest)

    def test_success_keeps_raw_and_publishes_traceable_manifest(self):
        raw_before = self.raw.read_bytes()
        tokenizer = TokenizerStub()
        report = self.build(tokenizer=tokenizer)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["chunks"], 2)
        self.assertEqual(self.raw.read_bytes(), raw_before)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertFalse(manifest["partial"])
        self.assertEqual(manifest["scope"], "standalone-development-chunks-not-indexed")
        self.assertIn("sha256", manifest["source"])
        self.assertIn("sha256", manifest["glossary"])
        self.assertIn("sha256", manifest["output"])
        self.assertEqual(len(tokenizer.calls), 2)
        self.assertTrue(all(c == {"add_special_tokens": True, "truncation": False} for c in tokenizer.calls))

    def test_limit_is_explicitly_partial(self):
        report = self.build(tokenizer=TokenizerStub(), limit=1)
        self.assertEqual(report["chunks"], 1)
        self.assertTrue(report["partial"])
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertTrue(manifest["partial"])
        self.assertEqual(manifest["raw_rows"], 2)

    def test_baseline_and_traversal_output_targets_are_rejected(self):
        for output in ("artifacts/chunks", "artifacts/manifest.json", "data/raw", "artifacts/ingestion_dev/../../chunks"):
            with self.subTest(output=output):
                self.config_data["output_dir"] = output
                self.save_config()
                with self.assertRaisesRegex(ValueError, "ingestion_dev"):
                    self.build(tokenizer=TokenizerStub())
                self.assertFalse((self.root / output).exists())

    def test_overlong_text_produces_diagnostic_without_chunks(self):
        report = self.build(tokenizer=TokenizerStub(513))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(len(report["overlong_records"]), 2)
        self.assertEqual(report["overlong_records"][0]["tokens"], 513)
        self.assertFalse((self.output / "manifest.json").exists())
        self.assertFalse((self.output / "ldsc_partitioned_2hrG.chunks.jsonl").exists())
        self.assertTrue((self.output / "validation_report.json").exists())

    def test_failed_rebuild_preserves_prior_outputs_but_marks_latest_failure(self):
        self.build(tokenizer=TokenizerStub())
        old_manifest = (self.output / "manifest.json").read_bytes()
        old_chunks = (self.output / "ldsc_partitioned_2hrG.chunks.jsonl").read_bytes()
        report = self.build(tokenizer=TokenizerStub(600))
        self.assertTrue(report["previous_artifacts_preserved"])
        self.assertEqual((self.output / "manifest.json").read_bytes(), old_manifest)
        self.assertEqual((self.output / "ldsc_partitioned_2hrG.chunks.jsonl").read_bytes(), old_chunks)
        self.assertEqual(json.loads((self.output / "validation_report.json").read_text())["status"], "failed")

    def test_duplicate_input_fails_without_publishing(self):
        self.raw.write_text(json.dumps(sample()) + "\n" + json.dumps(sample()) + "\n")
        report = self.build(tokenizer=TokenizerStub())
        self.assertEqual(report["status"], "failed")
        self.assertIn("Duplicate", report["error"])
        self.assertFalse((self.output / "manifest.json").exists())

    def test_manifest_publication_failure_restores_previous_chunks(self):
        self.build(tokenizer=TokenizerStub())
        old_manifest = (self.output / "manifest.json").read_bytes()
        old_chunks = (self.output / "ldsc_partitioned_2hrG.chunks.jsonl").read_bytes()
        original_replace = Path.replace

        def locked_manifest(path, target):
            if path.name == "manifest.json":
                raise PermissionError("manifest is locked")
            return original_replace(path, target)

        with patch.object(Path, "replace", locked_manifest):
            report = self.build(tokenizer=TokenizerStub(), limit=1)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(report["previous_artifacts_preserved"])
        self.assertEqual((self.output / "manifest.json").read_bytes(), old_manifest)
        self.assertEqual((self.output / "ldsc_partitioned_2hrG.chunks.jsonl").read_bytes(), old_chunks)

    def test_first_publication_failure_leaves_no_final_chunks(self):
        original_replace = Path.replace

        def locked_manifest(path, target):
            if path.name == "manifest.json":
                raise PermissionError("manifest is locked")
            return original_replace(path, target)

        with patch.object(Path, "replace", locked_manifest):
            report = self.build(tokenizer=TokenizerStub())
        self.assertEqual(report["status"], "failed")
        self.assertFalse((self.output / "manifest.json").exists())
        self.assertFalse((self.output / "ldsc_partitioned_2hrG.chunks.jsonl").exists())

    def test_tokenizer_failure_reports_cache_problem(self):
        with patch("chunk_ldsc_partitioned.load_tokenizer", side_effect=OSError("cache unavailable")):
            report = self.build()
        self.assertEqual(report["status"], "failed")
        self.assertIn("cache unavailable", report["error"])
        self.assertFalse((self.output / "manifest.json").exists())

    def test_same_input_produces_identical_chunk_hash(self):
        first = self.build(tokenizer=TokenizerStub())
        second = self.build(tokenizer=TokenizerStub())
        self.assertEqual(first["chunk_sha256"], second["chunk_sha256"])

    def test_local_snapshot_revision_is_recorded(self):
        tokenizer = TokenizerStub()
        revision = "a" * 40
        tokenizer.name_or_path = f"/cache/snapshots/{revision}"
        self.build(tokenizer=tokenizer)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["tokenizer"]["revision"], revision)

    def test_negative_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "limit"):
            self.build(tokenizer=TokenizerStub(), limit=-1)


if __name__ == "__main__":
    unittest.main()
