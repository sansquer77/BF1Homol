"""Operações administrativas V4; todas revalidam perfil e temporada no serviço."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from api.dependencies import get_current_context
from services.access_control import AuthenticatedContext, AuthorizationDenied
from services.admin_v4_service import create_user, list_admin_circuits, list_admin_drivers, list_admin_races, list_admin_teams, list_admin_users, refresh_admin_circuits, update_user, upsert_driver, upsert_race, upsert_team
from services.hall_admin_v4_service import bulk_save_hall, delete_hall_record, list_hall_admin, save_hall_record, update_hall_record
from services.financial_v4_service import get_financial, save_financial, send_financial_reminder
from services.rules_admin_v4_service import assign_rule, clone_rule, list_rules, save_rule
from services.results_admin_v4_service import get_result_management, save_and_process_result
from api.schemas import AdminTeam, FinancialReminderResponse, FinancialResponse, FinancialWriteRequest, ResultManagementResponse, ResultProcessResponse, RuleAssignmentRequest, RuleCloneRequest, RuleWriteRequest, TeamWriteRequest
from api.schemas import HallAdminResponse, HallAdminUpdateRequest, HallAdminWriteRequest

router = APIRouter(prefix="/admin", tags=["admin"])


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)
    profile: str = Field(pattern=r"^(participante|admin|master|inativo)$")
    user_status: str = Field(default="ativo", pattern=r"^(ativo|inativo)$")


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    profile: str | None = Field(default=None, pattern=r"^(participante|admin|master|inativo)$")
    user_status: str | None = Field(default=None, pattern=r"^(ativo|inativo)$")
    must_change_password: bool | None = None


class DriverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    team: str = Field(default="", max_length=120)
    status: str = Field(default="Ativo", max_length=30)
    number: int = Field(default=0, ge=0, le=99)


class RaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    date: str = Field(min_length=8, max_length=30)
    time: str = Field(default="", max_length=20)
    type: str = Field(default="Normal", max_length=30)
    race_status: str = Field(default="Pendente", max_length=30)
    circuit_id: str | None = Field(default=None, max_length=80)


class CircuitResponse(BaseModel):
    circuit_id: str
    circuit_name: str
    country: str
    locality: str


class CircuitRefreshResponse(BaseModel):
    temporadas: int = Field(ge=0)
    circuitos: int = Field(ge=0)


class ResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    positions: dict[str, Any]
    retirements: list[str] = Field(default_factory=list, max_length=100)


class HallBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[HallAdminWriteRequest] = Field(min_length=1, max_length=500)


def _run(action, *args, **kwargs):
    try:
        action(*args, **kwargs)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"status": "ok"}


def _read(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail="Acesso negado.") from exc

@router.get("/financial", response_model=FinancialResponse)
def admin_financial(season: str = Query(pattern=r"^\d{4}$"), context: AuthenticatedContext = Depends(get_current_context)):
    return _read(get_financial, context, season)

@router.put("/financial")
def update_admin_financial(payload: FinancialWriteRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(save_financial, context, payload.season, payload.fee, {item.user_id: item.paid for item in payload.payments})

@router.post("/financial/reminder", response_model=FinancialReminderResponse)
def remind_admin_financial(season: str = Query(pattern=r"^\d{4}$"), context: AuthenticatedContext = Depends(get_current_context)):
    try:
        recipients = send_financial_reminder(context, season)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail="Acesso negado.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "recipients": recipients}

@router.get("/rules")
def get_admin_rules(context: AuthenticatedContext = Depends(get_current_context)):
    return _read(list_rules, context)

@router.post("/rules", status_code=201)
def create_admin_rule(payload: RuleWriteRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(save_rule, context, None, payload.model_dump())

@router.put("/rules/{rule_id}")
def update_admin_rule(rule_id: int, payload: RuleWriteRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(save_rule, context, rule_id, payload.model_dump())

@router.post("/rules/assign")
def assign_admin_rule(payload: RuleAssignmentRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(assign_rule, context, payload.season, payload.rule_id)

@router.post("/rules/{rule_id}/clone", status_code=201)
def clone_admin_rule(rule_id: int, payload: RuleCloneRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(clone_rule, context, rule_id, payload.name)


@router.post("/users", status_code=201)
def create_admin_user(payload: UserCreateRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(create_user, context, name=payload.name, email=str(payload.email), password=payload.password, profile=payload.profile, user_status=payload.user_status)


@router.get("/users")
def get_admin_users(context: AuthenticatedContext = Depends(get_current_context)):
    return _read(list_admin_users, context)


@router.patch("/users/{user_id}")
def patch_admin_user(user_id: int, payload: UserUpdateRequest, context: AuthenticatedContext = Depends(get_current_context)):
    fields = {"nome": payload.name, "email": str(payload.email).lower() if payload.email else None, "perfil": payload.profile, "status": payload.user_status, "must_change_password": payload.must_change_password}
    return _run(update_user, context, user_id, {key: value for key, value in fields.items() if value is not None})


@router.put("/drivers/{driver_id}")
def update_admin_driver(driver_id: int, payload: DriverRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(upsert_driver, context, driver_id, {"nome": payload.name, "equipe": payload.team, "status": payload.status, "numero": payload.number})


@router.get("/drivers")
def get_admin_drivers(context: AuthenticatedContext = Depends(get_current_context)):
    return _read(list_admin_drivers, context)


@router.post("/drivers", status_code=201)
def create_admin_driver(payload: DriverRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(upsert_driver, context, None, {"nome": payload.name, "equipe": payload.team, "status": payload.status, "numero": payload.number})


@router.get("/teams", response_model=list[AdminTeam])
def get_admin_teams(context: AuthenticatedContext = Depends(get_current_context)):
    return _read(list_admin_teams, context)


@router.post("/teams", status_code=201)
def create_admin_team(payload: TeamWriteRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(upsert_team, context, None, payload.model_dump())


@router.put("/teams/{team_id}")
def update_admin_team(team_id: int, payload: TeamWriteRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(upsert_team, context, team_id, payload.model_dump())


@router.put("/races/{race_id}")
def update_admin_race(race_id: int, season: str = Query(pattern=r"^\d{4}$"), payload: RaceRequest = ..., context: AuthenticatedContext = Depends(get_current_context)):
    return _run(upsert_race, context, race_id, season, {"nome": payload.name, "data": payload.date, "horario_prova": payload.time, "tipo": payload.type, "status": payload.race_status, "circuit_id": payload.circuit_id})


@router.post("/races", status_code=201)
def create_admin_race(season: str = Query(pattern=r"^\d{4}$"), payload: RaceRequest = ..., context: AuthenticatedContext = Depends(get_current_context)):
    return _run(upsert_race, context, None, season, {"nome": payload.name, "data": payload.date, "horario_prova": payload.time, "tipo": payload.type, "status": payload.race_status, "circuit_id": payload.circuit_id})


@router.get("/races")
def get_admin_races(season: str = Query(pattern=r"^\d{4}$"), context: AuthenticatedContext = Depends(get_current_context)):
    return _read(list_admin_races, context, season)


@router.get("/circuits", response_model=list[CircuitResponse])
def get_admin_circuits(context: AuthenticatedContext = Depends(get_current_context)):
    return _read(list_admin_circuits, context)


@router.post("/circuits/refresh", response_model=CircuitRefreshResponse)
def refresh_circuits(season: str = Query(pattern=r"^\d{4}$"), context: AuthenticatedContext = Depends(get_current_context)):
    try:
        return refresh_admin_circuits(context, season)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail="Acesso negado.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/results", response_model=ResultManagementResponse)
def get_admin_results(season: str = Query(pattern=r"^\d{4}$"), context: AuthenticatedContext = Depends(get_current_context)):
    return _read(get_result_management, context, season)


@router.put("/races/{race_id}/result", response_model=ResultProcessResponse)
def update_admin_result(race_id: int, season: str = Query(pattern=r"^\d{4}$"), payload: ResultRequest = ..., context: AuthenticatedContext = Depends(get_current_context)):
    try:
        return save_and_process_result(context, race_id, season, payload.positions, payload.retirements)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail="Acesso negado.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/hall-of-fame", response_model=HallAdminResponse)
def get_admin_hall(season: str | None = Query(default=None, pattern=r"^\d{4}$"), context: AuthenticatedContext = Depends(get_current_context)):
    try:
        return list_hall_admin(context, season)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail="Acesso negado.") from exc


@router.post("/hall-of-fame", status_code=201)
def create_admin_hall(payload: HallAdminWriteRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(save_hall_record, context, user_id=payload.user_id, season=payload.season, position=payload.position, points=payload.points)


@router.post("/hall-of-fame/bulk", status_code=201)
def bulk_admin_hall(payload: HallBulkRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(bulk_save_hall, context, [item.model_dump() for item in payload.records])


@router.put("/hall-of-fame/{record_id}")
def patch_admin_hall(record_id: int, payload: HallAdminUpdateRequest, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(update_hall_record, context, record_id, season=payload.season, position=payload.position, points=payload.points)


@router.delete("/hall-of-fame/{record_id}")
def remove_admin_hall(record_id: int, context: AuthenticatedContext = Depends(get_current_context)):
    return _run(delete_hall_record, context, record_id)
