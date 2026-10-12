from __future__ import annotations

import argparse
import faulthandler
import sys
from pathlib import Path

faulthandler.enable()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.dense_retriever import (
    SentenceTransformerEncoder,
    build_dense_index,
    save_dense_index,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build the CS-46 Qwen3 dense FAISS index. Run this manually; it can take 15-40 minutes."
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--device", type=str, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_retrieval_config(PROJECT_ROOT, args.config)
    output_dir = args.output_dir or config.dense_index_dir
    batch_size = args.batch_size or config.dense_batch_size
    device = args.device or config.dense_device

    print("Loading corpus...", flush=True)
    corpus = load_corpus_from_config(config)
    print(f"Loaded {len(corpus.records)} chunks {corpus.collection_counts}", flush=True)
    encoder = SentenceTransformerEncoder(
        model_name=config.dense_model,
        device=device,
        max_seq_length=config.dense_max_seq_length,
        dimension=config.dense_dimension,
    )
    print(
        f"Encoding content with batch_size={batch_size} device={encoder.device}",
        flush=True,
    )
    index = build_dense_index(corpus, encoder, batch_size)
    save_dense_index(index, output_dir)
    print(
        f"Wrote dense index ntotal={index.faiss_index.ntotal} dim={index.faiss_index.d} -> {output_dir}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
