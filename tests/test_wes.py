from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT
for directory in (ROOT, ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(directory))

import copy
import json
import tempfile
import unittest
from chunking.phenotype_glossary import PhenotypeGlossary
from chunking.wes_chunker import chunk_wes
from unittest.mock import patch
from types import SimpleNamespace
import yaml
from tests import test_ldsc_partitioned as fixture_module
from tests.test_ldsc_partitioned import TokenizerStub
from chunk_ldsc_partitioned import build_wes
from retrieval.router import ALL_COLLECTIONS, route_query
import chunk_corpus


def wes_sample(gene='HIF3A', **changes):
    row = dict(source='AMP T2D-GENES', phenotype='2hrG', gene=gene,
               pValue=0.8865548496821851, beta=0.6937300000000001,
               masks=[dict(mask='LoF_HC', pValue=0.5643330448687558,
                           beta=0.68928, stdErr=1.1958, n=551,
                           combinedAF=0.0018149000000000002,
                           singleVariants=1, passingVariants=1)])
    row.update(changes)
    return row

class WESChunkingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'wes.jsonl'
        self.baseline = self.root / 'rare.chunks.jsonl'
        self.baseline.write_text(json.dumps(dict(chunk_id='gassoc_rare:2hrG:HIF3A',
            metadata=dict(gene='HIF3A', phenotype='2hrG', pValue=wes_sample()['pValue'],
                          beta=wes_sample()['beta']))) + '\n')
        glossary = self.root / 'glossary.json'
        glossary.write_text(json.dumps({'2hrG': {'label': '2-hour glucose', 'category': 'other'}}))
        self.glossary = PhenotypeGlossary.from_file(glossary)

    def build(self, rows):
        self.source.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        return chunk_wes(self.source, self.glossary, self.root, self.baseline)

    def test_keeps_overlapping_summary_and_mask_exactly(self):
        row = wes_sample()
        result = self.build([row])
        self.assertEqual(len(result.chunks), 2)
        summary, mask = result.chunks
        self.assertEqual(summary.chunk_id, 'wes:2hrG:HIF3A:summary')
        self.assertEqual(mask.chunk_id, 'wes:2hrG:HIF3A:mask:LoF_HC')
        self.assertEqual(summary.metadata['raw_record'], row)
        self.assertEqual(mask.metadata['raw_mask'], row['masks'][0])
        for c in result.chunks:
            self.assertEqual(c.metadata['related_baseline_chunk_id'], 'gassoc_rare:2hrG:HIF3A')
            self.assertTrue(c.metadata['top_level_matches_baseline'])
            self.assertEqual(c.citation['source_row'], 1)
        self.assertNotIn('statistically significant', mask.content)

    def test_empty_masks_get_summary_and_invalid_gene_is_quarantined(self):
        result = self.build([wes_sample('NEW', masks=[]), wes_sample(float('nan'), masks=[])])
        self.assertEqual(len(result.chunks), 1)
        self.assertEqual(result.chunks[0].metadata['masks_status'], 'empty')
        self.assertIn('not proof', result.chunks[0].content)
        self.assertEqual(result.raw_rows, 2)
        self.assertEqual(result.quarantined[0]['source_row'], 2)
        self.assertIn('NaN', result.quarantined[0]['raw_line'])
        json.dumps(result.quarantined, allow_nan=False)

    def test_different_top_level_values_are_marked_without_dropping(self):
        result = self.build([wes_sample(pValue=0.4)])
        self.assertEqual(len(result.chunks), 2)
        self.assertFalse(result.chunks[0].metadata['top_level_matches_baseline'])
        self.assertIsNotNone(result.chunks[0].metadata['related_baseline_chunk_id'])

    def test_order_independent_ids_and_preserves_identical_named_masks(self):
        row = wes_sample()
        other = dict(row['masks'][0], mask='5of5')
        row['masks'].append(other)
        first = self.build([row])
        row['masks'].reverse()
        second = self.build([row])
        self.assertEqual([c.chunk_id for c in first.chunks], [c.chunk_id for c in second.chunks])
        self.assertEqual([c.content for c in first.chunks], [c.content for c in second.chunks])
        self.assertEqual(len(first.chunks), 3)

    def test_invalid_fields_duplicates_and_nonfinite_statistics_fail(self):
        for field, value in [('pValue', 2), ('stdErr', 0), ('n', 1.5), ('beta', float('inf')),
                             ('combinedAF', -1), ('singleVariants', -1)]:
            with self.subTest(field=field):
                row = wes_sample()
                row['masks'][0][field] = value
                with self.assertRaises(ValueError):
                    self.build([row])
        row = wes_sample(); row['masks'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.build([row])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.build([wes_sample(), wes_sample()])
        with self.assertRaises(ValueError):
            self.build([wes_sample(beta=float('nan'))])

    def test_ids_escape_components_and_preserve_unknown_fields(self):
        row = wes_sample('A:B', extra_source='release note')
        row['masks'][0]['mask'] = 'X:Y'
        row['masks'][0]['extra'] = 'supplied'
        result = self.build([row])
        self.assertEqual(result.chunks[1].chunk_id, 'wes:2hrG:A%3AB:mask:X%3AY')
        self.assertEqual(result.chunks[1].metadata['raw_mask']['extra'], 'supplied')
        self.assertEqual(result.chunks[1].metadata['raw_parent']['extra_source'], 'release note')


class WESPipelineTests(unittest.TestCase):
    def setUp(self):
        fixture = fixture_module.PartitionedPipelineTests()
        fixture.setUp()
        self.addCleanup(fixture.temp.cleanup)
        self.root, self.config = fixture.root, fixture.config
        fixture.configure_canonical_paths()
        self.source = self.root / 'wes.jsonl'
        self.source.write_text(json.dumps(wes_sample()) + '\n' + json.dumps(wes_sample(float('nan'), masks=[])) + '\n')
        self.paths = self.root / 'paths.yaml'
        cfg = yaml.safe_load(self.paths.read_text())
        cfg['raw']['wes_2hrg'] = self.source.name
        cfg['artifacts']['wes_validation_dir'] = 'artifacts/ingestion_dev/wes'
        self.paths.write_text(yaml.safe_dump(cfg))
        folder = self.root / 'artifacts/chunks'
        folder.mkdir(parents=True)
        self.old = folder / 'gene_association_rare_2hrG.chunks.jsonl'
        self.old.write_text(json.dumps(dict(chunk_id='gassoc_rare:2hrG:HIF3A',
            metadata=dict(gene='HIF3A', phenotype='2hrG', pValue=wes_sample()['pValue'], beta=wes_sample()['beta'])))+'\n')
        self.output = folder / 'wes_2hrG.chunks.jsonl'

    def test_publication_preserves_overlap_and_records_quarantine(self):
        before = self.old.read_bytes()
        report = build_wes(self.config, project_root=self.root, tokenizer=TokenizerStub())
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['chunks'], 2)
        self.assertEqual(report['raw_rows'], 2)
        self.assertEqual(report['quarantined_rows'], 1)
        self.assertEqual(report['record_kind_counts'], {'gene_summary': 1, 'mask_result': 1})
        self.assertEqual(self.old.read_bytes(), before)
        self.assertTrue(self.output.exists())

    def test_overlong_cannot_replace_previous_chunks(self):
        self.output.write_bytes(b'previous chunks')
        report = build_wes(self.config, project_root=self.root, tokenizer=TokenizerStub(600))
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(self.output.read_bytes(), b'previous chunks')

    def test_metadata_cannot_overlap_partitioned_directory(self):
        cfg = yaml.safe_load(self.paths.read_text())
        cfg['artifacts']['wes_validation_dir'] = yaml.safe_load(self.config.read_text())['output_dir']
        self.paths.write_text(yaml.safe_dump(cfg))
        with self.assertRaisesRegex(ValueError, 'metadata'):
            build_wes(self.config, project_root=self.root, tokenizer=TokenizerStub())

    def test_wes_only_cli_dispatches_without_rebuilding_old_chunks(self):
        (self.root / 'config').mkdir(exist_ok=True)
        (self.root / 'config/paths.yaml').write_bytes(self.paths.read_bytes())
        args = SimpleNamespace(paths_config=self.paths, gene_file=None, ldsc_file=None,
            glossary_file=None, output_dir=None, manifest_file=None, dry_run=0,
            partitioned_only=False, include_partitioned=False, clumped_only=False, wes_only=True,
            partitioned_config=self.config, partitioned_retrieval_config=self.root/'expanded.yaml')
        with patch.object(chunk_corpus, 'PROJECT_ROOT', self.root), \
             patch.object(chunk_corpus, 'parse_args', return_value=args), \
             patch.object(chunk_corpus, 'build_wes', return_value={'status':'passed'}) as build, \
             patch.object(chunk_corpus, 'prepare_manifest', return_value={}):
            self.assertEqual(chunk_corpus.main(), 0)
        build.assert_called_once()
        self.assertFalse((self.root/'artifacts/manifest.json').exists())

    def test_wes_intent_and_comparison_routes(self):
        available = [*ALL_COLLECTIONS, 'ldsc_partitioned_heritability', 'variant_association_clumped', 'gene_association_wes']
        for query in ('WES association for HIF3A', 'HIF3A LoF_HC mask results', 'whole-exome association'):
            self.assertEqual(route_query(query, available_collections=available).collections, ['gene_association_wes'])
        self.assertEqual(route_query('Compare bf_rare with WES masks', available_collections=available).collections,
                         ['gene_association_rare', 'gene_association_wes'])
        self.assertEqual(route_query('WES association', available_collections=ALL_COLLECTIONS).collections, [])


if __name__ == "__main__":
    unittest.main()
