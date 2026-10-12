from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.bm25_retriever import build_bm25_index, save_bm25_index
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config


def parse_args():
    parser = argparse.ArgumentParser(description="Build the CS-46 BM25 sparse index.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--text-fields", nargs="+", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_retrieval_config(PROJECT_ROOT, args.config)
    text_fields = tuple(args.text_fields) if args.text_fields else config.text_fields
    output_dir = args.output_dir or config.index_dir

    corpus = load_corpus_from_config(config)
    index = build_bm25_index(corpus, text_fields)
    save_bm25_index(index, output_dir)
    print(f"Indexed {len(corpus.records)} chunks -> {output_dir}")
    print(f"Collections: {corpus.collection_counts}")
    print(f"text_fields={list(text_fields)} method={index.meta.get('method')} k1={index.meta.get('k1')} b={index.meta.get('b')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
