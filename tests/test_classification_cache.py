from unittest.mock import patch

import pandas as pd

from services.classification_service import (
    build_classification,
    build_classification_history,
    build_classification_summary,
)
from utils.ttl_cache import clear_all_caches


def _make_frames():
    users = pd.DataFrame([{"id": 1, "nome": "Ana", "perfil": "participante"}])
    races = pd.DataFrame([{"id": 10, "nome": "GP A", "data": "2026-03-01", "tipo": "Normal", "temporada": "2026"}])
    bets = pd.DataFrame([{"usuario_id": 1, "prova_id": 10, "piloto_11": "X", "data_envio": "2026-02-28"}])
    results = pd.DataFrame([{"prova_id": 10, "posicoes": "{11: 'X'}"}])
    return users, races, bets, results


def test_build_classification_summary_is_cached_and_reuses_base():
    clear_all_caches("classificacao")
    users, races, bets, results = _make_frames()
    with patch("db.repo_bets.get_participantes_temporada_df", return_value=users), \
         patch("db.repo_races.get_provas_df", return_value=races), \
         patch("db.repo_bets.get_apostas_df", return_value=bets), \
         patch("db.repo_races.get_resultados_df", return_value=results), \
         patch("services.classification_service.calcular_pontuacao_lote", return_value=[100]), \
         patch("services.classification_service.get_regras_aplicaveis", return_value={"descarte": False}), \
         patch("services.classification_service.get_final_results", return_value=None):
        first = build_classification_summary("2026")
        second = build_classification_summary("2026")
    assert first["season"] == "2026"
    assert len(first["entries"]) == 1
    assert first["entries"][0]["participant"] == "Ana"
    assert second is first  # cache hit


def test_build_classification_history_is_cached_separately():
    clear_all_caches("classificacao")
    users, races, bets, results = _make_frames()
    with patch("db.repo_bets.get_participantes_temporada_df", return_value=users), \
         patch("db.repo_races.get_provas_df", return_value=races), \
         patch("db.repo_bets.get_apostas_df", return_value=bets), \
         patch("db.repo_races.get_resultados_df", return_value=results), \
         patch("services.classification_service.calcular_pontuacao_lote", return_value=[100]), \
         patch("services.classification_service.get_regras_aplicaveis", return_value={"descarte": False}), \
         patch("services.classification_service.get_final_results", return_value=None):
        summary = build_classification_summary("2026")
        history = build_classification_history("2026")
        full = build_classification("2026")
    assert "races" not in summary or summary["races"] == []
    assert len(history["races"]) == 1
    assert full["entries"] == summary["entries"]
    assert full["races"] == history["races"]


def test_classification_cache_is_invalidated_by_clear_all_caches():
    clear_all_caches("classificacao")
    users, races, bets, results = _make_frames()
    with patch("db.repo_bets.get_participantes_temporada_df", return_value=users), \
         patch("db.repo_races.get_provas_df", return_value=races), \
         patch("db.repo_bets.get_apostas_df", return_value=bets), \
         patch("db.repo_races.get_resultados_df", return_value=results), \
         patch("services.classification_service.calcular_pontuacao_lote", return_value=[100]), \
         patch("services.classification_service.get_regras_aplicaveis", return_value={"descarte": False}), \
         patch("services.classification_service.get_final_results", return_value=None):
        first = build_classification_summary("2026")
        clear_all_caches("classificacao")
        second = build_classification_summary("2026")
    assert first is not second
