from __future__ import annotations

import importlib
import re
from typing import Any, Optional


class InputValidationError(ValueError):
    pass


def _validate_email_basic(value: str) -> str:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    normalized = (value or "").strip().lower()
    if not re.match(pattern, normalized):
        raise InputValidationError("Email invalido")
    return normalized


def _validate_temporada(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized and not re.match(r"^\d{4}$", normalized):
        raise InputValidationError("Temporada deve seguir formato YYYY")
    return normalized or None


def _validate_nome_simples(value: str, field_name: str, max_len: int = 120) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise InputValidationError(f"{field_name} obrigatorio")
    if len(normalized) > max_len:
        raise InputValidationError(f"{field_name} excede tamanho maximo")
    return normalized


try:
    pydantic = importlib.import_module("pydantic")
    BaseModel = pydantic.BaseModel
    ConfigDict = pydantic.ConfigDict
    Field = pydantic.Field
    field_validator = pydantic.field_validator
    PydanticValidationError = pydantic.ValidationError

    class _LoginInputPydantic(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True)

        email: str = Field(min_length=5, max_length=254)
        senha: str = Field(min_length=1, max_length=256)

        @field_validator("email")
        @classmethod
        def validate_email(cls, value: str) -> str:
            return _validate_email_basic(value)

    class _BetSubmissionInputPydantic(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True)

        usuario_id: int = Field(gt=0)
        prova_id: int = Field(gt=0)
        pilotos: list[str] = Field(min_length=1)
        fichas: list[int] = Field(min_length=1)
        piloto_11: str = Field(min_length=1, max_length=100)
        nome_prova: str = Field(min_length=1, max_length=200)
        automatica: int = Field(ge=0, default=0)
        temporada: Optional[str] = Field(default=None, max_length=10)

        @field_validator("pilotos")
        @classmethod
        def validate_pilotos(cls, value: list[str]) -> list[str]:
            normalized = [str(v).strip() for v in value if str(v).strip()]
            if not normalized:
                raise InputValidationError("Lista de pilotos vazia")
            if len(set(normalized)) != len(normalized):
                raise InputValidationError("Pilotos repetidos nao sao permitidos")
            return normalized

        @field_validator("fichas")
        @classmethod
        def validate_fichas(cls, value: list[int]) -> list[int]:
            if any(int(v) < 0 for v in value):
                raise InputValidationError("Fichas devem ser nao negativas")
            return [int(v) for v in value]

        @field_validator("temporada")
        @classmethod
        def validate_temporada(cls, value: Optional[str]) -> Optional[str]:
            return _validate_temporada(value)

    class _ChampionshipBetInputPydantic(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True)

        user_id: int = Field(gt=0)
        user_nome: str = Field(min_length=1, max_length=120)
        champion: str = Field(min_length=1, max_length=120)
        vice: str = Field(min_length=1, max_length=120)
        team: str = Field(min_length=1, max_length=120)
        season: Optional[int] = Field(default=None, ge=2000, le=2100)

    class _ChampionshipResultInputPydantic(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True)

        champion: str = Field(min_length=1, max_length=120)
        vice: str = Field(min_length=1, max_length=120)
        team: str = Field(min_length=1, max_length=120)
        season: Optional[int] = Field(default=None, ge=2000, le=2100)

except Exception:
    PydanticValidationError = InputValidationError

    class _LoginInputFallback:
        def __init__(self, email: str, senha: str):
            senha_norm = (senha or "").strip()
            if not senha_norm:
                raise InputValidationError("Senha invalida")
            self.email = _validate_email_basic(email)
            self.senha = senha_norm

    class _BetSubmissionInputFallback:
        def __init__(
            self,
            usuario_id: Any,
            prova_id: Any,
            pilotos: list[str],
            fichas: list[int],
            piloto_11: str,
            nome_prova: str,
            automatica: int = 0,
            temporada: Optional[str] = None,
        ):
            self.usuario_id = int(usuario_id)
            self.prova_id = int(prova_id)
            if self.usuario_id <= 0 or self.prova_id <= 0:
                raise InputValidationError("IDs invalidos")

            normalized_pilotos = [str(v).strip() for v in (pilotos or []) if str(v).strip()]
            if not normalized_pilotos:
                raise InputValidationError("Lista de pilotos vazia")
            if len(set(normalized_pilotos)) != len(normalized_pilotos):
                raise InputValidationError("Pilotos repetidos nao sao permitidos")
            self.pilotos = normalized_pilotos

            normalized_fichas = [int(v) for v in (fichas or [])]
            if not normalized_fichas:
                raise InputValidationError("Lista de fichas vazia")
            if any(v < 0 for v in normalized_fichas):
                raise InputValidationError("Fichas devem ser nao negativas")
            self.fichas = normalized_fichas

            self.piloto_11 = str(piloto_11 or "").strip()
            self.nome_prova = str(nome_prova or "").strip()
            if not self.piloto_11 or not self.nome_prova:
                raise InputValidationError("Campos obrigatorios ausentes")

            self.automatica = int(automatica)
            if self.automatica < 0:
                raise InputValidationError("Campo automatica invalido")

            self.temporada = _validate_temporada(temporada)

    class _ChampionshipBetInputFallback:
        def __init__(
            self,
            user_id: Any,
            user_nome: str,
            champion: str,
            vice: str,
            team: str,
            season: Optional[int] = None,
        ):
            self.user_id = int(user_id)
            if self.user_id <= 0:
                raise InputValidationError("user_id invalido")
            self.user_nome = _validate_nome_simples(user_nome, "user_nome")
            self.champion = _validate_nome_simples(champion, "champion")
            self.vice = _validate_nome_simples(vice, "vice")
            self.team = _validate_nome_simples(team, "team")
            self.season = int(season) if season is not None else None
            if self.season is not None and not (2000 <= self.season <= 2100):
                raise InputValidationError("season invalida")

    class _ChampionshipResultInputFallback:
        def __init__(self, champion: str, vice: str, team: str, season: Optional[int] = None):
            self.champion = _validate_nome_simples(champion, "champion")
            self.vice = _validate_nome_simples(vice, "vice")
            self.team = _validate_nome_simples(team, "team")
            self.season = int(season) if season is not None else None
            if self.season is not None and not (2000 <= self.season <= 2100):
                raise InputValidationError("season invalida")


if "_LoginInputPydantic" in globals():
    LoginInput = _LoginInputPydantic
    BetSubmissionInput = _BetSubmissionInputPydantic
    ChampionshipBetInput = _ChampionshipBetInputPydantic
    ChampionshipResultInput = _ChampionshipResultInputPydantic
else:
    LoginInput = _LoginInputFallback
    BetSubmissionInput = _BetSubmissionInputFallback
    ChampionshipBetInput = _ChampionshipBetInputFallback
    ChampionshipResultInput = _ChampionshipResultInputFallback

ValidationError = PydanticValidationError
