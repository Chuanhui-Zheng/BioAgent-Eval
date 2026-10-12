from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from chunking.gene_association_chunker import (
    chunk_gene_association_common,
    chunk_gene_association_rare,
)
from chunking.gene_chunker import chunk_genes
from chunking.ldsc_chunker import chunk_ldsc_pairs
from chunking.paths import load_paths
from chunking.phenotype_glossary import PhenotypeGlossary
from chunking.schema import ChunkManifest
from chunking.utils import file_sha256, write_jsonl
from chunk_ldsc_partitioned import build_clumped, build_partitioned, build_wes
from prepare_partitioned_retrieval import prepare_manifest


def parse_args(defaults) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build normalized corpus chunks for CS-46 RAG.")
    parser.add_argument(
        "--paths-config",
        type=Path,
        default=defaults.config_file,
        help="Path to paths.yaml (default: config/paths.yaml)",
    )
    parser.add_argument("--gene-file", type=Path, default=None)
    parser.add_argument("--ldsc-file", type=Path, default=None)
    parser.add_argument("--glossary-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--manifest-file", type=Path, default=None)
    parser.add_argument("--dry-run", type=int, default=0, help="Only emit the first N chunks per source.")
    partitioned = parser.add_mutually_exclusive_group()
    partitioned.add_argument("--partitioned-only", action="store_true",
                             help="Build only LDSC partitioned chunks and the expanded manifest; preserve baseline artifacts.")
    partitioned.add_argument("--clumped-only", action="store_true",
                             help="Build only clumped regional chunks and refresh the expanded manifest; preserve existing chunks.")
    partitioned.add_argument("--wes-only", action="store_true",
                             help="Build only WES summaries/masks and refresh expanded manifest; preserve existing chunks.")
    partitioned.add_argument("--include-partitioned", action="store_true",
                             help="Rebuild baseline sources, then add LDSC partitioned chunks and an expanded manifest.")
    parser.add_argument("--partitioned-config", type=Path,
                        default=PROJECT_ROOT / "config/ldsc_partitioned_dev.yaml")
    parser.add_argument("--retrieval-config", "--partitioned-retrieval-config", dest="partitioned_retrieval_config", type=Path,
                        default=PROJECT_ROOT / "config/retrieval.yaml")
    return parser.parse_args()


def resolve_runtime_paths(args: argparse.Namespace):
    paths = load_paths(PROJECT_ROOT, args.paths_config)
    return replace(
        paths,
        gene_file=args.gene_file or paths.gene_file,
        ldsc_file=args.ldsc_file or paths.ldsc_file,
        glossary_file=args.glossary_file or paths.glossary_file,
        chunks_dir=args.output_dir or paths.chunks_dir,
        manifest_file=args.manifest_file or paths.manifest_file,
    )


def validate_chunk_records(records: list[dict]) -> None:
    seen_ids: set[str] = set()
    for record in records:
        chunk_id = record["chunk_id"]
        if chunk_id in seen_ids:
            raise ValueError(f"Duplicate chunk_id detected: {chunk_id}")
        seen_ids.add(chunk_id)

        required_fields = ["chunk_id", "collection", "entity_type", "title", "content", "metadata", "citation"]
        for field_name in required_fields:
            if field_name not in record or record[field_name] in (None, ""):
                raise ValueError(f"Missing required field '{field_name}' in chunk {chunk_id}")


def maybe_limit(records, limit: int):
    if limit <= 0:
        yield from records
        return

    count = 0
    for record in records:
        yield record
        count += 1
        if count >= limit:
            break


def main() -> int:
    defaults = load_paths(PROJECT_ROOT)
    args = parse_args(defaults)
    paths = resolve_runtime_paths(args)

    clumped_only = getattr(args, "clumped_only", False)
    wes_only = getattr(args, "wes_only", False)
    if args.partitioned_only or args.include_partitioned or clumped_only or wes_only:
        if args.dry_run or args.output_dir or args.manifest_file or args.glossary_file:
            raise ValueError("Partitioned publication requires full canonical paths; no dry-run/output/glossary overrides")
        if paths.ldsc_partitioned_2hrg_file is None:
            raise ValueError("Register ldsc_partitioned_2hrg in paths_config first")
    if wes_only:
        return build_partitioned_collection(paths, args, wes=True)
    if clumped_only:
        return build_partitioned_collection(paths, args, clumped=True)
    if args.partitioned_only:
        return build_partitioned_collection(paths, args)

    paths.chunks_dir.mkdir(parents=True, exist_ok=True)
    paths.manifest_file.parent.mkdir(parents=True, exist_ok=True)

    glossary = PhenotypeGlossary.from_file(paths.glossary_file)

    with paths.gene_file.open("r", encoding="utf-8") as handle:
        genes_payload = json.load(handle)

    gene_chunks = list(
        maybe_limit(chunk_genes(genes_payload, paths.gene_file, paths.project_root), args.dry_run)
    )
    ldsc_iter = chunk_ldsc_pairs(paths.ldsc_file, glossary, paths.project_root)
    ldsc_chunks = list(maybe_limit(ldsc_iter, args.dry_run))
    ldsc_raw_rows = getattr(chunk_ldsc_pairs, "raw_row_count", None)

    gassoc_common_iter = chunk_gene_association_common(
        paths.gene_association_common_2hrg_file,
        glossary,
        paths.project_root,
    )
    gassoc_common_chunks = list(maybe_limit(gassoc_common_iter, args.dry_run))
    gassoc_common_raw_rows = getattr(chunk_gene_association_common, "raw_row_count", None)

    gassoc_rare_iter = chunk_gene_association_rare(
        paths.gene_association_rare_2hrg_file,
        glossary,
        paths.project_root,
    )
    gassoc_rare_chunks = list(maybe_limit(gassoc_rare_iter, args.dry_run))
    gassoc_rare_raw_rows = getattr(chunk_gene_association_rare, "raw_row_count", None)

    if ldsc_raw_rows is None and args.dry_run == 0:
        ldsc_raw_rows = sum(len(item.metadata["results"]) for item in ldsc_chunks)

    gene_records = [chunk.to_dict() for chunk in gene_chunks]
    ldsc_records = [chunk.to_dict() for chunk in ldsc_chunks]
    gassoc_common_records = [chunk.to_dict() for chunk in gassoc_common_chunks]
    gassoc_rare_records = [chunk.to_dict() for chunk in gassoc_rare_chunks]

    all_records = gene_records + ldsc_records + gassoc_common_records + gassoc_rare_records
    validate_chunk_records(all_records)

    gene_output = paths.chunks_dir / "gene_info.chunks.jsonl"
    ldsc_output = paths.chunks_dir / "ldsc_2hrI.chunks.jsonl"
    gassoc_common_output = paths.chunks_dir / "gene_association_common_2hrG.chunks.jsonl"
    gassoc_rare_output = paths.chunks_dir / "gene_association_rare_2hrG.chunks.jsonl"

    gene_count = write_jsonl(gene_output, iter(gene_records))
    ldsc_count = write_jsonl(ldsc_output, iter(ldsc_records))
    gassoc_common_count = write_jsonl(gassoc_common_output, iter(gassoc_common_records))
    gassoc_rare_count = write_jsonl(gassoc_rare_output, iter(gassoc_rare_records))

    manifest = ChunkManifest(
        pipeline_version=paths.pipeline_version,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        sources={
            "gene_info": {
                "path": paths.gene_file.relative_to(paths.project_root).as_posix(),
                "sha256": file_sha256(paths.gene_file),
                "raw_records": len(genes_payload.get("genes", {})),
            },
            "ldsc_2hrI": {
                "path": paths.ldsc_file.relative_to(paths.project_root).as_posix(),
                "sha256": file_sha256(paths.ldsc_file),
                "raw_rows": ldsc_raw_rows,
            },
            "gene_id_map": {
                "path": paths.gene_id_map_file.relative_to(paths.project_root).as_posix(),
                "sha256": file_sha256(paths.gene_id_map_file),
                "chunked": False,
                "note": "Reference lookup only; not embedded in RAG index",
            },
            "gene_association_common_2hrG": {
                "path": paths.gene_association_common_2hrg_file.relative_to(
                    paths.project_root
                ).as_posix(),
                "sha256": file_sha256(paths.gene_association_common_2hrg_file),
                "raw_rows": gassoc_common_raw_rows,
            },
            "gene_association_rare_2hrG": {
                "path": paths.gene_association_rare_2hrg_file.relative_to(
                    paths.project_root
                ).as_posix(),
                "sha256": file_sha256(paths.gene_association_rare_2hrg_file),
                "raw_rows": gassoc_rare_raw_rows,
            },
            "paths_config": paths.config_file.relative_to(paths.project_root).as_posix(),
        },
        outputs={
            "gene_info.chunks.jsonl": {
                "path": gene_output.relative_to(paths.project_root).as_posix(),
                "chunks": gene_count,
            },
            "ldsc_2hrI.chunks.jsonl": {
                "path": ldsc_output.relative_to(paths.project_root).as_posix(),
                "chunks": ldsc_count,
            },
            "gene_association_common_2hrG.chunks.jsonl": {
                "path": gassoc_common_output.relative_to(paths.project_root).as_posix(),
                "chunks": gassoc_common_count,
            },
            "gene_association_rare_2hrG.chunks.jsonl": {
                "path": gassoc_rare_output.relative_to(paths.project_root).as_posix(),
                "chunks": gassoc_rare_count,
            },
        },
    )

    with paths.manifest_file.open("w", encoding="utf-8") as handle:
        json.dump(manifest.to_dict(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Using paths config: {paths.config_file}")
    print(f"Wrote {gene_count} gene chunks -> {gene_output}")
    print(f"Wrote {ldsc_count} LDSC chunks -> {ldsc_output}")
    print(f"Wrote {gassoc_common_count} common association chunks -> {gassoc_common_output}")
    print(f"Wrote {gassoc_rare_count} rare association chunks -> {gassoc_rare_output}")
    print(f"Wrote manifest -> {paths.manifest_file}")
    if args.include_partitioned:
        return build_partitioned_collection(paths, args)
    return 0


def build_partitioned_collection(paths, args, *, clumped=False, wes=False) -> int:
    builder = build_wes if wes else build_clumped if clumped else build_partitioned
    report = builder(args.partitioned_config, project_root=paths.project_root,
                               paths_config_file=paths.config_file)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "passed":
        return 1
    result = prepare_manifest(args.partitioned_retrieval_config, project_root=paths.project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
