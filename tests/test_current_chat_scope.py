from pathlib import Path

from retrieval.access import WORKSPACES
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_manifest_counts


def test_current_chat_uses_only_new_delivery_collections():
    root = Path(__file__).resolve().parents[1]
    config = load_retrieval_config(root)
    names = [source.collection for source in config.chunk_sources]
    assert names == list(WORKSPACES["all"]["collections"])
    assert len(names) == 7
    assert "ldsc_partitioned_heritability" not in names
    assert list(load_manifest_counts(config.manifest_file)) == names
