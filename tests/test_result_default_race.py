import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

from services.painel_controller import get_prova_atual_sem_resultado_id
from utils.datetime_utils import SAO_PAULO_TZ


class ResultDefaultRaceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 3, 20, 12, 0, tzinfo=SAO_PAULO_TZ)
        self.races = pd.DataFrame([
            {"id": 1, "nome": "Austrália", "data": "2026-03-08", "horario_prova": "01:00"},
            {"id": 2, "nome": "China", "data": "2026-03-15", "horario_prova": "04:00"},
            {"id": 3, "nome": "Japão", "data": "2026-03-29", "horario_prova": "02:00"},
        ])

    def test_prioriza_ultima_prova_iniciada_sem_resultado(self):
        resultados = pd.DataFrame([{"prova_id": 1}])
        self.assertEqual(
            get_prova_atual_sem_resultado_id(self.races, resultados, self.now),
            2,
        )

    def test_quando_passadas_estao_preenchidas_seleciona_proxima(self):
        resultados = pd.DataFrame([{"prova_id": 1}, {"prova_id": 2}])
        self.assertEqual(
            get_prova_atual_sem_resultado_id(self.races, resultados, self.now),
            3,
        )

    def test_ignora_ids_de_resultado_em_string(self):
        resultados = pd.DataFrame([{"prova_id": "1"}, {"prova_id": "2"}])
        self.assertEqual(
            get_prova_atual_sem_resultado_id(self.races, resultados, self.now),
            3,
        )

    def test_retorna_none_quando_todas_possuem_resultado(self):
        resultados = pd.DataFrame([{"prova_id": 1}, {"prova_id": 2}, {"prova_id": 3}])
        self.assertIsNone(
            get_prova_atual_sem_resultado_id(self.races, resultados, self.now)
        )

    def test_data_invalida_tem_fallback_pendente_estavel(self):
        races = pd.DataFrame([
            {"id": 7, "data": "inválida", "horario_prova": ""},
            {"id": 8, "data": None, "horario_prova": ""},
        ])
        self.assertEqual(
            get_prova_atual_sem_resultado_id(races, pd.DataFrame(), self.now),
            7,
        )

    def test_tela_preserva_escolha_manual_ate_trocar_temporada_ou_salvar(self):
        source = (
            Path(__file__).resolve().parents[1] / "ui" / "gestao_resultados.py"
        ).read_text(encoding="utf-8")
        self.assertIn("current_selection not in prova_options", source)
        self.assertIn("season_changed", source)
        self.assertIn('st.session_state.pop("resultados_reselecionar", False)', source)
        self.assertIn('st.session_state["resultados_reselecionar"] = True', source)


if __name__ == "__main__":
    unittest.main()
