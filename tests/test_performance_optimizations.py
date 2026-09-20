import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Event, Lock
from time import sleep
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

    def test_cache_frio_agrupa_misses_concorrentes_da_mesma_chave(self):
        calls = 0
        calls_lock = Lock()

        @ttl_cache(ttl=60, tags=("single-flight",))
        def expensive(season):
            nonlocal calls
            with calls_lock:
                calls += 1
            sleep(0.05)
            return {"season": season}

        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(expensive, ["2026"] * 12))

        self.assertEqual(calls, 1)
        self.assertEqual(results, [{"season": "2026"}] * 12)

    def test_chaves_diferentes_continuam_processando_em_paralelo(self):
        both_started = Barrier(2, timeout=2)

        @ttl_cache(ttl=60, tags=("parallel-keys",))
        def read_key(key):
            both_started.wait()
            return key

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(read_key, key) for key in ("2025", "2026")]
            self.assertEqual([future.result(timeout=2) for future in futures], ["2025", "2026"])

    def test_invalidacao_durante_miss_nao_reinsere_resultado_obsoleto(self):
        started = Event()
        release = Event()
        calls = 0

        @ttl_cache(ttl=60, tags=("invalidate-in-flight",))
        def read_value():
            nonlocal calls
            calls += 1
            current = calls
            if current == 1:
                started.set()
                release.wait(timeout=2)
            return current

        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(read_value)
            self.assertTrue(started.wait(timeout=2))
            clear_all_caches("invalidate-in-flight")
            release.set()
            self.assertEqual(first.result(timeout=2), 1)

        self.assertEqual(read_value(), 2)
        self.assertEqual(read_value(), 2)
        self.assertEqual(calls, 2)

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

if __name__ == "__main__":
    unittest.main()
