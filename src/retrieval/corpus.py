from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chunking.utils import file_sha256, load_jsonl
from retrieval.config import ChunkSource, RetrievalConfig
from retrieval.schema import ChunkRecord


@dataclass
class LoadedCorpus:
    records: list[ChunkRecord]
    chunk_hashes: dict[str, str]
    collection_counts: dict[str, int]


def _manifest_entries(manifest_file: Path) -> dict[str, dict[str, Any]]:
    with manifest_file.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    entries: dict[str, dict[str, Any]] = {}
    filename_to_collection = {
        "gene_info.chunks.jsonl": "gene_info",
        "ldsc_2hrI.chunks.jsonl": "ldsc_genetic_correlation",
        "gene_association_common_2hrG.chunks.jsonl": "gene_association_common",
        "gene_association_rare_2hrG.chunks.jsonl": "gene_association_rare",
    }
    for filename, payload in manifest.get("outputs", {}).items():
        collection = payload.get("collection") or filename_to_collection.get(filename)
        if not isinstance(collection, str) or not collection:
            raise ValueError(f"Manifest output has no recognized collection: {filename}")
        if collection in entries:
            raise ValueError(f"Duplicate collection in manifest: {collection}")
        if type(payload.get("chunks")) is not int or payload["chunks"] < 0:
            raise ValueError(f"Invalid manifest count for {collection}")
        entries[collection] = payload
    if not entries:
        raise ValueError(f"Manifest has no indexed outputs: {manifest_file}")
    return entries


def load_manifest_counts(manifest_file: Path) -> dict[str, int]:
    return {collection: entry["chunks"] for collection, entry in _manifest_entries(manifest_file).items()}


def load_corpus(
    sources: list[ChunkSource] | tuple[ChunkSource, ...],
    *,
    manifest_file: Path | None = None,
    expected_total: int | None = 41103,
    project_root: Path | None = None,
) -> LoadedCorpus:
    records: list[ChunkRecord] = []
    chunk_hashes: dict[str, str] = {}
    collection_counts: dict[str, int] = {}
    seen_ids: set[str] = set()
    entries = _manifest_entries(manifest_file) if manifest_file else {}
    if entries and set(entries) != {source.collection for source in sources}:
        raise ValueError("Manifest collections do not match configured source collections")

    source_versions = {}
    if manifest_file:
        payload = json.loads(manifest_file.read_text())
        source_versions = {s["path"]: s["sha256"] for s in payload.get("sources", {}).values()
                           if isinstance(s, dict) and "path" in s and "sha256" in s}
        manifest_version = file_sha256(manifest_file)
    for source in sources:
        if not source.path.exists():
            raise FileNotFoundError(f"Chunk artifact not found: {source.path}")
        chunk_hashes[source.path.as_posix()] = file_sha256(source.path)
        if entries:
            entry = entries[source.collection]
            expected_hash = entry.get("sha256")
            if expected_hash and expected_hash != chunk_hashes[source.path.as_posix()]:
                raise ValueError(f"Manifest hash mismatch for {source.collection}")
            if entry.get("path"):
                root = project_root or manifest_file.parent
                expected_path = (root / entry["path"]).resolve()
                if source.path.resolve() != expected_path:
                    raise ValueError(f"Manifest path mismatch for {source.collection}")
        count = 0
        for payload in load_jsonl(source.path):
            record = ChunkRecord.from_dict(payload)
            if record.collection != source.collection:
                raise ValueError(
                    f"Collection mismatch in {source.path}: {record.collection} != {source.collection}"
                )
            if record.chunk_id in seen_ids:
                raise ValueError(f"Duplicate chunk_id: {record.chunk_id}")
            seen_ids.add(record.chunk_id)
            if manifest_file:
                citation = record.citation
                source_hash = citation.get("source_sha256") or source_versions.get(citation.get("source_file"))
                if source_hash:
                    citation["source_sha256"] = source_hash
                    citation.setdefault("source_version", "sha256:" + source_hash)
                citation["corpus_version"] = "sha256:" + manifest_version
                citation["chunk_file_sha256"] = chunk_hashes[source.path.as_posix()]
            records.append(record)
            count += 1
        collection_counts[source.collection] = count

    if expected_total is not None and len(records) != expected_total:
        raise ValueError(f"Expected {expected_total} chunks, loaded {len(records)}")

    if entries:
        for collection, entry in entries.items():
            count = entry["chunks"]
            actual = collection_counts.get(collection)
            if actual != count:
                raise ValueError(
                    f"Manifest count mismatch for {collection}: expected {count}, got {actual}"
                )

    return LoadedCorpus(
        records=records,
        chunk_hashes=chunk_hashes,
        collection_counts=collection_counts,
    )


def load_corpus_from_config(config: RetrievalConfig, *, expected_total: int | None = None) -> LoadedCorpus:
    # A configured corpus is validated against its versioned manifest, not a
    # global baseline count. Explicit totals remain an additional assertion.
    if expected_total is None:
        expected_total = sum(load_manifest_counts(config.manifest_file).values())
    return load_corpus(
        config.chunk_sources,
        manifest_file=config.manifest_file,
        expected_total=expected_total,
        project_root=config.project_root,
    )


def corpus_by_id(records: list[ChunkRecord]) -> dict[str, ChunkRecord]:
    return {record.chunk_id: record for record in records}


def metadata_matches(record: ChunkRecord, filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        actual = record.metadata.get(key, getattr(record, key, None))
        if actual != expected:
            return False
    return True
