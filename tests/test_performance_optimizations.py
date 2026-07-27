import unittest
from contextlib import contextmanager
from unittest.mock import patch

from tests._db_driver_stub import install_if_needed

install_if_needed()

from db import db_schema
from db.repo_bets import get_participantes_temporada_df
from utils.ttl_cache import clear_all_caches, ttl_cache


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.execute_count = 0
        self.description = []

    def execute(self, query, params=()):
        self.execute_count += 1

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        pass


class _Connection:
    def __init__(self, cursor):
        self.value = cursor

    def cursor(self):
        return self.value


class PerformanceOptimizationTests(unittest.TestCase):
    def tearDown(self):
        clear_all_caches()
        db_schema.clear_schema_cache()

    def test_metadados_de_colunas_sao_consultados_uma_vez(self):
        cursor = _Cursor([{"column_name": "id"}, {"column_name": "nome"}])
        conn = _Connection(cursor)
        db_schema.clear_schema_cache()

        first = db_schema.get_table_columns(conn, "usuarios")
        first.append("mutacao-local")
        second = db_schema.get_table_columns(conn, "usuarios")

        self.assertEqual(cursor.execute_count, 1)
        self.assertEqual(second, ["id", "nome"])

    def test_invalidacao_por_tag_preserva_cache_nao_relacionado(self):
        calls = {"apostas": 0, "provas": 0}

        @ttl_cache(ttl=60, tags=("apostas",))
        def apostas():
            calls["apostas"] += 1
            return calls["apostas"]

        @ttl_cache(ttl=60, tags=("provas",))
        def provas():
            calls["provas"] += 1
            return calls["provas"]

        self.assertEqual((apostas(), provas()), (1, 1))
        clear_all_caches("apostas")
        self.assertEqual((apostas(), provas()), (2, 1))

    def test_participantes_com_historico_usam_uma_consulta_de_dados(self):
        cursor = _Cursor([{"id": 7, "nome": "Ana", "status": "inativo"}])
        conn = _Connection(cursor)

        @contextmanager
        def connection():
            yield conn

        with patch("db.repo_bets.db_connect", connection), patch(
            "db.repo_bets._usuarios_status_historico_exists", return_value=True
        ), patch("db.repo_bets._query_to_df", side_effect=AssertionError("fallback inesperado")):
            result = get_participantes_temporada_df("2026")

        self.assertEqual(cursor.execute_count, 1)
        self.assertEqual(result["id"].tolist(), [7])

    def test_envio_normal_nao_forca_segundo_rerun(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "ui" / "painel.py").read_text(encoding="utf-8")
        success = source.index('st.success("Aposta registrada/atualizada!")')
        next_section = source.index('st.warning("Administração deve cadastrar', success)
        self.assertNotIn("st.rerun()", source[success:next_section])


if __name__ == "__main__":
    unittest.main()
