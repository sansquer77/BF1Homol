"""Escaping contextual e ponto único de renderização de HTML/JavaScript."""

from __future__ import annotations

import html
import json
from typing import Any


def escape_html_text(value: Any) -> str:
    """Escapa um valor destinado a um nó de texto HTML."""
    return html.escape("" if value is None else str(value), quote=False)


def escape_html_attr(value: Any) -> str:
    """Escapa um valor destinado a um atributo HTML entre aspas."""
    return html.escape("" if value is None else str(value), quote=True)


def serialize_js_value(value: Any) -> str:
    """Serializa dados para um literal JS sem permitir fechamento de ``<script>``."""
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        serialized.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_trusted_html(st_module: Any, html_content: str, *, allow_javascript: bool = False, height: int = 0) -> None:
    """Único sink permitido para markup do repositório já escapado por contexto."""
    if hasattr(st_module, "html"):
        if allow_javascript:
            st_module.html(html_content, unsafe_allow_javascript=True)
        else:
            st_module.html(html_content)
        return

    st_module.markdown(html_content, unsafe_allow_html=True)


def render_global_css(st_module: Any, css: str) -> None:
    """Injeta CSS global no documento da aplicação.

    Usa o padrão clássico ``st.markdown(..., unsafe_allow_html=True)``,
    comprovado para injetar ``<style>`` no documento (a ``<style>`` via
    ``st.html`` nem sempre alcança o documento em todas as versões).
    """
    st_module.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


__all__ = [
    "escape_html_attr",
    "escape_html_text",
    "render_global_css",
    "render_trusted_html",
    "serialize_js_value",
]
