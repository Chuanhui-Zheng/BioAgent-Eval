from pathlib import Path

from retrieval.access import WORKSPACES
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_manifest_counts


def test_chat_scope_matches_the_eight_collection_corpus():
    root = Path(__file__).resolve().parents[1]
    config = load_retrieval_config(root)
    names = [source.collection for source in config.chunk_sources]
    assert names == list(WORKSPACES["all"]["collections"])
    # The evaluation benchmarks (dev/test/blind) are labelled on all eight collections.
    assert len(names) == 8
    assert "ldsc_partitioned_heritability" in names
    assert list(load_manifest_counts(config.manifest_file)) == names
