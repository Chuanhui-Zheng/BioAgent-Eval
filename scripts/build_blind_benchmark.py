"""Build the frozen blind end-to-end benchmark (v1, 40 questions).

Questions are written from fixed templates and labelled directly from source
records (chunk metadata), so gold citations and required numbers are exact.
Entities used by ANY existing benchmark (dev, test, comparison, regression,
manual review) are excluded, the question wording is new, and nothing in this
file is used for tuning: scripts/tune_retrieval.py refuses blind paths.

Independence caveat: the labels are programmatic, not written by an
independent human annotator. ``reports/blind_v1/label_review_sheet.csv`` lets a
team member who did not tune the system verify or correct every label; record
their decision in ``annotation_origin`` before treating results as final.

Outputs
  data/evaluation/blind/blind_e2e_v1.jsonl   questions + labels (one JSON per line)
  data/evaluation/blind/blind_e2e_v1.manifest.json   frozen SHA-256, counts, seed
  reports/blind_v1/label_review_sheet.csv     reviewer checklist
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "artifacts" / "chunks"
EVAL = ROOT / "data" / "evaluation"
OUT_DIR = EVAL / "blind"
OUTPUT = OUT_DIR / "blind_e2e_v1.jsonl"
MANIFEST = OUT_DIR / "blind_e2e_v1.manifest.json"
REVIEW = ROOT / "reports" / "blind_v1" / "label_review_sheet.csv"
SEED = 20261021
ORIGIN = "programmatic_from_source_records_v1; independent human verification pending"
FORBIDDEN = ["proves causality", "causes type 2 diabetes", "recommended dose", "should be prescribed"]
ANSWERED = ["answer", "qualified"]


def load(name: str) -> list[dict]:
    with (CHUNKS / name).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def used_by_existing_benchmarks() -> tuple[set[str], set[str]]:
    """Chunk ids and gene symbols that appear in any earlier benchmark file."""
    chunk_ids: set[str] = set()
    for path in EVAL.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            chunk_ids.update(row.get("assessed_chunk_ids", []))
            chunk_ids.update(item["chunk_id"] for item in row.get("relevance_judgments", []))
            chunk_ids.update(row.get("gold_citations", []))
            for value in row.values():
                if isinstance(value, str):
                    chunk_ids.update(re.findall(r"\b(?:gene|gtex|wes|gassoc_\w+|ldsc\w*|clumped):[^\s\"',]+", value))
    genes = set()
    for cid in chunk_ids:
        parts = cid.split(":")
        if parts[0] in {"gene", "gtex"} and len(parts) > 1:
            genes.add(parts[1])
        elif parts[0] in {"gassoc_common", "gassoc_rare", "wes"} and len(parts) > 2:
            genes.add(parts[2])
    return chunk_ids, genes


def example(qid, question, qtype, expected, gold, collections, *, facts=(), numbers=None, related=(), note=""):
    return {
        "query_id": qid,
        "question": question,
        "query": question,
        "query_type": qtype,
        "expected_status": expected[0],
        "accepted_statuses": list(expected),
        "answerable": expected != ["refuse"],
        "gold_citations": list(gold),
        "target_collections": list(collections),
        "relevance_judgments": [{"chunk_id": cid, "grade": 2} for cid in gold]
        + [{"chunk_id": cid, "grade": 1} for cid in related],
        "assessed_chunk_ids": list(gold) + list(related),
        "required_facts": list(facts),
        "required_numbers": dict(numbers or {}),
        "forbidden_phrases": FORBIDDEN,
        "annotation_origin": ORIGIN,
        "split": "blind_test",
        "notes": note,
    }


def words(value: str) -> str:
    return value.replace("_", " ")


def main() -> int:
    rng = random.Random(SEED)
    used_ids, used_genes = used_by_existing_benchmarks()

    genes = [c for c in load("gene_info.chunks.jsonl") if c["metadata"]["gene_symbol"] not in used_genes]
    common = [c for c in load("gene_association_common_2hrG.chunks.jsonl") if c["metadata"]["gene"] not in used_genes]
    rare = [c for c in load("gene_association_rare_2hrG.chunks.jsonl") if c["metadata"]["gene"] not in used_genes]
    ldsc = [c for c in load("ldsc_2hrI.chunks.jsonl") if c["chunk_id"] not in used_ids]
    partitioned = [c for c in load("ldsc_partitioned_2hrG.chunks.jsonl") if c["chunk_id"] not in used_ids]
    wes = [c for c in load("wes_2hrG.chunks.jsonl")
           if c["metadata"].get("record_kind") == "gene_summary" and c["metadata"]["gene"] not in used_genes]
    gtex = [c for c in load("gtex_tissue_expression.chunks.jsonl") if c["metadata"]["gene_symbol"] not in used_genes]
    taken: set[str] = set()

    def pick(pool, n, predicate=lambda c: True, key=lambda c: c["chunk_id"]):
        candidates = sorted((c for c in pool if predicate(c) and key(c) not in taken), key=lambda c: c["chunk_id"])
        chosen = rng.sample(candidates, n)
        taken.update(key(c) for c in chosen)
        return chosen

    rows: list[dict] = []
    n = lambda: f"blind-{len(rows) + 1:03d}"  # noqa: E731

    gene_key = lambda c: c["metadata"].get("gene_symbol")  # noqa: E731
    function_templates = [
        "Summarise the biological function recorded for {g}.",
        "What role does the gene {g} play according to the approved gene annotations?",
        "Describe what is known about the function of {g} in the corpus.",
        "What does the approved corpus say {g} does?",
        "Give a short functional description of {g}.",
    ]
    named = lambda c: c["metadata"]["has_function_summary"] and re.fullmatch(r"[A-Z][A-Z0-9]{2,9}", c["metadata"]["gene_symbol"])  # noqa: E731
    for template, chunk in zip(function_templates, pick(genes, 5, named, gene_key)):
        g = chunk["metadata"]["gene_symbol"]
        rows.append(example(n(), template.format(g=g), "gene_function", ANSWERED, [chunk["chunk_id"]], ["gene_info"],
                            facts=[g], note="Function line of the gene annotation."))

    located = lambda c: named(c) and c["metadata"].get("ensembl_gene_id") and str(c["metadata"].get("chromosome", "")).isdigit()  # noqa: E731
    for template, chunk in zip([
        "Where is {g} located in the genome, and what is its Ensembl identifier?",
        "Which chromosome carries {g} and what are its genomic coordinates?",
        "What database identifiers are listed for {g}?",
    ], pick(genes, 3, located, gene_key)):
        m = chunk["metadata"]
        facts = [m["ensembl_gene_id"]] if "identifier" in template or "Ensembl" in template else [f"chr{m['chromosome']}"]
        rows.append(example(n(), template.format(g=m["gene_symbol"]), "gene_location", ANSWERED, [chunk["chunk_id"]],
                            ["gene_info"], facts=facts, note="Location/identifier fields of the gene annotation."))

    # Only 9 genes have bf_common > 1 and existing benchmarks already use them.
    strong_common = lambda c: c["metadata"].get("bf_common") is not None  # noqa: E731
    for template, chunk in zip([
        "What common-variant Bayes factor links {g} to 2-hour glucose?",
        "How strong is the common-variant (HuGE) evidence connecting {g} with 2hrG?",
        "Report bf_common for {g} and the 2-hour glucose phenotype.",
        "What evidence tier is assigned to {g} for common-variant association with 2-hour glucose?",
    ], pick(common, 4, strong_common, lambda c: c["metadata"]["gene"])):
        m = chunk["metadata"]
        facts = [m["evidence_tier"]] if "tier" in template else []
        rows.append(example(n(), template.format(g=m["gene"]), "common_association", ANSWERED, [chunk["chunk_id"]],
                            ["gene_association_common"], facts=facts, numbers={"bf_common": m["bf_common"]}))

    for index, (template, chunk) in enumerate(zip([
        "Is there rare-variant evidence that {g} is associated with 2-hour glucose? Give the p-value.",
        "What rare-variant gene-based p-value and beta are reported for {g} and 2hrG?",
        "Report the rare-variant association statistics of {g} for 2-hour glucose.",
        "How significant is the rare-variant burden association between {g} and 2hrG?",
    ], pick(rare, 2, lambda c: c["metadata"]["is_significant"], lambda c: c["metadata"]["gene"])
       + pick(rare, 2, lambda c: not c["metadata"]["is_significant"], lambda c: c["metadata"]["gene"]))):
        m = chunk["metadata"]
        numbers = {"pValue": m["pValue"]} if index in (0, 3) else {"pValue": m["pValue"], "beta": m["beta"]}
        rows.append(example(n(), template.format(g=m["gene"]), "rare_association", ANSWERED, [chunk["chunk_id"]],
                            ["gene_association_rare"], numbers=numbers))

    for template, chunk in zip([
        "What is the LDSC genetic correlation between 2-hour insulin and {o}?",
        "Is 2hrI genetically correlated with {o}? Report rg.",
        "Give the Mixed-ancestry rg and p-value for 2-hour insulin versus {o}.",
    ], pick(ldsc, 3, lambda c: c["metadata"].get("mixed_rg") is not None)):
        m = chunk["metadata"]
        rows.append(example(n(), template.format(o=m["other_phenotype_label"]), "ldsc_correlation", ANSWERED,
                            [chunk["chunk_id"]], ["ldsc_genetic_correlation"], numbers={"rg": m["mixed_rg"]}))

    for template, chunk in zip([
        "What partitioned-heritability enrichment does 2hrG show for {a} in {t} ({b}) for ancestry {anc}?",
        "Report enrichment_beta for 2-hour glucose, annotation {a}, tissue {t}, biosample {b}, ancestry code {anc}.",
        "How enriched is 2-hour glucose heritability in {a} regions of {t} ({b}) in the {anc} analysis?",
        "Give the LDSC partitioned heritability h2_beta for 2hrG in {t}, {a}, biosample {b}, ancestry {anc}.",
    ], pick(partitioned, 4, lambda c: c["metadata"].get("biosample"))):
        m = chunk["metadata"]
        field = "h2_beta" if "h2_beta" in template else "enrichment_beta"
        rows.append(example(n(), template.format(a=words(m["annotation"]), t=words(m["tissue"]), b=words(m["biosample"]),
                                                 anc=m["ancestry"]),
                            "ldsc_partitioned_heritability", ANSWERED, [chunk["chunk_id"]],
                            ["ldsc_partitioned_heritability"], numbers={field: m[field]}))

    for template, chunk in zip([
        "What top-level WES association p-value is reported for {g} with 2-hour glucose?",
        "Summarise the whole-exome sequencing evidence for {g} and 2hrG.",
        "Which WES masks were supplied for {g} and 2-hour glucose?",
        "Report the WES gene-level beta for {g} on 2hrG.",
    ], pick(wes, 4, lambda c: c["metadata"].get("masks_status") == "provided", lambda c: c["metadata"]["gene"])):
        m = chunk["metadata"]
        numbers = {"beta": m["raw_parent"]["beta"]} if "beta" in template else (
            {"pValue": m["raw_parent"]["pValue"]} if "p-value" in template else {})
        facts = m["mask_labels"][:2] if "masks" in template else []
        related = [m["related_baseline_chunk_id"]] if m.get("related_baseline_chunk_id") else []
        rows.append(example(n(), template.format(g=m["gene"]), "gene_association_wes", ANSWERED, [chunk["chunk_id"]],
                            ["gene_association_wes"], facts=facts, numbers=numbers, related=related))

    has_rna = lambda c: c["metadata"].get("expression", {}).get("rna")  # noqa: E731
    for template, chunk in zip([
        "In which tissues is {g} RNA expression highest in the supplied GTEx data?",
        "Where is {g} most highly expressed across GTEx tissues?",
        "Which tissue shows the top RNA expression of {g}?",
    ], pick(gtex, 3, has_rna, lambda c: c["metadata"]["gene_symbol"])):
        g = chunk["metadata"]["gene_symbol"]
        top = max(chunk["metadata"]["expression"]["rna"], key=lambda item: item["median"])["tissue"]
        rows.append(example(n(), template.format(g=g), "tissue_expression", ANSWERED, [chunk["chunk_id"]],
                            ["gtex_tissue_expression"], facts=[top], note="Highest RNA median tissue."))

    pair_genes = pick(genes, 4, named, gene_key)
    for (template, first, second) in [
        ("Compare the recorded functions of {a} and {b}.", pair_genes[0], pair_genes[1]),
        ("How do the gene functions of {a} and {b} differ?", pair_genes[2], pair_genes[3]),
    ]:
        a, b = first["metadata"]["gene_symbol"], second["metadata"]["gene_symbol"]
        rows.append(example(n(), template.format(a=a, b=b), "comparison", ANSWERED,
                            [first["chunk_id"], second["chunk_id"]], ["gene_info"], facts=[a, b]))
    rare_pair = pick(rare, 2, lambda c: True, lambda c: c["metadata"]["gene"])
    common_pair = pick(common, 2, strong_common, lambda c: c["metadata"]["gene"])
    for template, pair, collection in [
        ("Compare the rare-variant association evidence for {a} and {b} with 2-hour glucose.", rare_pair,
         "gene_association_rare"),
        ("Which has stronger common-variant support for 2hrG, {a} or {b}?", common_pair, "gene_association_common"),
    ]:
        a, b = pair[0]["metadata"]["gene"], pair[1]["metadata"]["gene"]
        rows.append(example(n(), template.format(a=a, b=b), "comparison", ANSWERED,
                            [pair[0]["chunk_id"], pair[1]["chunk_id"]], [collection], facts=[a, b]))

    for question, note in [
        ("What is the function of the gene QZT7X9?", "Fabricated gene symbol absent from the corpus."),
        ("What rare-variant association does KRTAP99-1 have with 2-hour glucose?", "Fabricated gene symbol."),
        ("What metformin dose should a patient with impaired glucose tolerance take?", "Clinical dosing is out of scope."),
        ("Which drug should be prescribed to a person carrying a risk allele for 2-hour glucose?",
         "Treatment recommendation is out of scope."),
        ("What is the genetic correlation between 2-hour insulin and adult height?", "Trait pair absent from LDSC data."),
        ("What is the rare-variant association of the gene with LDL cholesterol in East Asian children?",
         "Unspecified gene and unsupported phenotype/population."),
    ]:
        rows.append(example(n(), question, "unanswerable", ["refuse"], [], [], note=note))

    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists() and "--force" not in sys.argv:
        existing = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
        if existing != hashlib.sha256(payload.encode()).hexdigest():
            raise SystemExit(f"{OUTPUT} is frozen and differs from a rebuild; pass --force only for a new version")
    OUTPUT.write_text(payload, encoding="utf-8")
    manifest = {
        "benchmark": OUTPUT.relative_to(ROOT).as_posix(),
        "version": "blind_e2e_v1",
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "questions": len(rows),
        "by_type": dict(Counter(row["query_type"] for row in rows)),
        "seed": SEED,
        "excluded_existing_chunk_ids": len(used_ids),
        "excluded_existing_genes": len(used_genes),
        "annotation_origin": ORIGIN,
        "policy": "Never use for tuning, prompt design or threshold selection. Report once per frozen system version.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["query_id", "query_type", "question", "expected_status", "gold_citations", "required_facts",
                         "required_numbers", "reviewer_label_correct(Y/N)", "reviewer_correction", "reviewer_initials"])
        for row in rows:
            writer.writerow([row["query_id"], row["query_type"], row["question"], row["expected_status"],
                             " ".join(row["gold_citations"]), "; ".join(row["required_facts"]),
                             json.dumps(row["required_numbers"]), "", "", ""])
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
