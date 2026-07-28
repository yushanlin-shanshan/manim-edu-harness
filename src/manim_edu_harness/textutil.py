"""Text helpers: slugify + secret sanitization for reports."""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata


_SECRET_PATTERNS = [
    re.compile(r"(?i)(ZHIPU_API_KEY|API[_-]?KEY|AUTHORIZATION)\s*[=:]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"\b[0-9a-f]{32}\.[A-Za-z0-9]{10,}\b"),  # zhipu-style keys
]


def slugify(title: str, *, max_len: int = 48) -> str:
    """ASCII-ish slug; falls back to short hash for CJK-only titles."""
    text = unicodedata.normalize("NFKC", (title or "").strip())
    ascii_part = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    ascii_part = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_part).strip("-").lower()
    if ascii_part:
        return ascii_part[:max_len]
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"kp-{digest}"


def sanitize_text(value: object) -> str:
    """Redact secrets before writing reports / logs."""
    text = "" if value is None else str(value)
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    # Also scrub live env key if present.
    key = (os.environ.get("ZHIPU_API_KEY") or "").strip()
    if key and key in text:
        text = text.replace(key, "[REDACTED]")
    return text
