import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ApostasProgressoTests(unittest.TestCase):
    """Indicador de progresso da Etapa 2 por validações concluídas.

    spec: apostas-de-prova v1.3 — critério 11
    """

    @classmethod
    def setUpClass(cls):
        cls.fonte = (ROOT / "ui" / "painel.py").read_text(encoding="utf-8")

    def test_progresso_usa_fracao_real_de_validacoes(self):
        self.assertIn("st.progress(", self.fonte)
        self.assertIn("concluidas_etapa2 / len(validacoes_etapa2)", self.fonte)
        self.assertIn('text=f"Etapa 2: {concluidas_etapa2}/{len(validacoes_etapa2)} validações concluídas"', self.fonte)

    def test_progresso_fixo_antigo_removido(self):
        self.assertNotIn("1.0 if passo2_ok else 0.67", self.fonte)
        self.assertNotIn('text="Progresso do preenchimento"', self.fonte)

    def test_validacoes_listadas_explicitamente(self):
        self.assertIn('f"Mínimo de {min_pilotos_regra} pilotos com fichas"', self.fonte)
        self.assertIn('f"Soma exata de {quantidade_fichas} fichas"', self.fonte)
        self.assertIn('"Nenhum piloto repetido"', self.fonte)
        self.assertIn('"Nenhuma equipe repetida"', self.fonte)
        self.assertIn('f"Máximo de {fichas_max_por_piloto} fichas por piloto"', self.fonte)
        self.assertIn('"11º colocado diferente dos apostados"', self.fonte)

    def test_lista_de_validacoes_com_estado(self):
        self.assertIn("for ok_etapa2, descricao in validacoes_etapa2:", self.fonte)
        self.assertIn("f\"- {'[x]' if ok_etapa2 else '[ ]'} {descricao}\"", self.fonte)

    def test_regras_do_envio_permanecem(self):
        self.assertIn('"Não é permitido apostar em dois pilotos iguais."', self.fonte)
        self.assertIn('"Não é permitido apostar em dois pilotos da mesma equipe."', self.fonte)
        self.assertIn('st.success("Aposta registrada/atualizada!")', self.fonte)


if __name__ == "__main__":
    unittest.main()