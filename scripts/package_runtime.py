"""Validate and package the active BM25 runtime, including corpus manifests."""
from pathlib import Path
import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analysis.data import DataStore
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.bm25_retriever import load_bm25_index


def package(root, output):
    config = load_retrieval_config(root)
    corpus = load_corpus_from_config(config)
    load_bm25_index(config.index_dir, corpus.records,
                    expected_chunk_hashes=corpus.chunk_hashes)
    store = DataStore(root)
    store.ensure()
    files = {s.path for s in config.chunk_sources}
    files.add(config.manifest_file)
    baseline = root / 'artifacts/manifest.json'
    if baseline.exists():
        files.add(baseline)
    files.update(p for p in config.index_dir.rglob('*') if p.is_file())
    example = root / 'data/reference/client_example/example.json'
    if example.exists():
        files.add(example)
    output.parent.mkdir(parents=True, exist_ok=True)
    hashes = {}
    with tempfile.TemporaryDirectory() as tmp:
        backup = Path(tmp) / 'analysis.sqlite'
        with sqlite3.connect(store.path) as source, sqlite3.connect(backup) as dest:
            source.backup(dest)
            assert dest.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        entries = [(p.relative_to(root).as_posix(), p) for p in sorted(files)]
        entries.append(('artifacts/structured/analysis.sqlite', backup))
        temporary = output.with_suffix('.zip.tmp')
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, path in entries:
                digest = hashlib.sha256()
                with path.open('rb') as handle:
                    for block in iter(lambda: handle.read(1024*1024), b''):
                        digest.update(block)
                hashes[name] = digest.hexdigest()
                archive.write(path, name)
            archive.writestr('runtime-package.json', json.dumps({
                'schema': 1, 'retrieval': 'bm25',
                'collections': corpus.collection_counts,
                'sha256': hashes,
                'requires': 'Matching source code, dependencies and data/raw from repository',
            }, indent=2))
        temporary.replace(output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n')
    print(f'Validated {len(corpus.records)} chunks; packaged {len(entries)} files: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.root.resolve(), args.output.resolve())
