import sys
import types
import unittest
from unittest.mock import patch

from services.access_control import (
    AuthenticatedContext,
    AuthenticationRequired,
    AuthorizationDenied,
    authorize_context,
    page_is_allowed,
    require_operation,
    resolve_authenticated_context,
)


class PermissionsExtendedTests(unittest.TestCase):
    def test_escopo_vazio_de_admin_e_global(self):
        context = AuthenticatedContext(1, "Admin", "admin", "ativo", frozenset())
        authorize_context(context, frozenset({"admin"}), season="1999")

    def test_temporada_autorizada_do_participante_e_aceita(self):
        context = AuthenticatedContext(1, "Participante", "participante", "ativo", frozenset({"2026"}))
        authorize_context(context, frozenset({"participante"}), season="2026")

    def test_perfil_desconhecido_nao_recebe_acesso_a_pagina(self):
        self.assertFalse(page_is_allowed("Classificação", "superuser"))
        self.assertFalse(page_is_allowed("Página inexistente", "master"))

    def test_operacao_desconhecida_falha_fechado(self):
        with self.assertRaisesRegex(RuntimeError, "sem politica"):
            require_operation("operacao.nao.cadastrada")

    def test_contexto_rejeita_token_ausente_sem_consultar_banco(self):
        fake_repo = types.SimpleNamespace(
            get_user_by_id=lambda user_id: self.fail("banco não deveria ser consultado"),
            get_usuario_temporadas_ativas=lambda user_id: [],
        )
        fake_auth = types.SimpleNamespace(decode_token=lambda token: None)
        with patch("app_runtime.get_session", return_value={}), patch.dict(
            sys.modules,
            {"db.repo_users": fake_repo, "services.auth_service": fake_auth},
        ):
            with self.assertRaises(AuthenticationRequired):
                resolve_authenticated_context()

    def test_contexto_revalida_perfil_e_status_no_banco(self):
        fake_repo = types.SimpleNamespace(
            get_user_by_id=lambda user_id: {
                "id": user_id, "nome": "Ex-admin", "perfil": "master", "status": "inativo",
            },
            get_usuario_temporadas_ativas=lambda user_id: ["2024", "2025"],
        )
        fake_auth = types.SimpleNamespace(
            decode_token=lambda token: {
                "user_id": 7, "nome": "Nome antigo", "perfil": "master", "status": "ativo",
            }
        )
        with patch("app_runtime.get_session", return_value={"token": "jwt"}), patch.dict(
            sys.modules,
            {"db.repo_users": fake_repo, "services.auth_service": fake_auth},
        ):
            context = resolve_authenticated_context()
        self.assertEqual(context.user_id, 7)
        self.assertEqual(context.perfil, "inativo")
        self.assertEqual(context.status, "inativo")
        self.assertEqual(context.temporadas_autorizadas, frozenset({"2024", "2025"}))
        with self.assertRaises(AuthorizationDenied):
            authorize_context(context, frozenset({"master"}))


if __name__ == "__main__":
    unittest.main()
