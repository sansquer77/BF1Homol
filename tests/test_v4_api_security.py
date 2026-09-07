import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from tests._db_driver_stub import install_if_needed

install_if_needed()
os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-thirty-two-bytes")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("ALLOWED_ORIGINS", "https://bf1.test")


class V4ApiSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            raise unittest.SkipTest(f"FastAPI não instalado: {exc}")
        import api.config
        importlib.reload(api.config)
        from api.main import app
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_live_health_has_versioned_contract_and_request_id(self):
        with patch("db.repo_observability.record_event"):
            response = self.client.get("/api/v1/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertTrue(response.headers["x-request-id"])

    def test_unsafe_request_rejects_missing_origin(self):
        with patch("db.repo_observability.record_event"):
            response = self.client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "secret"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("allowed_origins", response.text)

    def test_login_failure_is_indistinguishable_for_missing_and_wrong_password(self):
        from db import repo_users
        headers = {"Origin": "https://bf1.test"}
        with patch("api.routes.auth.recent_failures", return_value=(0, 0, False)), \
             patch("api.routes.auth.record_attempt"), patch("api.routes.auth.record_access"), \
             patch.object(repo_users, "get_user_by_email", side_effect=[None, {"id": 1, "email": "a@example.com", "senha_hash": "invalid", "status": "ativo"}]), \
             patch.object(repo_users, "check_password", return_value=False), \
             patch("db.repo_observability.record_event"):
            absent = self.client.post("/api/v1/auth/login", headers=headers, json={"email": "a@example.com", "password": "wrong"})
            wrong = self.client.post("/api/v1/auth/login", headers=headers, json={"email": "a@example.com", "password": "wrong"})
        self.assertEqual((absent.status_code, absent.json()["detail"]), (wrong.status_code, wrong.json()["detail"]))

    def test_password_reset_response_does_not_enumerate_users(self):
        headers = {"Origin": "https://bf1.test"}
        with patch("api.routes.auth.recent_failures", return_value=(0, 0, False)), \
             patch("api.routes.auth.record_attempt"), patch("services.auth_service.redefinir_senha_usuario", return_value=(False, "missing")), \
             patch("db.repo_observability.record_event"):
            response = self.client.post("/api/v1/auth/password-reset", headers=headers, json={"email": "missing@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Se o email estiver cadastrado", response.json()["message"])

    def test_user_object_rejects_idor_as_not_found(self):
        from api.dependencies import get_current_context
        from api.main import app
        from services.access_control import AuthenticatedContext
        app.dependency_overrides[get_current_context] = lambda: AuthenticatedContext(7, "A", "participante", "ativo", frozenset({"2026"}))
        try:
            with patch("db.repo_observability.record_event"):
                response = self.client.get("/api/v1/users/8")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["detail"], "Recurso não encontrado.")
        finally:
            app.dependency_overrides.clear()


class ObservabilitySanitizationTests(unittest.TestCase):
    def test_sensitive_nested_metadata_is_redacted(self):
        from db.repo_observability import sanitize_metadata
        result = sanitize_metadata({"password": "sentinel", "nested": {"authorization": "Bearer sentinel"}, "ok": "value"})
        self.assertEqual(result["password"], "[redacted]")
        self.assertEqual(result["nested"]["authorization"], "[redacted]")
        self.assertEqual(result["ok"], "value")


if __name__ == "__main__":
    unittest.main()
