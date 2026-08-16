import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GestaoApostasUxTests(unittest.TestCase):
    # spec: apostas-automaticas v1.1 — critério 8
    def test_tabela_resumo_e_expander_por_item(self):
        source = (ROOT / "ui" / "gestao_apostas.py").read_text(encoding="utf-8")
        self.assertIn('st.dataframe(pd.DataFrame(resumo_linhas), width="stretch", hide_index=True)', source)
        self.assertIn('st.dataframe(pd.DataFrame(resumo_part_linhas), width="stretch", hide_index=True)', source)
        self.assertIn('with st.expander(f"{prova.nome} ({prova.data} {prova.horario_prova}) — {situacao}"):', source)
        self.assertIn('with st.expander(f"{part.nome} — {situacao}"):', source)
        self.assertIn('"Situação": "Sem aposta"', source)
        self.assertNotIn('st.markdown(f"#### {prova.nome}', source)
        self.assertNotIn('st.markdown(f"##### {part.nome}', source)


if __name__ == "__main__":
    unittest.main()