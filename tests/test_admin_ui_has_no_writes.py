from pathlib import Path
import ast
import unittest


ADMIN_UI = (
    "gestao_provas.py",
    "gestao_pilotos.py",
    "gestao_resultados.py",
    "usuarios.py",
    "hall_da_fama.py",
    "championship_results.py",
    "gestao_regras.py",
    "gestao_apostas.py",
    "backup.py",
)
MUTATIONS = {"INSERT", "UPDATE", "DELETE", "TRUNCATE", "ALTER", "CREATE"}


class AdminUiBoundariesTests(unittest.TestCase):
    def test_admin_ui_contains_no_sql_mutation(self):
        ui = Path(__file__).parents[1] / "ui"
        violations = []
        for name in ADMIN_UI:
            tree = ast.parse((ui / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr not in {"execute", "executemany"} or not node.args:
                    continue
                sql = node.args[0]
                if isinstance(sql, ast.Constant) and isinstance(sql.value, str):
                    first = sql.value.lstrip().split(None, 1)[0].upper()
                    if first in MUTATIONS:
                        violations.append(f"{name}:{node.lineno}")
        self.assertFalse(violations, f"SQL administrativo encontrado na UI: {violations}")
