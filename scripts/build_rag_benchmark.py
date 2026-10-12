from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/evaluation/retrieval_test.jsonl"
OUTPUT = ROOT / "data/evaluation/rag_e2e.jsonl"


def required_fields(query: str) -> list[str]:
    q = query.lower()
    fields: list[str] = []
    if "p-value" in q or "p value" in q:
        fields.append("pValue_or_mixed_pvalue")
    if "bayes factor" in q:
        fields.append("bf_common_or_bf_rare")
    if "function" in q or "role" in q:
        fields.append("approved_function_text")
    if "correlation" in q or "ldsc" in q:
        fields.append("mixed_rg_and_mixed_pvalue")
    return fields


def main() -> int:
    rows = []
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        allowed = [
            x["chunk_id"]
            for x in item.get("relevance_judgments", [])
            if int(x.get("grade", 0)) == 2
        ]
        item["rag_expectation"] = {
            "expected_status": "answer_or_qualified" if item["answerable"] else "refuse",
            "allowed_citation_chunk_ids": allowed,
            "required_fact_fields": required_fields(item["query"]),
            "prohibited_claims": [
                "individual medical diagnosis",
                "association proves causality",
                "citation outside supplied context",
            ],
        }
        rows.append(item)
    OUTPUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} RAG benchmark rows -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
