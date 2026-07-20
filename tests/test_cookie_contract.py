import ast
from pathlib import Path
import unittest


class CookieContractTests(unittest.TestCase):
    def test_every_session_cookie_write_has_full_security_contract(self):
        source = (Path(__file__).parents[1] / "services" / "auth_service.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        writes = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "set":
                continue
            if len(node.args) < 2 or not isinstance(node.args[0], ast.Constant) or node.args[0].value != "session_token":
                continue
            writes.append(node)
            options_kw = next((kw.value for kw in node.keywords if kw.arg == "options"), None)
            expires_kw = next((kw.value for kw in node.keywords if kw.arg == "expires_at"), None)
            self.assertIsNotNone(expires_kw)
            self.assertIsInstance(options_kw, ast.Dict)
            options = {key.value: value.value for key, value in zip(options_kw.keys, options_kw.values)}
            self.assertEqual(options, {"path": "/", "secure": True, "httponly": True, "samesite": "Strict"})
        self.assertEqual(len(writes), 2, "Emissao e expiracao devem compartilhar o contrato completo.")

    def test_no_permissive_cookie_fallback_exists(self):
        source = (Path(__file__).parents[1] / "services" / "auth_service.py").read_text(encoding="utf-8")
        self.assertNotIn("_FallbackCookieManager", source)
        self.assertNotIn("except TypeError", source)

