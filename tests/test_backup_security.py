import io
import sys
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit as st

from utils.backup_security import (
    BackupLimitExceeded,
    RestoreNotAuthorized,
    RestoreReauthenticationFailed,
    grant_restore_authorization,
    require_restore_authorized,
    restore_authorization_error,
    restore_is_authorized,
    validate_excel_archive,
    validate_excel_dimensions,
    validate_sql_content_size,
    validate_upload_size,
)


ROOT = Path(__file__).resolve().parents[1]


class _Uploaded:
    def __init__(self, size):
        self.size = size


class BackupSecurityTests(unittest.TestCase):
    def test_restore_fica_bloqueado_por_padrao(self):
        with patch.object(st, "session_state", {}), patch(
            "utils.backup_security._current_restore_identity",
            return_value=(7, "jti-atual"),
        ):
            self.assertFalse(restore_is_authorized())
            with self.assertRaises(RestoreNotAuthorized):
                require_restore_authorized()

    def test_restore_exige_grant_vinculado_ao_usuario_e_jti(self):
        state = {}
        with patch.object(st, "session_state", state), patch(
            "utils.backup_security._current_restore_identity",
            return_value=(7, "jti-atual"),
        ), patch("utils.backup_security.time.time", return_value=1000):
            grant_restore_authorization(user_id=7, jti="jti-atual")
            self.assertTrue(restore_is_authorized())
            require_restore_authorized()

            state["_backup_restore_grant"]["jti"] = "outra-sessao"
            self.assertFalse(restore_is_authorized())

    def test_restore_expira_e_remove_grant(self):
        state = {
            "_backup_restore_grant": {
                "user_id": 7,
                "jti": "jti-atual",
                "expires_at": 999,
            }
        }
        with patch.object(st, "session_state", state), patch(
            "utils.backup_security._current_restore_identity",
            return_value=(7, "jti-atual"),
        ), patch("utils.backup_security.time.time", return_value=1000):
            self.assertIn("expirou", restore_authorization_error())
            self.assertNotIn("_backup_restore_grant", state)

    def test_variaveis_antigas_nao_liberam_restore(self):
        configured = {
            "BACKUP_RESTORE_ENABLED": "true",
            "APP_ENVIRONMENT": "homologation",
            "BACKUP_RESTORE_ALLOWED_ENVIRONMENTS": "development,homologation",
        }
        with patch.dict("os.environ", configured, clear=True), patch.object(
            st, "session_state", {}
        ), patch(
            "utils.backup_security._current_restore_identity",
            return_value=(7, "jti-atual"),
        ):
            self.assertFalse(restore_is_authorized())

    def test_reautenticacao_valida_hash_atual_e_vincula_sessao(self):
        from services import backup_restore_authorization
        from services.access_control import AuthenticatedContext

        context = AuthenticatedContext(7, "Master", "master", "ativo", frozenset())
        check_password = Mock(return_value=True)
        fake_repo = types.SimpleNamespace(
            get_user_by_id=lambda user_id: {"senha_hash": "hash-atual"},
            check_password=check_password,
        )
        fake_db = types.ModuleType("db")
        fake_db.repo_users = fake_repo
        fake_auth = types.SimpleNamespace(
            decode_token=lambda token: {"user_id": 7, "jti": "jti-atual"}
        )
        with patch.object(st, "session_state", {"token": "token-atual"}), patch(
            "services.backup_restore_authorization.require_operation", return_value=context
        ), patch.dict(
            sys.modules,
            {"db": fake_db, "db.repo_users": fake_repo, "services.auth_service": fake_auth},
        ), patch(
            "services.backup_restore_authorization.grant_restore_authorization", return_value=1600
        ) as grant:
            self.assertEqual(backup_restore_authorization.reauthorize_restore("senha"), 1600)

        check_password.assert_called_once_with("senha", "hash-atual")
        grant.assert_called_once_with(user_id=7, jti="jti-atual")

    def test_reautenticacao_invalida_nao_cria_grant(self):
        from services import backup_restore_authorization
        from services.access_control import AuthenticatedContext

        context = AuthenticatedContext(7, "Master", "master", "ativo", frozenset())
        fake_repo = types.SimpleNamespace(
            get_user_by_id=lambda user_id: {"senha_hash": "hash-atual"},
            check_password=Mock(return_value=False),
        )
        fake_db = types.ModuleType("db")
        fake_db.repo_users = fake_repo
        fake_auth = types.SimpleNamespace(
            decode_token=lambda token: {"user_id": 7, "jti": "jti-atual"}
        )
        with patch.object(st, "session_state", {"token": "token-atual"}), patch(
            "services.backup_restore_authorization.require_operation", return_value=context
        ), patch.dict(
            sys.modules,
            {"db": fake_db, "db.repo_users": fake_repo, "services.auth_service": fake_auth},
        ), patch(
            "services.backup_restore_authorization.clear_restore_authorization"
        ) as clear, patch(
            "services.backup_restore_authorization.grant_restore_authorization"
        ) as grant:
            with self.assertRaises(RestoreReauthenticationFailed):
                backup_restore_authorization.reauthorize_restore("senha-incorreta")

        clear.assert_called_once_with()
        grant.assert_not_called()

    def test_limites_de_bytes_sql_e_upload(self):
        with patch.dict("os.environ", {"BACKUP_SQL_MAX_BYTES": "8"}, clear=True):
            self.assertEqual(validate_sql_content_size("SELECT 1"), 8)
            with self.assertRaises(BackupLimitExceeded):
                validate_sql_content_size("SELECT 10")
            with self.assertRaises(BackupLimitExceeded):
                validate_upload_size(_Uploaded(9), 8, "Backup SQL")

    def test_excel_limita_descompactacao_e_dimensoes(self):
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/worksheets/sheet1.xml", "x" * 100)

        with patch.dict(
            "os.environ",
            {
                "BACKUP_EXCEL_MAX_UNCOMPRESSED_BYTES": "50",
                "BACKUP_EXCEL_MAX_ROWS": "2",
                "BACKUP_EXCEL_MAX_COLUMNS": "2",
                "BACKUP_EXCEL_MAX_CELLS": "4",
            },
            clear=True,
        ):
            with self.assertRaises(BackupLimitExceeded):
                validate_excel_archive(content.getvalue())
            with self.assertRaises(BackupLimitExceeded):
                validate_excel_dimensions(3, 2)

    def test_todos_os_caminhos_de_restore_aplicam_politica_e_limites(self):
        service = (ROOT / "services" / "data_access_backup.py").read_text(encoding="utf-8")
        authorization = (ROOT / "services" / "backup_restore_authorization.py").read_text(encoding="utf-8")
        sql = (ROOT / "db" / "backup_sql.py").read_text(encoding="utf-8")
        excel = (ROOT / "db" / "backup_excel.py").read_text(encoding="utf-8")
        legacy = (ROOT / "db" / "backup_utils.py").read_text(encoding="utf-8")

        self.assertGreaterEqual(service.count("require_restore_authorized()"), 2)
        self.assertIn('require_operation("backup.write")', authorization)
        self.assertIn("check_password(candidate, password_hash)", authorization)
        self.assertIn("grant_restore_authorization", authorization)
        self.assertNotIn("BACKUP_RESTORE_ENABLED", service)
        self.assertIn("validate_sql_content_size(sql_content)", sql)
        self.assertIn("validate_upload_size(uploaded, max_sql_bytes", sql)
        self.assertNotIn('decode("utf-8", errors="ignore")', sql)
        self.assertIn("validate_excel_archive(content)", excel)
        self.assertIn("validate_excel_dimensions", excel)
        self.assertIn("nrows=limits.excel_rows + 1", excel)
        self.assertGreaterEqual(legacy.count("require_restore_authorized()"), 4)


if __name__ == "__main__":
    unittest.main()
