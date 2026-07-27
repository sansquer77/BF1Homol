import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LazyScreenLoadingTests(unittest.TestCase):
    def test_main_nao_importa_todas_as_telas_no_startup(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        eager_ui_imports = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("ui."):
                eager_ui_imports.append(node.module)
        self.assertEqual(eager_ui_imports, ["ui.auth_transport", "ui.oidc_auth"])
        self.assertIn("def _load_view(page: str)", source)
        self.assertIn("import_module(module_name)", source)

    def test_painel_executa_apenas_secao_ativa(self):
        source = (ROOT / "ui" / "painel.py").read_text(encoding="utf-8")
        self.assertNotIn("tabs = st.tabs(tab_labels)", source)
        self.assertIn('active_section = st.radio(', source)
        self.assertIn('show_apostas_tab and active_section == "Apostas"', source)
        self.assertIn('active_section == f"Apostas - {season}"', source)
        self.assertIn('active_section == "Histórico"', source)
        self.assertIn('active_section == "Minha Conta"', source)

    def test_historico_anual_calcula_somente_prova_selecionada(self):
        source = (ROOT / "ui" / "painel.py").read_text(encoding="utf-8")
        self.assertIn('aposta_detalhe = st.selectbox(', source)
        self.assertIn("apostas_part.iloc[[detalhe_index]].iterrows()", source)
        self.assertNotIn("abas = st.tabs(nomes_abas)", source)

    def test_matplotlib_e_carregado_somente_na_geracao_de_imagem(self):
        source = (ROOT / "ui" / "classificacao.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        top_level_modules = {
            node.module
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module
        }
        top_level_names = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("matplotlib.pyplot", top_level_names)
        self.assertNotIn("matplotlib.offsetbox", top_level_modules)
        self.assertGreaterEqual(source.count("import matplotlib.pyplot as plt"), 2)


if __name__ == "__main__":
    unittest.main()
