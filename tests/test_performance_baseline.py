import json
import os
import unittest
from unittest.mock import patch

from scripts.performance_benchmark import assert_safe_copy, database_identity
from scripts.performance_report import aggregate, iter_events
from utils.performance import (
    journey,
    promote_current_journey,
    record_cache,
    record_processed_rows,
    record_query,
    record_rows,
)


class PerformanceJourneyTests(unittest.TestCase):
    def test_jornada_promovida_emite_todas_as_metricas(self):
        with patch.dict(os.environ, {"PERFORMANCE_METRICS_ENABLED": "1"}):
            with self.assertLogs("bf1.performance", level="INFO") as captured:
                with journey("abertura_painel", page="Painel do Participante"):
                    promote_current_journey("historico", section="historico_consolidado")
                    record_query("SELECT * FROM apostas WHERE usuario_id = %s", 0.012)
                    record_rows(7)
                    record_processed_rows(7)
                    record_cache(True)
                    record_cache(False)

        payload = json.loads(captured.output[-1][captured.output[-1].find("{"):])
        self.assertEqual(payload["journey"], "historico")
        self.assertEqual(payload["query_count"], 1)
        self.assertEqual(payload["db_time_ms"], 12.0)
        self.assertEqual(payload["rows_fetched"], 7)
        self.assertEqual(payload["rows_processed"], 7)
        self.assertEqual(payload["cache_hits"], 1)
        self.assertEqual(payload["cache_misses"], 1)
        self.assertEqual(payload["section"], "historico_consolidado")
        self.assertIn("usuario_id", next(iter(payload["query_fingerprints"])))
        self.assertNotIn("segredo", next(iter(payload["query_fingerprints"])))

    def test_instrumentacao_pode_ser_desativada(self):
        with patch.dict(os.environ, {"PERFORMANCE_METRICS_ENABLED": "0"}):
            with self.assertNoLogs("bf1.performance", level="INFO"):
                with journey("classificacao"):
                    record_query("SELECT 1", 0.001)


class PerformanceReportTests(unittest.TestCase):
    def test_agrega_p95_cache_e_volume(self):
        lines = [
            'prefixo {"event":"journey_performance","journey":"login","duration_ms":100,"query_count":1,"db_time_ms":20,"rows_fetched":1,"rows_processed":1,"cache_hits":0,"cache_misses":1,"success":true}',
            '{"event":"journey_performance","journey":"login","duration_ms":300,"query_count":2,"db_time_ms":40,"rows_fetched":2,"rows_processed":2,"cache_hits":1,"cache_misses":0,"success":true}',
            "linha sem JSON",
        ]
        report = aggregate(iter_events(lines))
        login = report["journeys"]["login"]
        self.assertEqual(report["event_count"], 2)
        self.assertEqual(login["p50_ms"], 200.0)
        self.assertEqual(login["p95_ms"], 300.0)
        self.assertEqual(login["avg_query_count"], 1.5)
        self.assertEqual(login["cache_hit_rate"], 0.5)


class SafeBenchmarkTests(unittest.TestCase):
    def test_identidade_ignora_senha_e_opcoes(self):
        first = "postgresql://usuario:senha-a@db.example:5432/bf1?sslmode=require"
        second = "postgresql://usuario:senha-b@DB.EXAMPLE/bf1?application_name=x"
        self.assertEqual(database_identity(first), database_identity(second))

    def test_exige_confirmacao_explicita(self):
        with self.assertRaises(SystemExit):
            assert_safe_copy("postgresql://u:p@copy.example/bf1", "", False)

    def test_recusa_mesma_identidade_de_producao(self):
        with self.assertRaises(SystemExit):
            assert_safe_copy(
                "postgresql://usuario:outra@db.example/bf1?sslmode=require",
                "postgresql://usuario:segredo@db.example:5432/bf1",
                True,
            )


if __name__ == "__main__":
    unittest.main()
