import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrameworkBoundaryTests(unittest.TestCase):
    def test_production_sources_do_not_contain_numbered_copies(self):
        violations = []
        production_roots = ("api", "services", "db", "utils", "frontend/src")
        source_suffixes = {".py", ".ts", ".tsx", ".js", ".jsx"}
        for layer in production_roots:
            for path in (ROOT / layer).glob("**/*"):
                if path.suffix not in source_suffixes:
                    continue
                stem_suffix = path.stem.rsplit(" ", 1)
                if len(stem_suffix) == 2 and stem_suffix[1].isdigit():
                    violations.append(str(path.relative_to(ROOT)))
        self.assertEqual(violations, [])

    def test_internal_layers_do_not_import_streamlit(self):
        violations = []
        for layer in ("services", "db", "utils"):
            for path in (ROOT / layer).glob("**/*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        names = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        names = [node.module or ""]
                    else:
                        continue
                    if any(name == "streamlit" or name.startswith("streamlit.") for name in names):
                        violations.append(str(path.relative_to(ROOT)))
        self.assertEqual(violations, [])

    def test_legacy_cookie_component_is_absent(self):
        violations = []
        for layer in ("api", "services", "db", "utils"):
            for path in (ROOT / layer).glob("**/*.py"):
                source = path.read_text(encoding="utf-8")
                if "extra_streamlit_components" in source:
                    violations.append(str(path.relative_to(ROOT)))
        self.assertEqual(violations, [])
