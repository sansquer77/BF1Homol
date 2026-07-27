import unittest
from unittest.mock import patch

import pandas as pd

from tests._db_driver_stub import install_if_needed

install_if_needed()

from services.bets_scoring import calcular_pontuacao_lote


class BetsScoringRulesTests(unittest.TestCase):
    def _score(self, aposta, resultado, prova, regra):
        with patch("services.bets_scoring.get_regras_aplicaveis", return_value=regra):
            return calcular_pontuacao_lote(
                pd.DataFrame([aposta]),
                pd.DataFrame([resultado]),
                pd.DataFrame([prova]),
            )[0]

    def test_normal_combina_fichas_bonus_11_e_penalidade_por_abandono(self):
        score = self._score(
            {
                "prova_id": 1,
                "pilotos": "A,B,C",
                "fichas": "2,1,3",
                "piloto_11": "D",
                "automatica": 0,
                "temporada": "2026",
            },
            {
                "prova_id": 1,
                "posicoes": "{1: 'A', 2: 'B', 11: 'D'}",
                "abandono_pilotos": "B,C",
            },
            {"id": 1, "nome": "Austrália", "tipo": "Normal", "temporada": "2026"},
            {
                "pontos_posicoes": [25, 18, 15],
                "pontos_11_colocado": 10,
                "penalidade_abandono": True,
                "pontos_penalidade": 4,
            },
        )
        self.assertEqual(score, 70)  # 2*25 + 1*18 + 10 - 2*4

    def test_sprint_usa_tabela_especifica_e_dobra_total_inclusive_bonus(self):
        score = self._score(
            {
                "prova_id": 2,
                "pilotos": "A,B",
                "fichas": "2,1",
                "piloto_11": "C",
                "automatica": 0,
            },
            {"prova_id": 2, "posicoes": "{1: 'A', 3: 'B', 11: 'C'}", "abandono_pilotos": ""},
            {"id": 2, "nome": "China", "tipo": "Sprint", "temporada": "2026"},
            {
                "pontos_posicoes": [25, 18, 15],
                "pontos_sprint_posicoes": [8, 7, 6],
                "pontos_11_colocado": 5,
                "pontos_dobrada": True,
            },
        )
        self.assertEqual(score, 54)  # (2*8 + 1*6 + 5) * 2

    def test_segunda_aposta_automatica_aplica_percentual_configurado(self):
        score = self._score(
            {
                "prova_id": 3,
                "pilotos": "A",
                "fichas": "4",
                "piloto_11": "X",
                "automatica": 2,
            },
            {"prova_id": 3, "posicoes": "{1: 'A', 11: 'B'}", "abandono_pilotos": ""},
            {"id": 3, "nome": "Mônaco", "tipo": "Normal", "temporada": "2026"},
            {"pontos_posicoes": [25], "penalidade_auto_percent": 15},
        )
        self.assertEqual(score, 85.0)

    def test_sem_resultado_retorna_none_e_nao_busca_regra(self):
        with patch("services.bets_scoring.get_regras_aplicaveis") as rules:
            points = calcular_pontuacao_lote(
                pd.DataFrame([{
                    "prova_id": 99, "pilotos": "A", "fichas": "1",
                    "piloto_11": "B", "automatica": 0,
                }]),
                pd.DataFrame(columns=["prova_id", "posicoes"]),
                pd.DataFrame([{"id": 99, "nome": "Teste", "tipo": "Normal"}]),
            )
        self.assertEqual(points, [None])
        rules.assert_not_called()

    def test_regra_e_carregada_uma_vez_por_temporada_e_tipo(self):
        apostas = pd.DataFrame([
            {"prova_id": 1, "pilotos": "A", "fichas": "1", "piloto_11": "X", "automatica": 0, "temporada": "2026"},
            {"prova_id": 1, "pilotos": "B", "fichas": "1", "piloto_11": "X", "automatica": 0, "temporada": "2026"},
        ])
        resultados = pd.DataFrame([{"prova_id": 1, "posicoes": "{1: 'A', 2: 'B'}"}])
        provas = pd.DataFrame([{"id": 1, "nome": "Teste", "tipo": "Normal", "temporada": "2026"}])
        with patch(
            "services.bets_scoring.get_regras_aplicaveis",
            return_value={"pontos_posicoes": [25, 18]},
        ) as rules:
            self.assertEqual(calcular_pontuacao_lote(apostas, resultados, provas), [25, 18])
        rules.assert_called_once_with("2026", "Normal")


if __name__ == "__main__":
    unittest.main()
