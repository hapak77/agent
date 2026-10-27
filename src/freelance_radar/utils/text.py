"""Text normalization and hashing helpers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
WHITESPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00a0", " ")
    text = WHITESPACE_RE.sub(" ", text).strip().lower()
    return text


def extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text or "")


def content_hash(text: str) -> str:
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def semantic_fingerprint(text: str, *, max_tokens: int = 40) -> str:
    """Cheap semantic fingerprint: sorted unique significant tokens."""
    normalized = normalize_text(text)
    normalized = NON_WORD_RE.sub(" ", normalized)
    tokens = [t for t in normalized.split() if len(t) > 2]
    # Drop very common Russian/English stopwords lightly
    stop = {
        "это",
        "для",
        "как",
        "или",
        "что",
        "нужен",
        "нужна",
        "нужно",
        "ищу",
        "есть",
        "кто",
        "the",
        "and",
        "for",
        "with",
        "need",
        "looking",
        "help",
        "please",
        "можно",
        "пожалуйста",
        "сегодня",
        "завтра",
    }
    meaningful = sorted({t for t in tokens if t not in stop})[:max_tokens]
    joined = " ".join(meaningful)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]


def truncate(text: str, limit: int = 200) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).netloc.lower() or None
    except Exception:
        return None
