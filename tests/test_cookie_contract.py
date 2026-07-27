from pathlib import Path
import unittest


class CookieContractTests(unittest.TestCase):
    def test_no_client_side_auth_cookie_is_written(self):
        source = (Path(__file__).parents[1] / "ui" / "auth_transport.py").read_text(encoding="utf-8")
        self.assertNotIn("CookieManager", source)
        self.assertNotIn("session_token", source)
        self.assertNotIn("extra_streamlit_components", source)

    def test_persistence_uses_native_oidc(self):
        source = (Path(__file__).parents[1] / "ui" / "oidc_auth.py").read_text(encoding="utf-8")
        self.assertIn("st_module.login()", source)
        self.assertIn("st_module.logout()", source)
        self.assertIn("get_user_by_email(email)", source)
