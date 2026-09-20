import unittest

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
