import unittest
from datetime import datetime, timedelta

import pandas as pd

from services.bets_rules import _aposta_valida_regras, ajustar_aposta_para_regras, pode_fazer_aposta
from utils.datetime_utils import SAO_PAULO_TZ


class BetsRulesExtendedTests(unittest.TestCase):
    def setUp(self):
        self.pilotos = pd.DataFrame([
            {"nome": "A", "equipe": "Equipe 1"},
            {"nome": "B", "equipe": "Equipe 1"},
            {"nome": "C", "equipe": "Equipe 2"},
            {"nome": "D", "equipe": "Equipe 3"},
        ])
        self.regra = {
            "qtd_minima_pilotos": 3,
            "quantidade_fichas": 6,
            "fichas_por_piloto": 3,
            "mesma_equipe": False,
        }

    def test_aposta_valida_respeita_todos_os_limites(self):
        self.assertTrue(_aposta_valida_regras(["A", "C", "D"], [3, 2, 1], "B", self.pilotos, self.regra))

    def test_rejeita_piloto_repetido_11_apostado_e_equipe_repetida(self):
        cases = [
            (["A", "A", "D"], [2, 2, 2], "C"),
            (["A", "C", "D"], [2, 2, 2], "A"),
            (["A", "B", "D"], [2, 2, 2], "C"),
        ]
        for pilotos, fichas, piloto_11 in cases:
            with self.subTest(pilotos=pilotos, piloto_11=piloto_11):
                self.assertFalse(_aposta_valida_regras(pilotos, fichas, piloto_11, self.pilotos, self.regra))

    def test_rejeita_total_limite_e_piloto_desconhecido(self):
        cases = [
            (["A", "C", "D"], [3, 1, 1], "B"),
            (["A", "C", "D"], [4, 1, 1], "B"),
            (["A", "C", "Z"], [2, 2, 2], "B"),
            (["A", "C", "D"], [2, 2, 2], "Z"),
        ]
        for pilotos, fichas, piloto_11 in cases:
            with self.subTest(pilotos=pilotos, fichas=fichas, piloto_11=piloto_11):
                self.assertFalse(_aposta_valida_regras(pilotos, fichas, piloto_11, self.pilotos, self.regra))

    def test_ajuste_produz_total_e_limites_validos(self):
        pilotos, fichas = ajustar_aposta_para_regras(["A", "C", "D"], [10, -2, 0], self.regra, self.pilotos)
        self.assertEqual(sum(fichas), 6)
        self.assertLessEqual(max(fichas), 3)
        self.assertTrue(all(value >= 0 for value in fichas))
        self.assertEqual(len(pilotos), len(fichas))

    def test_deadline_corrida_aceita_instante_exato_e_bloqueia_depois(self):
        deadline = datetime(2026, 7, 26, 15, 0, tzinfo=SAO_PAULO_TZ)
        allowed_at, _, parsed = pode_fazer_aposta("2026-07-26", "15:00", deadline)
        allowed_after, _, _ = pode_fazer_aposta("2026-07-26", "15:00", deadline + timedelta(microseconds=1))
        self.assertTrue(allowed_at)
        self.assertFalse(allowed_after)
        self.assertEqual(parsed, deadline)

    def test_deadline_invalido_falha_fechado(self):
        allowed, message, parsed = pode_fazer_aposta("data-invalida", "hora-invalida")
        self.assertFalse(allowed)
        self.assertIn("Erro ao validar horário", message)
        self.assertIsNone(parsed)


if __name__ == "__main__":
    unittest.main()
