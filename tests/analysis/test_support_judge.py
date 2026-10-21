from __future__ import annotations

import json
from types import SimpleNamespace

from analysis.support_judge import LLMSupportJudge, deterministic_grounding, summarise_support
from generation.schema import Claim, GeneratedAnswer


def passage(chunk_id, content, metadata=None, title="T"):
    return SimpleNamespace(chunk_id=chunk_id, content=content, metadata=metadata or {}, title=title)


def answer(*claims):
    return GeneratedAnswer("answer", "\n\n".join(c.text for c in claims), list(claims), [], [])


PASSAGES = [
    passage("gassoc_rare:2hrG:NIPA2", "Rare-variant evidence NIPA2: p-value=0.0277, beta=0.41",
            {"gene": "NIPA2", "pValue": 0.02767741, "beta": 0.41}),
    passage("gene:NFIC", "Gene: NFIC\nEnsembl ENSG00000141905, chr19:3359561-3469217"),
]


def test_grounded_claim_with_rounded_number_and_identifier():
    result = deterministic_grounding(answer(Claim("NIPA2 has rare-variant p=0.02768 and beta=0.41.",
                                                  ["gassoc_rare:2hrG:NIPA2"])), PASSAGES)
    assert result[0].grounded


def test_fabricated_number_and_wrong_entity_are_flagged():
    result = deterministic_grounding(answer(Claim("PPARG has p=0.5 for 2hrG.", ["gassoc_rare:2hrG:NIPA2"])), PASSAGES)
    assert result[0].unsupported_numbers == [0.5]
    assert result[0].unsupported_entities == ["PPARG"]


def test_numbers_must_come_from_the_claims_own_citation():
    claim = Claim("NFIC location is chr19 with beta=0.41.", ["gene:NFIC"])
    assert deterministic_grounding(answer(claim), PASSAGES)[0].unsupported_numbers == [0.41]


def test_identifiers_are_checked_as_entities_not_numbers():
    claim = Claim("NFIC has Ensembl ID ENSG00000141905 on chr19:3359561-3469217.", ["gene:NFIC"])
    assert deterministic_grounding(answer(claim), PASSAGES)[0].grounded


class FakeJudgeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.messages = []

    def complete(self, messages, max_tokens=None):
        self.messages.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def describe(self):
        return {"provider": "fake"}


def test_llm_judge_labels_and_errors_are_never_support():
    llm = FakeJudgeLLM([json.dumps({"label": "supported", "reason": "ok"}),
                        "<think>x</think>{\"label\": \"contradicted\", \"reason\": \"beta differs\"}",
                        RuntimeError("timeout")])
    claims = [Claim("a", ["gene:NFIC"]), Claim("b", ["gene:NFIC"]), Claim("c", ["gene:NFIC"]),
              Claim("d", ["missing"])]
    judgements = LLMSupportJudge(llm).judge(answer(*claims), PASSAGES)
    assert [j.label for j in judgements] == ["supported", "contradicted", "judge_error", "unsupported"]
    assert len(llm.messages) == 3  # no API call for a claim whose citation is not in context
    evidence = json.loads(llm.messages[0][1]["content"])["evidence"]
    assert [e["chunk_id"] for e in evidence] == ["gene:NFIC"]
    summary = summarise_support(deterministic_grounding(answer(*claims), PASSAGES), judgements)
    assert summary["judge_labels"]["supported"] == 1 and summary["judge_labels"]["judge_error"] == 1
