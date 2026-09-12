import io
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from db.backup_excel import export_table_excel, restore_table_excel, validate_table_excel

ROOT = Path(__file__).resolve().parents[1]
V3_EXCEL = ROOT / "tests/fixtures/backups/v3_excel"

def workbook_bytes(columns=None) -> bytes:
    buffer = io.BytesIO()
    pd.DataFrame([[1, "Ana"]], columns=columns or ["id", "nome"]).to_excel(
        buffer, index=False, sheet_name="data"
    )
    return buffer.getvalue()


@contextmanager
def fake_connection(rows=None, description=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = rows or []
    cursor.description = description or []
    connection = MagicMock()
    connection.cursor.return_value = cursor
    yield connection


def test_export_excel_preserves_v3_data_sheet_and_headers():
    rows = [{"id": 1, "nome": "Ana"}]
    with patch("db.backup_excel._require_excel_table", return_value="usuarios"), patch(
        "db.backup_excel._get_table_column_types", return_value={"id": "integer", "nome": "text"}
    ), patch(
        "db.backup_excel.db_connect",
        return_value=fake_connection(rows, [("id",), ("nome",)]),
    ):
        content = export_table_excel("usuarios")

    restored = pd.read_excel(io.BytesIO(content), sheet_name="data")
    assert list(restored.columns) == ["id", "nome"]
    assert restored.to_dict(orient="records") == [{"id": 1, "nome": "Ana"}]


def test_validate_excel_checks_table_columns_without_writing():
    connection = fake_connection()
    with patch("db.backup_excel._require_excel_table", return_value="usuarios"), patch(
        "db.backup_excel._table_columns", return_value=["id", "nome"]
    ), patch("db.backup_excel._get_required_columns_for_insert", return_value=["nome"]), patch(
        "db.backup_excel.db_connect", return_value=connection
    ):
        result = validate_table_excel(workbook_bytes(), "usuarios")
    assert result["table"] == "usuarios"
    assert result["rows"] == 1
    assert result["compatible_columns"] == ["id", "nome"]


def test_validate_excel_rejects_file_for_another_table():
    with patch("db.backup_excel._require_excel_table", return_value="usuarios"), patch(
        "db.backup_excel._table_columns", return_value=["id", "nome"]
    ):
        with pytest.raises(ValueError, match="Nenhuma coluna compatível"):
            validate_table_excel(workbook_bytes(["prova_id", "pontos"]), "usuarios")


def test_all_anonymized_v3_excel_fixtures_pass_structural_validation():
    files = sorted(V3_EXCEL.glob("*.xlsx"))
    assert len(files) == 21
    for path in files:
        frame = pd.read_excel(path, sheet_name="data")
        with patch("db.backup_excel._require_excel_table", return_value=path.stem), patch(
            "db.backup_excel._table_columns", return_value=list(frame.columns)
        ), patch("db.backup_excel._get_required_columns_for_insert", return_value=[]), patch(
            "db.backup_excel.db_connect", return_value=fake_connection()
        ):
            result = validate_table_excel(path.read_bytes(), path.stem)
        assert result["rows"] == len(frame.index)
        assert result["compatible_columns"] == list(frame.columns)


def test_restore_excel_requires_authorization_before_schema_or_data_changes():
    with patch("db.backup_excel.require_restore_authorized", side_effect=PermissionError("denied")), patch(
        "db.backup_excel.validate_table_excel"
    ) as validate, patch("db.backup_excel._prepare_schema_for_restore") as prepare:
        with pytest.raises(PermissionError):
            restore_table_excel(workbook_bytes(), "usuarios")
    validate.assert_not_called()
    prepare.assert_not_called()


def test_v4_exposes_excel_backup_and_restore_in_master_screen():
    api = (ROOT / "api/routes/backup.py").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend/src/components/backup-admin-view.tsx").read_text(encoding="utf-8")
    for path in ("/excel/tables", "/excel/{table_name}", "/validate/excel/{table_name}", "/restore/excel/{table_name}"):
        assert path in api
    assert "Baixar tabela Excel" in frontend
    assert "Reautenticar e restaurar Excel" in frontend
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in frontend


def test_excel_api_validates_and_restores_with_master_dependency():
    from api.dependencies import require_master
    from api.config import settings
    from api.main import app
    from services.access_control import AuthenticatedContext

    master = AuthenticatedContext(1, "Master", "master", "ativo", frozenset())
    app.dependency_overrides[require_master] = lambda: master
    client = TestClient(app, raise_server_exceptions=False)
    metadata = {"table": "usuarios", "rows": 1, "columns": 2, "compatible_columns": ["id", "nome"]}
    restored = {"status": "ok", "table": "usuarios", "rows": 1, "columns": 2, "normalized_cells": 0, "mode": "upsert"}
    origin = settings.allowed_origins[0]
    try:
        with patch("db.repo_observability.record_event"), patch("db.backup_excel.validate_table_excel", return_value=metadata):
            response = client.post(
                "/api/v1/backup/validate/excel/usuarios",
                content=workbook_bytes(),
                headers={"Origin": origin},
            )
        assert response.status_code == 200
        assert response.json()["table"] == "usuarios"

        with patch("db.repo_observability.record_event"), patch("api.security.consume_restore_authorization", return_value=(1, "jti")), patch(
            "utils.backup_security.grant_restore_authorization"
        ), patch("db.backup_excel.restore_table_excel", return_value=restored) as restore:
            response = client.post(
                "/api/v1/backup/restore/excel/usuarios",
                content=workbook_bytes(),
                headers={"Origin": origin, "X-File-Name": "usuarios_20260907.xlsx"},
            )
        assert response.status_code == 200
        assert response.json()["filename"] == "usuarios_20260907.xlsx"
        restore.assert_called_once()
    finally:
        app.dependency_overrides.clear()
