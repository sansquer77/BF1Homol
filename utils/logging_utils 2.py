from __future__ import annotations

import hashlib


def redact_identifier(value: str | None) -> str:
    """Return deterministic redacted identifier for logs.

    Keeps log correlation while avoiding direct exposure of PII.
    """
    if not value:
        return "anon"
    normalized = str(value).strip().lower().encode("utf-8")
    digest = hashlib.sha256(normalized).hexdigest()[:12]
    return f"id:{digest}"
