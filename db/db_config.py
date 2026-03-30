"""Configurações centralizadas de banco de dados."""

from __future__ import annotations

import os

# URL do banco para produção (ex.: PostgreSQL gerenciado)
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_BACKEND = "postgres"

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não configurada. Esta aplicação opera exclusivamente com PostgreSQL 18."
    )

if not DATABASE_URL.lower().startswith(("postgres://", "postgresql://")):
    raise RuntimeError(
        "DATABASE_URL inválida. Use uma URL PostgreSQL (postgresql://...)."
    )

# Configurações de Pool
POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "5"))
DB_TIMEOUT = float(os.environ.get("DB_TIMEOUT", "30.0"))
DB_MIN_CONN = int(os.environ.get("DB_MIN_CONN", "1"))
DB_MAX_CONN = int(os.environ.get("DB_MAX_CONN", str(max(POOL_SIZE, 5))))
DB_CONN_MAX_LIFETIME = float(os.environ.get("DB_CONN_MAX_LIFETIME", "1800"))

# Configurações de Cache
CACHE_TTL_CURTO = int(os.environ.get("CACHE_TTL_CURTO", "300"))  # 5 minutos
CACHE_TTL_MEDIO = int(os.environ.get("CACHE_TTL_MEDIO", "3600"))  # 1 hora
CACHE_TTL_LONGO = int(os.environ.get("CACHE_TTL_LONGO", "86400"))  # 24 horas

# Índices para otimização (criados em migrations.py)
INDICES = {
    "usuarios": [
        "CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email)",
        "CREATE INDEX IF NOT EXISTS idx_usuarios_perfil ON usuarios(perfil)",
        "CREATE INDEX IF NOT EXISTS idx_usuarios_status ON usuarios(status)",
    ],
    "apostas": [
        "CREATE INDEX IF NOT EXISTS idx_apostas_usuario ON apostas(usuario_id)",
        "CREATE INDEX IF NOT EXISTS idx_apostas_prova ON apostas(prova_id)",
        "CREATE INDEX IF NOT EXISTS idx_apostas_data ON apostas(data_envio)",
        "CREATE INDEX IF NOT EXISTS idx_apostas_temporada ON apostas(temporada)",
        "CREATE INDEX IF NOT EXISTS idx_apostas_usuario_prova_temporada ON apostas(usuario_id, prova_id, temporada)",
    ],
    "provas": [
        "CREATE INDEX IF NOT EXISTS idx_provas_data ON provas(data)",
        "CREATE INDEX IF NOT EXISTS idx_provas_status ON provas(status)",
        "CREATE INDEX IF NOT EXISTS idx_provas_temporada_data ON provas(temporada, data)",
    ],
    "resultados": [
        "CREATE INDEX IF NOT EXISTS idx_resultados_prova ON resultados(prova_id)",
        "CREATE INDEX IF NOT EXISTS idx_resultados_prova_temporada ON resultados(prova_id, temporada)",
    ],
}

# Configurações de Segurança
BCRYPT_ROUNDS = int(os.environ.get("BCRYPT_ROUNDS", "12"))
SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "3600"))  # 1 hora em segundos
MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_DURATION = int(os.environ.get("LOCKOUT_DURATION", "900"))  # 15 minutos
MAX_RESET_ATTEMPTS = int(os.environ.get("MAX_RESET_ATTEMPTS", "3"))
RESET_LOCKOUT_DURATION = int(os.environ.get("RESET_LOCKOUT_DURATION", "900"))  # 15 minutos
