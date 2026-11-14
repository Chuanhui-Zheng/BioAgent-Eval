from __future__ import annotations
import hashlib
import json
import math
import time
from generation.numeric_validation import ALIASES, NUMBER
from retrieval.service import RetrievalRequest
from retrieval.router import SUPPORTED_COLLECTIONS
from analysis.support_judge import deterministic_grounding, summarise_support


def evaluate_annotated(pipeline, text: str, judge=None) -> dict:
    """Score against user-supplied independent annotations, without inventing gold labels.

    ``judge`` is an optional ``LLMSupportJudge``; every run also gets the
    deterministic claim-grounding check (numbers/identifiers vs cited passages).
    """
    items = []
    for line in text.splitlines():
        if line.strip():
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Benchmark must be JSONL with one valid object per line."
                ) from exc
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("question"), str)
                or item.get("expected_status") not in {"answer", "qualified", "refuse"}
                or not isinstance(item.get("gold_citations"), list)
                or not all(
                    isinstance(cid, str) for cid in item.get("gold_citations", [])
                )
            ):
                raise ValueError(
                    "Each question needs question, expected_status and gold_citations."
                )
            items.append(item)
    if not 1 <= len(items) <= 100:
        raise ValueError("Provide 1–100 independently annotated questions per batch.")
    rows = []
    for item in items:
        started = time.perf_counter()
        run = pipeline.run(
            RetrievalRequest(
                item["question"],
                authorized_collections=tuple(
                    item.get(
                        "authorized_collections",
                        tuple(SUPPORTED_COLLECTIONS),
                    )
                ),
            )
        )
        gold = set(item["gold_citations"])
        cited = {cid for c in run.answer.claims for cid in c.citations}
        retrieved = {r.chunk_id for r in run.retrieval.results}
        facts = item.get("required_facts", [])
        forbidden = item.get("forbidden_phrases", [])
        if (
            not isinstance(facts, list)
            or not all(isinstance(f, str) for f in facts)
            or not isinstance(forbidden, list)
            or not all(isinstance(f, str) for f in forbidden)
        ):
            raise ValueError(
                "required_facts and forbidden_phrases must be string lists."
            )
        missing = [f for f in facts if f.lower() not in run.answer.answer.lower()]
        prohibited = [f for f in forbidden if f.lower() in run.answer.answer.lower()]
        numbers = item.get("required_numbers", {})
        if not isinstance(numbers, dict):
            raise ValueError("required_numbers must map field names to numeric values.")
        observed = {}
        for match in NUMBER.finditer(run.answer.answer):
            observed.setdefault(
                ALIASES.get(match["field"].lower(), match["field"].lower()), []
            ).append(float(match["number"]))
        number_errors = []
        for field, value in numbers.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError("Required numeric values must be finite numbers.")
            if not any(
                math.isclose(value, n, rel_tol=5e-4, abs_tol=1e-300)
                for n in observed.get(ALIASES.get(field.lower(), field.lower()), [])
            ):
                number_errors.append(field)
        accepted = item.get("accepted_statuses") or [item["expected_status"]]
        groundings = deterministic_grounding(run.answer, run.context.passages)
        judgements = judge.judge(run.answer, run.context.passages) if judge is not None else None
        support = summarise_support(groundings, judgements)
        rows.append(
            {
                "query_id": item.get("query_id"),
                "query_type": item.get("query_type", "unspecified"),
                "question": item["question"],
                "annotation_origin": item.get("annotation_origin", "user-supplied; independence not verified"),
                "expected_status": item["expected_status"],
                "status": run.answer.status,
                "accepted_statuses": accepted,
                "status_correct": run.answer.status in accepted,
                "support": support,
                "gold_retrieval_hit": bool(gold & retrieved) if gold else None,
                "gold_citation_precision": len(gold & cited) / len(cited)
                if cited
                else (1 if not gold else 0),
                "gold_citation_recall": len(gold & cited) / len(gold)
                if gold
                else (1 if not cited else 0),
                "missing_required_facts": missing,
                "missing_or_wrong_numbers": number_errors,
                "prohibited_phrases": prohibited,
                "validation_errors": run.validation.errors,
                "answer": run.answer.to_dict(),
                "latency_s": time.perf_counter() - started,
                "provider": run.answer.provider,
                "usage": run.answer.diagnostics.get("usage", {"estimated_cost_usd": 0.0}),
                "fallback_used": bool(run.answer.diagnostics.get("fallback_from")),
                "human_review": {
                    "correctness": None,
                    "relevance": None,
                    "completeness": None,
                    "citation_support": None,
                    "notes": "",
                },
            }
        )
    return {
        "benchmark_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "questions": len(rows),
        "provider_mode": getattr(pipeline.generator, "provider", "unknown"),
        "annotation_origins": sorted({r["annotation_origin"] for r in rows}),
        "gold_retrieval_hit_rate": sum(r["gold_retrieval_hit"] for r in rows if r["gold_retrieval_hit"] is not None) / max(1, sum(r["gold_retrieval_hit"] is not None for r in rows)),
        "fallback_rate": sum(r["fallback_used"] for r in rows) / len(rows),
        "mean_latency_s": sum(r["latency_s"] for r in rows) / len(rows),
        "mean_input_tokens": _mean_usage(rows, "input_tokens"),
        "mean_output_tokens": _mean_usage(rows, "output_tokens"),
        "mean_total_tokens": _mean_usage(rows, "total_tokens"),
        "cost": {
            "estimated_usd": sum(r["usage"]["estimated_cost_usd"] for r in rows)
                if all(r["usage"].get("estimated_cost_usd") is not None for r in rows) else None,
            "unpriced_runs": sum(r["usage"].get("estimated_cost_usd") is None for r in rows),
        },
        "status_accuracy": sum(r["status_correct"] for r in rows) / len(rows),
        "gold_citation_precision": sum(r["gold_citation_precision"] for r in rows)
        / len(rows),
        "gold_citation_recall": sum(r["gold_citation_recall"] for r in rows)
        / len(rows),
        "numeric_policy_pass_rate": sum(not r["missing_or_wrong_numbers"] for r in rows)
        / len(rows),
        "fact_policy_pass_rate": sum(
            not r["missing_required_facts"] and not r["prohibited_phrases"]
            for r in rows
        )
        / len(rows),
        "claim_grounding_rate": _ratio(sum(r["support"]["grounded_claims"] for r in rows),
                                       sum(r["support"]["claims"] for r in rows)),
        "llm_judge": _judge_summary(rows, judge),
        "retrieval_method": getattr(getattr(pipeline, "retriever", None), "method", None),
        "by_query_type": _by_type(rows),
        "results": rows,
        "limitations": [
            "Gold labels must be supplied independently by a reviewer; this tool does not establish their quality. Exact required-fact matching is a deterministic contract, not an entailment judge. Claim grounding checks numbers and identifiers only; LLM-judge labels are an automated estimate. Human correctness and citation-support review remains pending until the exported rubric is completed."
        ],
    }


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _mean_usage(rows, field):
    values = []
    for row in rows:
        usage = row["usage"]
        value = usage.get(field)
        if field == "total_tokens" and value is None:
            input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
            if isinstance(input_tokens, (int, float)) and isinstance(output_tokens, (int, float)):
                value = input_tokens + output_tokens
        if isinstance(value, (int, float)):
            values.append(value)
    return sum(values) / len(values) if values else None


def _judge_summary(rows, judge):
    if judge is None:
        return None
    counts = {}
    for row in rows:
        for label, value in row["support"].get("judge_labels", {}).items():
            counts[label] = counts.get(label, 0) + value
    judged = sum(v for k, v in counts.items() if k != "judge_error")
    return {
        "judge": judge.description,
        "labels": counts,
        "supported_rate": _ratio(counts.get("supported", 0), judged),
        "supported_or_partial_rate": _ratio(counts.get("supported", 0) + counts.get("partial", 0), judged),
        "contradicted_claims": counts.get("contradicted", 0),
        "judge_errors": counts.get("judge_error", 0),
    }


def _by_type(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["query_type"], []).append(row)
    summary = {}
    for name, items in sorted(groups.items()):
        claims = sum(r["support"]["claims"] for r in items)
        summary[name] = {
            "n": len(items),
            "status_accuracy": sum(r["status_correct"] for r in items) / len(items),
            "gold_citation_recall": sum(r["gold_citation_recall"] for r in items) / len(items),
            "gold_citation_precision": sum(r["gold_citation_precision"] for r in items) / len(items),
            "numeric_policy_pass_rate": sum(not r["missing_or_wrong_numbers"] for r in items) / len(items),
            "fact_policy_pass_rate": sum(not r["missing_required_facts"] and not r["prohibited_phrases"]
                                         for r in items) / len(items),
            "claim_grounding_rate": _ratio(sum(r["support"]["grounded_claims"] for r in items), claims),
        }
    return summary
