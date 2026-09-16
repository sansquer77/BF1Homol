"""Geração de imagens de relatórios administrativos."""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from typing import Any

from PIL import Image, ImageDraw, ImageFont


# Paleta institucional alinhada ao frontend V4.
COLORS = {
    "bg": "#FFFFFF",
    "header_bg": "#0F172A",
    "header_text": "#FFFFFF",
    "primary_text": "#1E293B",
    "secondary_text": "#64748B",
    "border": "#E2E8F0",
    "row_alt": "#F8FAFC",
    "manual": "#10B981",
    "automatic": "#3B82F6",
    "missing": "#EF4444",
    "total": "#1E293B",
    "progress_bg": "#E2E8F0",
}

_WIDTH = 1280
_MARGIN = 48
_HEADER_HEIGHT = 132
_FOOTER_HEIGHT = 44
_ROW_HEIGHT = 58
_TABLE_HEADER_HEIGHT = 52
_FONT_SIZE_TITLE = 32
_FONT_SIZE_SUBTITLE = 18
_FONT_SIZE_BODY = 16
_FONT_SIZE_SMALL = 13
_FONT_SIZE_FOOTER = 12
_LOGO_SIZE = 80


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Tenta carregar uma fonte sans-serif do sistema; usa fallback em último caso."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial.ttf",
        "/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _load_logo(path: str | None = None) -> Image.Image | None:
    """Carrega o logo do BF1; retorna None se não encontrado."""
    candidates = [
        path,
        os.environ.get("BF1_LOGO_PATH"),
        "frontend/public/bf1-icon.png",
        "static/icon-192.png",
        "static/apple-touch-icon.png",
        "favicon.png",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            logo = Image.open(candidate).convert("RGBA")
            logo.thumbnail((_LOGO_SIZE, _LOGO_SIZE), Image.Resampling.LANCZOS)
            return logo
        except Exception:
            continue
    return None


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> tuple[int, int]:
    """Retorna (largura, altura) de um texto renderizado."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def generate_bets_coverage_image(
    season: str,
    races_total: int,
    reports: list[dict[str, Any]],
    logo_path: str | None = None,
) -> bytes:
    """Gera imagem PNG do relatório de cobertura de apostas por participante.

    Args:
        season: Temporada do relatório.
        races_total: Quantidade total de provas na temporada.
        reports: Lista de relatórios no formato retornado por `get_admin_bets`.
        logo_path: Caminho opcional para o logo; usa descoberta automática se omitido.

    Returns:
        Bytes da imagem PNG.
    """
    # spec: gestao-administrativa-de-postas v0.1 — critério 7
    title_font = _load_font(_FONT_SIZE_TITLE)
    subtitle_font = _load_font(_FONT_SIZE_SUBTITLE)
    body_font = _load_font(_FONT_SIZE_BODY)
    small_font = _load_font(_FONT_SIZE_SMALL)
    footer_font = _load_font(_FONT_SIZE_FOOTER)
    bold_body_font = _load_font(_FONT_SIZE_BODY + 1)

    rows = sorted(reports, key=lambda r: str(r.get("name") or "").casefold())
    table_height = _TABLE_HEADER_HEIGHT + len(rows) * _ROW_HEIGHT
    height = _HEADER_HEIGHT + 24 + table_height + 24 + _FOOTER_HEIGHT

    image = Image.new("RGB", (_WIDTH, height), COLORS["bg"])
    draw = ImageDraw.Draw(image)

    # Cabeçalho institucional.
    draw.rectangle([0, 0, _WIDTH, _HEADER_HEIGHT], fill=COLORS["header_bg"])
    logo = _load_logo(logo_path)
    logo_x = _MARGIN
    logo_y = (_HEADER_HEIGHT - (logo.height if logo else _LOGO_SIZE)) // 2
    if logo:
        image.paste(logo, (logo_x, logo_y), logo)
        text_x = logo_x + logo.width + 24
    else:
        text_x = logo_x + _LOGO_SIZE + 24

    title_y = (_HEADER_HEIGHT - _text_size(draw, "Relatório", title_font)[1] - _text_size(draw, "Cobertura de apostas", subtitle_font)[1] - 4) // 2
    draw.text((text_x, title_y), "Cobertura de apostas", font=title_font, fill=COLORS["header_text"])
    subtitle_y = title_y + _text_size(draw, "Cobertura de apostas", title_font)[1] + 4
    draw.text((text_x, subtitle_y), f"Temporada {season} · {races_total} provas", font=subtitle_font, fill=COLORS["header_text"])

    # Tabela.
    table_top = _HEADER_HEIGHT + 24
    col_x = {
        "participant": _MARGIN,
        "total": 420,
        "manual": 720,
        "automatic": 860,
        "missing": 1040,
    }
    col_widths = {
        "participant": col_x["total"] - col_x["participant"] - 16,
        "total": col_x["manual"] - col_x["total"] - 16,
        "manual": col_x["automatic"] - col_x["manual"] - 16,
        "automatic": col_x["missing"] - col_x["automatic"] - 16,
        "missing": _WIDTH - _MARGIN - col_x["missing"],
    }

    # Cabeçalho da tabela.
    draw.rectangle([_MARGIN, table_top, _WIDTH - _MARGIN, table_top + _TABLE_HEADER_HEIGHT], fill=COLORS["header_bg"])
    headers = [
        ("Participante", "participant"),
        ("Cobertura", "total"),
        ("Manuais", "manual"),
        ("Automáticas", "automatic"),
        ("Sem registro", "missing"),
    ]
    header_y = table_top + (_TABLE_HEADER_HEIGHT - _text_size(draw, "Participante", body_font)[1]) // 2
    for label, key in headers:
        draw.text((col_x[key], header_y), label, font=body_font, fill=COLORS["header_text"])

    # Linhas de dados.
    for index, report in enumerate(rows):
        y = table_top + _TABLE_HEADER_HEIGHT + index * _ROW_HEIGHT
        fill = COLORS["row_alt"] if index % 2 == 1 else COLORS["bg"]
        draw.rectangle([_MARGIN, y, _WIDTH - _MARGIN, y + _ROW_HEIGHT], fill=fill)
        draw.line([(_MARGIN, y + _ROW_HEIGHT), (_WIDTH - _MARGIN, y + _ROW_HEIGHT)], fill=COLORS["border"], width=1)

        name = str(report.get("name") or "—")
        manual = int(report.get("manual_total") or 0)
        automatic = int(report.get("automatic_total") or 0)
        missing = int(report.get("missing_total") or 0)
        total = manual + automatic
        coverage_pct = (total / races_total * 100) if races_total else 0

        # Nome.
        draw.text((col_x["participant"], y + (_ROW_HEIGHT - _text_size(draw, name, body_font)[1]) // 2), name, font=body_font, fill=COLORS["primary_text"])

        # Barra de progresso de cobertura.
        bar_y = y + (_ROW_HEIGHT - 14) // 2
        bar_width = col_widths["total"]
        draw.rounded_rectangle([col_x["total"], bar_y, col_x["total"] + bar_width, bar_y + 14], radius=7, fill=COLORS["progress_bg"])
        filled_width = int(bar_width * min(coverage_pct, 100) / 100)
        if filled_width > 0:
            draw.rounded_rectangle([col_x["total"], bar_y, col_x["total"] + filled_width, bar_y + 14], radius=7, fill=COLORS["total"])
        label_text = f"{total}/{races_total} ({coverage_pct:.0f}%)"
        draw.text((col_x["total"], bar_y + 20), label_text, font=small_font, fill=COLORS["secondary_text"])

        # Contadores coloridos.
        counters = [
            (manual, COLORS["manual"], "manual"),
            (automatic, COLORS["automatic"], "automatic"),
            (missing, COLORS["missing"], "missing"),
        ]
        for count, color, key in counters:
            text = str(count)
            tw, th = _text_size(draw, text, bold_body_font)
            cx = col_x[key] + (col_widths[key] - tw) // 2
            cy = y + (_ROW_HEIGHT - th) // 2
            draw.text((cx, cy), text, font=bold_body_font, fill=color)

    # Rodapé.
    footer_y = height - _FOOTER_HEIGHT + (_FOOTER_HEIGHT - _text_size(draw, "Gerado", footer_font)[1]) // 2
    generated_at = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    draw.text((_MARGIN, footer_y), f"Gerado em {generated_at}", font=footer_font, fill=COLORS["secondary_text"])
    right_text = "BF1 — Bolão de Fórmula 1"
    rtw, _ = _text_size(draw, right_text, footer_font)
    draw.text((_WIDTH - _MARGIN - rtw, footer_y), right_text, font=footer_font, fill=COLORS["secondary_text"])

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
