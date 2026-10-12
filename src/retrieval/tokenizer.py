from __future__ import annotations

import re
import unicodedata

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._:\-][a-z0-9]+)*", re.IGNORECASE)

QUERY_STOPWORDS = {
    "a",
    "an",
    "also",
    "and",
    "are",
    "as",
    "according",
    "between",
    "by",
    "called",
    "for",
    "from",
    "function",
    "gene",
    "genes",
    "identified",
    "identifier",
    "identifiers",
    "in",
    "is",
    "known",
    "linking",
    "of",
    "on",
    "or",
    "reported",
    "results",
    "the",
    "there",
    "this",
    "that",
    "to",
    "vs",
    "what",
    "which",
    "with",
}


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return TOKEN_RE.findall(normalize_text(text))


def tokenize_query(text: str) -> list[str]:
    return [token for token in tokenize(text) if token not in QUERY_STOPWORDS]
