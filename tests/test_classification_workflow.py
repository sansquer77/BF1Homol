import unittest
from unittest.mock import Mock, patch

import pandas as pd

from tests._db_driver_stub import install_if_needed

install_if_needed()

from services.bets_scoring import atualizar_classificacoes_todas_as_provas


class ClassificationWorkflowTests(unittest.TestCase):
    def _run(self, users, races, bets, results):
        captured = []
        frames = iter([users, races, bets, results])
        with patch("services.bets_scoring.require_operation") as authorize, patch(
            "services.bets_scoring.db_connect"
        ), patch(
            "services.bets_scoring._fetch_df", side_effect=lambda *args, **kwargs: next(frames)
        ), patch(
            "services.bets_scoring.get_regras_aplicaveis",
            return_value={"pontos_posicoes": [10], "pontos_11_colocado": 0},
        ), patch(
            "services.bets_scoring._salvar_classificacoes_provas_lote",
            side_effect=lambda value: captured.extend(value),
        ):
            atualizar_classificacoes_todas_as_provas("2026")
        authorize.assert_called_once_with("resultado.write", season="2026")
        return captured

    def test_desempate_prioriza_envio_mais_cedo_antes_do_acerto_11(self):
        captured = self._run(
            pd.DataFrame([{"id": 1}, {"id": 2}]),
            pd.DataFrame([{"id": 10, "nome": "A", "data": "2026-03-01", "tipo": "Normal", "temporada": "2026"}]),
            pd.DataFrame([
                {
                    "usuario_id": 1, "prova_id": 10, "data_envio": "2026-02-20T10:00:00",
                    "pilotos": "A", "fichas": "1", "piloto_11": "X", "automatica": 0, "temporada": "2026",
                },
                {
                    "usuario_id": 2, "prova_id": 10, "data_envio": "2026-02-20T11:00:00",
                    "pilotos": "A", "fichas": "1", "piloto_11": "B", "automatica": 0, "temporada": "2026",
                },
            ]),
            pd.DataFrame([{"prova_id": 10, "posicoes": "{1: 'A', 11: 'B'}", "abandono_pilotos": ""}]),
        )
        self.assertEqual(len(captured), 1)
        ranking = captured[0][1]
        self.assertEqual(ranking["usuario_id"].tolist(), [1, 2])
        self.assertEqual(ranking["posicao"].tolist(), [1, 2])

    def test_primeira_prova_sem_aposta_recebe_85_porcento_do_pior_valido(self):
        captured = self._run(
            pd.DataFrame([{"id": 1}, {"id": 2}, {"id": 3}]),
            pd.DataFrame([{"id": 10, "nome": "A", "data": "2026-03-01", "tipo": "Normal", "temporada": "2026"}]),
            pd.DataFrame([
                {
                    "usuario_id": 1, "prova_id": 10, "data_envio": "2026-02-20T10:00:00",
                    "pilotos": "A", "fichas": "2", "piloto_11": "X", "automatica": 0, "temporada": "2026",
                },
                {
                    "usuario_id": 2, "prova_id": 10, "data_envio": "2026-02-20T11:00:00",
                    "pilotos": "A", "fichas": "1", "piloto_11": "X", "automatica": 0, "temporada": "2026",
                },
            ]),
            pd.DataFrame([{"prova_id": 10, "posicoes": "{1: 'A'}", "abandono_pilotos": ""}]),
        )
        ranking = captured[0][1].set_index("usuario_id")
        self.assertEqual(ranking.loc[1, "pontos"], 20)
        self.assertEqual(ranking.loc[2, "pontos"], 10)
        self.assertEqual(ranking.loc[3, "pontos"], 8.5)

    def test_prova_sem_apostas_nao_gera_classificacao(self):
        captured = self._run(
            pd.DataFrame([{"id": 1}]),
            pd.DataFrame([{"id": 10, "nome": "A", "data": "2026-03-01", "tipo": "Normal", "temporada": "2026"}]),
            pd.DataFrame(columns=[
                "usuario_id", "prova_id", "data_envio", "pilotos", "fichas",
                "piloto_11", "automatica", "temporada",
            ]),
            pd.DataFrame([{"prova_id": 10, "posicoes": "{1: 'A'}", "abandono_pilotos": ""}]),
        )
        self.assertEqual(captured, [])


if __name__ == "__main__":
    unittest.main()
