import os
import re
import logging
import hashlib
import bcrypt
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import pandas as pd
import psycopg2
import psycopg2.extras

from db.db_config import DATABASE_URL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

@contextmanager
def db_connect():
    """Context manager que fornece uma conexão PostgreSQL com commit/rollback automático."""
    conn = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10,
    )
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_table_columns(conn, table_name: str) -> list[str]:
    """Retorna lista de colunas de uma tabela."""
    c = conn.cursor()
    c.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return [str(r[0]) for r in (c.fetchall() or []) if r]


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(senha: str) -> str:
    """Gera hash bcrypt da senha."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(senha: str, senha_hash: str) -> bool:
    """Verifica senha contra hash bcrypt."""
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def get_user_by_email(email: str) -> dict | None:
    """Busca usuário por email."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM usuarios WHERE email = %s",
                (email.strip().lower(),),
            )
            row = c.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.exception("Erro ao buscar usuário por email: %s", e)
        return None


def get_user_by_id(user_id: int) -> dict | None:
    """Busca usuário por ID."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
            row = c.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.exception("Erro ao buscar usuário por ID: %s", e)
        return None


def get_usuarios_df() -> pd.DataFrame:
    """Retorna DataFrame de todos os usuários."""
    with db_connect() as conn:
        return pd.read_sql_query("SELECT * FROM usuarios ORDER BY nome", conn)


def get_usuarios_ativos_df() -> pd.DataFrame:
    """Retorna DataFrame de usuários ativos."""
    with db_connect() as conn:
        return pd.read_sql_query(
            "SELECT * FROM usuarios WHERE status = 'Ativo' ORDER BY nome", conn
        )


# ---------------------------------------------------------------------------
# Provas helpers
# ---------------------------------------------------------------------------

def get_provas_df() -> pd.DataFrame:
    """Retorna DataFrame de todas as provas."""
    with db_connect() as conn:
        return pd.read_sql_query("SELECT * FROM provas ORDER BY data", conn)


def get_provas_ativas_df() -> pd.DataFrame:
    """Retorna DataFrame de provas ativas."""
    with db_connect() as conn:
        return pd.read_sql_query(
            "SELECT * FROM provas WHERE ativo = TRUE ORDER BY data", conn
        )


# ---------------------------------------------------------------------------
# Apostas helpers
# ---------------------------------------------------------------------------

def get_apostas_df() -> pd.DataFrame:
    """Retorna DataFrame de todas as apostas."""
    with db_connect() as conn:
        return pd.read_sql_query("SELECT * FROM apostas", conn)


def get_resultados_df() -> pd.DataFrame:
    """Retorna DataFrame de todos os resultados."""
    with db_connect() as conn:
        return pd.read_sql_query("SELECT * FROM resultados", conn)


# ---------------------------------------------------------------------------
# Log apostas
# ---------------------------------------------------------------------------

def get_log_apostas_df() -> pd.DataFrame:
    """Retorna DataFrame do log de apostas."""
    with db_connect() as conn:
        return pd.read_sql_query("SELECT * FROM log_apostas ORDER BY data DESC", conn)


def corrigir_log_apostas_datas(dry_run: bool = False) -> dict:
    """
    Corrige entradas no log_apostas onde data e horário estão trocados.
    Retorna dicionário com contagem de correções e erros.
    """
    stats = {"corrigidos": 0, "erros": 0, "ignorados": 0}
    DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")

    with db_connect() as conn:
        c = conn.cursor()
        c.execute("SELECT id, data, horario FROM log_apostas")
        rows = c.fetchall() or []

        for row in rows:
            rid = row["id"] if hasattr(row, "keys") else row[0]
            data_val = str(row["data"] if hasattr(row, "keys") else row[1] or "")
            horario_val = str(row["horario"] if hasattr(row, "keys") else row[2] or "")

            data_is_time = bool(TIME_RE.match(data_val))
            horario_is_date = bool(DATE_RE.match(horario_val))

            if data_is_time and horario_is_date:
                if not dry_run:
                    c.execute(
                        "UPDATE log_apostas SET data = %s, horario = %s WHERE id = %s",
                        (horario_val, data_val, rid),
                    )
                stats["corrigidos"] += 1
            elif data_is_time and not horario_is_date:
                if not dry_run:
                    c.execute(
                        "UPDATE log_apostas SET horario = %s WHERE id = %s",
                        (data_val, rid),
                    )
                stats["corrigidos"] += 1
            else:
                stats["ignorados"] += 1

        if not dry_run:
            conn.commit()

    return stats


# ---------------------------------------------------------------------------
# Temporadas helpers
# ---------------------------------------------------------------------------

def get_temporadas_ativas() -> list[str]:
    """Retorna lista de temporadas com apostas ou resultados."""
    with db_connect() as conn:
        c = conn.cursor()
        cols = get_table_columns(conn, "apostas")
        if "temporada" in cols:
            c.execute(
                """
                SELECT DISTINCT temporada
                FROM apostas
                WHERE TRIM(COALESCE(temporada, '')) <> ''
                ORDER BY temporada
                """
            )
        else:
            return []
        return [str(r[0]) for r in (c.fetchall() or []) if r and r[0]]


def get_usuario_temporadas_ativas(usuario_id: int) -> list[str]:
    """
    Retorna temporadas em que o usuário tem apostas ou posições registradas.
    Combina apostas + posicoes_participantes para garantir cobertura completa.
    """
    temporadas: set[str] = set()

    with db_connect() as conn:
        apostas_cols = get_table_columns(conn, "apostas")
        posicoes_cols = get_table_columns(conn, "posicoes_participantes")
        champ_cols = get_table_columns(conn, "championship_bets") if _table_exists(conn, "championship_bets") else []

        c = conn.cursor()

        if "temporada" in apostas_cols:
            c.execute(
                """
                SELECT DISTINCT temporada
                FROM apostas
                WHERE usuario_id = %s AND TRIM(COALESCE(temporada, '')) <> ''
                """,
                (usuario_id,),
            )
            for r in (c.fetchall() or []):
                v = r[0] if not hasattr(r, "keys") else r["temporada"]
                if v:
                    temporadas.add(str(v))

        if "temporada" in posicoes_cols and "usuario_id" in posicoes_cols:
            c.execute(
                """
                SELECT DISTINCT temporada
                FROM posicoes_participantes
                WHERE usuario_id = %s AND TRIM(COALESCE(temporada, '')) <> ''
                """,
                (usuario_id,),
            )
            for r in (c.fetchall() or []):
                v = r[0] if not hasattr(r, "keys") else r["temporada"]
                if v:
                    temporadas.add(str(v))

        if champ_cols and "user_id" in champ_cols and "season" in champ_cols:
            c.execute(
                """
                SELECT DISTINCT TRIM(CAST(season AS TEXT))
                FROM championship_bets
                WHERE user_id = %s AND TRIM(CAST(season AS TEXT)) <> ''
                """,
                (usuario_id,),
            )
            for r in (c.fetchall() or []):
                v = r[0] if not hasattr(r, "keys") else r[0]
                if v:
                    temporadas.add(str(v))

    return sorted(temporadas)


def _table_exists(conn, table_name: str) -> bool:
    """Verifica se uma tabela existe no schema atual."""
    c = conn.cursor()
    c.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = current_schema() AND table_name = %s
        """,
        (table_name,),
    )
    return c.fetchone() is not None


# ---------------------------------------------------------------------------
# Status histórico helpers
# ---------------------------------------------------------------------------

def registrar_mudanca_status(
    usuario_id: int,
    novo_status: str,
    alterado_por: int | None = None,
    motivo: str | None = None,
) -> bool:
    """Registra mudança de status no histórico."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, "usuarios_status_historico")
            if not cols:
                return False

            c.execute(
                """
                SELECT id FROM usuarios_status_historico
                WHERE usuario_id = %s AND fim_em IS NULL
                ORDER BY inicio_em DESC LIMIT 1
                """,
                (usuario_id,),
            )
            anterior = c.fetchone()
            if anterior:
                ant_id = anterior[0] if not hasattr(anterior, "keys") else anterior["id"]
                c.execute(
                    "UPDATE usuarios_status_historico SET fim_em = %s WHERE id = %s",
                    (datetime.utcnow().isoformat(), ant_id),
                )

            insert_cols = ["usuario_id", "status", "inicio_em"]
            insert_vals: list[Any] = [usuario_id, novo_status, datetime.utcnow().isoformat()]

            if "alterado_por" in cols and alterado_por is not None:
                insert_cols.append("alterado_por")
                insert_vals.append(alterado_por)
            if "motivo" in cols and motivo is not None:
                insert_cols.append("motivo")
                insert_vals.append(motivo)

            placeholders = ', '.join(['%s'] * len(insert_cols))
            col_sql = ', '.join(insert_cols)
            c.execute(
                f"INSERT INTO usuarios_status_historico ({col_sql}) VALUES ({placeholders})",
                insert_vals,
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Erro ao registrar mudança de status: %s", e)
        return False


# ---------------------------------------------------------------------------
# Email / Password update
# ---------------------------------------------------------------------------

def atualizar_email_usuario(user_id: int, novo_email: str) -> bool:
    """Atualiza o email de um usuário."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            c.execute('UPDATE usuarios SET email = %s WHERE id = %s', (novo_email, user_id))
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Erro ao atualizar email: %s", e)
        return False


def atualizar_senha_usuario(user_id: int, nova_senha: str) -> bool:
    """Atualiza a senha de um usuário."""
    try:
        senha_hash = hash_password(nova_senha)
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, "usuarios")
            if "must_change_password" in cols:
                c.execute(
                    'UPDATE usuarios SET senha_hash = %s, must_change_password = 0 WHERE id = %s',
                    (senha_hash, user_id),
                )
            else:
                c.execute('UPDATE usuarios SET senha_hash = %s WHERE id = %s', (senha_hash, user_id))
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Erro ao atualizar senha: %s", e)
        return False


# ---------------------------------------------------------------------------
# Prova nome helper
# ---------------------------------------------------------------------------

def get_nome_prova(prova_id: int) -> str:
    """Retorna o nome de uma prova pelo ID."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, "provas")
            if "horario_prova" in cols:
                c.execute('SELECT nome, data, horario_prova FROM provas WHERE id = %s', (prova_id,))
            else:
                c.execute('SELECT nome, data FROM provas WHERE id = %s', (prova_id,))
            row = c.fetchone()
            if row:
                nome = row[0] if not hasattr(row, "keys") else row["nome"]
                return str(nome)
            return f"Prova {prova_id}"
    except Exception as e:
        logger.exception("Erro ao buscar nome da prova: %s", e)
        return f"Prova {prova_id}"
