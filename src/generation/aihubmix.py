from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from augmentation.schema import ContextPackage
from generation.schema import Claim, GeneratedAnswer


class AIHubMixGenerationError(RuntimeError):
    """Raised when the hosted provider cannot return a valid grounded answer."""


class _AIHubMixQuotaError(AIHubMixGenerationError):
    """Raised when AIHubMix returns an account quota notice as model content."""


def _json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        # Some reasoning models prepend <think> blocks or explanatory text even
        # when asked for JSON only. Extract the first object that matches the
        # answer schema instead of rejecting an otherwise usable response.
        decoder = json.JSONDecoder()
        value = None
        required_keys = {"status", "answer", "claims"}
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and required_keys.issubset(candidate):
                value = candidate
                break
        if value is None:
            raise AIHubMixGenerationError("provider returned invalid JSON")
    if not isinstance(value, dict):
        raise AIHubMixGenerationError("provider response must be a JSON object")
    return value


def _parse_answer(payload: dict[str, Any], context: ContextPackage, model: str) -> GeneratedAnswer:
    status = payload.get("status")
    if status not in {"answer", "qualified", "refuse"}:
        raise AIHubMixGenerationError("provider returned an invalid answer status")
    answer_text = payload.get("answer")
    if not isinstance(answer_text, str) or not answer_text.strip():
        raise AIHubMixGenerationError("provider returned an empty answer")

    raw_claims = payload.get("claims", [])
    if not isinstance(raw_claims, list):
        raise AIHubMixGenerationError("claims must be a list")
    claims: list[Claim] = []
    for item in raw_claims:
        if not isinstance(item, dict):
            raise AIHubMixGenerationError("each claim must be an object")
        text = item.get("text")
        citations = item.get("citations")
        if not isinstance(text, str) or not text.strip():
            raise AIHubMixGenerationError("each claim must contain text")
        if not isinstance(citations, list) or not all(isinstance(cid, str) for cid in citations):
            raise AIHubMixGenerationError("each claim must contain a citation list")
        claims.append(Claim(text=text.strip(), citations=list(dict.fromkeys(citations))))

    if status in {"answer", "qualified"} and not claims:
        raise AIHubMixGenerationError("non-refusal answers must contain cited claims")
    if status == "refuse" and claims:
        raise AIHubMixGenerationError("refusal answers must not contain factual claims")
    if context.evidence_status == "qualified" and status == "answer":
        status = "qualified"

    raw_limitations = payload.get("limitations", [])
    if not isinstance(raw_limitations, list) or not all(
        isinstance(item, str) for item in raw_limitations
    ):
        raise AIHubMixGenerationError("limitations must be a list of strings")
    limitations = list(dict.fromkeys([*context.limitations, *raw_limitations]))

    cited_ids = list(dict.fromkeys(cid for claim in claims for cid in claim.citations))
    citations = [context.citation_registry[cid] for cid in cited_ids if cid in context.citation_registry]
    return GeneratedAnswer(
        status=status,
        answer=answer_text.strip(),
        claims=claims,
        citations=citations,
        limitations=limitations,
        provider="aihubmix",
        prompt_policy_version="1.1.0",
        diagnostics={"model": model, "claim_count": len(claims)},
    )


def _messages(context: ContextPackage) -> list[dict[str, str]]:
    evidence = [
        {
            "chunk_id": passage.chunk_id,
            "collection": passage.collection,
            "title": passage.title,
            "content": passage.content,
            "metadata": passage.metadata,
        }
        for passage in context.passages
    ]
    system = """You are an evidence-grounded scientific assistant.
Use only the supplied evidence. Do not use outside knowledge.
Return JSON only with this exact structure:
{
  "status": "answer|qualified|refuse",
  "answer": "concise natural-language answer",
  "claims": [{"text": "one factual claim", "citations": ["exact chunk_id"]}],
  "limitations": ["limitation text"]
}
Every factual claim must cite one or more exact chunk_id values from the evidence.
Never invent a citation. If evidence is insufficient, return status "refuse" with no claims.
Preserve scientific numbers exactly and do not claim that association proves causality."""
    user = json.dumps(
        {
            "question": context.question,
            "evidence_status": context.evidence_status,
            "known_limitations": context.limitations,
            "evidence": evidence,
        },
        ensure_ascii=False,
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


@dataclass
class AIHubMixGenerator:
    api_key: str
    model: str = "nemotron-3-ultra-550b-a55b-free"
    base_url: str = "https://aihubmix.com/v1"
    max_tokens: int = 800
    timeout_s: float = 60.0
    repair_attempts: int = 1
    client: Any | None = None

    provider = "aihubmix"
    prompt_policy_version = "1.1.0"

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("AIHUBMIX_API_KEY is required")
        if self.client is None:
            try:
                from openai import OpenAI
            except ModuleNotFoundError as exc:
                raise ModuleNotFoundError(
                    "AIHubMix support requires: pip install -r requirements-llm.txt"
                ) from exc
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_s,
                max_retries=0,
            )

    def _request(self, messages: list[dict[str, str]]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            stream=False,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise AIHubMixGenerationError("provider returned empty content")
        normalized = content.lower()
        if "can only try 10 times" in normalized or (
            "free" in normalized and "quota" in normalized and "topup" in normalized
        ):
            raise _AIHubMixQuotaError(
                "AIHubMix free-trial quota is exhausted. Use a key from an account "
                "with available quota or top up the current account."
            )
        return content

    def generate(self, context: ContextPackage) -> GeneratedAnswer:
        if context.evidence_status == "refuse":
            return GeneratedAnswer(
                status="refuse",
                answer="I cannot answer this question from the authorized approved corpus.",
                claims=[],
                citations=[],
                limitations=context.limitations,
                provider=self.provider,
                prompt_policy_version=self.prompt_policy_version,
                diagnostics={"model": self.model, "api_called": False},
            )

        messages = _messages(context)
        last_error: Exception | None = None
        for attempt in range(self.repair_attempts + 1):
            try:
                content = self._request(messages)
                return _parse_answer(_json_content(content), context, self.model)
            except _AIHubMixQuotaError:
                raise
            except (AIHubMixGenerationError, KeyError, IndexError, TypeError) as exc:
                last_error = exc
                if attempt >= self.repair_attempts:
                    break
                messages = [
                    *messages,
                    {"role": "assistant", "content": content if "content" in locals() else ""},
                    {
                        "role": "user",
                        "content": (
                            "The response was invalid. Return exactly one valid JSON object "
                            "matching the schema. Do not include reasoning, <think> tags, "
                            "Markdown fences, or any text before or after the JSON."
                        ),
                    },
                ]
            except Exception as exc:
                raise AIHubMixGenerationError("AIHubMix request failed") from exc
        raise AIHubMixGenerationError("AIHubMix returned no valid structured answer") from last_error
