from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import sys
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from chunking.ldsc_partitioned_chunker import chunk_ldsc_partitioned
from chunking.clumped_chunker import COLLECTION as CLUMPED_COLLECTION, OUTPUT_NAME as CLUMPED_OUTPUT, chunk_clumped_regions
from chunking.wes_chunker import COLLECTION as WES_COLLECTION, OUTPUT_NAME as WES_OUTPUT, chunk_wes
from chunking.paths import load_paths
from chunking.phenotype_glossary import PhenotypeGlossary
from chunking.utils import artifact_staging_directory, file_sha256, relative_source_path, write_jsonl


def load_tokenizer(model: str):
    from huggingface_hub import try_to_load_from_cache
    from transformers import AutoTokenizer

    cached_config = try_to_load_from_cache(model, "config.json")
    location = str(Path(cached_config).parent) if isinstance(cached_config, str) else model
    return AutoTokenizer.from_pretrained(location, local_files_only=True)


def _tokenizer_revision(tokenizer: Any) -> str | None:
    revision = getattr(tokenizer, "init_kwargs", {}).get("_commit_hash")
    if revision:
        return str(revision)
    location = Path(str(getattr(tokenizer, "name_or_path", "")))
    if location.parent.name == "snapshots" and re.fullmatch(r"[0-9a-f]{40,64}", location.name):
        return location.name
    return None


def _write_json(path: Path, value: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def _save_report(output_dir: Path, report: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with artifact_staging_directory(output_dir, ".validation-") as staging:
        path = staging / "validation_report.json"
        _write_json(path, report)
        path.replace(output_dir / path.name)


def build_collection(
    config_file: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    limit: int = 0,
    tokenizer: Any | None = None,
    paths_config_file: Path | None = None,
    collection: str = "ldsc_partitioned_heritability",
) -> dict[str, Any]:
    """Validate new chunks before publishing canonical or isolated artifacts.

    Unsafe configuration raises ValueError without writing. Source/tokenizer
    failures return a failed report and preserve any previous successful output.
    """
    if type(limit) is not int or limit < 0:
        raise ValueError("limit must be a nonnegative integer")
    if collection not in ("ldsc_partitioned_heritability", CLUMPED_COLLECTION, WES_COLLECTION):
        raise ValueError("Unsupported evidence collection")
    project_config_root = project_root.resolve()
    root = Path(os.environ.get("BIOAGENT_DATA_ROOT", str(project_config_root))).resolve()
    config_file = config_file.resolve()
    config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    paths = {
        key: ((root if key in {"raw_file", "output_dir"} else project_config_root) / config[key]).resolve()
        for key in ("raw_file", "glossary_file", "retrieval_config", "output_dir")
    }
    output_dir = paths["output_dir"]
    output_name = {CLUMPED_COLLECTION: CLUMPED_OUTPUT, WES_COLLECTION: WES_OUTPUT}.get(collection, "ldsc_partitioned_2hrG.chunks.jsonl")
    final_chunks = output_dir / output_name
    paths_config = None
    canonical_inputs: set[Path] = set()
    if paths_config_file is not None or config.get("paths_config"):
        paths_config = (paths_config_file or project_config_root / config["paths_config"]).resolve()
        canonical = load_paths(project_config_root, paths_config)
        if (canonical.project_root != root or not canonical.chunks_dir.is_relative_to(root)
                or canonical.chunks_dir != (root / "artifacts/chunks").resolve()):
            raise ValueError("Canonical chunks_dir must be artifacts/chunks under project_root")
        source = (canonical.wes_2hrg_file if collection == WES_COLLECTION else
                  canonical.metaanalysis_clumped_2hrg_eu_file if collection == CLUMPED_COLLECTION
                  else canonical.ldsc_partitioned_2hrg_file)
        if source is None:
            raise ValueError("paths_config must register the selected evidence source")
        if limit:
            raise ValueError("A partial build (limit > 0) cannot replace canonical chunks")
        paths["raw_file"] = source
        paths["glossary_file"] = canonical.glossary_file
        final_chunks = canonical.chunks_dir / final_chunks.name
        if collection == CLUMPED_COLLECTION:
            if canonical.clumped_validation_dir is None:
                raise ValueError("paths_config must register clumped_validation_dir")
            output_dir = canonical.clumped_validation_dir
            partitioned_dir = paths["output_dir"]
            if output_dir.is_relative_to(partitioned_dir) or partitioned_dir.is_relative_to(output_dir):
                raise ValueError("Clumped and partitioned metadata directories must be separate")
        if collection == WES_COLLECTION:
            if canonical.wes_validation_dir is None:
                raise ValueError("paths_config must register wes_validation_dir")
            output_dir = canonical.wes_validation_dir
            for other in (paths["output_dir"], canonical.clumped_validation_dir):
                if other is not None and (output_dir.is_relative_to(other) or other.is_relative_to(output_dir)):
                    raise ValueError("WES metadata directory must be separate from other collections")
        canonical_inputs = {canonical.manifest_file, canonical.gene_file, canonical.ldsc_file,
                            canonical.gene_id_map_file, canonical.gene_association_common_2hrg_file,
                            canonical.gene_association_rare_2hrg_file}
        if canonical.partitioned_manifest_file is not None:
            canonical_inputs.add(canonical.partitioned_manifest_file)
        for source_path in (canonical.ldsc_partitioned_2hrg_file, canonical.metaanalysis_clumped_2hrg_eu_file, canonical.wes_2hrg_file):
            if source_path is not None:
                canonical_inputs.add(source_path)
        for filename in ("gene_info.chunks.jsonl", "ldsc_2hrI.chunks.jsonl",
                         "gene_association_common_2hrG.chunks.jsonl", "gene_association_rare_2hrG.chunks.jsonl",
                         "ldsc_partitioned_2hrG.chunks.jsonl", CLUMPED_OUTPUT, WES_OUTPUT):
            target = canonical.chunks_dir / filename
            if target != final_chunks:
                canonical_inputs.add(target)
    elif collection in (CLUMPED_COLLECTION, WES_COLLECTION):
        raise ValueError("Clumped build requires canonical paths_config")
    allowed = (root / "artifacts/ingestion_dev").resolve()
    # Restrict development publication, including resolved traversal/symlinks.
    if not allowed.is_relative_to(root) or output_dir == allowed or not output_dir.is_relative_to(allowed):
        raise ValueError("output_dir must be a subdirectory of artifacts/ingestion_dev")
    existing_manifest = output_dir / "manifest.json"
    if existing_manifest.exists():
        previous_collection = json.loads(existing_manifest.read_text(encoding="utf-8")).get("collection")
        if previous_collection is not None and previous_collection != collection:
            raise ValueError("Output metadata belongs to another collection")
    inputs = [config_file, *(paths[k] for k in ("raw_file", "glossary_file", "retrieval_config"))]
    if paths_config is not None:
        inputs.append(paths_config)
    if collection == WES_COLLECTION:
        baseline_chunks = canonical.chunks_dir / "gene_association_rare_2hrG.chunks.jsonl"
        inputs.append(baseline_chunks)
    protected_inputs = set(inputs) | canonical_inputs
    if any(p.is_relative_to(output_dir) for p in protected_inputs):
        raise ValueError("ingestion_dev output directory cannot contain input/config files")
    if final_chunks.resolve() in protected_inputs:
        raise ValueError("Canonical output cannot overwrite an input/config file")

    report: dict[str, Any] = {
        "status": "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "canonical-chunks-not-indexed" if paths_config else "standalone-development-chunks-not-indexed",
        "partial": limit > 0,
        "limit": limit,
        "overlong_records": [],
        "previous_artifacts_preserved": (output_dir / "manifest.json").exists() or final_chunks.exists(),
    }
    try:
        retrieval = yaml.safe_load(paths["retrieval_config"].read_text(encoding="utf-8"))
        dense = retrieval["dense"]
        model, max_tokens = dense["model"], dense["max_seq_length"]
        if not isinstance(model, str) or not model.strip() or type(max_tokens) is not int or max_tokens <= 0:
            raise ValueError("dense model/max_seq_length configuration is invalid")
        fingerprints = {str(p): file_sha256(p) for p in inputs}
        glossary = PhenotypeGlossary.from_file(paths["glossary_file"])
        chunker = chunk_clumped_regions if collection == CLUMPED_COLLECTION else chunk_ldsc_partitioned
        wes_result = None
        if collection == WES_COLLECTION:
            wes_result = chunk_wes(paths["raw_file"], glossary, root, baseline_chunks)
            all_chunks = wes_result.chunks
        else:
            all_chunks = list(chunker(paths["raw_file"], glossary, root))
        if not all_chunks:
            raise ValueError("Source contains no evidence records")
        chunks = all_chunks[:limit] if limit else all_chunks
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("Duplicate chunk IDs detected")
        report.update({
            "raw_rows": (wes_result.raw_rows if wes_result else sum(c.metadata["member_count"] for c in all_chunks)
                         if collection in (CLUMPED_COLLECTION, WES_COLLECTION) else len(all_chunks)), "chunks": len(chunks),
            "groups": len({c.metadata["group_id"] for c in chunks}),
            "model": model, "max_seq_length": max_tokens,
            "source_validation": ("unique variants, consistent region bounds, one minimum-p lead, finite statistics, positive SE/n, pValue bounds"
                                  if collection == CLUMPED_COLLECTION else
                                  "required fields, finite statistics, nonnegative standard errors, pValue bounds, unique identities"),
            "source_file": relative_source_path(paths["raw_file"], root),
            "source_sha256": fingerprints[str(paths["raw_file"])],
        })
        if collection == WES_COLLECTION:
            report.update({"quarantined_rows": len(wes_result.quarantined),
                           "quarantine": wes_result.quarantined,
                           "record_kind_counts": dict(Counter(c.metadata["record_kind"] for c in chunks)),
                           "overlapping_gene_summaries": sum(c.metadata["record_kind"] == "gene_summary" and c.metadata["top_level_matches_baseline"] for c in chunks),
                           "source_validation": "valid gene/phenotype identities, finite statistics, unique masks, positive SE/n, pValue/count bounds; invalid genes quarantined"})
        else:
            report["ancestry_counts"] = dict(Counter(c.metadata["ancestry"] for c in chunks))
        if collection == "ldsc_partitioned_heritability":
            report["biosample_status_counts"] = dict(Counter(c.metadata["biosample_status"] for c in chunks))
        tokenizer = tokenizer if tokenizer is not None else load_tokenizer(model)
        lengths = []
        for chunk in chunks:
            tokens = len(tokenizer(chunk.content, add_special_tokens=True, truncation=False)["input_ids"])
            lengths.append(tokens)
            if tokens > max_tokens:
                location = ({"source_rows": chunk.metadata["source_rows"]} if collection == CLUMPED_COLLECTION
                            else {"source_row": chunk.metadata["source_row"]})
                report["overlong_records"].append({"chunk_id": chunk.chunk_id, "tokens": tokens, **location})
        report["token_lengths"] = {"min": min(lengths), "max": max(lengths), "median": statistics.median(lengths)}
        if report["overlong_records"]:
            raise ValueError(f"{len(report['overlong_records'])} chunks exceed {max_tokens} tokens; no truncation applied")
        if any(file_sha256(p) != fingerprints[str(p)] for p in inputs):
            raise ValueError("Input or configuration changed during validation; rerun required")

        output_dir.mkdir(parents=True, exist_ok=True)
        final_chunks.parent.mkdir(parents=True, exist_ok=True)
        with artifact_staging_directory(output_dir, ".build-") as staged:
            chunk_path = staged / output_name
            write_jsonl(chunk_path, (c.to_dict() for c in chunks))
            chunk_hash = file_sha256(chunk_path)
            manifest = {
                "schema_version": 1, "created_at": report["created_at"],
                "scope": report["scope"], "partial": report["partial"], "raw_rows": report["raw_rows"],
                "collection": collection,
                "source": {"path": report["source_file"], "sha256": report["source_sha256"]},
                "glossary": {"path": relative_source_path(paths["glossary_file"], root),
                             "sha256": fingerprints[str(paths["glossary_file"])]},
                "output": {"path": relative_source_path(final_chunks, root),
                           "chunks": len(chunks), "sha256": chunk_hash},
                "config_snapshot": config, "dense_config_snapshot": dense,
                "config_sha256": fingerprints[str(config_file)],
                "retrieval_config_sha256": fingerprints[str(paths["retrieval_config"])],
                "tokenizer": {"model": model, "revision": _tokenizer_revision(tokenizer),
                              "add_special_tokens": True, "truncation": False},
            }
            if collection == WES_COLLECTION:
                manifest["baseline_reference"] = {"path": relative_source_path(baseline_chunks, root),
                                                  "sha256": fingerprints[str(baseline_chunks)]}
                manifest["quarantined_rows"] = report["quarantined_rows"]
            if paths_config is not None:
                manifest["paths_config"] = {"path": relative_source_path(paths_config, root),
                                            "sha256": fingerprints[str(paths_config)]}
            _write_json(staged / "manifest.json", manifest)
            backup = staged / "previous.chunks.jsonl"
            if final_chunks.exists():
                shutil.copyfile(final_chunks, backup)
            published_chunks = False
            try:
                chunk_path.replace(final_chunks)
                published_chunks = True
                (staged / "manifest.json").replace(output_dir / "manifest.json")
            except Exception:
                if published_chunks:
                    try:
                        if backup.exists():
                            backup.replace(final_chunks)
                        else:
                            final_chunks.unlink()
                    except Exception as rollback_error:
                        report["previous_artifacts_preserved"] = False
                        report["rollback_error"] = str(rollback_error)
                        if backup.exists():
                            recovery = output_dir / f"recovery-{staged.name}.chunks.jsonl"
                            shutil.copyfile(backup, recovery)
                            report["recovery_file"] = relative_source_path(recovery, root)
                        raise RuntimeError("Publication and rollback failed; inspect recovery diagnostic") from rollback_error
                raise
        report.update({"status": "passed", "chunk_sha256": chunk_hash,
                       "previous_artifacts_preserved": False})
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    _save_report(output_dir, report)
    return report


def build_partitioned(config_file: Path, **kwargs) -> dict[str, Any]:
    return build_collection(config_file, collection="ldsc_partitioned_heritability", **kwargs)


def build_clumped(config_file: Path, **kwargs) -> dict[str, Any]:
    return build_collection(config_file, collection=CLUMPED_COLLECTION, **kwargs)


def build_wes(config_file: Path, **kwargs) -> dict[str, Any]:
    return build_collection(config_file, collection=WES_COLLECTION, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and validate LDSC partitioned chunks using configured canonical paths.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/ldsc_partitioned_dev.yaml")
    parser.add_argument("--limit", type=int, default=0,
                        help="0 = full source; partial output requires an isolated config without paths_config")
    args = parser.parse_args()
    try:
        report = build_partitioned(args.config, limit=args.limit)
    except (ValueError, OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
