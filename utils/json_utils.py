"""Utilitários puros para respostas JSON produzidas por serviços externos."""

from __future__ import annotations

import json
from typing import Any


def extract_json_object(raw_text: str) -> dict[str, Any] | None:
    """Extrai um objeto JSON puro ou envolvido por texto explicativo."""
    if not raw_text:
        return None

    text = raw_text.strip()
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None

    try:
        parsed = json.loads(text[start : end + 1])
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None
