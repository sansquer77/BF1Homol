import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MenuNavigationTests(unittest.TestCase):
    def test_sidebar_nao_usa_navegacao_em_dois_niveis(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertNotIn('key="menu_secao"', source)
        self.assertNotIn('key="menu_lateral"', source)
        self.assertNotIn('"Seção",', source)

    def test_sidebar_renderiza_secoes_como_expansores(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("st.sidebar.expander(section_name, expanded=expanded)", source)
        self.assertIn("if st.button(", source)

    # spec: menu-e-navegacao v1.5 — critério 8
    def test_menu_em_texto_sem_bordas_e_compacto_no_mobile(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("render_dom_styles(", source)
        self.assertIn('button[data-testid="stBaseButton-secondary"]', source)
        self.assertIn('"background": "transparent"', source)
        self.assertIn('"border": "none"', source)
        self.assertIn('"overflowY": "auto"', source)
        self.assertIn('"media": "(max-width: 768px)"', source)
        self.assertIn('"minHeight": "1.9rem"', source)

    def test_grupos_do_menu_sem_retangulo_de_expansor(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('[data-testid="stSidebar"] [data-testid="stExpander"]', source)
        self.assertIn('[data-testid="stSidebar"] [data-testid="stExpanderDetails"]', source)
        self.assertIn('stBaseButton-headerNoPadding', source)
        self.assertIn('"boxShadow": "none"', source)
        self.assertIn('stExpander"]:hover', source)

    def test_dom_styles_aplica_inline_com_observer_e_escapa_rules(self):
        source = (ROOT / "utils" / "html_utils.py").read_text(encoding="utf-8")
        self.assertIn("setProperty(k,rule.style[k],", source)
        self.assertIn("MutationObserver", source)
        self.assertIn("matchMedia", source)
        self.assertIn("serialize_js_value(rules)", source)
        self.assertTrue(
            "unsafe_allow_javascript" in source or "allow_javascript" in source,
            "o JS deve ser renderizado pelo sink central com permissão de script",
        )

    def test_itens_sao_botoes_com_primeiro_clique_navegando(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('key=f"menu_btn_{profile_key}_{section_name}_{item}"', source)
        self.assertIn('label = f"▶ {item}" if ativo else item', source)
        self.assertNotIn('st.radio(', source)
        self.assertNotIn('menu_applied_', source)
        self.assertNotIn('menu_radio_', source)

    def test_itens_por_perfil_permanecem_agrupados(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        for fn in (
            "grouped_menu_master",
            "grouped_menu_admin",
            "grouped_menu_participante",
            "grouped_menu_inativo",
        ):
            self.assertIn(f"def {fn}(", source)
        self.assertIn("_normalize_grouped_menu(menu_items, grouped_menu)", source)
        self.assertIn('has_logout = "Logout" in menu_items', source)

    def test_secao_ativa_e_persistida_para_expansao(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('last_section_key = f"menu_secao_last_{profile_key}"', source)
        self.assertIn("default_section = persisted_section if persisted_section in grouped_menu", source)
        self.assertIn('expanded = section_name == default_section', source)

    def test_guard_de_rotas_e_timezone_permanecem(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("_enforce_route_guard(pagina)", source)
        self.assertIn('st.sidebar.selectbox(', source)


if __name__ == "__main__":
    unittest.main()