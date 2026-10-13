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
from chunking.clumped_chunker import chunk_clumped_regions
from chunking.phenotype_glossary import PhenotypeGlossary
from unittest.mock import patch
from types import SimpleNamespace
import yaml
import chunk_corpus
from chunk_ldsc_partitioned import build_clumped
from tests import test_ldsc_partitioned as partitioned_fixture
from tests.test_ldsc_partitioned import TokenizerStub


def clumped_sample(position=100, lead=True, **changes):
    row = {"phenotype": "2hrG", "chromosome": "10", "clump": 3,
           "clumpStart": 100, "clumpEnd": 201, "position": position,
           "reference": "G", "alt": "T", "varId": f"10:{position}:G:T",
           "leadSNP": lead, "pValue": 1e-10 if lead else 0.01, "beta": -0.12,
           "stdErr": 0.03, "n": 1000.0, "alignment": -1.0,
           "freqType": "common", "metaType": "bottom-line",
           "inMetaTypes": "bottom-line;min_p", "paramType": "analysis"}
    row.update(changes)
    return row

class ClumpedChunkingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "raw/ancestry=EU/records.jsonl"
        self.source.parent.mkdir(parents=True)
        self.glossary = PhenotypeGlossary({"2hrG": {"label": "2-hour glucose (OGTT)"}})

    def chunks(self, rows):
        self.source.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding="utf-8")
        return list(chunk_clumped_regions(self.source, self.glossary, self.root))

    def test_region_preserves_all_members_and_source_rows(self):
        rows = [clumped_sample(200, False, n=500.0), clumped_sample()]
        chunk = self.chunks(rows)[0]
        self.assertEqual(chunk.chunk_id, "clumped:2hrG:EU:10:3:100-201")
        self.assertEqual(chunk.collection, "variant_association_clumped")
        self.assertEqual(chunk.metadata["member_count"], 2)
        self.assertEqual(chunk.metadata["ancestry_source"], "directory")
        by_row = dict(zip(chunk.metadata["source_rows"], chunk.metadata["members"]))
        self.assertEqual(by_row, {1: rows[0], 2: rows[1]})
        self.assertEqual(chunk.citation["source_rows"], chunk.metadata["source_rows"])
        self.assertEqual(chunk.citation["chunk_id"], chunk.chunk_id)
        self.assertIn("10:100:G:T", chunk.content)
        self.assertNotIn("10:200:G:T", chunk.content)
        self.assertIn("beta=-0.12", chunk.content)
        self.assertNotIn("is_significant", chunk.metadata)

    def test_member_reordering_keeps_ids_body_and_member_order(self):
        rows = [clumped_sample(), clumped_sample(200, False)]
        a = self.chunks(rows)[0]
        b = self.chunks(rows[::-1])[0]
        self.assertEqual(a.chunk_id, b.chunk_id)
        self.assertEqual(a.content, b.content)
        self.assertEqual(a.metadata["members"], b.metadata["members"])

    def test_lead_and_boundaries_must_be_consistent(self):
        cases = [[clumped_sample(), clumped_sample(200, True)],
                 [clumped_sample(100, False)],
                 [clumped_sample(), clumped_sample(200, False, clumpEnd=300)],
                 [clumped_sample(), clumped_sample(200, False, pValue=1e-12)]]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.chunks(rows)

    def test_invalid_identity_numeric_and_duplicate_variants_rejected(self):
        for changes in ({"varId": "wrong"}, {"position": 300}, {"pValue": 2},
                        {"stdErr": 0}, {"beta": float("nan")}, {"leadSNP": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.chunks([clumped_sample(**changes)])
        with self.assertRaises(ValueError):
            self.chunks([clumped_sample(), clumped_sample()])

    def test_ancestry_directory_required(self):
        self.source = self.root / "records.jsonl"
        with self.assertRaisesRegex(ValueError, "ancestry"):
            self.chunks([clumped_sample()])

    def test_members_extra_fields_and_numeric_precision_retained(self):
        row = clumped_sample(extra={"note": "source"}, beta=0.123456789)
        chunk = self.chunks([row])[0]
        self.assertEqual(chunk.metadata["members"], [row])
        self.assertIn("beta=0.1235", chunk.content)


class ClumpedPipelineTests(unittest.TestCase):
    def setUp(self):
        fixture = partitioned_fixture.PartitionedPipelineTests()
        fixture.setUp()
        self.addCleanup(fixture.temp.cleanup)
        self.root = fixture.root
        self.config = fixture.config
        fixture.configure_canonical_paths()
        self.source = self.root / "raw/ancestry=EU/records.jsonl"
        self.source.parent.mkdir(parents=True)
        self.source.write_text(json.dumps(clumped_sample()) + '\n' +
                               json.dumps(clumped_sample(200, False, n=500.0)) + '\n')
        config = yaml.safe_load((self.root / "paths.yaml").read_text())
        config["raw"]["metaanalysis_clumped_2hrg_eu"] = self.source.relative_to(self.root).as_posix()
        config["artifacts"]["clumped_validation_dir"] = "artifacts/ingestion_dev/clumped"
        (self.root / "paths.yaml").write_text(yaml.safe_dump(config))
        self.output = self.root / "artifacts/chunks/metaanalysis_clumped_2hrG_EU.chunks.jsonl"
        self.metadata_dir = self.root / "artifacts/ingestion_dev/clumped"

    def build(self, **kwargs):
        return build_clumped(self.config, project_root=self.root, **kwargs)

    def test_clumped_only_cli_preserves_baseline_and_partitioned(self):
        args = SimpleNamespace(paths_config=self.root / "paths.yaml", gene_file=None,
                               ldsc_file=None, glossary_file=None, output_dir=None,
                               manifest_file=None, dry_run=0, partitioned_only=False,
                               include_partitioned=False, clumped_only=True,
                               partitioned_config=self.config,
                               partitioned_retrieval_config=self.root / "expanded.yaml")
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "config/paths.yaml").write_bytes((self.root / "paths.yaml").read_bytes())
        with patch.object(chunk_corpus, "PROJECT_ROOT", self.root), \
             patch.object(chunk_corpus, "parse_args", return_value=args), \
             patch.object(chunk_corpus, "build_clumped", return_value={"status": "passed"}) as build, \
             patch.object(chunk_corpus, "prepare_manifest", return_value={}) as publish:
            self.assertEqual(chunk_corpus.main(), 0)
        build.assert_called_once_with(self.config, project_root=self.root.resolve(),
                                      paths_config_file=(self.root / "paths.yaml").resolve())
        publish.assert_called_once()
        self.assertFalse((self.root / "artifacts/manifest.json").exists())

    def test_build_counts_source_members_and_preserves_old_collections(self):
        self.output.parent.mkdir(parents=True)
        old = self.output.parent / "ldsc_partitioned_2hrG.chunks.jsonl"
        old.write_bytes(b"previous collection")
        report = self.build(tokenizer=TokenizerStub())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["chunks"], 1)
        self.assertEqual(report["raw_rows"], 2)
        self.assertEqual(old.read_bytes(), b"previous collection")
        self.assertTrue(self.output.exists())
        built = json.loads((self.metadata_dir / "manifest.json").read_text())
        self.assertEqual(built["collection"], "variant_association_clumped")
        self.assertEqual(built["output"]["path"], self.output.relative_to(self.root).as_posix())

    def test_overlong_clump_reports_all_source_rows_without_publishing(self):
        report = self.build(tokenizer=TokenizerStub(600))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["overlong_records"][0]["source_rows"], [1, 2])
        self.assertFalse(self.output.exists())

    def test_clumped_cannot_overwrite_partitioned_build_metadata(self):
        config = yaml.safe_load((self.root / "paths.yaml").read_text())
        shared = yaml.safe_load(self.config.read_text())["output_dir"]
        config["artifacts"]["clumped_validation_dir"] = shared
        (self.root / "paths.yaml").write_text(yaml.safe_dump(config))
        shared_dir = self.root / shared
        shared_dir.mkdir(parents=True, exist_ok=True)
        manifest = shared_dir / "manifest.json"
        report = shared_dir / "validation_report.json"
        manifest.write_text(json.dumps({"collection": "ldsc_partitioned_heritability"}))
        report.write_text("previous validation")
        before = (manifest.read_bytes(), report.read_bytes())
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.build(tokenizer=TokenizerStub())
        self.assertEqual((manifest.read_bytes(), report.read_bytes()), before)
        self.assertFalse(self.output.exists())

    def test_invalid_clump_source_produces_failure_and_no_output(self):
        self.source.write_text(json.dumps(clumped_sample(lead=False)) + '\n')
        report = self.build(tokenizer=TokenizerStub())
        self.assertEqual(report["status"], "failed")
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
