import importlib
import gzip
import json
import os
import sys
import unittest
from datetime import datetime, timezone
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

    def tearDown(self):
        self.client.cookies.clear()
        from api.main import app
        app.dependency_overrides.clear()

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

    def test_season_object_rejects_idor_as_not_found(self):
        from api.dependencies import authorize_season_object
        from fastapi import HTTPException
        from services.access_control import AuthenticatedContext
        context = AuthenticatedContext(7, "A", "participante", "ativo", frozenset({"2026"}))
        with self.assertRaises(HTTPException) as raised:
            authorize_season_object("2025", context)
        self.assertEqual((raised.exception.status_code, raised.exception.detail), (404, "Recurso não encontrado."))

    def test_rate_limit_is_server_side_audited_without_password(self):
        headers = {"Origin": "https://bf1.test"}
        with patch("api.routes.auth.recent_failures", return_value=(5, 15, True)), \
             patch("api.routes.auth.record_attempt") as attempt, \
             patch("api.routes.auth.record_access") as access, \
             patch("db.repo_observability.record_event"):
            response = self.client.post("/api/v1/auth/login", headers=headers, json={"email": "a@example.com", "password": "sentinel-secret"})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("sentinel-secret", repr(attempt.call_args_list) + repr(access.call_args_list))
        access.assert_called_once()
        self.assertEqual(access.call_args.kwargs["event"], "login_blocked")
        self.assertEqual(access.call_args.kwargs["detail"], "rate_limit")

    def test_revoked_or_expired_session_is_rejected(self):
        self.client.cookies.set("bf1_session", "revoked-token")
        with patch("services.auth_service.decode_token", return_value=None), \
             patch("db.repo_observability.record_event"):
            response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Autenticação necessária.")

    def test_cookie_mutation_requires_matching_csrf(self):
        self.client.cookies.set("bf1_session", "token")
        self.client.cookies.set("bf1_csrf", "csrf-cookie")
        with patch("db.repo_observability.record_event"):
            response = self.client.post("/api/v1/auth/logout", headers={"Origin": "https://bf1.test", "X-CSRF-Token": "wrong"})
        self.assertEqual(response.status_code, 403)

    def test_active_session_can_be_rotated_with_csrf(self):
        from api.dependencies import get_current_context
        from api.main import app
        from services.access_control import AuthenticatedContext
        app.dependency_overrides[get_current_context] = lambda: AuthenticatedContext(7, "A", "participante", "ativo", frozenset({"2026"}))
        self.client.cookies.set("bf1_session", "old-token")
        self.client.cookies.set("bf1_csrf", "csrf-cookie")
        user = {"id": 7, "nome": "A", "email": "a@example.com", "perfil": "participante", "status": "ativo"}
        with patch("db.repo_users.get_user_by_id", return_value=user), \
             patch("services.auth_service.generate_token", return_value="new-token") as generate, \
             patch("api.routes.auth.record_access"), \
             patch("db.repo_observability.record_event"):
            response = self.client.post("/api/v1/auth/refresh", headers={"Origin": "https://bf1.test", "X-CSRF-Token": "csrf-cookie"})
        self.assertEqual(response.status_code, 200)
        generate.assert_called_once()
        cookies = response.headers.get_list("set-cookie")
        self.assertTrue(any("bf1_session=new-token" in value and "HttpOnly" in value and "SameSite=lax" in value for value in cookies))

    def test_unhandled_failure_is_opaque_and_correlated(self):
        with patch("db.db_schema.db_connect", side_effect=RuntimeError("sentinel database detail")), \
             patch("db.repo_observability.record_event") as record:
            response = self.client.get("/api/v1/health/ready", headers={"X-Request-ID": "trace-123"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["x-request-id"], "trace-123")
        self.assertEqual(response.json()["request_id"], "trace-123")
        self.assertNotIn("sentinel", response.text)
        self.assertEqual(record.call_args.kwargs["exception_class"], "RuntimeError")

    def test_untrusted_request_id_is_replaced(self):
        with patch("db.repo_observability.record_event"):
            response = self.client.get("/api/v1/health/live", headers={"X-Request-ID": "bad request id"})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.headers["x-request-id"], "bad request id")

    def test_non_master_cannot_export_logs(self):
        from api.dependencies import get_current_context
        from api.main import app
        from services.access_control import AuthenticatedContext
        app.dependency_overrides[get_current_context] = lambda: AuthenticatedContext(7, "A", "participante", "ativo", frozenset({"2026"}))
        with patch("db.repo_observability.record_event"):
            response = self.client.get("/api/v1/logs/export", headers={"X-Reauth-Password": "sentinel"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("filename", response.text.lower())

    def test_reauthenticated_master_exports_bounded_safe_gzip(self):
        from api.dependencies import get_current_context
        from api.main import app
        from services.access_control import AuthenticatedContext
        app.dependency_overrides[get_current_context] = lambda: AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
        row = {"id": 1, "created_at": datetime(2026, 9, 8, tzinfo=timezone.utc), "event": "request_completed"}
        with patch("db.repo_users.get_user_by_id", return_value={"id": 1, "senha_hash": "hash"}), \
             patch("db.repo_users.check_password", return_value=True), \
             patch("api.routes.logs.export_events", return_value=[row]) as export, \
             patch("api.routes.logs.record_event") as audit, \
             patch("db.repo_observability.record_event"):
            response = self.client.get("/api/v1/logs/export", headers={"X-Reauth-Password": "correct"})
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.headers["content-disposition"], r'^attachment; filename="bf1-logs-\d{8}T\d{6}Z\.jsonl\.gz"$')
        self.assertEqual(json.loads(gzip.decompress(response.content).decode().strip())["event"], "request_completed")
        self.assertLessEqual(export.call_args.kwargs["limit"], 50_000)
        self.assertEqual(audit.call_args.kwargs["event"], "log_exported")

    def test_api_has_no_public_signup_contract(self):
        with patch("db.repo_observability.record_event"):
            paths = self.client.get("/api/v1/openapi.json").json()["paths"]
        self.assertNotIn("/api/v1/auth/signup", paths)
        self.assertNotIn("/api/v1/auth/register", paths)


class ObservabilitySanitizationTests(unittest.TestCase):
    def test_sensitive_nested_metadata_is_redacted(self):
        from db.repo_observability import sanitize_metadata
        result = sanitize_metadata({"password": "sentinel", "access_token": "sentinel", "nested": {"authorization": "Bearer sentinel"}, "ok": "value"})
        self.assertEqual(result["password"], "[redacted]")
        self.assertEqual(result["access_token"], "[redacted]")
        self.assertEqual(result["nested"]["authorization"], "[redacted]")
        self.assertEqual(result["ok"], "value")


if __name__ == "__main__":
    unittest.main()
