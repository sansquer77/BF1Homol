import unittest
from unittest.mock import patch

import streamlit as st

from utils.performance import instrumented_cache_data


class PerformanceCacheNamespaceTests(unittest.TestCase):
    def test_funcoes_com_mesmos_argumentos_nao_compartilham_valores(self):
        shared_cache = {}

        def fake_cache_data(*, ttl, show_spinner):
            del ttl, show_spinner

            def decorate(func):
                def cached(*args, **kwargs):
                    key = (args, tuple(sorted(kwargs.items())))
                    if key not in shared_cache:
                        shared_cache[key] = func(*args, **kwargs)
                    return shared_cache[key]

                cached.clear = shared_cache.clear
                return cached

            return decorate

        with patch.object(st, "cache_data", fake_cache_data):
            @instrumented_cache_data(ttl=60)
            def participantes(temporada):
                return f"participantes-{temporada}"

            @instrumented_cache_data(ttl=60)
            def provas(temporada):
                return f"provas-{temporada}"

            self.assertEqual(participantes("2026"), "participantes-2026")
            self.assertEqual(provas("2026"), "provas-2026")


if __name__ == "__main__":
    unittest.main()
