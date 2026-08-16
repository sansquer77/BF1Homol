import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TimezonePreferenceTests(unittest.TestCase):
    def test_escolha_manual_e_persistida_e_prevalece_sobre_detector(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        self.assertIn('_TZ_SOURCE_MANUAL = "manual"', source)
        self.assertIn('st.query_params[_TZ_SOURCE_PARAM] = _TZ_SOURCE_MANUAL', source)
        self.assertIn('if ({timezone_source_js} === {manual_source_js}) return;', source)
        self.assertIn('params.set({source_param_js}, {auto_source_js});', source)

        reruns = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "rerun"
        ]
        self.assertTrue(reruns, "A alteração manual deve concluir com rerun controlado da UI.")

    # spec: pwa-e-preferencias-do-cliente v1.1 — critério 8
    def test_agenda_exibe_no_fuso_selecionado(self):
        source = (ROOT / "ui" / "calendario.py").read_text(encoding="utf-8")
        self.assertIn('"timezone": tz_exibicao', source)
        self.assertNotIn('"timezone": "local"', source)


if __name__ == "__main__":
    unittest.main()
