"""Configuração isolada da suíte antes da coleta dos módulos da aplicação."""

from __future__ import annotations

import os


os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/bf1_test")
os.environ.setdefault("ALLOWED_ORIGINS", "https://bf1.test")
os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-thirty-two-bytes")
