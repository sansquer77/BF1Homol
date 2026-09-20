import unittest

from utils.performance import instrumented_cache_data
from utils.ttl_cache import clear_all_caches


class PerformanceCacheNamespaceTests(unittest.TestCase):
    def test_funcoes_com_mesmos_argumentos_nao_compartilham_valores(self):
        clear_all_caches()
        try:
            @instrumented_cache_data(ttl=60)
            def participantes(temporada):
                return f"participantes-{temporada}"

            @instrumented_cache_data(ttl=60)
            def provas(temporada):
                return f"provas-{temporada}"

            self.assertEqual(participantes("2026"), "participantes-2026")
            self.assertEqual(provas("2026"), "provas-2026")
        finally:
            clear_all_caches()


if __name__ == "__main__":
    unittest.main()
