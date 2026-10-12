from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure src is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from augmentation.builder import ContextBuilder
from chunking.phenotype_glossary import PhenotypeGlossary
from generation.aihubmix import AIHubMixGenerator
from generation.offline import OfflineEvidenceGenerator
from rag.pipeline import RAGPipeline
from retrieval.bm25_retriever import load_bm25_index
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.router import ALL_COLLECTIONS
from retrieval.service import RetrievalRequest, RetrieverService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag-api")

app = FastAPI(
    title="GenEngine Evidence-Grounded Scientific RAG API",
    description="Scientific RAG assistant API with claim citations and quality evaluation for drug discovery.",
    version="1.2.0",
)

# Enable CORS for React frontend (e.g., http://localhost:5173 or other local dev origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory pipeline state
_PIPELINE: Optional[RAGPipeline] = None
_GLOSSARY: Optional[PhenotypeGlossary] = None
_GENE_INDEX: dict[str, dict[str, Any]] = {}
_COMMON_ASSOC: dict[str, list[dict[str, Any]]] = {}
_RARE_ASSOC: dict[str, list[dict[str, Any]]] = {}


def get_pipeline() -> RAGPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        logger.info("Initializing RAG pipeline from disk...")
        config = load_retrieval_config(PROJECT_ROOT)
        corpus = load_corpus_from_config(config)
        backend = load_bm25_index(config.index_dir, corpus.records)
        _PIPELINE = RAGPipeline(
            RetrieverService(backend, "bm25"),
            ContextBuilder(),
            OfflineEvidenceGenerator(),
        )
        logger.info("RAG pipeline ready.")
    return _PIPELINE


def get_glossary() -> PhenotypeGlossary:
    global _GLOSSARY
    if _GLOSSARY is None:
        glossary_path = PROJECT_ROOT / "config/phenotype_glossary.json"
        _GLOSSARY = PhenotypeGlossary.from_file(glossary_path)
    return _GLOSSARY


def load_gene_indexes():
    global _GENE_INDEX, _COMMON_ASSOC, _RARE_ASSOC
    if _GENE_INDEX:
        return
    # Pre-index gene chunks for instant entity lookup
    chunks_dir = PROJECT_ROOT / "artifacts/chunks"
    gene_info_path = chunks_dir / "gene_info.chunks.jsonl"
    if gene_info_path.exists():
        with open(gene_info_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    gene = item.get("metadata", {}).get("gene") or item.get("title", "").replace("Gene ", "")
                    if gene:
                        _GENE_INDEX[gene.upper()] = item

    # Pre-index common associations
    common_path = chunks_dir / "gene_association_common_2hrG.chunks.jsonl"
    if common_path.exists():
        with open(common_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    gene = item.get("metadata", {}).get("gene", "").upper()
                    if gene:
                        _COMMON_ASSOC.setdefault(gene, []).append(item)

    # Pre-index rare associations
    rare_path = chunks_dir / "gene_association_rare_2hrG.chunks.jsonl"
    if rare_path.exists():
        with open(rare_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    gene = item.get("metadata", {}).get("gene", "").upper()
                    if gene:
                        _RARE_ASSOC.setdefault(gene, []).append(item)


@app.on_event("startup")
def startup_event():
    get_pipeline()
    get_glossary()
    load_gene_indexes()


# --- Models ---
class QueryRequest(BaseModel):
    question: str = Field(..., description="The scientific question to ask.")
    authorized_collections: Optional[list[str]] = Field(None, description="Collections to restrict search to.")
    top_k: int = Field(10, ge=1, le=50, description="Max passages to retrieve.")
    api_key: Optional[str] = Field(None, description="Optional AIHubMix API key for online LLM synthesis.")
    model: Optional[str] = Field("gpt-4o-mini", description="LLM model name if using API key.")


class ClaimResponse(BaseModel):
    text: str
    citations: list[str]


class QueryResponse(BaseModel):
    status: str
    answer: str
    claims: list[ClaimResponse]
    citations: list[dict[str, Any]]
    limitations: list[str]
    validation: dict[str, Any]
    latency_s: dict[str, float]
    retrieved_count: int
    provider: str


# --- Endpoints ---
@app.get("/api/health")
def health_check():
    get_pipeline()
    return {
        "status": "healthy",
        "collections": ALL_COLLECTIONS,
        "indexed_genes": len(_GENE_INDEX),
        "glossary_terms": len(get_glossary()._entries),
        "total_chunks": 41103,
    }


@app.post("/api/rag/query", response_model=QueryResponse)
def query_rag(req: QueryRequest):
    pipeline = get_pipeline()
    collections = tuple(req.authorized_collections or ALL_COLLECTIONS)

    generator = OfflineEvidenceGenerator()
    provider_name = "offline_evidence"
    if req.api_key and req.api_key.strip():
        generator = AIHubMixGenerator(api_key=req.api_key.strip(), model=req.model or "gpt-4o-mini")
        provider_name = f"aihubmix:{req.model}"

    # Swap generator for this query
    active_pipeline = RAGPipeline(
        pipeline.retriever,
        pipeline.context_builder,
        generator,
    )

    start_time = time.perf_counter()
    try:
        run = active_pipeline.run(
            RetrievalRequest(
                req.question,
                authorized_collections=collections,
                top_k=req.top_k,
            )
        )
    except Exception as e:
        logger.warning(f"Generator {provider_name} failed: {e}. Falling back to OfflineEvidenceGenerator.")
        fallback_pipeline = RAGPipeline(
            pipeline.retriever,
            pipeline.context_builder,
            OfflineEvidenceGenerator(),
        )
        run = fallback_pipeline.run(
            RetrievalRequest(
                req.question,
                authorized_collections=collections,
                top_k=req.top_k,
            )
        )
        provider_name = "offline_fallback"
        run.answer.limitations.append(f"Online LLM unavailable: {e}. Automatically used local verified evidence engine.")

    total_time = time.perf_counter() - start_time

    claims = [ClaimResponse(text=c.text, citations=c.citations) for c in run.answer.claims]
    latencies = {**run.latency_s, "total_api": total_time}

    formatted_citations = []
    for c in run.answer.citations:
        if isinstance(c, dict):
            item = dict(c)
            item["id"] = item.get("chunk_id") or item.get("id", "source")
            item["title"] = item.get("source_name") or item.get("title") or item["id"]
            formatted_citations.append(item)
        else:
            formatted_citations.append({"id": str(c), "title": str(c), "chunk_id": str(c)})

    return QueryResponse(
        status=run.answer.status,
        answer=run.answer.answer,
        claims=claims,
        citations=formatted_citations,
        limitations=run.answer.limitations,
        validation=asdict(run.validation),
        latency_s=latencies,
        retrieved_count=len(run.retrieval.results),
        provider=run.answer.provider or provider_name,
    )


@app.get("/api/genes")
def list_genes(q: Optional[str] = None):
    """List sample high-priority genes or search by symbol/alias query."""
    featured = ["PPARG", "TCF7L2", "ADCY5", "LPCAT2", "SLC30A8", "INS", "KCNJ11", "GCK", "HNF1A", "CDKAL1", "AKT1", "BAD", "CEBPA", "IRS1", "CD36", "LIPC"]
    if q and q.strip():
        q_upper = q.strip().upper()
        matches = [g for g in _GENE_INDEX.keys() if g.startswith(q_upper)]
        if len(matches) < 15:
            matches += [g for g in _GENE_INDEX.keys() if q_upper in g and g not in matches]
        selected = matches[:15]
    else:
        selected = featured

    out = []
    for g in selected:
        entry = _GENE_INDEX.get(g)
        if entry:
            out.append({
                "symbol": g,
                "title": entry.get("title", f"Gene {g}"),
                "metadata": entry.get("metadata", {}),
                "has_common_evidence": g in _COMMON_ASSOC,
                "has_rare_evidence": g in _RARE_ASSOC,
            })
    return {"genes": out, "total_indexed": len(_GENE_INDEX)}


@app.get("/api/genes/{symbol}")
def get_gene_details(symbol: str):
    sym = symbol.strip().upper()
    entry = _GENE_INDEX.get(sym)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Gene {symbol} not found in approved corpus.")
    
    common = _COMMON_ASSOC.get(sym, [])
    rare = _RARE_ASSOC.get(sym, [])

    common_bf = common[0].get("metadata", {}).get("bf_common", 1.0) if common else 1.0
    rare_bf = rare[0].get("metadata", {}).get("bf_rare", 1.0) if rare else 1.0
    huge_score = float(common_bf) * float(rare_bf)

    phenotype_map: dict[str, dict[str, Any]] = {}
    for c in common:
        meta = c.get("metadata", {})
        pt = meta.get("phenotype", "2hrG")
        phenotype_map.setdefault(pt, {})["common_bf"] = meta.get("bf_common", 1.0)
        phenotype_map[pt]["label"] = meta.get("phenotype_label", pt)
        phenotype_map[pt]["evidence_tier"] = meta.get("evidence_tier", "baseline")
        phenotype_map[pt]["has_causal"] = meta.get("has_causal_annotation", False)
        phenotype_map[pt]["causal_p"] = meta.get("pValueCausal")

    for r in rare:
        meta = r.get("metadata", {})
        pt = meta.get("phenotype", "2hrG")
        phenotype_map.setdefault(pt, {})["rare_bf"] = meta.get("bf_rare", 1.0)
        phenotype_map[pt]["label"] = meta.get("phenotype_label", pt)
        phenotype_map[pt]["beta"] = meta.get("beta")
        phenotype_map[pt]["z"] = meta.get("z")
        phenotype_map[pt]["p_value"] = meta.get("pValue")

    assoc_summary = []
    for pt, vals in phenotype_map.items():
        c_bf = float(vals.get("common_bf", 1.0))
        r_bf = float(vals.get("rare_bf", 1.0))
        assoc_summary.append({
            "phenotype": pt,
            "label": vals.get("label", pt),
            "common_bf": c_bf,
            "rare_bf": r_bf,
            "huge_score": round(c_bf * r_bf, 2),
            "beta": vals.get("beta"),
            "z": vals.get("z"),
            "p_value": vals.get("p_value") or vals.get("causal_p"),
            "evidence_tier": vals.get("evidence_tier", "standard"),
        })

    return {
        "symbol": sym,
        "title": entry.get("title"),
        "content": entry.get("content"),
        "metadata": entry.get("metadata"),
        "citation": entry.get("citation"),
        "huge_score": round(huge_score, 2),
        "common_evidence_count": len(common),
        "rare_evidence_count": len(rare),
        "associations": assoc_summary,
        "common_evidence": [c.get("metadata") for c in common],
        "rare_evidence": [r.get("metadata") for r in rare],
    }


@app.get("/api/phenotypes")
def list_phenotypes(q: Optional[str] = None):
    glossary = get_glossary()
    items = []
    if q and q.strip():
        q_lower = q.strip().lower()
        count = 0
        for code, entry in glossary._entries.items():
            label = entry.label or code
            if q_lower in code.lower() or q_lower in label.lower() or any(q_lower in a.lower() for a in entry.aliases):
                items.append({
                    "code": code,
                    "label": label,
                    "category": entry.category,
                    "group": entry.group,
                    "aliases": entry.aliases,
                })
                count += 1
                if count >= 25:
                    break
    else:
        priority = ["2hrG", "2hrI", "T2D", "BMI", "2hrFFA", "Alb_invn", "ALT", "AD", "FG", "FI", "HbA1c", "CAD", "HDL", "LDL", "TG"]
        for code in priority:
            if code in glossary._entries:
                label, _ = glossary.get_label(code)
                items.append({
                    "code": code,
                    "label": label,
                    "category": glossary.get_category(code),
                    "group": glossary.get_group(code),
                    "aliases": glossary.get_aliases(code),
                })
    return {"phenotypes": items, "total_terms": len(glossary._entries)}


@app.get("/api/phenotypes/{code}")
def get_phenotype_details(code: str):
    glossary = get_glossary()
    resolved = glossary.resolve_code(code) or code
    entry = glossary._entries.get(resolved)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Phenotype {code} not recognized.")
    label, origin = glossary.get_label(resolved)
    return {
        "code": resolved,
        "label": label,
        "category": glossary.get_category(resolved),
        "group": glossary.get_group(resolved),
        "aliases": glossary.get_aliases(resolved),
        "curation_status": origin,
    }
