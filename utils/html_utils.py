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


def render_dom_styles(st_module: Any, rules: list[dict[str, Any]], *, extra_css: str = "") -> None:
    """Aplica estilos diretamente no DOM renderizado, imunes a especificidade.

    Cada regra: ``{"selector": str, "style": {prop: valor}, "media": str | None}``.
    Um ``MutationObserver`` reaplica os estilos inline (via ``setProperty`` com
    prioridade ``important``) após qualquer mutação do Streamlit, cobrindo
    reruns, expansores e o drawer móvel. ``extra_css`` injeta ``<style>`` de
    apoio para estados que inline não alcança (ex.: ``:hover``/``:focus``).
    """
    payload = serialize_js_value(rules)
    script = (
        "<script>"
        "(function(){"
        "var rules=" + payload + ";"
        "function apply(){"
        "for(var i=0;i<rules.length;i++){"
        "var rule=rules[i];"
        "if(rule.media&&!window.matchMedia(rule.media).matches)continue;"
        "var els=document.querySelectorAll(rule.selector);"
        "for(var j=0;j<els.length;j++){"
        "var el=els[j];"
        "for(var k in rule.style){"
        "el.style.setProperty(k,rule.style[k],\"important\")"
        "}"
        "}"
        "}"
        "}"
        "apply();"
        "var mo=new MutationObserver(apply);"
        "mo.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:[\"class\",\"data-testid\"]});"
        "})()"
        "</script>"
    )
    body = script if not extra_css else f"<style>{extra_css}</style>{script}"
    render_trusted_html(st_module, body, allow_javascript=True)


__all__ = [
    "escape_html_attr",
    "escape_html_text",
    "render_dom_styles",
    "render_global_css",
    "render_trusted_html",
    "serialize_js_value",
]
