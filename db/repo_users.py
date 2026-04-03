"""Repositório focado em usuários."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import bcrypt
import pandas as pd

from db.db_schema import db_connect, get_table_columns, table_exists

logger = logging.getLogger(__name__)

_COLUNAS_USUARIOS_VALIDAS: frozenset[str] = frozenset(
    {
        "nome",
        "email",
        "senha_hash",
        "perfil",
        "status",
        "must_change_password",
        "faltas",
        "criado_em",
    }
)


def _query_to_df(query: str, params: tuple | None = None) -> pd.DataFrame:
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(query, params or ())
        rows = cur.fetchall() or []
        if not rows:
            col_names = [desc[0] for desc in (cur.description or [])]
            cur.close()
            return pd.DataFrame(columns=col_names)
        cur.close()
    return pd.DataFrame([dict(r) for r in rows])


def _usuarios_status_historico_exists(conn) -> bool:
    return table_exists(conn, "usuarios_status_historico")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def get_user_by_email(email: str) -> Optional[dict]:
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None


def get_master_user() -> Optional[dict]:
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE perfil = 'master' LIMIT 1")
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None


def cadastrar_usuario(nome: str, email: str, senha: str, perfil: str = "participante") -> bool:
    try:
        hashed = hash_password(senha)
        with db_connect() as conn:
            cur = conn.cursor()
            cols = get_table_columns(conn, "usuarios")
            if "faltas" in cols:
                cur.execute(
                    "INSERT INTO usuarios (nome, email, senha_hash, perfil, faltas) VALUES (%s, %s, %s, %s, %s)",
                    (nome, email, hashed, perfil, 0),
                )
            else:
                cur.execute(
                    "INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (%s, %s, %s, %s)",
                    (nome, email, hashed, perfil),
                )
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("cadastrar_usuario falhou: %s", exc)
        return False


def autenticar_usuario(email: str, senha: str) -> Optional[dict]:
    user = get_user_by_email(email)
    if user and check_password(senha, user["senha_hash"]):
        return user
    return None


def update_user_email(user_id: int, novo_email: str) -> bool:
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE usuarios SET email = %s WHERE id = %s",
                (novo_email, user_id),
            )
            cur.close()
            conn.commit()
        logger.info("Email do usuário %s atualizado", user_id)
        return True
    except Exception as exc:
        logger.error("Erro ao atualizar email: %s", exc)
        return False


def update_user_password(user_id: int, nova_senha: str) -> bool:
    try:
        if isinstance(nova_senha, str) and nova_senha.startswith("$2"):
            senha_hash = nova_senha
        else:
            senha_hash = hash_password(nova_senha)
        with db_connect() as conn:
            cur = conn.cursor()
            cols = get_table_columns(conn, "usuarios")
            if "must_change_password" in cols:
                cur.execute(
                    "UPDATE usuarios SET senha_hash = %s, must_change_password = FALSE WHERE id = %s",
                    (senha_hash, user_id),
                )
            else:
                cur.execute(
                    "UPDATE usuarios SET senha_hash = %s WHERE id = %s",
                    (senha_hash, user_id),
                )
            cur.close()
            conn.commit()
        logger.info("Senha do usuário %s atualizada", user_id)
        return True
    except Exception as exc:
        logger.error("Erro ao atualizar senha: %s", exc)
        return False


def update_usuario(user_id: int, **campos) -> bool:
    if not campos:
        return False
    campos_invalidos = set(campos) - _COLUNAS_USUARIOS_VALIDAS
    if campos_invalidos:
        logger.error("update_usuario: colunas não permitidas rejeitadas: %s", campos_invalidos)
        raise ValueError(f"Colunas não permitidas em update_usuario: {campos_invalidos}")
    set_clause = ", ".join(f"{k} = %s" for k in campos)
    values = list(campos.values()) + [user_id]
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE usuarios SET {set_clause} WHERE id = %s", values)
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.error("update_usuario falhou: %s", exc)
        return False


def delete_usuario(user_id: int) -> bool:
    try:
        with db_connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
            cur.close()
            conn.commit()
        return True
    except Exception as exc:
        logger.error("delete_usuario falhou: %s", exc)
        return False


def get_usuarios_df() -> pd.DataFrame:
    return _query_to_df("SELECT * FROM usuarios")


def usuarios_status_historico_disponivel() -> bool:
    with db_connect() as conn:
        return _usuarios_status_historico_exists(conn)


def registrar_historico_status_usuario(
    usuario_id: int,
    novo_status: str,
    alterado_por: Optional[int] = None,
    motivo: Optional[str] = None,
    data_referencia: Optional[str] = None,
) -> None:
    if data_referencia is None:
        data_referencia = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db_connect() as conn:
        cursor = conn.cursor()
        if not _usuarios_status_historico_exists(conn):
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios_status_historico (
                    id          INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    usuario_id  INTEGER NOT NULL,
                    status      TEXT NOT NULL,
                    inicio_em   TIMESTAMP NOT NULL,
                    fim_em      TIMESTAMP,
                    alterado_por INTEGER,
                    motivo      TEXT,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                )
                """
            )

        cursor.execute(
            "SELECT id, status FROM usuarios_status_historico "
            "WHERE usuario_id = %s AND fim_em IS NULL ORDER BY inicio_em DESC LIMIT 1",
            (usuario_id,),
        )
        row = cursor.fetchone()
        if row and row["status"] == novo_status:
            cursor.close()
            return

        if row:
            cursor.execute(
                "UPDATE usuarios_status_historico SET fim_em = %s WHERE id = %s",
                (data_referencia, row["id"]),
            )

        cursor.execute(
            """
            INSERT INTO usuarios_status_historico
                (usuario_id, status, inicio_em, fim_em, alterado_por, motivo)
            VALUES (%s, %s, %s, NULL, %s, %s)
            """,
            (usuario_id, novo_status, data_referencia, alterado_por, motivo),
        )
        cursor.close()
        conn.commit()


def get_usuario_temporadas_ativas(user_id: int) -> list[str]:
    def _infer_por_atividade(user_id: int) -> list[str]:
        temporadas: set[str] = set()
        df = _query_to_df(
            "SELECT DISTINCT trim(coalesce(temporada,'')) AS t FROM apostas "
            "WHERE usuario_id = %s AND trim(coalesce(temporada,'')) <> ''",
            (int(user_id),),
        )
        temporadas.update(df["t"].tolist() if not df.empty else [])

        with db_connect() as conn:
            log_cols = set(get_table_columns(conn, "log_apostas")) if table_exists(conn, "log_apostas") else set()
        user_col = "usuario_id" if "usuario_id" in log_cols else ("user_id" if "user_id" in log_cols else None)
        if user_col:
            parts = []
            if "temporada" in log_cols:
                parts.append("NULLIF(trim(coalesce(temporada,'')),'')")
            if "data" in log_cols:
                parts.append("NULLIF(trim(substr(coalesce(data,''),1,4)),'')")
            if parts:
                df2 = _query_to_df(
                    f"SELECT DISTINCT COALESCE({', '.join(parts)}) AS t "
                    f"FROM log_apostas WHERE {user_col} = %s",
                    (int(user_id),),
                )
                temporadas.update([v for v in df2["t"].tolist() if v] if not df2.empty else [])

        with db_connect() as conn:
            has_pos = table_exists(conn, "posicoes_participantes")
        if has_pos:
            df3 = _query_to_df(
                "SELECT DISTINCT trim(coalesce(temporada,'')) AS t "
                "FROM posicoes_participantes "
                "WHERE usuario_id = %s AND trim(coalesce(temporada,'')) <> ''",
                (int(user_id),),
            )
            temporadas.update(df3["t"].tolist() if not df3.empty else [])

        return sorted(temporadas)

    df_base = _query_to_df(
        """
        SELECT DISTINCT COALESCE(NULLIF(trim(temporada),''), substr(data,1,4)) AS t
        FROM provas
        WHERE COALESCE(NULLIF(trim(temporada),''), substr(data,1,4)) IS NOT NULL
        ORDER BY t
        """
    )
    temporadas_base = [str(v).strip() for v in df_base["t"].tolist() if v] if not df_base.empty else []
    if not temporadas_base:
        return []

    with db_connect() as conn:
        has_hist = _usuarios_status_historico_exists(conn)

    if not has_hist:
        user = get_user_by_id(int(user_id))
        status = str(user.get("status", "")).strip().lower() if user else ""
        if status == "ativo":
            return temporadas_base
        return _infer_por_atividade(int(user_id))

    df_ativas = _query_to_df(
        """
        SELECT DISTINCT s.t
        FROM (
            SELECT COALESCE(NULLIF(trim(temporada),''), substr(data,1,4)) AS t
            FROM provas
        ) s
        JOIN usuarios_status_historico h ON h.usuario_id = %s
        WHERE lower(trim(coalesce(h.status,''))) = 'ativo'
          AND h.inicio_em <= (s.t || '-12-31 23:59:59')::timestamp
          AND (h.fim_em IS NULL OR h.fim_em >= (s.t || '-01-01 00:00:00')::timestamp)
        ORDER BY s.t
        """,
        (int(user_id),),
    )
    if not df_ativas.empty:
        return [str(v).strip() for v in df_ativas["t"].tolist() if v]

    return _infer_por_atividade(int(user_id))

__all__ = [
    "hash_password",
    "check_password",
    "get_user_by_email",
    "get_user_by_id",
    "get_master_user",
    "cadastrar_usuario",
    "autenticar_usuario",
    "update_user_email",
    "update_user_password",
    "update_usuario",
    "delete_usuario",
    "get_usuarios_df",
    "usuarios_status_historico_disponivel",
    "registrar_historico_status_usuario",
    "get_usuario_temporadas_ativas",
]
