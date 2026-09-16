import io
import sys
import time
import types
import unittest
import zipfile
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import Response
from starlette.requests import Request

from utils.backup_security import (
    BackupLimitExceeded,
    BF1_SQL_BACKUP_TABLES,
    RestoreNotAuthorized,
    RestoreReauthenticationFailed,
    UnsafeSqlBackup,
    grant_restore_authorization,
    require_restore_authorized,
    restore_authorization_error,
    restore_is_authorized,
    validate_excel_archive,
    validate_excel_dimensions,
    validate_sql_content_size,
    validate_sql_backup_content,
    validate_upload_size,
)
from db.backup_repair import _repair_insert_boolean_literals
from db.backup_excel import _normalize_excel_typed_value


ROOT = Path(__file__).resolve().parents[1]


class _Uploaded:
    def __init__(self, size):
        self.size = size


class BackupSecurityTests(unittest.TestCase):
    def test_api_restore_grant_atravessa_requisicoes_e_fica_vinculado_ao_jti(self):
        from api.security import consume_restore_authorization, issue_restore_authorization_cookie

        response = Response()
        with patch("services.auth_service._get_jwt_secret", return_value="s" * 32):
            issue_restore_authorization_cookie(
                response, user_id=7, session_jti="sessao-atual", expires_at=time.time() + 300
            )
        cookies = SimpleCookie()
        for header in response.headers.getlist("set-cookie"):
            cookies.load(header)
        grant = cookies["bf1_restore_authorization"].value
        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/api/v1/backup/restore/sql",
            "headers": [(b"cookie", f"bf1_restore_authorization={grant}; bf1_session=session-token".encode())],
        })
        with patch("services.auth_service._get_jwt_secret", return_value="s" * 32), patch(
            "services.auth_service.decode_token",
            return_value={"user_id": 7, "jti": "sessao-atual"},
        ):
            self.assertEqual(consume_restore_authorization(request), (7, "sessao-atual"))

    def test_excel_restore_normaliza_booleanos_legados(self):
        self.assertIs(_normalize_excel_typed_value(1, "boolean"), True)
        self.assertIs(_normalize_excel_typed_value(0, "boolean"), False)
        self.assertIs(_normalize_excel_typed_value("sim", "boolean"), True)
        self.assertIs(_normalize_excel_typed_value("false", "boolean"), False)

    def test_excel_restore_rejeita_booleano_ambiguo(self):
        with self.assertRaisesRegex(ValueError, "booleano incompatível"):
            _normalize_excel_typed_value("talvez", "boolean")

    def test_reparo_converte_somente_inteiros_de_colunas_booleanas(self):
        statement = (
            'INSERT INTO "usuarios" ("id", "must_change_password", "faltas") '
            "VALUES (7, 0, 1)"
        )
        with patch("db.backup_repair._get_boolean_columns", return_value={"must_change_password"}):
            repaired = _repair_insert_boolean_literals(Mock(), statement, "usuarios")

        self.assertEqual(
            repaired,
            'INSERT INTO "usuarios" ("id", "must_change_password", "faltas") '
            "VALUES (7, FALSE, 1)",
        )

    def test_restore_fica_bloqueado_por_padrao(self):
        with patch("app_runtime.get_session", return_value={}), patch(
            "utils.backup_security._current_restore_identity",
            return_value=(7, "jti-atual"),
        ):
            self.assertFalse(restore_is_authorized())
            with self.assertRaises(RestoreNotAuthorized):
                require_restore_authorized()

    def test_restore_exige_grant_vinculado_ao_usuario_e_jti(self):
        state = {}
        with patch("app_runtime.get_session", return_value=state), patch(
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
        with patch("app_runtime.get_session", return_value=state), patch(
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
        with patch.dict("os.environ", configured, clear=True), patch(
            "app_runtime.get_session", return_value={}
        ), patch(
            "utils.backup_security._current_restore_identity",
            return_value=(7, "jti-atual"),
        ):
            self.assertFalse(restore_is_authorized())

    def test_reautenticacao_valida_hash_atual_e_vincula_sessao(self):
        from services import backup_restore_authorization
        from services.access_control import AuthenticatedContext

        context = AuthenticatedContext(7, "Master", "master", "ativo", frozenset())
        fake_auth = types.SimpleNamespace(
            decode_token=lambda token: {"user_id": 7, "jti": "jti-atual"}
        )
        with (
            patch("services.backup_restore_authorization.get_session", return_value={"token": "token-atual"}),
            patch("services.backup_restore_authorization.require_operation", return_value=context),
            patch.dict(sys.modules, {"services.auth_service": fake_auth}),
            patch(
                "services.critical_reauthentication.verify_critical_password",
                return_value={"id": 7, "email": "master@example.com"},
            ) as verify,
            patch("utils.request_utils.get_client_ip", return_value="203.0.113.7"),
            patch(
                "services.backup_restore_authorization.grant_restore_authorization",
                return_value=1600,
            ) as grant,
        ):
            self.assertEqual(backup_restore_authorization.reauthorize_restore("senha"), 1600)

        verify.assert_called_once_with(7, "senha", ip_address="203.0.113.7")
        grant.assert_called_once_with(user_id=7, jti="jti-atual")

    def test_reautenticacao_invalida_nao_cria_grant(self):
        from services import backup_restore_authorization
        from services.access_control import AuthenticatedContext

        context = AuthenticatedContext(7, "Master", "master", "ativo", frozenset())
        fake_auth = types.SimpleNamespace(
            decode_token=lambda token: {"user_id": 7, "jti": "jti-atual"}
        )
        from services.critical_reauthentication import CriticalReauthenticationFailed

        with (
            patch("services.backup_restore_authorization.get_session", return_value={"token": "token-atual"}),
            patch("services.backup_restore_authorization.require_operation", return_value=context),
            patch.dict(sys.modules, {"services.auth_service": fake_auth}),
            patch(
                "services.critical_reauthentication.verify_critical_password",
                side_effect=CriticalReauthenticationFailed,
            ),
            patch("utils.request_utils.get_client_ip", return_value="203.0.113.7"),
            patch("services.backup_restore_authorization.clear_restore_authorization") as clear,
            patch("services.backup_restore_authorization.grant_restore_authorization") as grant,
        ):
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

    def test_backup_sql_v35_real_anonimizado_passa_na_gramatica_canonica(self):
        statements = validate_sql_backup_content(
            (ROOT / "tests" / "fixtures" / "backups" / "v3_5_0" / "fixture.sql").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(len(statements), 3914)
        self.assertTrue(statements[0].upper().startswith("TRUNCATE TABLE"))
        self.assertTrue(all("setval" not in statement.lower() for statement in statements))

    def test_backup_sql_preserva_ponto_e_virgula_e_arrays_em_valores_literais(self):
        sql = """-- BF1 POSTGRES DATA-ONLY DUMP
BEGIN;
TRUNCATE TABLE "pilotos" RESTART IDENTITY CASCADE;
INSERT INTO "pilotos" ("id", "nome", "aliases") VALUES (1, 'Nome; com ''aspas''', ARRAY['a,b', 'c']);
COMMIT;
"""

        statements = validate_sql_backup_content(sql)

        self.assertEqual(len(statements), 2)
        self.assertIn("Nome; com ''aspas''", statements[1])

    def test_backup_sql_rejeita_meta_comandos_psql_e_sql_arbitrario(self):
        attacks = (
            "\\! id",
            "  \\copy usuarios TO PROGRAM 'id'",
            "UPDATE usuarios SET perfil='master'",
            "DELETE FROM usuarios",
            "CREATE EXTENSION file_fdw",
            "DO $$ BEGIN PERFORM pg_sleep(1); END $$",
            "INSERT INTO \"pilotos\" (\"id\") VALUES ((SELECT 1))",
            "INSERT INTO \"pilotos\" (\"id\") VALUES (pg_sleep(1))",
        )
        for attack in attacks:
            sql = (
                "-- BF1 POSTGRES DATA-ONLY DUMP\nBEGIN;\n"
                'TRUNCATE TABLE "pilotos" RESTART IDENTITY CASCADE;\n'
                f"{attack};\nCOMMIT;\n"
            )
            with self.subTest(attack=attack), self.assertRaises(UnsafeSqlBackup):
                validate_sql_backup_content(sql)

    def test_backup_sql_rejeita_marcador_copiado_para_script_malicioso(self):
        with self.assertRaises(UnsafeSqlBackup):
            validate_sql_backup_content(
                "-- BF1 POSTGRES DATA-ONLY DUMP\nBEGIN;\nDROP TABLE usuarios;\nCOMMIT;\n"
            )

    def test_restore_rejeita_meta_comando_antes_de_schema_processo_ou_banco(self):
        from db.backup_utils import restore_backup_from_sql

        malicious = """-- BF1 POSTGRES DATA-ONLY DUMP
BEGIN;
TRUNCATE TABLE "usuarios" RESTART IDENTITY CASCADE;
\\! id;
COMMIT;
"""
        presenter = Mock()
        with patch("db.backup_utils.require_restore_authorized"), patch(
            "db.backup_utils._prepare_schema_for_restore"
        ) as prepare, patch("db.backup_utils._run_command") as run_command, patch(
            "db.backup_utils.db_connect"
        ) as connect:
            self.assertFalse(restore_backup_from_sql(malicious, presenter))

        prepare.assert_not_called()
        run_command.assert_not_called()
        connect.assert_not_called()
        presenter.error.assert_called_once()

    def test_backup_sql_rejeita_tabela_fora_do_contrato_ou_nao_declarada(self):
        attacks = (
            """-- BF1 POSTGRES DATA-ONLY DUMP
BEGIN;
TRUNCATE TABLE "shadow_control" RESTART IDENTITY CASCADE;
INSERT INTO "shadow_control" ("id") VALUES (1);
COMMIT;
""",
            """-- BF1 POSTGRES DATA-ONLY DUMP
BEGIN;
TRUNCATE TABLE "pilotos" RESTART IDENTITY CASCADE;
INSERT INTO "usuarios" ("id") VALUES (1);
COMMIT;
""",
        )
        for attack in attacks:
            with self.subTest(sql=attack), self.assertRaises(UnsafeSqlBackup):
                validate_sql_backup_content(attack)

    def test_contrato_sql_cobre_todas_as_tabelas_da_fixture_v35(self):
        import json

        manifest = json.loads(
            (ROOT / "tests" / "fixtures" / "backups" / "v3_5_0" / "manifest.json").read_text()
        )
        self.assertTrue(set(manifest["tables"]).issubset(BF1_SQL_BACKUP_TABLES))

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
        self.assertIn("verify_critical_password(", authorization)
        self.assertIn("grant_restore_authorization", authorization)
        self.assertNotIn("BACKUP_RESTORE_ENABLED", service)
        self.assertIn("validate_upload_size(uploaded, max_sql_bytes", sql)
        self.assertNotIn('decode("utf-8", errors="ignore")', sql)
        self.assertIn("restore_canonical_sql(sql_content, presenter)", sql)
        self.assertIn("validate_excel_archive(content)", excel)
        self.assertIn("validate_excel_dimensions", excel)
        self.assertIn("nrows=limits.excel_rows + 1", excel)
        self.assertGreaterEqual(legacy.count("require_restore_authorized()"), 4)
        restore = legacy[legacy.index("def restore_backup_from_sql"):legacy.index("def upload_db")]
        self.assertIn("validate_sql_backup_content(sql_content)", restore)
        self.assertNotIn("sql_input=sql_content", restore)
        self.assertIn("SET LOCAL standard_conforming_strings = on", restore)

    def test_preparacao_do_restore_cria_tabelas_v35_antes_do_dump(self):
        legacy = (ROOT / "db" / "backup_utils.py").read_text(encoding="utf-8")
        prepare = legacy[legacy.index("def _prepare_schema_for_restore"):legacy.index("def _extract_truncate_tables")]

        for table in (
            "temporadas",
            "login_attempts",
            "access_logs",
            "financeiro_participantes",
            "financeiro_config_temporada",
        ):
            self.assertIn(table, prepare)
        self.assertIn("init_rules_table()", prepare)
        self.assertNotIn("BOOLEAN DEFAULT 0", prepare)
        self.assertIn("DROP CONSTRAINT IF EXISTS pilotos_nome_key", prepare)
        self.assertIn("data_registro TIMESTAMP", prepare)
        self.assertIn('for legacy_column in ("temporada", "tipo_prova")', prepare)
        self.assertIn("if legacy_column in rule_columns", prepare)
        self.assertIn("nome_regra TEXT", prepare)

    def test_preparacao_nao_altera_coluna_legada_ausente(self):
        from db.backup_utils import _prepare_schema_for_restore

        cursor = Mock()
        cursor.fetchall.return_value = [{"column_name": "id"}, {"column_name": "nome_regra"}]
        connection = Mock()
        connection.cursor.return_value = cursor
        manager = Mock()
        manager.__enter__ = Mock(return_value=connection)
        manager.__exit__ = Mock(return_value=False)

        with patch("db.db_schema.run_migrations"), patch("db.rules_utils.init_rules_table"), patch(
            "db.backup_utils.db_connect", return_value=manager
        ):
            _prepare_schema_for_restore()

        statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
        self.assertFalse(any("ALTER COLUMN \"temporada\"" in sql for sql in statements))
        self.assertFalse(any("ALTER COLUMN \"tipo_prova\"" in sql for sql in statements))


if __name__ == "__main__":
    unittest.main()
