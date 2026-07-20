from pathlib import Path
import unittest


class LoginCookieFallbackTests(unittest.TestCase):
    def test_cookie_failure_does_not_revoke_new_login(self):
        source = (Path(__file__).parents[1] / "ui" / "login.py").read_text(encoding="utf-8")
        start = source.index("try:\n                set_auth_cookies(token)")
        end = source.index("# Registrar sucesso", start)
        cookie_failure_block = source[start:end]
        self.assertNotIn("revoke_token(token)", cookie_failure_block)
        self.assertNotIn("return", cookie_failure_block)
        self.assertIn("sessao Streamlit revogavel", cookie_failure_block)

