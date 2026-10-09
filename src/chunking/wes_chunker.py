from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from urllib.parse import quote

from chunking.phenotype_glossary import PhenotypeGlossary
from chunking.schema import Chunk
from chunking.utils import file_sha256, relative_source_path

COLLECTION = 'gene_association_wes'
OUTPUT_NAME = 'wes_2hrG.chunks.jsonl'
DEFINITIONS = ['mask_rules', 'cohort_and_ancestry', 'effect_scale_and_allele',
               'n_definition', 'combinedAF_definition', 'variant_count_definitions',
               'top_level_test_or_aggregation', 'release']


@dataclass
class WESChunkingResult:
    chunks: list[Chunk]
    raw_rows: int
    quarantined: list[dict]


def _number(value, name: str, line: int) -> None:
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f'Source line {line}: invalid {name}')


def _validate(row: dict, line: int) -> None:
    for name in ('source', 'phenotype', 'gene'):
        if not isinstance(row.get(name), str) or not row[name].strip():
            raise ValueError(f'Source line {line}: invalid {name}')
    for name in ('pValue', 'beta'):
        _number(row.get(name), name, line)
    if not 0 <= row['pValue'] <= 1 or not isinstance(row.get('masks'), list):
        raise ValueError(f'Source line {line}: invalid pValue/masks')
    labels = set()
    for mask in row['masks']:
        if not isinstance(mask, dict) or not isinstance(mask.get('mask'), str) or not mask['mask'].strip():
            raise ValueError(f'Source line {line}: invalid mask')
        if mask['mask'] in labels:
            raise ValueError(f'Source line {line}: duplicate mask')
        labels.add(mask['mask'])
        for name in ('pValue', 'beta', 'stdErr', 'n', 'combinedAF', 'singleVariants', 'passingVariants'):
            _number(mask.get(name), name, line)
        if not 0 <= mask['pValue'] <= 1 or mask['stdErr'] <= 0 or mask['combinedAF'] < 0:
            raise ValueError(f'Source line {line}: invalid mask statistic range')
        for name in ('n', 'singleVariants', 'passingVariants'):
            if type(mask[name]) is not int or mask[name] < (1 if name == 'n' else 0):
                raise ValueError(f'Source line {line}: invalid {name} count')
    try:
        json.dumps(row, allow_nan=False)
    except ValueError as exc:
        raise ValueError(f'Source line {line}: nonfinite value in original fields') from exc


def chunk_wes(source: Path, glossary: PhenotypeGlossary, project_root: Path,
              baseline_chunks: Path) -> WESChunkingResult:
    """Retain every valid summary/mask; link numeric overlap without dropping evidence."""
    baseline = {}
    with baseline_chunks.open(encoding='utf-8') as handle:
        for text in handle:
            if not text.strip():
                continue
            chunk = json.loads(text)
            m = chunk['metadata']
            key = (m.get('phenotype'), m.get('gene'))
            if key in baseline:
                raise ValueError(f'duplicate baseline gene/phenotype: {key}')
            baseline[key] = chunk
    rows, quarantined, seen = [], [], set()
    raw_rows = 0
    with source.open(encoding='utf-8-sig') as handle:
        for line, text in enumerate(handle, 1):
            if not text.strip():
                continue
            raw_rows += 1
            try:
                row = json.loads(text)
            except ValueError as exc:
                raise ValueError(f'Source line {line}: invalid JSON') from exc
            if not isinstance(row, dict):
                raise ValueError(f'Source line {line}: expected object')
            gene = row.get('gene')
            if not isinstance(gene, str) or not gene.strip() or gene.strip().lower() == 'nan':
                quarantined.append(dict(source_row=line, reason='invalid gene identifier', raw_line=text.rstrip('\r\n')))
                continue
            _validate(row, line)
            key = (row['phenotype'], gene)
            if key in seen:
                raise ValueError(f'Source line {line}: duplicate gene/phenotype {key}')
            seen.add(key)
            rows.append((key, line, row))
    source_file = relative_source_path(source, project_root)
    source_hash = file_sha256(source)
    baseline_file = relative_source_path(baseline_chunks, project_root)
    baseline_hash = file_sha256(baseline_chunks)
    chunks = []
    for key, line, row in sorted(rows):
        phenotype, gene = key
        old = baseline.get(key)
        related = old['chunk_id'] if old else None
        matches = bool(old and row['pValue'] == old['metadata'].get('pValue') and
                       row['beta'] == old['metadata'].get('beta'))
        label, confidence = glossary.get_label(phenotype)
        parent = {k: v for k, v in row.items() if k != 'masks'}
        group_id = 'wes:' + ':'.join(quote(v, safe='-_.') for v in key)
        units = [('gene_summary', None, None)]
        units += [('mask_result', index, mask) for index, mask in
                  sorted(enumerate(row['masks']), key=lambda item: item[1]['mask'])]
        for kind, index, mask in units:
            chunk_id = group_id + (':mask:' + quote(mask['mask'], safe='-_.') if mask else ':summary')
            title = f"WES {'mask '+mask['mask'] if mask else 'gene summary'}: {gene} and {label} ({phenotype})"
            lines = [f'Client-reported WES association: {gene} and {label} ({phenotype}).',
                     f"Source label: {row['source']}."]
            if mask:
                lines += [f"Source mask label: {mask['mask']} (selection rules unconfirmed).",
                          'Mask results (displayed to 4 significant digits):']
                lines += [f'{name}={mask[name]:.4g}' for name in
                          ('pValue', 'beta', 'stdErr', 'n', 'combinedAF', 'singleVariants', 'passingVariants')]
                lines.append('This mask result is not the gene-level aggregate; different masks are not independent corroboration.')
            else:
                lines += [f"Source top-level pValue={row['pValue']:.4g}; beta={row['beta']:.4g}.",
                          f"Supplied mask results: {len(row['masks'])}.",
                          'Top-level test/aggregation is unconfirmed; do not interpret this as the minimum mask pValue.']
                if not row['masks']:
                    lines.append('No mask detail supplied; this is not proof of no association or no analysis.')
            if matches:
                lines.append(f'Related baseline summary: {related}; identical top-level pValue/beta, not independent corroboration.')
            lines += ['Population-level association, not causal proof or an individual diagnosis.',
                      'Mask rules, cohort/ancestry, effect scale, n, combinedAF, variant counts and release are unconfirmed.',
                      f'Source: {source_file}']
            metadata = dict(record_kind=kind, gene=gene, phenotype=phenotype,
                phenotype_label=label, phenotype_label_confidence=confidence, group_id=group_id,
                raw_parent=parent, mask_count=len(row['masks']),
                masks_status='provided' if row['masks'] else 'empty',
                mask_labels=sorted(m['mask'] for m in row['masks']),
                related_baseline_chunk_id=related, top_level_matches_baseline=matches,
                source_file=source_file, source_row=line, source_sha256=source_hash,
                definition_status='unconfirmed', unconfirmed_definitions=DEFINITIONS.copy())
            if old:
                metadata['baseline_reference'] = dict(path=baseline_file, sha256=baseline_hash,
                                                     chunk_id=related, compared_fields=['pValue', 'beta'])
            citation = dict(source_name=row['source'], release=None, source_file=source_file,
                            source_row=line, source_sha256=source_hash, chunk_id=chunk_id)
            if mask:
                metadata.update(mask=mask['mask'], raw_mask=mask, source_mask_index=index)
                citation['source_mask_index'] = index
            else:
                metadata['raw_record'] = row
            chunks.append(Chunk(chunk_id, COLLECTION,
                'gene_mask_association' if mask else 'gene_phenotype_summary', title,
                '\n'.join(lines), metadata, citation))
    return WESChunkingResult(chunks, raw_rows, quarantined)
