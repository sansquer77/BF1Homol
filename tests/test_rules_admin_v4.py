from unittest.mock import patch

import pytest

from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.rules_admin_v4_service import RULE_FIELDS, _validated_fields, recalculate_season
from services.rules_service import get_regras_aplicaveis


def _context(role: str = "master") -> AuthenticatedContext:
    return AuthenticatedContext(1, "Master", role, "ativo", frozenset())


def _rule_payload() -> dict:
    payload = {
        "nome_regra": "BF1 2026", "quantidade_fichas": 15, "fichas_por_piloto": 5,
        "mesma_equipe": False, "descarte": True, "pontos_pole": 0, "pontos_vr": 0,
        "pontos_posicoes": [25, 18, 15, 12, 10], "pontos_11_colocado": 50,
        "regra_sprint": True, "pontos_sprint_pole": 0, "pontos_sprint_vr": 0,
        "pontos_sprint_posicoes": [8, 7, 6, 5], "pontos_dobrada": False,
        "bonus_vencedor": 0, "bonus_podio_completo": 0, "bonus_podio_qualquer": 0,
        "qtd_minima_pilotos": 5, "penalidade_abandono": True, "pontos_penalidade": -5,
        "penalidade_auto_percent": 20, "pontos_campeao": 150, "pontos_vice": 100,
        "pontos_equipe": 80,
    }
    assert set(payload) == set(RULE_FIELDS)
    return payload


def test_complete_v35_rule_contract_accepts_every_persisted_field():
    clean = _validated_fields(_rule_payload())
    assert clean["pontos_penalidade"] == -5
    assert clean["pontos_posicoes"] == [25, 18, 15, 12, 10]


def test_rule_contract_rejects_hidden_or_incomplete_updates():
    payload = _rule_payload()
    del payload["bonus_podio_completo"]
    with pytest.raises(ValueError, match="bonus_podio_completo"):
        _validated_fields(payload)


def test_sprint_table_does_not_depend_on_special_sprint_composition_flag():
    rule = {**_rule_payload(), "id": 7, "regra_sprint": False}
    get_regras_aplicaveis.clear()
    with patch("services.rules_service.get_regra_temporada", return_value=rule):
        resolved = get_regras_aplicaveis("2026", "Sprint")

    assert resolved["quantidade_fichas"] == 15
    assert resolved["qtd_minima_pilotos"] == 5
    assert resolved["pontos_posicoes"] == rule["pontos_sprint_posicoes"]


def test_recalculate_is_master_only_and_scoped_to_selected_season():
    with patch("services.bets_scoring.atualizar_classificacoes_todas_as_provas") as recalculate, \
         patch("services.rules_admin_v4_service._clear_rule_caches"):
        recalculate_season(_context(), "2026")
    recalculate.assert_called_once_with(temporada="2026")
    with pytest.raises(AuthorizationDenied):
        recalculate_season(_context("admin"), "2026")


def test_admin_rules_api_exposes_edit_positions_delete_and_recalculate():
    from api.main import app

    paths = app.openapi()["paths"]
    assert "put" in paths["/api/v1/admin/rules/{rule_id}"]
    assert "delete" in paths["/api/v1/admin/rules/{rule_id}"]
    assert "put" in paths["/api/v1/admin/rules/position-points"]
    assert "post" in paths["/api/v1/admin/rules/recalculate"]
