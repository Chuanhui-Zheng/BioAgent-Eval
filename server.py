from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, SecretStr
from fastapi.exceptions import RequestValidationError

# Ensure src is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi.responses import JSONResponse
from retrieval.access import WORKSPACES, workspace_id, allowed_collections, path_is_allowed
from generation.fallback import FallbackGenerator
from augmentation.builder import ContextBuilder
from chunking.phenotype_glossary import PhenotypeGlossary
from generation.aihubmix import AIHubMixGenerator
from generation.hosted import OpenAIGenerator, AnthropicGenerator, GeminiGenerator, Provider, list_models, connection_error
from generation.llm_provider import OpenAICompatibleGenerator, validate_base_url
from generation.offline import OfflineEvidenceGenerator
from rag.pipeline import RAGPipeline
from retrieval.factory import build_search_backend
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.router import SUPPORTED_COLLECTIONS as ALL_COLLECTIONS
from retrieval.service import RetrievalRequest, RetrieverService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag-api")


@asynccontextmanager
async def lifespan(application):
    startup_event()
    yield


app = FastAPI(
    title="BioAgent-Eval Scientific Agent API",
    description="Evidence-grounded Scientific RAG API for the BioAgent-Eval Agent Harness and evaluation platform.",
    version="1.3.0",
    lifespan=lifespan,
)

# Enable CORS for local CLI/API integrations and automation clients.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def simulated_workspace(request, call_next):
    selected = request.headers.get("X-Workspace-ID", "all")
    if selected not in WORKSPACES:
        return JSONResponse({"detail": "Unknown simulated workspace."}, status_code=422)
    token = workspace_id.set(selected)
    try:
        if not path_is_allowed(request.url.path):
            return JSONResponse({"detail": "This resource is outside the selected simulated workspace."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Workspace-ID"] = selected
        response.headers["Vary"] = "X-Workspace-ID"
        return response
    finally:
        workspace_id.reset(token)

@app.get("/api/workspaces")
def workspaces():
    return {"mode": "simulated", "workspaces": WORKSPACES,
            "notice": "Workspace selection demonstrates isolation; it is not authentication."}

# Global in-memory pipeline state
_PIPELINE: Optional[RAGPipeline] = None
_GLOSSARY: Optional[PhenotypeGlossary] = None
_RETRIEVAL_STATUS: dict[str, Any] = {"method": "not_loaded"}
_GENE_INDEX: dict[str, dict[str, Any]] = {}
_COMMON_ASSOC: dict[str, list[dict[str, Any]]] = {}
_RARE_ASSOC: dict[str, list[dict[str, Any]]] = {}


def get_pipeline() -> RAGPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        logger.info("Initializing RAG pipeline from disk...")
        config = load_retrieval_config(PROJECT_ROOT)
        corpus = load_corpus_from_config(config)
        bundle = build_search_backend(config, corpus)
        global _RETRIEVAL_STATUS
        _RETRIEVAL_STATUS = {"method": bundle.method, "requested_method": bundle.requested_method,
                             "fallback_reasons": bundle.fallback_reasons}
        _PIPELINE = RAGPipeline(
            RetrieverService(bundle.backend, bundle.method),
            ContextBuilder(),
            OfflineEvidenceGenerator(),
        )
        logger.info("RAG pipeline ready (retrieval=%s, requested=%s).", bundle.method, bundle.requested_method)
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
                    gene = item.get("metadata", {}).get("gene") or item.get(
                        "title", ""
                    ).replace("Gene ", "")
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


def startup_event():
    get_pipeline()
    get_glossary()
    load_gene_indexes()


# --- Models ---
class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The scientific question to ask.",
    )
    authorized_collections: Optional[list[str]] = Field(
        None, description="Collections to restrict search to."
    )
    top_k: int = Field(10, ge=1, le=50, description="Max passages to retrieve.")
    api_key: Optional[SecretStr] = Field(None, description="Optional key for the selected provider.")
    provider: Provider = "aihubmix"
    model: Optional[str] = Field(None, max_length=200, description="Model ID from the selected provider.")
    base_url: Optional[str] = Field(
        None, max_length=500,
        description="Required for provider 'custom': any OpenAI-compatible base URL (https, or http on localhost).")


class ProviderRequest(BaseModel):
    provider: Provider
    api_key: SecretStr
    model: Optional[str] = Field(None, max_length=200)
    base_url: Optional[str] = Field(None, max_length=500)


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    # Pydantic includes rejected inputs by default; credentials must not be echoed.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
    ]})


def provider_settings(req, require_model=True):
    key = req.api_key.get_secret_value().strip() if req.api_key else ""
    model = (req.model or "").strip()
    if require_model and not model:
        if req.provider in {"aihubmix", "openai"}:
            model = "gpt-4o-mini"
        else:
            raise HTTPException(422, "Choose a model ID from your provider account.")
    return key, model


def custom_base_url(req):
    """Validated endpoint for provider 'custom' (OpenAI-compatible relays, local servers)."""
    if req.provider != "custom":
        return None
    try:
        return validate_base_url(req.base_url or "")
    except ValueError as exc:
        raise HTTPException(422, f"{exc}. Enter the provider's OpenAI-compatible base URL, e.g. https://api.example.com/v1.") from None


def hosted_generator(provider, key, model, base_url=None):
    classes = {"aihubmix": AIHubMixGenerator, "openai": OpenAIGenerator,
               "anthropic": AnthropicGenerator, "gemini": GeminiGenerator}
    # Model-only prices are relay prices (AIHubMix or a custom relay); never reuse them for direct APIs.
    rates = {}
    if provider in {"aihubmix", "custom"} and (PROJECT_ROOT / "config/model_pricing.json").exists():
        rates = json.loads((PROJECT_ROOT / "config/model_pricing.json").read_text()).get(model, {})
    pricing = {"input_cost_per_million": rates.get("input_usd_per_million"),
               "output_cost_per_million": rates.get("output_usd_per_million")}
    if provider == "custom":
        # The user chose this endpoint; the URL is validated (https, or http only on localhost).
        # Relays and large reasoning models often need well over 60 s for a full evidence answer.
        return OpenAICompatibleGenerator(api_key=key, model=model, base_url=base_url,
                                         provider_name="custom", timeout_s=120.0, **pricing)
    return classes[provider](api_key=key, model=model, **pricing)


def close_generator(generator):
    client = getattr(generator, "client", None)
    if callable(getattr(client, "close", None)):
        try:
            client.close()
        except Exception as exc:
            logger.warning("Provider client cleanup failed (%s)", type(exc).__name__)


@app.post("/api/llm/models")
def available_models(req: ProviderRequest):
    key, _ = provider_settings(req, require_model=False)
    if not key:
        raise HTTPException(422, "Enter an API key for the selected provider.")
    try:
        return {"models": list_models(req.provider, key, base_url=custom_base_url(req))}
    except Exception as exc:
        raise HTTPException(502, connection_error(exc)) from None


@app.post("/api/llm/test")
def test_provider(req: ProviderRequest):
    key, model = provider_settings(req)
    if not key:
        raise HTTPException(422, "Enter an API key for the selected provider.")
    generator = None
    try:
        generator = hosted_generator(req.provider, key, model, custom_base_url(req))
        generator._request([
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": 'Return only this JSON: {"ok": true}'},
        ])
        return {"ok": True, "provider": req.provider, "model": model,
                "message": "Model responded. This checks connectivity, not scientific answer quality."}
    except Exception as exc:
        raise HTTPException(502, connection_error(exc)) from None
    finally:
        if generator is not None:
            close_generator(generator)


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
    model: str | None = None
    run_id: str = ""
    workspace: str = "all"
    usage: dict[str, Any] = Field(default_factory=dict)


# --- Endpoints ---
@app.get("/api/health")
def health_check():
    get_pipeline()
    return {
        "status": "healthy",
        "collections": list(allowed_collections()),
        "indexed_genes": len(_GENE_INDEX),
        "glossary_terms": len(get_glossary()._entries),
        "total_chunks": sum(r.collection in allowed_collections() for r in get_pipeline().retriever.backend.records),
        "retrieval": _RETRIEVAL_STATUS,
    }


@app.post("/api/rag/query", response_model=QueryResponse)
def query_rag(req: QueryRequest):
    pipeline = get_pipeline()
    collections = tuple(
        ALL_COLLECTIONS
        if req.authorized_collections is None
        else req.authorized_collections
    )
    try:
        if set(collections) - set(ALL_COLLECTIONS):
            raise ValueError("Unknown authorized collection")
        request = RetrievalRequest(
            req.question, authorized_collections=tuple(c for c in collections if c in allowed_collections()), top_k=req.top_k
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    generator = OfflineEvidenceGenerator()
    initialization_failed = False
    primary = None
    key = req.api_key.get_secret_value().strip() if req.api_key else ""
    if key:
        key, model = provider_settings(req)
        base_url = custom_base_url(req)  # invalid URL -> 422, not a silent offline fallback
        try:
            primary = hosted_generator(req.provider, key, model, base_url)
            generator = FallbackGenerator(primary, OfflineEvidenceGenerator())
        except Exception as exc:
            logger.warning("Hosted provider initialization failed (%s)", type(exc).__name__)
            initialization_failed = True
    active_pipeline = RAGPipeline(pipeline.retriever, pipeline.context_builder, generator)
    start_time = time.perf_counter()
    try:
        run = active_pipeline.run(request)
    finally:
        if primary is not None:
            close_generator(primary)
    if initialization_failed or run.answer.diagnostics.get("fallback_from"):
        run.answer.provider = "offline_fallback"
        run.answer.diagnostics["fallback_from"] = req.provider
        if initialization_failed:
            run.answer.limitations.append("Hosted generation was unavailable; the answer uses local evidence excerpts.")
    run.retrieval.diagnostics["workspace"] = workspace_id.get()
    run.retrieval.diagnostics["index_metadata"] = getattr(pipeline.retriever.backend, "meta", {})
    # No request/API key or raw provider exception is serialized.
    RAGPipeline.save_run(run, PROJECT_ROOT / "artifacts/runs" / workspace_id.get())
    provider_name = run.answer.provider

    total_time = time.perf_counter() - start_time

    claims = [
        ClaimResponse(text=c.text, citations=c.citations) for c in run.answer.claims
    ]
    latencies = {**run.latency_s, "total_api": total_time}

    formatted_citations = []
    for c in run.answer.citations:
        if isinstance(c, dict):
            item = dict(c)
            item["id"] = item.get("chunk_id") or item.get("id", "source")
            item["title"] = item.get("source_name") or item.get("title") or item["id"]
            formatted_citations.append(item)
        else:
            formatted_citations.append(
                {"id": str(c), "title": str(c), "chunk_id": str(c)}
            )

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
        model=run.answer.diagnostics.get("model"),
        run_id=run.run_id,
        workspace=workspace_id.get(),
        usage=run.answer.diagnostics.get("usage", {"api_calls": 0, "estimated_cost_usd": 0.0}),
    )


@app.get("/api/evidence/{chunk_id:path}")
def get_evidence(chunk_id: str, corpus_version: str | None = None):
    """Return a corpus passage and its provenance for citation inspection."""
    for record in get_pipeline().retriever.backend.records:
        if record.chunk_id == chunk_id and record.collection in allowed_collections():
            if corpus_version and record.citation.get("corpus_version") != corpus_version:
                raise HTTPException(status_code=409, detail="The corpus version changed. Re-run the query to inspect current evidence.")
            return record.to_dict()
    raise HTTPException(status_code=404, detail="Evidence passage not found in corpus.")


@app.get("/api/genes")
def list_genes(q: Optional[str] = None):
    """List sample high-priority genes or search by symbol/alias query."""
    featured = [
        "PPARG",
        "TCF7L2",
        "ADCY5",
        "LPCAT2",
        "SLC30A8",
        "INS",
        "KCNJ11",
        "GCK",
        "HNF1A",
        "CDKAL1",
        "AKT1",
        "BAD",
        "CEBPA",
        "IRS1",
        "CD36",
        "LIPC",
    ]
    if q and q.strip():
        q_upper = q.strip().upper()
        matches = [g for g in _GENE_INDEX.keys() if g.startswith(q_upper)]
        if len(matches) < 15:
            matches += [
                g for g in _GENE_INDEX.keys() if q_upper in g and g not in matches
            ]
        selected = matches[:15]
    else:
        selected = featured

    out = []
    for g in selected:
        entry = _GENE_INDEX.get(g)
        if entry:
            out.append(
                {
                    "symbol": g,
                    "title": entry.get("title", f"Gene {g}"),
                    "metadata": entry.get("metadata", {}),
                    "has_common_evidence": g in _COMMON_ASSOC and "gene_association_common" in allowed_collections(),
                    "has_rare_evidence": g in _RARE_ASSOC and "gene_association_rare" in allowed_collections(),
                }
            )
    return {"genes": out, "total_indexed": len(_GENE_INDEX)}


@app.get("/api/genes/{symbol}")
def get_gene_details(symbol: str):
    sym = symbol.strip().upper()
    entry = _GENE_INDEX.get(sym)
    if entry is None:
        for candidate, record in _GENE_INDEX.items():
            metadata = record.get("metadata", {})
            identifiers = [
                *(metadata.get("alternative_names") or []),
                *(
                    metadata.get(key)
                    for key in (
                        "ensembl_gene_id",
                        "hgnc_id",
                        "entrezgene",
                        "uniprot_accession",
                    )
                ),
            ]
            if any(
                str(identifier).upper() == sym
                for identifier in identifiers
                if identifier is not None
            ):
                sym, entry = candidate, record
                break
    if not entry:
        raise HTTPException(
            status_code=404, detail=f"Gene {symbol} not found in approved corpus."
        )

    common = _COMMON_ASSOC.get(sym, []) if "gene_association_common" in allowed_collections() else []
    rare = _RARE_ASSOC.get(sym, []) if "gene_association_rare" in allowed_collections() else []

    common_bf = common[0].get("metadata", {}).get("bf_common") if common else None
    rare_bf = rare[0].get("metadata", {}).get("bf_rare") if rare else None
    huge_score = (
        float(common_bf) * float(rare_bf)
        if common_bf is not None and rare_bf is not None
        else None
    )

    phenotype_map: dict[str, dict[str, Any]] = {}
    for c in common:
        meta = c.get("metadata", {})
        pt = meta.get("phenotype", "2hrG")
        phenotype_map.setdefault(pt, {})["common_bf"] = meta.get("bf_common")
        phenotype_map[pt]["label"] = meta.get("phenotype_label", pt)
        phenotype_map[pt]["evidence_tier"] = meta.get("evidence_tier", "baseline")
        phenotype_map[pt]["has_causal"] = meta.get("has_causal_annotation", False)
        phenotype_map[pt]["causal_p"] = meta.get("pValueCausal")

    for r in rare:
        meta = r.get("metadata", {})
        pt = meta.get("phenotype", "2hrG")
        phenotype_map.setdefault(pt, {})["rare_bf"] = meta.get("bf_rare")
        phenotype_map[pt]["label"] = meta.get("phenotype_label", pt)
        phenotype_map[pt]["beta"] = meta.get("beta")
        phenotype_map[pt]["z"] = meta.get("z")
        phenotype_map[pt]["p_value"] = meta.get("pValue")

    assoc_summary = []
    for pt, vals in phenotype_map.items():
        c_bf = float(vals["common_bf"]) if vals.get("common_bf") is not None else None
        r_bf = float(vals["rare_bf"]) if vals.get("rare_bf") is not None else None
        assoc_summary.append(
            {
                "phenotype": pt,
                "label": vals.get("label", pt),
                "common_bf": c_bf,
                "rare_bf": r_bf,
                "huge_score": round(c_bf * r_bf, 2)
                if c_bf is not None and r_bf is not None
                else None,
                "beta": vals.get("beta"),
                "z": vals.get("z"),
                "p_value": vals.get("p_value")
                if vals.get("p_value") is not None
                else vals.get("causal_p"),
                "evidence_tier": vals.get("evidence_tier", "standard"),
            }
        )

    return {
        "symbol": sym,
        "title": entry.get("title"),
        "content": entry.get("content"),
        "metadata": entry.get("metadata"),
        "citation": entry.get("citation"),
        "huge_score": round(huge_score, 2) if huge_score is not None else None,
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
            label, _ = glossary.get_label(code)
            if (
                q_lower in code.lower()
                or q_lower in label.lower()
                or any(q_lower in a.lower() for a in glossary.get_aliases(code))
            ):
                items.append(
                    {
                        "code": code,
                        "label": label,
                        "category": glossary.get_category(code),
                        "group": glossary.get_group(code),
                        "aliases": glossary.get_aliases(code),
                    }
                )
                count += 1
                if count >= 25:
                    break
    else:
        priority = [
            "2hrG",
            "2hrI",
            "T2D",
            "BMI",
            "2hrFFA",
            "Alb_invn",
            "ALT",
            "AD",
            "FG",
            "FI",
            "HbA1c",
            "CAD",
            "HDL",
            "LDL",
            "TG",
        ]
        for code in priority:
            if code in glossary._entries:
                label, _ = glossary.get_label(code)
                items.append(
                    {
                        "code": code,
                        "label": label,
                        "category": glossary.get_category(code),
                        "group": glossary.get_group(code),
                        "aliases": glossary.get_aliases(code),
                    }
                )
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


# Structured data queries are kept separate from RAG text retrieval.
from analysis.routes import create_router

app.include_router(
    create_router(PROJECT_ROOT, get_pipeline, get_gene_details, get_glossary)
)
