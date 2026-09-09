import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _carregar_layout_imagem():
    source = (ROOT / "ui" / "classificacao.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    nomes = {
        "_IMAGE_DPI",
        "_IMAGE_MAX_WIDTH_IN",
        "_IMAGE_MAX_HEIGHT_IN",
        "_IMAGE_MAX_PIXELS",
    }
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in nomes for target in node.targets
        ))
        or (isinstance(node, ast.FunctionDef) and node.name == "_calcular_layout_imagem")
    ]
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "ui/classificacao.py", "exec"), namespace)
    return namespace


def _carregar_layout_imagem_v4():
    source = (ROOT / "services" / "classification_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_PNG_COLUMN_WIDTHS" for target in node.targets)
    ]
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "services/classification_service.py", "exec"), namespace)
    return source, namespace


class ClassificacaoImagemTests(unittest.TestCase):
    def test_png_v4_prioriza_participante_e_inclui_logo_oficial(self):
        source, namespace = _carregar_layout_imagem_v4()
        widths = namespace["_PNG_COLUMN_WIDTHS"]

        self.assertAlmostEqual(sum(widths), 1.0)
        self.assertGreater(widths[1], max(widths[2:]))
        self.assertIn('root / "BF1 2.0.png"', source)
        self.assertIn("logo_axis.imshow", source)

    def test_layout_extenso_respeita_limites_de_canvas(self):
        ns = _carregar_layout_imagem()
        largura, altura, dpi = ns["_calcular_layout_imagem"](
            500,
            1000,
            largura_minima=16.0,
            altura_minima=4.8,
            fator_largura=0.14,
        )

        self.assertLessEqual(largura, ns["_IMAGE_MAX_WIDTH_IN"])
        self.assertLessEqual(altura, ns["_IMAGE_MAX_HEIGHT_IN"])
        self.assertLessEqual(largura * altura * dpi * dpi, ns["_IMAGE_MAX_PIXELS"])

    def test_exportacao_fecha_figura_mesmo_em_erro(self):
        source = (ROOT / "ui" / "classificacao.py").read_text(encoding="utf-8")

        self.assertEqual(source.count("finally:\n        plt.close(fig)"), 2)
        self.assertNotIn("dpi=320", source)
        self.assertNotIn("plt.savefig(", source)


if __name__ == "__main__":
    unittest.main()
