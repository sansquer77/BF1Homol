from unittest.mock import patch

import pandas as pd

from services.classification_service import build_classification, calculate_totals, render_classification_png


def test_total_valido_preserves_canonical_formula():
    assert calculate_totals(300, 150, 100, 80, 40)["valid_total"] == 590


def test_classification_png_is_generated():
    image = render_classification_png({"season": "2026", "entries": []})
    assert image.read(8) == b"\x89PNG\r\n\x1a\n"


def test_classification_orders_by_valid_total_and_applies_discard_once():
    users = pd.DataFrame([
        {"id": 1, "nome": "Ana", "perfil": "participante"},
        {"id": 2, "nome": "Beto", "perfil": "participante"},
    ])
    races = pd.DataFrame([{"id": 10, "nome": "GP A", "data": "2026-03-01", "tipo": "Normal", "temporada": "2026"}])
    bets = pd.DataFrame([
        {"usuario_id": 1, "prova_id": 10, "piloto_11": "X", "data_envio": "2026-02-28"},
        {"usuario_id": 2, "prova_id": 10, "piloto_11": "Y", "data_envio": "2026-02-28"},
    ])
    results = pd.DataFrame([{"prova_id": 10, "posicoes": "{11: 'X'}"}])
    with patch("db.repo_bets.get_participantes_temporada_df", return_value=users), \
         patch("db.repo_bets.get_apostas_df", return_value=bets), \
         patch("db.repo_races.get_provas_df", return_value=races), \
         patch("db.repo_races.get_resultados_df", return_value=results), \
         patch("services.classification_service.calcular_pontuacao_lote", return_value=[100, 80]), \
         patch("services.classification_service.get_regras_aplicaveis", return_value={"descarte": True}), \
         patch("services.classification_service.get_final_results", return_value=None):
        result = build_classification("2026")

    assert result["discard_active"] is True
    assert result["entries"][0]["participant"] == "Ana"
    assert result["entries"][0]["total"] == 100
    assert result["entries"][0]["discard"] == 100
    assert result["entries"][0]["valid_total"] == 0
    assert result["entries"][0]["eleventh_hits"] == 1
