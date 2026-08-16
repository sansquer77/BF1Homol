import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FONTE_PAINEL = ROOT / "ui" / "painel.py"


class ApostasGradeTests(unittest.TestCase):
    """Verificação estática da grade única de montagem da aposta.

    spec: apostas-de-prova v1.1 — critério 9
    """

    @classmethod
    def setUpClass(cls):
        cls.fonte = FONTE_PAINEL.read_text(encoding="utf-8")

    def test_formulario_usa_grade_unica(self):
        self.assertIn("editor_data = st.data_editor(", self.fonte)
        self.assertIn('key="aposta_editor_data"', self.fonte)
        self.assertIn('num_rows="fixed"', self.fonte)

    def test_grade_combina_selecao_e_distribuicao_de_fichas(self):
        self.assertIn('"Piloto": st.column_config.SelectboxColumn(', self.fonte)
        self.assertIn('options=["Nenhum"] + pilotos', self.fonte)
        self.assertIn('"Fichas": st.column_config.NumberColumn(', self.fonte)
        self.assertIn("max_value=fichas_max_por_piloto", self.fonte)

    def test_grade_preenche_aposta_existente(self):
        self.assertIn('st.session_state.pop("aposta_editor_data", None)', self.fonte)
        self.assertNotIn('st.session_state["aposta_editor_data"] =', self.fonte)
        self.assertIn('if prova_id_form != prova_id or force_reload_form:', self.fonte)
        self.assertIn("editor_data = st.data_editor(", self.fonte)
        self.assertIn("        df_form_aposta,", self.fonte)

    def test_formulario_antigo_empilhado_removido(self):
        self.assertNotIn('f"Piloto {i+1}"', self.fonte)
        self.assertNotIn('f"Fichas para {piloto_sel}"', self.fonte)
        self.assertNotIn("key_piloto = f\"piloto_aposta_{i}\"", self.fonte)

    def test_validacoes_e_persistencia_preservadas(self):
        self.assertIn('st.session_state["aposta_erros"]', self.fonte)
        self.assertIn("pilotos_com_ficha", self.fonte)
        self.assertIn("fichas_com_ficha", self.fonte)
        self.assertIn("salvar_aposta(", self.fonte)
        self.assertIn('st.success("Aposta registrada/atualizada!")', self.fonte)


if __name__ == "__main__":
    unittest.main()