import unittest
from unittest.mock import patch

from utils.pagination import paginate


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


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class PaginationIntegrationTests(unittest.TestCase):
    def test_page_is_clamped_after_last_item_is_removed(self):
        page = paginate(page=9, page_size=50, total_items=51)
        self.assertEqual(page.page, 2)
        self.assertEqual(page.total_pages, 2)
        self.assertEqual(page.offset, 50)

    def test_access_log_count_and_page_share_filters(self):
        from ui import log_acessos

        cursor = _Cursor([
            {"total": 101, "successes": 80, "failures": 21},
            [{"id": 1, "created_at": None, "evento": "login", "sucesso": True}],
        ])
        with patch.object(log_acessos, "db_connect", return_value=_Connection(cursor)):
            result = log_acessos._load_access_logs(
                __import__("datetime").date(2026, 1, 1),
                __import__("datetime").date(2026, 1, 31),
                "admin", "login", "Sucesso", "10.", "ana",
                limit=50, offset=50,
            )

        self.assertEqual(result.total, 101)
        self.assertEqual(result.successes, 80)
        self.assertEqual(len(result.rows), 1)
        self.assertIn("COUNT(*) FILTER", cursor.executions[0][0])
        self.assertEqual(cursor.executions[1][1][-2:], (50, 50))
        self.assertEqual(cursor.executions[0][1], cursor.executions[1][1][:-2])

    def test_betting_filters_are_applied_before_limit(self):
        from ui import log_apostas

        cursor = _Cursor([
            {"total": 1},
            [{
                "id": 7, "usuario_id": 4, "data": "2026-07-01",
                "horario": None, "apostador": "Ana", "nome_prova": "Áustria",
                "pilotos": "", "aposta": "", "piloto_11": "",
                "tipo_aposta": 1, "automatica": 1, "ip_address": None,
                "temporada": "2026", "status": "Registrada",
            }],
        ])
        with (
            patch.object(log_apostas, "db_connect", return_value=_Connection(cursor)),
            patch.object(
                log_apostas,
                "get_table_columns",
                return_value={
                    "status", "ip_address", "usuario_id", "temporada",
                    "data", "data_criacao",
                },
            ),
        ):
            result = log_apostas.carregar_logs(
                "2026", usuario_id=4, is_admin=True, apostador="ana",
                tipo_aposta=1, data="2026-07-01", status="Registrada",
                apenas_automaticas=True, limit=25, offset=25,
            )

        count_sql, count_params = cursor.executions[0]
        self.assertEqual(result.total, 1)
        self.assertIn("LOWER(COALESCE(apostador, '')) LIKE %s", count_sql)
        self.assertIn("COALESCE(automatica, 0) > 0", count_sql)
        self.assertEqual(count_params, cursor.executions[1][1][:-2])
        self.assertEqual(cursor.executions[1][1][-2:], (25, 25))


if __name__ == "__main__":
    unittest.main()
