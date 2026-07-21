import unittest
from pathlib import Path

import pandas as pd

from utils.dataframe_contracts import (
    APOSTAS_COLUMNS,
    CHAMPIONSHIP_BETS_COLUMNS,
    CHAMPIONSHIP_RESULTS_COLUMNS,
    PILOTOS_COLUMNS,
    POSICOES_COLUMNS,
    PROVAS_COLUMNS,
    RESULTADOS_COLUMNS,
    USUARIOS_COLUMNS,
    with_required_columns,
)


class ApostasDataFrameContractTests(unittest.TestCase):
    def test_empty_dataframe_preserves_required_schema(self):
        result = with_required_columns(pd.DataFrame(), APOSTAS_COLUMNS)
        self.assertTrue(set(APOSTAS_COLUMNS).issubset(result.columns))
        self.assertTrue(result.empty)

    def test_existing_rows_are_preserved(self):
        original = pd.DataFrame([{"usuario_id": 7, "prova_id": 11}])
        result = with_required_columns(original, APOSTAS_COLUMNS)
        self.assertEqual(result.loc[0, "usuario_id"], 7)
        self.assertEqual(result.loc[0, "prova_id"], 11)

    def test_gestao_apostas_normalizes_both_dataframe_reads(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "gestao_apostas.py").read_text(encoding="utf-8")
        self.assertIn("def _normalizar_apostas_df", source)
        self.assertEqual(2, source.count("_normalizar_apostas_df(get_apostas_df(season))"))
        self.assertIn("_normalizar_provas_df(get_provas_df(season))", source)
        self.assertIn("_normalizar_participantes_df(get_participantes_temporada_df(season))", source)
        self.assertNotIn('provas_df.sort_values("data")', source)

    def test_painel_fallback_keeps_prova_id_after_sem_ideias_rerun(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "painel.py").read_text(encoding="utf-8")
        self.assertNotIn("apostas_part = pd.DataFrame()", source)
        self.assertIn("apostas_part = with_required_columns(apostas_df, APOSTAS_COLUMNS)", source)
        self.assertIn("'prova_id' in apostas_part.columns", source)

    def test_sem_ideias_clears_specific_cache_and_preserves_feedback(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "painel.py").read_text(encoding="utf-8")
        self.assertIn("get_apostas_df.clear()", source)
        self.assertIn('st.session_state["sem_ideias_feedback"] = msg_auto', source)
        self.assertIn('st.session_state.pop("sem_ideias_feedback", None)', source)
        self.assertIn('st.session_state["sem_ideias_detalhes"] = detalhes_auto', source)
        self.assertIn('st.session_state.pop("sem_ideias_detalhes", None)', source)

    def test_all_public_dataframe_contracts_preserve_empty_schema(self):
        contracts = (
            PILOTOS_COLUMNS,
            PROVAS_COLUMNS,
            RESULTADOS_COLUMNS,
            USUARIOS_COLUMNS,
            POSICOES_COLUMNS,
            CHAMPIONSHIP_BETS_COLUMNS,
            CHAMPIONSHIP_RESULTS_COLUMNS,
        )
        for columns in contracts:
            with self.subTest(columns=columns):
                result = with_required_columns(None, columns)
                self.assertEqual(set(columns), set(result.columns))
                self.assertTrue(result.empty)

    def test_gestao_resultados_normalizes_every_result_read(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "gestao_resultados.py").read_text(encoding="utf-8")
        self.assertIn("def _normalizar_dados_resultados", source)
        self.assertEqual(2, source.count("get_resultados_df(temporada_selecionada)"))
        self.assertIn("with_required_columns(\n        get_resultados_df(temporada_selecionada), RESULTADOS_COLUMNS", source)

    def test_high_risk_pages_apply_contracts_at_ui_boundary(self):
        root = Path(__file__).resolve().parents[1] / "ui"
        expected = {
            "championship_results.py": "PILOTOS_COLUMNS",
            "championship_bets.py": "USUARIOS_COLUMNS",
            "classificacao.py": "RESULTADOS_COLUMNS",
            "hall_da_fama.py": "USUARIOS_COLUMNS",
            "usuarios.py": "USUARIOS_COLUMNS",
            "calendario.py": "PROVAS_COLUMNS",
            "painel.py": "POSICOES_COLUMNS",
            "gestao_provas.py": "PROVAS_COLUMNS",
        }
        for filename, contract in expected.items():
            with self.subTest(filename=filename):
                source = (root / filename).read_text(encoding="utf-8")
                self.assertIn("with_required_columns", source)
                self.assertIn(contract, source)
