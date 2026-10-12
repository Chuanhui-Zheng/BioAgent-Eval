from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import bm25s
import numpy as np

from retrieval.corpus import LoadedCorpus, metadata_matches
from retrieval.identifiers import exact_match_score, record_identifier_keys, record_label_needles
from retrieval.schema import ChunkRecord, SearchResult
from retrieval.tokenizer import tokenize, tokenize_query


@dataclass
class BM25Index:
    model: Any
    records: list[ChunkRecord]
    text_fields: tuple[str, ...]
    meta: dict[str, Any]
    identifier_keys: list[set[str]]
    label_needles: list[list[str]]

    def search(
        self,
        query: str,
        top_k: int = 10,
        collections: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            return []

        tokens = tokenize_query(query)
        if not tokens:
            tokens = tokenize(query)
        if not tokens:
            return []

        allowed = [
            index
            for index, record in enumerate(self.records)
            if (collections is None or record.collection in collections)
            and metadata_matches(record, filters)
        ]
        if not allowed:
            return []
        allowed_set = set(allowed)

        exact_hits = [
            (
                index,
                exact_match_score(
                    query,
                    tokens,
                    self.identifier_keys[index],
                    self.label_needles[index],
                ),
            )
            for index in allowed
        ]
        exact_hits = [(index, score) for index, score in exact_hits if score > 0]
        exact_hits.sort(
            key=lambda item: (
                -item[1],
                len(self.records[item[0]].metadata.get("other_phenotype_label") or ""),
                self.records[item[0]].chunk_id,
            )
        )

        n_docs = len(self.records)
        filtered = collections is not None or filters
        retrieve_k = min(n_docs, top_k if not filtered else min(n_docs, max(top_k * 20, 200)))
        query_tokens = [tokens]
        doc_ids = np.arange(n_docs)
        retrieved, scores = self.model.retrieve(
            query_tokens, corpus=doc_ids, k=retrieve_k, sorted=True, show_progress=False
        )
        bm25_rank: dict[int, tuple[int, float]] = {}
        for rank_pos, (doc_index, score) in enumerate(zip(retrieved[0], scores[0]), start=1):
            doc_index = int(doc_index)
            if doc_index < 0 or doc_index >= n_docs:
                continue
            if filtered and doc_index not in allowed_set:
                continue
            bm25_rank[doc_index] = (rank_pos, float(score))

        ranked: list[SearchResult] = []
        used: set[int] = set()
        max_bm25 = max((score for _, score in bm25_rank.values()), default=0.0)
        for doc_index, match_score in exact_hits:
            if len(ranked) >= top_k:
                break
            used.add(doc_index)
            record = self.records[doc_index]
            bm25_pos, bm25_score = bm25_rank.get(doc_index, (None, 0.0))
            ranked.append(
                SearchResult(
                    chunk_id=record.chunk_id,
                    collection=record.collection,
                    rank=len(ranked) + 1,
                    score=float(max_bm25 + match_score),
                    method="bm25",
                    component_scores={
                        "bm25": bm25_score,
                        "bm25_rank": bm25_pos,
                        "exact_match": match_score,
                    },
                    chunk=record.to_dict(),
                )
            )

        for doc_index, (rank_pos, score) in sorted(bm25_rank.items(), key=lambda item: item[1][0]):
            if len(ranked) >= top_k:
                break
            if doc_index in used:
                continue
            record = self.records[doc_index]
            ranked.append(
                SearchResult(
                    chunk_id=record.chunk_id,
                    collection=record.collection,
                    rank=len(ranked) + 1,
                    score=score,
                    method="bm25",
                    component_scores={"bm25": score, "bm25_rank": rank_pos, "exact_match": 0},
                    chunk=record.to_dict(),
                )
            )
        return ranked


TITLE_REPEAT = 2
ENTITY_INDEX_FIELDS = (
    "gene_symbol",
    "gene",
    "ensembl_gene_id",
    "ensembl",
    "alternative_names",
    "other_phenotype",
    "other_phenotype_label",
)


def build_index_text(record: ChunkRecord, text_fields: tuple[str, ...], title_repeat: int = TITLE_REPEAT) -> str:
    parts: list[str] = []
    if "title" in text_fields and record.title:
        parts.extend([record.title] * max(title_repeat, 1))
    if "content" in text_fields and record.content:
        parts.append(record.content)
    entity_bits: list[str] = []
    for field_name in ENTITY_INDEX_FIELDS:
        value = record.metadata.get(field_name)
        if isinstance(value, list):
            entity_bits.extend(str(item) for item in value if item)
        elif value:
            entity_bits.append(str(value))
    if entity_bits:
        parts.append(" ".join(entity_bits))
    return "\n".join(parts)


def build_bm25_index(corpus: LoadedCorpus, text_fields: tuple[str, ...]) -> BM25Index:
    tokenized = [tokenize(build_index_text(record, text_fields)) for record in corpus.records]
    model = bm25s.BM25()
    model.index(tokenized, show_progress=False)
    avg_len = float(np.mean([len(tokens) for tokens in tokenized])) if tokenized else 0.0
    meta = {
        "library": "bm25s",
        "library_version": getattr(bm25s, "__version__", "unknown"),
        "method": getattr(model, "method", None),
        "k1": getattr(model, "k1", None),
        "b": getattr(model, "b", None),
        "document_count": len(corpus.records),
        "average_document_length": avg_len,
        "text_fields": list(text_fields),
        "tokenizer": {
            "unicode_form": "NFKC",
            "lowercase": True,
            "stem": False,
            "document_stopwords": False,
            "query_stopwords": True,
        },
        "title_repeat": TITLE_REPEAT,
        "chunk_hashes": corpus.chunk_hashes,
        "collection_counts": corpus.collection_counts,
    }
    return BM25Index(
        model=model,
        records=corpus.records,
        text_fields=text_fields,
        meta=meta,
        identifier_keys=[record_identifier_keys(record) for record in corpus.records],
        label_needles=[record_label_needles(record) for record in corpus.records],
    )


def save_bm25_index(index: BM25Index, index_dir: Path) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    bm25_dir = index_dir / "bm25s"
    if bm25_dir.exists():
        shutil.rmtree(bm25_dir)
    index.model.save(str(bm25_dir))

    doc_map_path = index_dir / "doc_map.jsonl"
    with doc_map_path.open("w", encoding="utf-8") as handle:
        for position, record in enumerate(index.records):
            handle.write(
                json.dumps(
                    {
                        "index": position,
                        "chunk_id": record.chunk_id,
                        "collection": record.collection,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    meta_path = index_dir / "index_meta.json"
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(index.meta, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_bm25_index(index_dir: Path, records: list[ChunkRecord]) -> BM25Index:
    meta_path = index_dir / "index_meta.json"
    with meta_path.open("r", encoding="utf-8") as handle:
        meta = json.load(handle)
    model = bm25s.BM25.load(str(index_dir / "bm25s"), load_corpus=False)
    text_fields = tuple(meta.get("text_fields", ["title", "content"]))
    if len(records) != int(meta.get("document_count", len(records))):
        raise ValueError("Loaded corpus size does not match BM25 index metadata")
    return BM25Index(
        model=model,
        records=records,
        text_fields=text_fields,
        meta=meta,
        identifier_keys=[record_identifier_keys(record) for record in records],
        label_needles=[record_label_needles(record) for record in records],
    )
