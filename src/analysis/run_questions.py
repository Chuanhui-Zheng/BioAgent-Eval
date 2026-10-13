"""Extractive answers over a server-owned analysis snapshot and approved corpus."""
from dataclasses import asdict
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from augmentation.schema import ContextPackage, EvidencePassage
from generation.schema import Claim, GeneratedAnswer
from generation.validator import validate_answer
from retrieval.access import allowed_collections
from retrieval.service import RetrievalRequest


def answer_run_question(root, run, selected, request, pipeline):
    question = request["question"].strip()
    filters = {k: request[k] for k in ("component", "weight", "z_cutoff", "trait")}
    snapshot = {"analysis_run_id": run["run_id"], "workspace": run["workspace"],
                "filters": filters, "selection": selected, "sources": run["sources"]}
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    claims, citations, passages = [], [], []
    limits = list(run["limitations"])
    limits.append("Local extractive analysis explanation, not an LLM-generated mechanism or semantic entailment assessment.")
    def add(text, kind, evidence):
        cid = f"analysis:{run['run_id']}:{digest[:12]}:{len(claims)}"
        citation = {"id": cid, "chunk_id": cid, "title": kind,
                    "source_name": kind, "analysis_run_id": run["run_id"],
                    "snapshot_sha256": digest, "content": text, "evidence": evidence,
                    "sources": run["sources"]}
        claims.append(Claim(text, [cid]))
        citations.append(citation)
        passages.append(EvidencePassage(cid, "analysis_run", len(passages)+1, 1, kind,
                                        text, {"evidence": evidence}, citation))
    # This endpoint only explains the actual run, never generates clinical claims.
    unsupported = bool(re.search(r"cure|dosage|prescrib|agonist|antagonist|治疗|剂量|激动剂|拮抗剂", question, re.I))
    intent = bool(re.search(r"why|select|filter|summari|explain|evidence|function|mechanism|为什么|筛选|解释|总结|证据|功能|机制", question, re.I))
    named = [g for g in run["genes"] if re.search(r"(?<![A-Za-z0-9])"+re.escape(g)+r"(?![A-Za-z0-9])", question, re.I)]
    if unsupported or not (intent or named):
        limits.append("Ask about selection, source effects or reference gene function. Treatment and causal conclusions are unsupported.")
    else:
        add(f"Analysis {run['run_id']} selects {selected['total']} of {len(run['genes'])} measured genes in {selected['component']}. "
            f"Filters: W >= {filters['weight']:g}; absolute association Z >= {filters['z_cutoff']:g}; "
            f"trait substring = {filters['trait'] or '(all)'}. "
            "W is a computed factor weight, not an effect size or a causal probability.",
            "Computed selection snapshot", {"filters": filters, "total": selected["total"], "diagnostics": run["diagnostics"]})
        by_gene = {g["gene"]: g for g in selected["genes"]}
        targets = named[:3] if named else [g["gene"] for g in selected["genes"][:3]]
        if len(named) > 3 or (not named and selected["total"] > 3):
            limits.append("Detailed explanation is limited to three genes; the full selection is in the exported dossier.")
        for gene in targets:
            row = by_gene.get(gene)
            if row is None:
                idx = run["genes"].index(gene)
                weight = run["w"][idx][filters["component"]]
                effects = [a for a in run["associations"] if a["gene"] == gene and
                           (not filters["trait"] or filters["trait"].lower() in a["phenotype"].lower())]
                reasons = []
                if weight < filters["weight"]: reasons.append("W is below the selected threshold")
                if filters["trait"] and not effects: reasons.append("no supplied effect matches the trait filter")
                if filters["z_cutoff"] > 0 and not any(abs(a["z"]) >= filters["z_cutoff"] for a in effects):
                    reasons.append("no matching supplied effect meets the absolute Z threshold")
                add(f"{gene} is not selected: {'; '.join(reasons)}.", "Computed exclusion", {"gene": gene, "weight": weight, "effects": effects})
                continue
            add(f"{gene} is selected with computed W = {row['weight']:.8g}. It meets the current filters.",
                "Computed component weight", row)
            for effect in sorted(row["effects"], key=lambda a: (-abs(a["z"]), a["phenotype"]))[:3]:
                add(f"Source effect for {gene} / {effect['phenotype']}: beta = {effect['beta']:.8g}; "
                    f"association Z = {effect['z']:.8g}. Direction: {effect['direction']}. "
                    "This is association evidence, not a therapeutic mechanism.",
                    "Source association record", effect)
            # Reference evidence is explicitly separate from the selection calculation.
            ref = pipeline.run(RetrievalRequest(f"What is the function of {gene}?",
                authorized_collections=tuple(c for c in ("gene_info",) if c in allowed_collections()), top_k=1))
            if ref.validation.valid and ref.answer.claims:
                for claim in ref.answer.claims[:1]:
                    excerpt = re.split(r"(?<=[.!?])\s+", claim.text)[0]
                    claims.append(Claim("Reference gene function: " + excerpt, claim.citations))
                for citation in ref.answer.citations:
                    citations.append({**citation, "id": citation.get("chunk_id"), "title": "Approved corpus gene function",
                        "content": next((p.content for p in ref.context.passages if p.chunk_id == citation.get("chunk_id")), "")})
                passages.extend(ref.context.passages)
            else:
                limits.append(f"No gene-function excerpt available for {gene} in this workspace.")
    registry = {c["chunk_id"]: c for c in citations}
    context = ContextPackage(question, ["analysis_run", *allowed_collections()],
        ["analysis_run", "gene_info"], "analysis_snapshot_and_corpus", passages, registry,
        "qualified" if claims else "refuse", limits, 0, 12000)
    answer = GeneratedAnswer(status="qualified" if claims else "refuse",
        answer="\n\n".join(c.text for c in claims) if claims else "I cannot answer this question from the authorized approved corpus.",
        claims=claims, citations=citations, limitations=limits, provider="analysis_extracts_and_corpus")
    validation = validate_answer(answer, context)
    if not validation.valid:
        raise ValueError("Analysis explanation failed evidence validation: " + "; ".join(validation.errors))
    response = {**asdict(answer), "analysis_run_id": run["run_id"], "query_run_id": uuid.uuid4().hex,
        "snapshot_sha256": digest, "filters": filters, "workspace": run["workspace"],
        "validation": asdict(validation), "usage": {"api_calls": 0, "estimated_cost_usd": 0.0},
        "created_at": datetime.now(timezone.utc).isoformat()}
    folder = root / "artifacts/runs" / run["workspace"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"analysis-{response['query_run_id']}.json").write_text(json.dumps(
        {"response": response, "question": question, "snapshot": snapshot}, indent=2) + "\n")
    return response
