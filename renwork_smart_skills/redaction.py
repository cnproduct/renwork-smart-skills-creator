"""Conservative redaction for locally mined evidence."""

from __future__ import annotations

import re
from pathlib import Path


_PATTERNS = (
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{12,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key|access[_-]?token|client[_-]?secret|password)(\s*[=:]\s*)[^\s,;]+"), r"\1\2[REDACTED]"),
    (re.compile(r"https?://[^\s/:]+:[^\s/@]+@"), "https://[REDACTED]@"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[REDACTED_EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?\d[\d .()\-]{8,}\d)(?!\d)"), "[REDACTED_PHONE]"),
)


def redact(text: str, home: Path | None = None) -> str:
    """Return a normalized, secret-reduced excerpt suitable for local evidence."""
    value = text.replace("\x00", " ")
    if home:
        value = value.replace(str(home), "~")
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    return re.sub(r"[ \t]+", " ", value).strip()


def contains_secret(text: str) -> bool:
    """Fail-closed detector for content that must not be published."""
    for pattern, _ in _PATTERNS[:5]:
        if pattern.search(text):
            return True
    private_key_markers = ("BEGIN PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY")
    return any(marker in text for marker in private_key_markers)
