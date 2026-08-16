import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TELAS_CONSULTA = [
    "ui/classificacao.py",
    "ui/calendario.py",
    "ui/analysis.py",
    "ui/gestao_apostas.py",
    "ui/log_apostas.py",
    "ui/gestao_provas.py",
    "ui/painel.py",
    "ui/championship_bets.py",
    "ui/championship_results.py",
    "ui/gestao_resultados.py",
]

KEYS_ANTIGAS = [
    "classificacao_season",
    "calendario_temporada",
    "analysis_season",
    "gestao_apostas_season",
    "log_apostas_season",
    "resultados_temporada",
    "gestao_provas_temporada",
]


class TemporadaGlobalTests(unittest.TestCase):
    """Seletor global de temporada na sidebar.

    spec: temporada-global v1.0 — critérios 1, 2 e 4
    """

    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT / "main.py").read_text(encoding="utf-8")

    def test_sidebar_tem_seletor_global(self):
        self.assertIn('st.sidebar.markdown("### Temporada")', self.main)
        self.assertIn("season_options_global = get_season_options(fallback_years=[\"2025\", \"2026\"])", self.main)
        self.assertIn('st.sidebar.selectbox(\n            "Temporada",\n            season_options_global,', self.main)
        self.assertIn('key="temporada_global"', self.main)

    def test_telas_de_consulta_leem_o_global(self):
        for rel in TELAS_CONSULTA:
            fonte = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("temporada_global", fonte, rel)
            if rel == "ui/gestao_provas.py":
                # Campos de edição/criação de prova permanecem locais (critério 4).
                self.assertNotIn('key="gestao_provas_temporada"', fonte)
            else:
                self.assertNotIn('st.selectbox("Temporada"', fonte, rel)

    def test_keys_antigas_de_temporada_removidas(self):
        for rel in TELAS_CONSULTA:
            fonte = (ROOT / rel).read_text(encoding="utf-8")
            for key in KEYS_ANTIGAS:
                self.assertNotIn(key, fonte, rel)

    def test_campos_de_entrada_de_dados_permanecem_locais(self):
        fonte_provas = (ROOT / "ui" / "gestao_provas.py").read_text(encoding="utf-8")
        self.assertIn('key="nova_temporada_prova"', fonte_provas)

    def test_seletor_global_nao_quebra_timezone(self):
        self.assertIn('key="timezone_selector"', self.main)


if __name__ == "__main__":
    unittest.main()