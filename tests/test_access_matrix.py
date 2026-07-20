import unittest

from services.access_control import (
    AuthenticatedContext,
    AuthorizationDenied,
    OPERATION_ACCESS,
    PAGE_ACCESS,
    authorize_context,
    page_is_allowed,
)

ROLES = ("participante", "admin", "master", "inativo")
EXPECTED_PAGES = {
    "Login", "Painel do Participante", "Calendário", "Gestão de Usuários",
    "Gestão de Pilotos", "Gestão de Provas", "Gestão de Apostas",
    "Gestão de Regras", "Análise de Apostas", "Atualização de resultados",
    "Apostas Campeonato", "Resultado Campeonato", "Log de Apostas",
    "Log de Acessos", "Classificação", "Hall da Fama", "Dashboard F1",
    "Backup dos Bancos de Dados", "Regulamento", "Sobre",
}
EXPECTED_OPERATIONS = {
    "piloto.write", "prova.write", "resultado.write",
    "resultado_campeonato.write", "usuario.write", "regra.write",
    "hall_da_fama.write", "backup.write", "aposta_admin.write",
}


class AccessMatrixTests(unittest.TestCase):
    def test_matrix_covers_every_page_and_sensitive_operation(self):
        self.assertEqual(set(PAGE_ACCESS), EXPECTED_PAGES)
        self.assertEqual(set(OPERATION_ACCESS), EXPECTED_OPERATIONS)

    def test_page_access_matrix(self):
        for page, allowed in PAGE_ACCESS.items():
            for role in ROLES:
                with self.subTest(page=page, role=role):
                    self.assertEqual(page_is_allowed(page, role), role in allowed)

    def test_operation_access_matrix(self):
        for operation, allowed in OPERATION_ACCESS.items():
            for role in ROLES:
                context = AuthenticatedContext(1, "Teste", role, "ativo", frozenset())
                with self.subTest(operation=operation, role=role):
                    if role in allowed and role != "inativo":
                        authorize_context(context, allowed)
                    else:
                        with self.assertRaises(AuthorizationDenied):
                            authorize_context(context, allowed)

    def test_inactive_status_denied_even_with_master_role(self):
        context = AuthenticatedContext(1, "Teste", "master", "inativo", frozenset())
        with self.assertRaises(AuthorizationDenied):
            authorize_context(context, frozenset({"master"}))

    def test_season_outside_authenticated_scope_is_denied(self):
        context = AuthenticatedContext(7, "Teste", "participante", "ativo", frozenset({"2026"}))
        with self.assertRaises(AuthorizationDenied):
            authorize_context(context, frozenset({"participante"}), season="2025")
