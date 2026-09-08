"""Schemas públicos do contrato /api/v1."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    token: str = Field(min_length=16, max_length=512)
    new_password: str = Field(min_length=8, max_length=1024)


class UserResponse(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    status: str
    must_change_password: bool = False


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
    request_id: str


class AboutResponse(BaseModel):
    name: str
    full_name: str
    version: str
    architecture: str


class RaceResponse(BaseModel):
    id: int
    name: str
    date: str
    time: str | None = None
    type: str
    status: str
    season: str
    circuit_id: str | None = None
