"""Cliente centralizado para geração de conteúdo com o SDK oficial Google Gen AI."""

from __future__ import annotations

import logging
import os
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:  # Permite fallback local enquanto a dependência não está disponível.
    genai = None
    types = None


logger = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


def gemini_disponivel() -> bool:
    """Indica se chave e SDK oficial estão disponíveis."""
    return bool(os.environ.get("GEMINI_API_KEY", "").strip() and genai is not None and types is not None)


def gerar_conteudo_gemini(
    *,
    system_instruction: str,
    prompt: str,
    temperature: float,
    max_output_tokens: int,
    response_schema: dict[str, Any] | None = None,
    timeout_seconds: float = 12.0,
) -> str | None:
    """Gera conteúdo via Gemini e devolve texto; falhas ficam a cargo do fallback chamador."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or genai is None or types is None:
        return None

    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    config_kwargs: dict[str, Any] = {
        "system_instruction": system_instruction,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if response_schema is not None:
        config_kwargs.update(
            response_mime_type="application/json",
            response_json_schema=response_schema,
        )

    client = None
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return (response.text or "").strip() or None
    except Exception as exc:
        logger.warning("Falha temporária na geração de conteúdo via Gemini: %s", exc)
        return None
    finally:
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                logger.debug("Falha ao fechar cliente Gemini: %s", exc)


__all__ = ["DEFAULT_GEMINI_MODEL", "gemini_disponivel", "gerar_conteudo_gemini"]
