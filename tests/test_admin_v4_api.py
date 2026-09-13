from unittest.mock import patch


def test_admin_write_routes_deny_participant_and_do_not_call_service():
    from fastapi.testclient import TestClient
    from api.main import app
    from api.dependencies import get_current_context
    from services.access_control import AuthenticatedContext

    app.dependency_overrides[get_current_context] = lambda: AuthenticatedContext(7, "Ana", "participante", "ativo", frozenset({"2026"}))
    try:
        client = TestClient(app, raise_server_exceptions=False)
        with patch("api.routes.admin.create_user", side_effect=__import__("services.access_control", fromlist=["AuthorizationDenied"]).AuthorizationDenied("denied")) as create, patch("db.repo_observability.record_event"):
            response = client.post("/api/v1/admin/users", headers={"Origin": "https://bf1.test"}, json={"name": "X", "email": "x@example.com", "password": "strong-password", "profile": "participante", "user_status": "ativo"})
        assert response.status_code == 403
        create.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_admin_result_route_allows_admin_only_after_service_authorization():
    from fastapi.testclient import TestClient
    from api.main import app
    from api.dependencies import get_current_context
    from services.access_control import AuthenticatedContext

    app.dependency_overrides[get_current_context] = lambda: AuthenticatedContext(2, "Admin", "admin", "ativo", frozenset())
    try:
        client = TestClient(app, raise_server_exceptions=False)
        with patch("api.routes.admin.save_and_process_result", side_effect=__import__("services.access_control", fromlist=["AuthorizationDenied"]).AuthorizationDenied("allowed")) as save, patch("db.repo_observability.record_event"):
            response = client.put("/api/v1/admin/races/3/result?season=2026", headers={"Origin": "https://bf1.test"}, json={"positions": {"1": "Lando Norris"}, "retirements": []})
        assert response.status_code == 403
        save.assert_called_once()
    finally:
        app.dependency_overrides.clear()
