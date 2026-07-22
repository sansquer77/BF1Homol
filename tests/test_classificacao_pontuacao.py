import ast
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


def _carregar_funcoes_classificacao():
    source = (Path(__file__).resolve().parents[1] / "ui" / "classificacao.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    nomes = {"_montar_pontos_por_prova", "destacar_heatmap", "formatar_brasileiro"}
    funcoes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in nomes]
    namespace = {"pd": pd, "np": np}
    exec(compile(ast.Module(body=funcoes, type_ignores=[]), "ui/classificacao.py", "exec"), namespace)
    return tuple(namespace[nome] for nome in sorted(nomes))


_montar_pontos_por_prova, destacar_heatmap, formatar_brasileiro = _carregar_funcoes_classificacao()


class ClassificacaoPontuacaoTests(unittest.TestCase):
    def setUp(self):
        self.apostas = pd.DataFrame(
            [
                {"usuario_id": 1, "prova_id": 10, "__pontos_calculados": 100},
                {"usuario_id": 2, "prova_id": 10, "__pontos_calculados": 200},
                {"usuario_id": 1, "prova_id": 20, "__pontos_calculados": 0},
                {"usuario_id": 2, "prova_id": 20, "__pontos_calculados": 0},
            ]
        )
        self.classificacao = pd.DataFrame(
            [
                {"usuario_id": 2, "Participante": "Bruno"},
                {"usuario_id": 1, "Participante": "Ana"},
            ]
        )
        self.provas = pd.DataFrame(
            [
                {"id": 10, "nome": "Austrália"},
                {"id": 20, "nome": "China"},
            ]
        )

    def test_grade_mantem_provas_nas_linhas_e_participantes_nas_colunas(self):
        grade = _montar_pontos_por_prova(self.apostas, self.classificacao, self.provas)

        self.assertEqual(grade.index.tolist(), ["Austrália", "China"])
        self.assertEqual(grade.columns.tolist(), ["Bruno", "Ana"])
        self.assertEqual(grade.index.name, "Prova")

    def test_heatmap_colore_somente_prova_realizada(self):
        grade = _montar_pontos_por_prova(self.apostas, self.classificacao, self.provas)
        formatada = grade.map(lambda valor: formatar_brasileiro(float(valor)))
        resultados = pd.DataFrame([{"prova_id": 10}])

        contexto = destacar_heatmap(formatada, resultados, [10, 20])._compute().ctx

        # Bruno tem 200 (maior/verde) e Ana 100 (menor/vermelho) na Austrália.
        self.assertIn(("background-color", "rgb(0,255,0)"), contexto[(0, 0)])
        self.assertIn(("background-color", "rgb(255,0,0)"), contexto[(0, 1)])
        self.assertNotIn((1, 0), contexto)
        self.assertNotIn((1, 1), contexto)


if __name__ == "__main__":
    unittest.main()
