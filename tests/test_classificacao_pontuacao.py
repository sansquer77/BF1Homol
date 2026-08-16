import ast
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


def _carregar_funcoes_classificacao():
    source = (Path(__file__).resolve().parents[1] / "ui" / "classificacao.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    nomes = {
        "_calcular_descartes_atuais",
        "_cor_fundo_heatmap",
        "_montar_pontos_por_prova",
        "destacar_heatmap",
        "formatar_brasileiro",
        "_calcular_totais_classificacao",
        "_colunas_classificacao",
    }
    funcoes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in nomes]
    namespace = {"pd": pd, "np": np}
    exec(compile(ast.Module(body=funcoes, type_ignores=[]), "ui/classificacao.py", "exec"), namespace)
    return tuple(namespace[nome] for nome in sorted(nomes))


(
    _calcular_descartes_atuais,
    _calcular_totais_classificacao,
    _colunas_classificacao,
    _cor_fundo_heatmap,
    _montar_pontos_por_prova,
    destacar_heatmap,
    formatar_brasileiro,
) = _carregar_funcoes_classificacao()


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

        # spec: polimento-de-interface v1.0 — critério 2
        # Escala suave: Bruno tem 200 (máximo → verde claro) e Ana 100
        # (mínimo → vermelho claro) na Austrália; texto escuro legível.
        self.assertIn(("background-color", "rgb(205,255,205)"), contexto[(0, 0)])
        self.assertIn(("background-color", "rgb(255,205,205)"), contexto[(0, 1)])
        self.assertNotIn((1, 0), contexto)
        self.assertNotIn((1, 1), contexto)

    def test_descarte_considera_apenas_provas_com_resultado(self):
        apostas = pd.concat([
            self.apostas,
            pd.DataFrame([
                {"usuario_id": 1, "prova_id": 30, "__pontos_calculados": -50},
            ]),
        ], ignore_index=True)
        resultados = pd.DataFrame([{"prova_id": 10}, {"prova_id": 20}])

        descartes = _calcular_descartes_atuais(apostas, resultados, self.provas)

        self.assertEqual(descartes[1]["prova"], "China")
        self.assertEqual(descartes[1]["pontos"], 0)
        self.assertEqual(descartes[2]["pontos"], 0)

    def test_descarte_aceita_pontuacao_negativa(self):
        apostas = pd.DataFrame([
            {"usuario_id": 1, "prova_id": 10, "__pontos_calculados": 20},
            {"usuario_id": 1, "prova_id": 20, "__pontos_calculados": -10},
        ])
        resultados = pd.DataFrame([{"prova_id": 10}, {"prova_id": 20}])

        descartes = _calcular_descartes_atuais(apostas, resultados, self.provas)

        self.assertEqual(descartes[1]["prova"], "China")
        self.assertEqual(descartes[1]["pontos"], -10)

    def test_total_valido_soma_bonus_e_subtrai_descarte(self):
        totais = _calcular_totais_classificacao(2906, 125, 100, 85, 109)

        self.assertEqual(totais["Total Geral"], 2906)
        self.assertEqual(totais["Bônus Campeonato"], 310)
        self.assertEqual(totais["Descarte"], 109)
        self.assertEqual(totais["Total Válido"], 3107)

    def test_ordem_das_colunas_da_classificacao(self):
        self.assertEqual(
            _colunas_classificacao(True),
            [
                "Posição", "Participante", "Total Geral", "Bônus Campeão",
                "Bônus Vice", "Bônus Equipe", "Descarte", "Total Válido",
                "Diferença", "Movimentação",
            ],
        )


if __name__ == "__main__":
    unittest.main()
