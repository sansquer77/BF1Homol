"""Testes do indicador e filtro de apostas não efetivas no log de apostas."""

import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from db.repo_logs import registrar_log_aposta
from db.migrations import backfill_log_apostas_status_nao_efetiva
from services.logs_read_service import list_betting_logs


class _Cursor:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.executions = []
        self.current = None

    def execute(self, query, params=()):
        self.executions.append((" ".join(query.split()), tuple(params)))
        self.current = next(self.responses)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current

    def close(self):
        pass


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _make_table_columns():
    return {
        "status", "ip_address", "usuario_id", "temporada",
        "data", "data_criacao",
    }


class RegistrarLogApostaStatusTests(unittest.TestCase):
    def test_foraprazo_persiste_status_nao_efetiva(self):
        cursor = _Cursor([{"id": 1}])
        conn = _Connection(cursor)

        with patch("db.repo_logs.db_connect", return_value=conn), \
             patch("db.repo_logs.get_table_columns", return_value=_make_table_columns()):
            registrar_log_aposta(
                usuario_id=1,
                prova_id=2,
                apostador="Ana",
                pilotos="P1,P2",
                aposta="5,10",
                nome_prova="Áustria",
                piloto_11="P3",
                tipo_aposta=1,
                automatica=0,
                horario=datetime(2026, 7, 1, 12, 0, 0),
                temporada="2026",
                status="Registrada",
            )

        self.assertTrue(conn.committed)
        insert_sql, insert_params = cursor.executions[0]
        self.assertIn("INSERT INTO log_apostas", insert_sql)
        self.assertEqual(insert_params[-1], "Não efetiva")
        self.assertEqual(insert_params[-2], "2026")

    def test_dentro_prazo_mantem_status_informado(self):
        cursor = _Cursor([{"id": 1}])
        conn = _Connection(cursor)

        with patch("db.repo_logs.db_connect", return_value=conn), \
             patch("db.repo_logs.get_table_columns", return_value=_make_table_columns()):
            registrar_log_aposta(
                usuario_id=1,
                prova_id=2,
                apostador="Ana",
                pilotos="P1,P2",
                aposta="5,10",
                nome_prova="Áustria",
                piloto_11="P3",
                tipo_aposta=0,
                automatica=0,
                horario=datetime(2026, 7, 1, 12, 0, 0),
                temporada="2026",
                status="Registrada",
            )

        self.assertTrue(conn.committed)
        insert_params = cursor.executions[0][1]
        self.assertEqual(insert_params[-1], "Registrada")


class ListBettingLogsFilterTests(unittest.TestCase):
    def _run(self, cursor, **kwargs):
        conn = _Connection(cursor)
        with patch("db.db_schema.db_connect", return_value=conn), \
             patch("db.db_schema.get_table_columns", return_value=_make_table_columns()):
            return list_betting_logs("2026", scope_user_id=None, **kwargs)

    def test_bet_kind_late_filters_tipo_aposta_1(self):
        cursor = _Cursor([
            {"total": 1},
            [{"id": 1, "tipo_aposta": 1, "automatica": 0, "status": "Não efetiva"}],
        ])
        self._run(cursor, bet_kind="late")
        count_sql = cursor.executions[0][0]
        self.assertIn("tipo_aposta = 1", count_sql)

    def test_bet_kind_automatic_filters_automatica_gt_0(self):
        cursor = _Cursor([
            {"total": 1},
            [{"id": 1, "tipo_aposta": 0, "automatica": 1, "status": "Registrada"}],
        ])
        self._run(cursor, bet_kind="automatic")
        count_sql = cursor.executions[0][0]
        self.assertIn("COALESCE(automatica, 0) > 0", count_sql)

    def test_bettor_contains_applies_like_filter(self):
        cursor = _Cursor([
            {"total": 1},
            [{"id": 1, "tipo_aposta": 0, "automatica": 0, "status": "Registrada"}],
        ])
        self._run(cursor, bettor_contains="Ana")
        count_sql, count_params = cursor.executions[0]
        self.assertIn("LOWER(COALESCE(apostador, '')) LIKE %s", count_sql)
        self.assertIn("%ana%", count_params)

    def test_log_status_filter_applies_status_predicate(self):
        cursor = _Cursor([
            {"total": 1},
            [{"id": 1, "tipo_aposta": 1, "automatica": 0, "status": "Não efetiva"}],
        ])
        self._run(cursor, log_status="Não efetiva")
        count_sql, count_params = cursor.executions[0]
        self.assertIn("status = %s", count_sql)
        self.assertIn("Não efetiva", count_params)

    def test_event_date_filter_applies_date_predicate(self):
        cursor = _Cursor([
            {"total": 1},
            [{"id": 1, "tipo_aposta": 0, "automatica": 0, "status": "Registrada"}],
        ])
        self._run(cursor, event_date=date(2026, 7, 1))
        count_sql, count_params = cursor.executions[0]
        self.assertIn("SUBSTR(CAST(data AS TEXT), 1, 10) = %s", count_sql)
        self.assertIn("2026-07-01", count_params)


class BackfillStatusNaoEfetivaTests(unittest.TestCase):
    def test_backfill_updates_late_bets_to_nao_efetiva(self):
        cursor = _Cursor([{"updated": 3}])
        conn = _Connection(cursor)

        with patch("db.migrations.get_pool") as mock_pool, \
             patch("db.migrations.table_exists", return_value=True), \
             patch("db.migrations.get_table_columns", return_value={"status", "tipo_aposta"}):
            mock_pool.return_value.get_connection.return_value.__enter__ = lambda _: conn
            mock_pool.return_value.get_connection.return_value.__exit__ = lambda *args: False
            backfill_log_apostas_status_nao_efetiva()

        self.assertTrue(conn.committed)
        update_sql, update_params = cursor.executions[0]
        self.assertIn("UPDATE log_apostas", update_sql)
        self.assertIn("SET status = 'Não efetiva'", update_sql)
        self.assertIn("tipo_aposta = 1", update_sql)


if __name__ == "__main__":
    unittest.main()
