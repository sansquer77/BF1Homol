import unittest

import pandas as pd

from utils.dataframe_contracts import APOSTAS_COLUMNS, with_required_columns


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
