"""Aplicação FastAPI da versão 4 do BF1."""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.config import settings
from api.request_context import RequestContext, reset_request_context, set_request_context
from api.routes import admin, analysis, auth, backup, calendar, championship, classification, content, f1_dashboard, hall_of_fame, logs, telemetry, users
from api.security import validate_csrf, validate_origin
from api.version import API_VERSION
from app_runtime import bind_runtime, reset_runtime
from utils.request_utils import select_client_ip

logger = logging.getLogger(__name__)
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    from db.db_schema import run_migrations
    from db.master_user_manager import MasterUserManager
    run_migrations()
    MasterUserManager.create_master_user()
    yield
    from db.connection_pool import close_pool
    close_pool()


app = FastAPI(
    title="BF1 API",
    version=API_VERSION,
    openapi_url="/api/v1/openapi.json",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
app.include_router(backup.router, prefix="/api/v1")


def _opaque_error(status_code: int, detail: str, request_id: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "request_id": request_id}, headers={"Cache-Control": "no-store"})


def _request_id_from(request: Request) -> str:
    candidate = (request.headers.get("x-request-id") or "").strip()
    return candidate if _SAFE_REQUEST_ID.fullmatch(candidate) else uuid.uuid4().hex


@app.middleware("http")
async def request_security_and_context(request: Request, call_next):
    started = time.perf_counter()
    request_id = _request_id_from(request)
    request.state.request_id = request_id
    direct_ip = request.client.host if request.client else None
    try:
        client_ip = select_client_ip(
            __import__("os").environ.get("TRUSTED_PROXY_MODE", "direct"), request.headers, direct_ip,
            int(__import__("os").environ.get("TRUSTED_PROXY_HOPS", "0")),
        )
    except (RuntimeError, ValueError):
        client_ip = direct_ip
    request.state.client_ip = client_ip
    context_token = set_request_context(RequestContext(request_id, client_ip))
    runtime_tokens = bind_runtime({"token": request.cookies.get(settings.cookie_name)}, headers=request.headers, direct_ip=direct_ip)
    response = None
    caught = None
    try:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            validate_origin(request)
            if request.cookies.get(settings.cookie_name):
                validate_csrf(request)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        return response
    except HTTPException as exc:
        response = _opaque_error(exc.status_code, str(exc.detail), request_id)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as exc:
        caught = exc
        logger.exception("Unhandled API error request_id=%s", request_id)
        response = _opaque_error(500, "Erro interno. Informe o código da requisição ao suporte.", request_id)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration = round((time.perf_counter() - started) * 1000, 3)
        try:
            from db.repo_observability import record_event
            auth_context = getattr(request.state, "auth", None)
            record_event(
                level="ERROR" if caught else "INFO", category="http", event="request_completed",
                message="Requisição HTTP concluída", request_id=request_id,
                user_id=getattr(auth_context, "user_id", None), route=request.url.path,
                method=request.method, status_code=response.status_code if response else 500,
                duration_ms=duration, exception_class=type(caught).__name__ if caught else None,
            )
        finally:
            reset_runtime(runtime_tokens)
            reset_request_context(context_token)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(getattr(request, "state", None), "request_id", None) or request.headers.get("x-request-id") or "unknown"
    return _opaque_error(exc.status_code, str(exc.detail), request_id[:128])


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, _: RequestValidationError):
    request_id = getattr(getattr(request, "state", None), "request_id", None) or request.headers.get("x-request-id") or "unknown"
    return _opaque_error(422, "Dados inválidos.", request_id[:128])


@app.get("/api/v1/health/live", tags=["health"])
def live():
    return {"status": "ok"}


@app.get("/api/v1/health/ready", tags=["health"])
def ready():
    from db.db_schema import db_connect
    with db_connect() as conn:
        conn.cursor().execute("SELECT 1")
    return {"status": "ready"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")
app.include_router(telemetry.router, prefix="/api/v1")
app.include_router(classification.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(hall_of_fame.router, prefix="/api/v1")
app.include_router(f1_dashboard.router, prefix="/api/v1")
app.include_router(championship.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
