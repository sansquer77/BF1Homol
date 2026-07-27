import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-thirty-two-bytes")

from ui import oidc_auth


class OidcSessionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.st = SimpleNamespace(
            user=SimpleNamespace(is_logged_in=True, email="ANA@EXAMPLE.COM"),
            session_state={},
        )

    def test_trusted_identity_rehydrates_internal_session(self):
        user = {
            "id": 12, "nome": "Ana", "email": "ana@example.com",
            "perfil": "admin", "status": "Ativo",
        }
        with (
            patch.dict(os.environ, {"OIDC_AUTH_ENABLED": "true"}),
            patch.object(oidc_auth, "get_user_by_email", return_value=user) as lookup,
            patch.object(oidc_auth, "create_token", return_value="jwt-revogavel") as create,
        ):
            restored = oidc_auth.rehydrate_oidc_session(self.st)

        self.assertTrue(restored)
        lookup.assert_called_once_with("ana@example.com")
        create.assert_called_once_with(
            user_id=12, nome="Ana", perfil="admin", status="Ativo",
        )
        self.assertEqual(self.st.session_state["token"], "jwt-revogavel")
        self.assertEqual(self.st.session_state["pagina"], "Painel do Participante")

    def test_unknown_oidc_identity_is_not_auto_provisioned(self):
        with (
            patch.dict(os.environ, {"OIDC_AUTH_ENABLED": "true"}),
            patch.object(oidc_auth, "get_user_by_email", return_value=None),
            patch.object(oidc_auth, "create_token") as create,
        ):
            restored = oidc_auth.rehydrate_oidc_session(self.st)

        self.assertFalse(restored)
        self.assertNotIn("token", self.st.session_state)
        create.assert_not_called()

    def test_feature_disabled_does_not_read_identity(self):
        with patch.dict(os.environ, {"OIDC_AUTH_ENABLED": "false"}):
            self.assertFalse(oidc_auth.rehydrate_oidc_session(self.st))
        self.assertEqual(self.st.session_state, {})


if __name__ == "__main__":
    unittest.main()
