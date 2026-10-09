from __future__ import annotations

import argparse
from datetime import datetime, timezone
from dataclasses import replace
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from chunking.paths import load_paths
from chunking.utils import artifact_staging_directory, file_sha256, relative_source_path
from retrieval.config import ChunkSource, load_retrieval_config
from retrieval.corpus import load_corpus, load_corpus_from_config, load_manifest_counts

ADDITIONS = {
    "ldsc_partitioned_heritability": ("partitioned", "ldsc_partitioned_2hrG", "ldsc_partitioned_2hrG.chunks.jsonl"),
    "variant_association_clumped": ("clumped", "metaanalysis_clumped_2hrG_EU", "metaanalysis_clumped_2hrG_EU.chunks.jsonl"),
    "gene_association_wes": ("wes", "wes_2hrG", "wes_2hrG.chunks.jsonl"),
}


def prepare_manifest(config_file: Path, *, project_root: Path = PROJECT_ROOT) -> dict:
    """Prepare a hash-checked expanded corpus manifest, not indexes."""
    root = project_root.resolve()
    baseline_config = load_retrieval_config(root)
    expanded = load_retrieval_config(root, config_file)
    # The active primary config may already select the expanded corpus. Read the
    # immutable baseline from its manifest instead of treating active sources as baseline.
    baseline_reference = expanded.raw.get("baseline_manifest") or baseline_config.raw.get("baseline_manifest")
    if baseline_reference:
        baseline_manifest = (root / baseline_reference).resolve()
        baseline_payload = json.loads(baseline_manifest.read_text(encoding="utf-8"))
        baseline_names = list(load_manifest_counts(baseline_manifest))
        if any(name in ADDITIONS for name in baseline_names):
            raise ValueError("baseline_manifest must describe the original baseline collections")
        sources = tuple(ChunkSource(name, (root / entry["path"]).resolve())
                        for name, entry in zip(baseline_names, baseline_payload["outputs"].values()))
        baseline_config = replace(baseline_config, chunk_sources=sources, manifest_file=baseline_manifest)
    baseline_size = len(baseline_config.chunk_sources)
    if expanded.chunk_sources[:baseline_size] != baseline_config.chunk_sources:
        raise ValueError("Expanded sources must preserve baseline sources and their order")
    new_sources = expanded.chunk_sources[baseline_size:]
    names = [source.collection for source in new_sources]
    if names not in [list(ADDITIONS)[:n] for n in range(1, len(ADDITIONS)+1)]:
        raise ValueError("Expected partitioned heritability, optionally followed by clumped association and WES")
    allowed = (root / "artifacts/ingestion_dev").resolve()
    paths_config = None
    canonical_destination = None
    if expanded.raw.get("paths_config"):
        paths_config = (root / expanded.raw["paths_config"]).resolve()
        registered = load_paths(root, paths_config)
        canonical_destination = registered.partitioned_manifest_file
        if (registered.project_root != root or not registered.chunks_dir.is_relative_to(root)
                or registered.chunks_dir != (root / "artifacts/chunks").resolve()):
            raise ValueError("Canonical chunks_dir must be artifacts/chunks under project_root")
        if canonical_destination != (root / "artifacts/manifest_partitioned.json").resolve():
            raise ValueError("Canonical partitioned manifest must be artifacts/manifest_partitioned.json")
        for source in new_sources:
            if source.path != registered.chunks_dir / ADDITIONS[source.collection][2]:
                raise ValueError("Added chunks must match canonical paths_config output")
    if (not allowed.is_relative_to(root) or
            (expanded.manifest_file != canonical_destination and not expanded.manifest_file.is_relative_to(allowed))):
        raise ValueError("Expanded manifest must remain in artifacts/ingestion_dev")
    if expanded.manifest_file == baseline_config.manifest_file:
        raise ValueError("Cannot replace baseline manifest")

    builds = []
    for source in new_sources:
        prefix, source_key, _ = ADDITIONS[source.collection]
        build_manifest = (root / expanded.raw.get(
            f"{prefix}_build_manifest", str(source.path.parent / "manifest.json"))).resolve()
        build_report = (root / expanded.raw.get(
            f"{prefix}_validation_report", str(source.path.parent / "validation_report.json"))).resolve()
        builds.append((source, prefix, source_key, build_manifest, build_report))
    protected_inputs = {
        baseline_config.config_file.resolve(), baseline_config.manifest_file.resolve(),
        expanded.config_file.resolve(),
        *(source.path.resolve() for source in expanded.chunk_sources),
        *(path for _, _, _, manifest_path, report_path in builds for path in (manifest_path, report_path)),
    }
    if paths_config is not None:
        protected_inputs.add(paths_config)
    if expanded.manifest_file.resolve() in protected_inputs:
        raise ValueError("Expanded manifest destination would overwrite an input file")
    baseline = load_corpus_from_config(baseline_config)
    counts = dict(baseline.collection_counts)
    added_sources, glossaries, provenance = {}, {}, {}
    for source, prefix, source_key, development_manifest, development_report in builds:
        built = json.loads(development_manifest.read_text(encoding="utf-8"))
        report = json.loads(development_report.read_text(encoding="utf-8"))
        if built["partial"] or report.get("partial") or report.get("status") != "passed":
            raise ValueError(f"{prefix} development build is partial or failed")
        if built.get("collection", source.collection) != source.collection:
            raise ValueError(f"{prefix} collection does not match build manifest")
        if report.get("created_at") != built.get("created_at"):
            raise ValueError(f"{prefix} manifest/report refer to different runs")
        if source.collection == "gene_association_wes":
            reference = built.get("baseline_reference", {})
            baseline_rare = next(s.path for s in baseline_config.chunk_sources if s.collection == "gene_association_rare")
            if ((root / reference.get("path", "")).resolve() != baseline_rare or
                    reference.get("sha256") != file_sha256(baseline_rare)):
                raise ValueError("WES baseline reference changed; rebuild overlap links")
        validated_dense = built.get("dense_config_snapshot", {})
        if (validated_dense.get("model") != expanded.dense_model or
                validated_dense.get("max_seq_length") != expanded.dense_max_seq_length):
            raise ValueError("Expanded dense model/limit differs from token validation; rebuild required")
        if (root / built["output"]["path"]).resolve() != source.path:
            raise ValueError(f"{prefix} chunk path does not match build manifest")
        new_hash = file_sha256(source.path)
        if new_hash != built["output"]["sha256"] or new_hash != report.get("chunk_sha256"):
            raise ValueError(f"{prefix} build hash mismatch")
        counts.update(load_corpus([source], expected_total=built["output"]["chunks"]).collection_counts)
        added_sources[source_key] = built["source"]
        glossaries[f"{prefix}_glossary"] = built["glossary"]
        provenance[f"{prefix}_build_manifest"] = {
            "path": relative_source_path(development_manifest, root), "sha256": file_sha256(development_manifest)}
    previous = json.loads(baseline_config.manifest_file.read_text(encoding="utf-8"))
    manifest = {
        "pipeline_version": previous["pipeline_version"] + ".expanded-dev",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "expanded-development-corpus-not-an-index-release",
        "sources": {**previous["sources"], **added_sources},
        **glossaries,
        "provenance": {
            "baseline_manifest": {"path": relative_source_path(baseline_config.manifest_file, root),
                                  "sha256": file_sha256(baseline_config.manifest_file)},
            **provenance,
        },
        "outputs": {
            source.path.name: {"collection": source.collection,
                               "path": relative_source_path(source.path, root),
                               "chunks": counts[source.collection], "sha256": file_sha256(source.path)}
            for source in expanded.chunk_sources
        },
    }
    expanded.manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with artifact_staging_directory(expanded.manifest_file.parent, ".retrieval-") as staging:
        staged = staging / "retrieval_manifest.json"
        staged.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        load_corpus(expanded.chunk_sources, manifest_file=staged,
                    expected_total=sum(counts.values()), project_root=root)
        staged.replace(expanded.manifest_file)
    return {"manifest": str(expanded.manifest_file), "total": sum(counts.values()), "collections": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the expanded development retrieval corpus without modifying baseline artifacts.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/retrieval.yaml")
    args = parser.parse_args()
    print(json.dumps(prepare_manifest(args.config), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
