import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UiPolishTests(unittest.TestCase):
    def test_recuperacao_de_senha_em_passos_guiados(self):
        source = (ROOT / "ui" / "login.py").read_text(encoding="utf-8")
        self.assertIn('["1. Solicitar token", "2. Redefinir senha"]', source)
        self.assertIn('if passo_reset == "1. Solicitar token":', source)
        self.assertIn('key="reset_passo"', source)
        self.assertIn('st.form("forgot_password_form"', source)
        self.assertIn('st.form("forgot_password_token_form"', source)

    def test_heatmap_usa_escala_suave(self):
        source = (ROOT / "ui" / "classificacao.py").read_text(encoding="utf-8")
        self.assertIn("def _cor_fundo_heatmap(normalizado: float) -> str:", source)
        self.assertIn("_cor_fundo_heatmap(float(normalizado))", source)
        self.assertNotIn("rgb({vermelho},{verde},0)", source)

    def test_painel_sem_espacador_st_write(self):
        source = (ROOT / "ui" / "painel.py").read_text(encoding="utf-8")
        self.assertNotIn('st.write("")', source)
        self.assertIn('st.columns([6, 1.2, 1.4], vertical_alignment="center")', source)

    def test_seletor_de_timezone_com_rotulos_amigaveis(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("_TZ_LABELS: dict[str, str] = {", source)
        self.assertIn('"America/Sao_Paulo": "Brasil (São Paulo)"', source)
        self.assertIn("format_func=lambda tz: _TZ_LABELS.get(tz, tz)", source)
        self.assertIn('st.session_state["client_timezone"] = selected_tz', source)

    def test_cabecalho_compacto(self):
        source = (ROOT / "utils" / "helpers.py").read_text(encoding="utf-8")
        self.assertIn("def render_page_header(st_module: Any, title: str, logo_width: int = 55) -> None:", source)
        self.assertIn("st_module.header(title)", source)
        self.assertNotIn("st_module.title(title)", source)

    def test_saudacao_unica_pos_login(self):
        source = (ROOT / "ui" / "login.py").read_text(encoding="utf-8")
        self.assertNotIn('st.success(f"✅ Bem-vindo', source)
        self.assertIn('st.info("Seu acesso está em modo inativo e foi limitado para consulta.")', source)


if __name__ == "__main__":
    unittest.main()