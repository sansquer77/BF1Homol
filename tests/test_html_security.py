import ast
import unittest
from pathlib import Path

from utils.html_utils import escape_html_attr, escape_html_text, serialize_js_value


ROOT = Path(__file__).resolve().parents[1]


class HtmlSecurityTests(unittest.TestCase):
    def test_helpers_aplicam_escaping_contextual(self):
        payload = '\"><script>alert(1)</script>&'
        self.assertEqual(
            escape_html_text(payload),
            '\"&gt;&lt;script&gt;alert(1)&lt;/script&gt;&amp;',
        )
        self.assertNotIn('"', escape_html_attr(payload))
        self.assertNotIn("<", escape_html_attr(payload))

        serialized = serialize_js_value("</script><script>alert(1)</script>\u2028")
        self.assertNotIn("</script>", serialized)
        self.assertIn("\\u003c/script\\u003e", serialized)
        self.assertIn("\\u2028", serialized)

    def test_html_e_javascript_so_podem_ser_renderizados_pelo_sink_central(self):
        violations = []
        for path in [ROOT / "main.py", *sorted((ROOT / "ui").glob("*.py")), *sorted((ROOT / "utils").glob("*.py"))]:
            if path.name == "html_utils.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Attribute) and node.func.attr == "html":
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: chamada direta a .html")
                for keyword in node.keywords:
                    if keyword.arg in {"unsafe_allow_html", "unsafe_allow_javascript"}:
                        if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                            violations.append(
                                f"{path.relative_to(ROOT)}:{node.lineno}: {keyword.arg}=True fora do sink central"
                            )
        self.assertEqual([], violations, "\n".join(violations))

    def test_modulos_html_nao_usam_escape_disperso(self):
        violations = []
        for directory in (ROOT / "services", ROOT / "ui", ROOT / "utils"):
            for path in directory.glob("*.py"):
                if path.name == "html_utils.py":
                    continue
                source = path.read_text(encoding="utf-8")
                if "html.escape(" in source:
                    violations.append(str(path.relative_to(ROOT)))
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
