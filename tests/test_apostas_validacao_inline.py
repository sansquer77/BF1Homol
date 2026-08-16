import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _carregar_avisos_inline():
    source = (ROOT / "ui" / "painel.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    funcoes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_avisos_inline_aposta"
    ]
    namespace = {}
    exec(compile(ast.Module(body=funcoes, type_ignores=[]), "ui/painel.py", "exec"), namespace)
    return namespace["_avisos_inline_aposta"]


_avisos_inline_aposta = _carregar_avisos_inline()

EQUIPES = {"Verstappen": "Red Bull", "Perez": "Red Bull", "Hamilton": "Mercedes"}


class ApostasValidacaoInlineTests(unittest.TestCase):
    """Validação inline da grade de aposta.

    spec: apostas-de-prova v1.2 — critério 10
    """

    def test_avisa_piloto_repetido_com_numeros_de_linha(self):
        avisos = _avisos_inline_aposta(
            ["Verstappen", "Hamilton", "Verstappen"], EQUIPES, permite_mesma_equipe=True
        )
        self.assertIn("Linhas 1, 3: piloto repetido (Verstappen).", avisos)

    def test_avisa_mesma_equipe_quando_proibida(self):
        avisos = _avisos_inline_aposta(
            ["Verstappen", "Perez"], EQUIPES, permite_mesma_equipe=False
        )
        self.assertIn("Linhas 1, 2: mesma equipe (Red Bull).", avisos)

    def test_nao_avisa_mesma_equipe_quando_permitida(self):
        avisos = _avisos_inline_aposta(
            ["Verstappen", "Perez"], EQUIPES, permite_mesma_equipe=True
        )
        self.assertEqual(avisos, [])

    def test_linhas_ninguem_ignoradas(self):
        avisos = _avisos_inline_aposta(
            ["Nenhum", "Verstappen", "Nenhum", "Verstappen"], EQUIPES, permite_mesma_equipe=True
        )
        self.assertIn("Linhas 2, 4: piloto repetido (Verstappen).", avisos)

    def test_sem_violacoes_retorna_vazio(self):
        avisos = _avisos_inline_aposta(
            ["Verstappen", "Hamilton", "Nenhum"], EQUIPES, permite_mesma_equipe=False
        )
        self.assertEqual(avisos, [])

    def test_painel_exibe_avisos_inline_no_render(self):
        fonte = (ROOT / "ui" / "painel.py").read_text(encoding="utf-8")
        self.assertIn("_avisos_inline_aposta(pilotos_aposta, pilotos_equipe, permite_mesma_equipe)", fonte)
        self.assertIn('if piloto_11 in pilotos_com_ficha:', fonte)
        self.assertIn('st.warning(f"O 11º colocado ({piloto_11}) está entre os pilotos apostados.")', fonte)


if __name__ == "__main__":
    unittest.main()