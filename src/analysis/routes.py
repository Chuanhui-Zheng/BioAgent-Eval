from __future__ import annotations
import hashlib
import json
import math
import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Callable
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from analysis.data import DataStore, finite, provenance
from analysis.evaluation import evaluate_annotated
from analysis.client_example import load_example
from analysis.run_questions import answer_run_question
from retrieval.access import workspace_id, allowed_collections
from analysis.statistics import (
    enrichment,
    factorize,
    bayesian_factorize,
    parse_associations,
    parse_gmt,
    parse_matrix,
)


class MatrixRequest(BaseModel):
    matrix_csv: str | None = Field(None, max_length=8_000_000)
    w_csv: str | None = Field(None, max_length=8_000_000)
    h_csv: str | None = Field(None, max_length=8_000_000)
    associations_csv: str | None = Field(None, max_length=8_000_000)
    components: int = Field(2, ge=1, le=20)
    iterations: int = Field(500, ge=10, le=2000)
    seed: int = Field(46, ge=0, le=2**32 - 1)
    algorithm: str = Field("nmf", pattern="^(nmf|bayesian)$")


class RunQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    component: int = Field(0, ge=0)
    weight: float = Field(0, ge=0, allow_inf_nan=False)
    z_cutoff: float = Field(0, ge=0, allow_inf_nan=False)
    trait: str = Field("", max_length=200)


class EnrichmentRequest(BaseModel):
    genes: list[str] = Field(max_length=25000)
    background: list[str] = Field(max_length=25000)
    library: str | None = None
    gmt: str | None = Field(None, max_length=16_000_000)
    threshold: float = Field(0.05, gt=0, le=1)


class EvaluationRequest(BaseModel):
    benchmark_jsonl: str = Field(max_length=2_000_000)
    api_key: str | None = Field(None, max_length=1000)
    model: str = Field("gpt-4o-mini", max_length=100)


class CompareRequest(BaseModel):
    genes: list[str] = Field(min_length=1, max_length=20)
    phenotype: str = "2hrG"


def create_router(
    root: Path, pipeline: Callable, gene_details: Callable, glossary: Callable
):
    router = APIRouter(prefix="/api/analysis", tags=["Structured scientific analysis"])
    store = DataStore(root)
    runs = OrderedDict()
    lock = threading.RLock()
    library_dir = root / "data/reference/gene_sets"

    def libraries():
        return [
            {
                "name": p.stem,
                "terms": len(parse_gmt(p.read_text())),
                "provenance": json.loads(p.with_suffix(".provenance.json").read_text())
                if p.with_suffix(".provenance.json").exists()
                else provenance(p, root),
            }
            for p in sorted(library_dir.glob("*.gmt"))
        ]

    def library(name):
        choices = {p.stem: p for p in library_dir.glob("*.gmt")}
        if name not in choices:
            raise ValueError(
                "Select a locally available gene-set library or upload a GMT file."
            )
        file = choices[name]
        return parse_gmt(file.read_text()), provenance(file, root)

    def corpus_rows(collection):
        return [
            record
            for record in pipeline().retriever.backend.records
            if record.collection == collection and record.collection in allowed_collections()
        ]

    @router.get("/catalog")
    def catalog():
        return {
            **store.catalog(),
            "libraries": libraries(),
            "matrix_contract": "X: gene rows × phenotype columns; W: gene rows × component columns; H: component rows × phenotype columns. All factors nonnegative. Signed effects are uploaded separately.",
        }

    @router.get("/phenotypes")
    def phenotypes(q: str = "", limit: int = Query(2000, ge=1, le=2000)):
        terms = glossary()
        rows = []
        for code in terms._entries:
            label, _ = terms.get_label(code)
            aliases = terms.get_aliases(code)
            if (
                q
                and q.lower()
                not in (code + " " + label + " " + " ".join(aliases)).lower()
            ):
                continue
            rows.append(
                {
                    "code": code,
                    "label": label,
                    "category": terms.get_category(code),
                    "group": terms.get_group(code),
                    "aliases": aliases,
                }
            )
            if len(rows) >= limit:
                break
        return {"phenotypes": rows}

    @router.get("/expression/{gene}")
    def expression(gene: str, kind: str = Query("rna", pattern="^(rna|protein)$")):
        return store.expression(gene, kind)

    @router.get("/gwas")
    def gwas(
        phenotype: str = "2hrFFA",
        ancestry: str = Query("EU", pattern="^EU$"),
        threshold: float = Query(1, ge=0, le=1),
        chromosome: str | None = None,
        start: int | None = Query(None, ge=1),
        end: int | None = Query(None, ge=1),
        points: int = Query(2000, ge=100, le=10000),
    ):
        if start is not None and end is not None and start > end:
            raise HTTPException(422, "Region start must not exceed end.")
        if (start is not None or end is not None) and chromosome is None:
            raise HTTPException(422, "Specify a chromosome for interval queries.")
        return store.gwas(
            phenotype, ancestry, threshold, chromosome, start, end, points
        )

    @router.get("/references")
    def references(gene: str | None = None, variant: str | None = None):
        try:
            return store.references(gene, variant)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/annotations/{gene}")
    def annotations(gene: str):
        rows = []
        for available in libraries():
            terms, source = library(available["name"])
            rows.extend(
                {"term": term, "library": available["name"], "source": source}
                for term, genes in terms.items()
                if gene.upper() in genes
            )
        return {
            "gene": gene.upper(),
            "annotations": rows,
            "limitations": [
                "Gene-set membership is a reference annotation, not an enrichment p-value or causal conclusion."
            ],
        }

    @router.get("/phenotype-evidence/{phenotype}")
    def phenotype_evidence(phenotype: str):
        common = {
            r.metadata.get("gene"): r
            for r in corpus_rows("gene_association_common")
            if r.metadata.get("phenotype") == phenotype
        }
        rare = {
            r.metadata.get("gene"): r
            for r in corpus_rows("gene_association_rare")
            if r.metadata.get("phenotype") == phenotype
        }
        rows = []
        for gene in set(common) | set(rare):
            c = common.get(gene)
            r = rare.get(gene)
            cm = c.metadata if c else {}
            rm = r.metadata if r else {}
            cb = finite(cm.get("bf_common"))
            rb = finite(rm.get("bf_rare"))
            rows.append(
                {
                    "gene": gene,
                    "common_bf": cb,
                    "rare_bf": rb,
                    "huge_score": cb * rb
                    if cb is not None and rb is not None
                    else None,
                    "p_value": finite(rm.get("pValue")),
                    "beta": finite(rm.get("beta")),
                    "citations": [x.chunk_id for x in [c, r] if x],
                }
            )
        rows.sort(
            key=lambda r: (
                -(
                    r["huge_score"]
                    if r["huge_score"] is not None
                    else r["common_bf"] or r["rare_bf"] or 0
                )
            )
        )
        correlations = [
            {"chunk_id": r.chunk_id, "title": r.title, **r.metadata}
            for r in corpus_rows("ldsc_genetic_correlation")
            if phenotype == r.metadata.get("anchor_phenotype")
            or phenotype == r.metadata.get("other_phenotype")
            or phenotype == r.metadata.get("phenotype")
            or (phenotype == "2hrI" and "2hrI" in r.chunk_id)
        ]
        partitions = [
            {"chunk_id": r.chunk_id, **r.metadata}
            for r in corpus_rows("ldsc_partitioned_heritability")
            if r.metadata.get("phenotype") == phenotype
        ]
        partitions.sort(key=lambda r: r.get("pValue", 1))
        return {
            "phenotype": phenotype,
            "gene_total": len(rows),
            "genes": rows[:100],
            "correlations": correlations[:100],
            "partitioned": partitions[:100],
            "limitations": [
                "Combined scores require both supplied Bayes factors. These are association records, not causal evidence. Missing evidence is not a negative result."
            ],
        }

    @router.post("/compare")
    def compare(req: CompareRequest):
        dossiers = []
        for gene in dict.fromkeys(g.strip().upper() for g in req.genes):
            try:
                detail = gene_details(gene)
                associations = [
                    a for a in detail["associations"] if a["phenotype"] == req.phenotype
                ]
                dossiers.append(
                    {
                        "gene": gene,
                        "available": True,
                        "function": detail["content"],
                        "metadata": detail["metadata"],
                        "associations": [
                            {**row, "gene": detail["symbol"]} for row in associations
                        ],
                        "citation": detail["citation"],
                        "limitations": []
                        if associations
                        else [
                            f"No supplied gene-association record for {req.phenotype}."
                        ],
                    }
                )
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
                dossiers.append(
                    {
                        "gene": gene,
                        "available": False,
                        "associations": [],
                        "limitations": [
                            "Gene is absent from the approved annotation corpus."
                        ],
                    }
                )
        return {
            "phenotype": req.phenotype,
            "genes": dossiers,
            "limitations": [
                "Ranks are descriptive. No therapeutic mechanism or causal conclusion follows from beta sign or Bayes factors alone."
            ],
        }

    def save_run(genes, traits, w, h, associations, diagnostics, sources):
        if len(set(g.upper() for g in genes)) != len(genes):
            raise ValueError("Gene labels must be unique after case normalization.")
        run_id = uuid.uuid4().hex
        result = {
            "run_id": run_id,
            "workspace": workspace_id.get(),
            "genes": [g.upper() for g in genes],
            "traits": traits,
            "algorithm": diagnostics.get("method", "NMF"),
            "components": [f"C{i + 1}" for i in range(w.shape[1])],
            "w": w.tolist(),
            "h": h.tolist(),
            "associations": [
                {**row, "gene": row["gene"].upper()} for row in associations
            ],
            "diagnostics": diagnostics,
            "sources": sources,
            "limitations": [
                "Component labels are the highest-weight source traits, not validated biological mechanisms. Uploaded factors do not establish Bayesian inference. Directional effects describe association only."
            ],
        }
        with lock:
            runs[run_id] = result
            while len(runs) > 8:
                runs.popitem(last=False)
        return result

    @router.post("/matrix")
    def matrix(req: MatrixRequest):
        try:
            sources = {
                key: hashlib.sha256(value.encode()).hexdigest()
                for key, value in req.model_dump().items()
                if key.endswith("_csv") and value
            }
            if req.w_csv or req.h_csv:
                if not req.w_csv or not req.h_csv:
                    raise ValueError("Upload both W.csv and H.csv.")
                genes, components, w = parse_matrix(req.w_csv)
                h_components, traits, h = parse_matrix(req.h_csv)
                if set(components) != set(h_components):
                    raise ValueError("W columns and H row component labels must match.")
                h = h[[h_components.index(c) for c in components]]
                if np.any(w < 0) or np.any(h < 0):
                    raise ValueError("Factor matrices must be nonnegative.")
                if not np.any(w > 0) or not np.any(h > 0):
                    raise ValueError("Factors must contain positive values.")
                diagnostics = {
                    "method": "User-supplied factors (no Bayesian posterior validated)",
                    "original_components": components,
                }
                if req.matrix_csv:
                    xgenes, xtraits, x = parse_matrix(req.matrix_csv)
                    if set(xgenes) != set(genes) or set(xtraits) != set(traits):
                        raise ValueError(
                            "X labels must match W genes and H phenotypes."
                        )
                    x = x[[xgenes.index(g) for g in genes]][
                        :, [xtraits.index(t) for t in traits]
                    ]
                    diagnostics["relative_error"] = float(
                        np.linalg.norm(x - w @ h) / max(np.linalg.norm(x), 1e-12)
                    )
            elif req.matrix_csv:
                genes, traits, x = parse_matrix(req.matrix_csv)
                operation = (
                    bayesian_factorize if req.algorithm == "bayesian" else factorize
                )
                w, h, diagnostics = operation(
                    x, req.components, req.iterations, req.seed
                )
            else:
                raise ValueError("Upload matrix.csv, or W.csv and H.csv.")
            if w.size + h.size > 250000:
                raise ValueError("Factors exceed the 250,000-cell response limit.")
            associations = (
                parse_associations(req.associations_csv) if req.associations_csv else []
            )
            return save_run(genes, traits, w, h, associations, diagnostics, sources)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/matrix/client-example")
    def client_example():
        try:
            genes, traits, x, associations, sources = load_example(root)
            w, h, diagnostics = factorize(x, 2, 500, 46)
            diagnostics.update({"input": sources["transform"], "original_source_cluster": 0,
                                "client_example": True, "not_client_original_factors": True})
            result = save_run(genes, traits, w, h, associations, diagnostics, sources)
            result["limitations"].extend([
                sources["missing_input"], sources["selection"],
                "Exploratory NMF of absolute Z scores across four traits; signs are retained only in the effect records.",
                "Demo complete-case subset is not a genome-wide enrichment background; enrichment is conditional on this subset."
            ])
            return result
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/matrix/corpus")
    def corpus_matrix():
        common = {
            r.metadata["gene"]: r
            for r in corpus_rows("gene_association_common")
            if r.metadata.get("gene")
        }
        rare = {
            r.metadata["gene"]: r
            for r in corpus_rows("gene_association_rare")
            if r.metadata.get("gene")
        }
        genes = []
        values = []
        associations = []
        invalid = 0
        for gene in sorted(set(common) & set(rare)):
            cm = common[gene].metadata
            rm = rare[gene].metadata
            cb = finite(cm.get("bf_common"))
            rb = finite(rm.get("bf_rare"))
            if cb is None or rb is None or cb < 0 or rb < 0:
                continue
            genes.append(gene)
            values.append([math.log10(1 + cb) + math.log10(1 + rb)])
            beta = finite(rm.get("beta"))
            se = finite(rm.get("stdErr"))
            if beta is not None and se is not None and se > 0:
                associations.append(
                    {
                        "gene": gene,
                        "phenotype": "2hrG",
                        "beta": beta,
                        "z": beta / se,
                        "p_value": finite(rm.get("pValue")),
                        "direction": "positive association"
                        if beta > 0
                        else "negative association"
                        if beta < 0
                        else "zero association",
                        "chunk_id": rare[gene].chunk_id,
                    }
                )
            else:
                invalid += 1
        if not genes:
            raise HTTPException(
                404, "No overlapping common and rare records are available."
            )
        x = np.array(values)
        w, h, diagnostics = factorize(x, 1)
        diagnostics.update(
            {
                "input": "log10(1+common BF)+log10(1+rare BF), overlapping genes only",
                "trait_count": 1,
                "excluded_invalid_effect_rows": invalid,
                "note": "Single-trait baseline; upload a multi-trait matrix to discover multiple components.",
            }
        )
        return save_run(
            genes,
            ["2hrG"],
            w,
            h,
            associations,
            diagnostics,
            {
                "corpus_collections": [
                    "gene_association_common",
                    "gene_association_rare",
                ]
            },
        )

    @router.get("/runs/{run_id}/selection")
    def selection(
        run_id: str,
        component: int = Query(0, ge=0),
        weight: float = Query(0, ge=0),
        z_cutoff: float = Query(0, ge=0),
        trait: str = "",
    ):
        with lock:
            run = runs.get(run_id)
        if run is None or run.get("workspace") != workspace_id.get():
            raise HTTPException(
                404, "Analysis expired or server restarted; run it again."
            )
        if component >= len(run["components"]):
            raise HTTPException(422, "Component is outside the factor matrix.")
        w = np.asarray(run["w"])
        h = np.asarray(run["h"])
        weights = w[:, component]
        std = float(weights.std())
        mean = float(weights.mean())
        effects = {}
        for assoc in run["associations"]:
            if not trait or trait.lower() in assoc["phenotype"].lower():
                effects.setdefault(assoc["gene"], []).append(assoc)
        selected = []
        credible_low = run["diagnostics"].get("posterior_w_low")
        credible_high = run["diagnostics"].get("posterior_w_high")
        for i, gene in enumerate(run["genes"]):
            evidence = effects.get(gene, [])
            if weights[i] < weight:
                continue
            if trait and not evidence:
                continue
            if z_cutoff > 0 and not any(abs(a["z"]) >= z_cutoff for a in evidence):
                continue
            selected.append(
                {
                    "gene": gene,
                    "weight": float(weights[i]),
                    "weight_z": (float(weights[i]) - mean) / std if std > 0 else 0,
                    "effects": evidence,
                    "credible_low": credible_low[i][component]
                    if credible_low is not None
                    else None,
                    "credible_high": credible_high[i][component]
                    if credible_high is not None
                    else None,
                }
            )
        selected.sort(key=lambda r: (-r["weight"], r["gene"]))
        component_labels = [
            {
                "component": run["components"][c],
                "top_traits": [
                    {"trait": run["traits"][j], "weight": float(h[c, j])}
                    for j in np.argsort(h[c])[::-1][:5]
                ],
            }
            for c in range(h.shape[0])
        ]
        return {
            "run_id": run_id,
            "workspace": workspace_id.get(),
            "component": run["components"][component],
            "genes": selected,
            "total": len(selected),
            "background": run["genes"],
            "labels": component_labels,
            "limitations": run["limitations"],
        }

    @router.post("/runs/{run_id}/question")
    def question_about_run(run_id: str, req: RunQuestionRequest):
        with lock:
            run = runs.get(run_id)
        if run is None or run.get("workspace") != workspace_id.get():
            raise HTTPException(404, "Analysis expired or belongs to a different workspace.")
        selected = selection(run_id, req.component, req.weight, req.z_cutoff, req.trait)
        try:
            return answer_run_question(root, run, selected, req.model_dump(), pipeline())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/enrichment")
    def enrich(req: EnrichmentRequest):
        try:
            if req.gmt:
                terms = parse_gmt(req.gmt)
                source = {
                    "name": "Uploaded GMT",
                    "sha256": hashlib.sha256(req.gmt.encode()).hexdigest(),
                }
            else:
                terms, source = library(req.library)
            return {
                **enrichment(req.genes, req.background, terms, req.threshold),
                "source": source,
                "limitations": [
                    "Background is the measured gene universe. BH correction includes all testable library terms, including zero-overlap terms. Overrepresentation is hypothesis-generating, not causal or clinical evidence."
                ],
            }
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/evaluate")
    def evaluate(req: EvaluationRequest):
        try:
            active = pipeline()
            if req.api_key and req.api_key.strip():
                from generation.aihubmix import AIHubMixGenerator
                from generation.fallback import FallbackGenerator
                from generation.offline import OfflineEvidenceGenerator
                from rag.pipeline import RAGPipeline

                active = RAGPipeline(
                    active.retriever,
                    active.context_builder,
                    FallbackGenerator(
                        AIHubMixGenerator(api_key=req.api_key.strip(), model=req.model),
                        OfflineEvidenceGenerator(),
                    ),
                )
            return evaluate_annotated(active, req.benchmark_jsonl)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/templates/{kind}", response_class=PlainTextResponse)
    def template(kind: str):
        templates = {
            "matrix": "gene,TraitA,TraitB\nGENE_A,3,0\nGENE_B,0,3\nGENE_C,2,1\n",
            "w": "gene,C1,C2\nGENE_A,0.8,0.1\nGENE_B,0.1,0.8\nGENE_C,0.4,0.4\n",
            "h": "component,TraitA,TraitB\nC1,3,1\nC2,1,3\n",
            "associations": "gene,phenotype,beta,stdErr,pValue\nGENE_A,TraitA,0.6,0.1,0.000000002\nGENE_B,TraitB,-0.4,0.1,0.00006\n",
            "gmt": "ExampleSet\tsynthetic format example, not a biological reference\tGENE_A\tGENE_C\n",
        }
        templates["benchmark"] = (
            json.dumps(
                {
                    "question": "REPLACE WITH AN INDEPENDENT REVIEWER QUESTION",
                    "expected_status": "answer",
                    "gold_citations": ["REPLACE_WITH_SOURCE_CHUNK_ID"],
                    "required_facts": [],
                    "required_numbers": {},
                    "forbidden_phrases": [],
                }
            )
            + "\n"
        )
        if kind not in templates:
            raise HTTPException(404, "Unknown template")
        return PlainTextResponse(
            templates[kind],
            headers={
                "Content-Disposition": f'attachment; filename="{kind}.{"jsonl" if kind == "benchmark" else "gmt" if kind == "gmt" else "csv"}"'
            },
        )

    return router
