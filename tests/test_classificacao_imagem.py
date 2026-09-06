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


class ClassificacaoImagemTests(unittest.TestCase):
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
