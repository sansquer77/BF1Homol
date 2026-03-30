"""PostgreSQL migrations and schema hardening."""

import datetime
import logging

from db.circuitos_utils import ensure_circuitos_f1_table, ensure_provas_circuit_id_column
from db.connection_pool import get_pool
from db.db_config import INDICES
from db.db_utils import get_table_columns, init_db, table_exists

logger = logging.getLogger(__name__)


def _add_column_if_missing(cursor, conn, table_name: str, column_name: str, ddl: str) -> None:
    cols = get_table_columns(conn, table_name)
    if column_name not in cols:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")
        logger.info("✓ Coluna `%s` adicionada a `%s`", column_name, table_name)


def add_temporada_columns_if_missing() -> None:
    pool = get_pool()
    current_year = str(datetime.datetime.now().year)
    tables_to_update = ("provas", "apostas", "resultados", "posicoes_participantes")

    with pool.get_connection() as conn:
        cursor = conn.cursor()
        for table_name in tables_to_update:
            try:
                if table_exists(conn, table_name):
                    _add_column_if_missing(cursor, conn, table_name, "temporada", f"temporada TEXT DEFAULT '{current_year}'")
            except Exception as exc:
                logger.debug("Erro ao adicionar temporada em %s: %s", table_name, exc)
        conn.commit()


def add_abandono_column_if_missing() -> None:
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            if table_exists(conn, "resultados"):
                _add_column_if_missing(cursor, conn, "resultados", "abandono_pilotos", "abandono_pilotos TEXT DEFAULT ''")
            conn.commit()
        except Exception as exc:
            logger.debug("Erro ao adicionar abandono_pilotos: %s", exc)
            conn.rollback()


def add_legacy_columns_if_missing() -> None:
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            if table_exists(conn, "pilotos"):
                _add_column_if_missing(cursor, conn, "pilotos", "equipe", "equipe TEXT DEFAULT ''")
                _add_column_if_missing(cursor, conn, "pilotos", "status", "status TEXT DEFAULT 'Ativo'")
                _add_column_if_missing(cursor, conn, "pilotos", "numero", "numero INTEGER DEFAULT 0")

            if table_exists(conn, "provas"):
                _add_column_if_missing(cursor, conn, "provas", "horario_prova", "horario_prova TEXT DEFAULT ''")
                _add_column_if_missing(cursor, conn, "provas", "tipo", "tipo TEXT DEFAULT 'Normal'")

            conn.commit()
        except Exception as exc:
            logger.debug("Erro ao adicionar colunas legadas: %s", exc)
            conn.rollback()


def add_password_reset_flag_if_missing() -> None:
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            if table_exists(conn, "usuarios"):
                _add_column_if_missing(cursor, conn, "usuarios", "must_change_password", "must_change_password INTEGER DEFAULT 0")
            conn.commit()
        except Exception as exc:
            logger.debug("Erro ao adicionar must_change_password: %s", exc)
            conn.rollback()


def add_login_attempts_action_if_missing() -> None:
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            if table_exists(conn, "login_attempts"):
                _add_column_if_missing(cursor, conn, "login_attempts", "action", "action TEXT DEFAULT 'login'")
            conn.commit()
        except Exception as exc:
            logger.debug("Erro ao adicionar action: %s", exc)
            conn.rollback()


def add_login_attempts_ip_if_missing() -> None:
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            if table_exists(conn, "login_attempts"):
                _add_column_if_missing(cursor, conn, "login_attempts", "ip_address", "ip_address TEXT")
            conn.commit()
        except Exception as exc:
            logger.debug("Erro ao adicionar ip_address: %s", exc)
            conn.rollback()


def add_penalidade_auto_percent_if_missing() -> None:
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            if table_exists(conn, "regras"):
                _add_column_if_missing(
                    cursor,
                    conn,
                    "regras",
                    "penalidade_auto_percent",
                    "penalidade_auto_percent INTEGER NOT NULL DEFAULT 20",
                )
            conn.commit()
        except Exception as exc:
            logger.debug("Erro ao adicionar penalidade_auto_percent: %s", exc)
            conn.rollback()


def create_usuarios_status_historico_if_missing() -> None:
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios_status_historico (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    inicio_em TIMESTAMP NOT NULL,
                    fim_em TIMESTAMP,
                    alterado_por INTEGER,
                    motivo TEXT,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ush_usuario_id ON usuarios_status_historico(usuario_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ush_status ON usuarios_status_historico(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ush_periodo ON usuarios_status_historico(inicio_em, fim_em)")

            user_cols = get_table_columns(conn, "usuarios") if table_exists(conn, "usuarios") else []
            created_expr = "criado_em" if "criado_em" in user_cols else "CURRENT_TIMESTAMP"
            cursor.execute(
                f"""
                INSERT INTO usuarios_status_historico (usuario_id, status, inicio_em, fim_em, alterado_por, motivo)
                SELECT u.id, u.status, {created_expr}, NULL, NULL, 'backfill'
                FROM usuarios u
                WHERE NOT EXISTS (
                    SELECT 1 FROM usuarios_status_historico h WHERE h.usuario_id = u.id
                )
                """
            )
            conn.commit()
        except Exception as exc:
            logger.debug("Erro ao criar usuarios_status_historico: %s", exc)
            conn.rollback()


def create_missing_tables_if_needed() -> None:
    pool = get_pool()
    current_year = datetime.datetime.now().year

    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS championship_bets (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    user_nome TEXT NOT NULL,
                    champion TEXT NOT NULL,
                    vice TEXT NOT NULL,
                    team TEXT NOT NULL,
                    season INTEGER NOT NULL,
                    bet_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES usuarios(id),
                    UNIQUE(user_id, season)
                )
                """
            )

            if table_exists(conn, "championship_bets"):
                _add_column_if_missing(cursor, conn, "championship_bets", "season", f"season INTEGER NOT NULL DEFAULT {current_year}")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS championship_results (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    season INTEGER NOT NULL,
                    champion TEXT NOT NULL,
                    vice TEXT NOT NULL,
                    team TEXT NOT NULL,
                    UNIQUE(season)
                )
                """
            )

            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS championship_bets_log (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    user_nome TEXT NOT NULL,
                    champion TEXT NOT NULL,
                    vice TEXT NOT NULL,
                    team TEXT NOT NULL,
                    season INTEGER NOT NULL DEFAULT {current_year},
                    bet_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES usuarios(id)
                )
                """
            )

            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS log_apostas (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    usuario_id INTEGER,
                    prova_id INTEGER,
                    apostador TEXT,
                    aposta TEXT,
                    nome_prova TEXT,
                    pilotos TEXT,
                    piloto_11 TEXT,
                    tipo_aposta INTEGER,
                    automatica INTEGER,
                    data TEXT,
                    horario TIMESTAMP,
                    ip_address TEXT,
                    temporada TEXT DEFAULT '{current_year}',
                    status TEXT DEFAULT 'Registrada',
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                    FOREIGN KEY (prova_id) REFERENCES provas(id)
                )
                """
            )

            conn.commit()
        except Exception as exc:
            logger.debug("Erro ao criar tabelas faltantes: %s", exc)
            conn.rollback()


def run_migrations() -> None:
    init_db()

    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        try:
            create_missing_tables_if_needed()
            ensure_circuitos_f1_table()
            ensure_provas_circuit_id_column()
            add_temporada_columns_if_missing()
            add_abandono_column_if_missing()
            add_legacy_columns_if_missing()
            add_password_reset_flag_if_missing()
            add_login_attempts_action_if_missing()
            add_login_attempts_ip_if_missing()
            add_penalidade_auto_percent_if_missing()
            create_usuarios_status_historico_if_missing()

            for idx in INDICES.get("usuarios", []):
                cursor.execute(idx)
            for idx in INDICES.get("apostas", []):
                cursor.execute(idx)
            for idx in INDICES.get("provas", []):
                cursor.execute(idx)
            for idx in INDICES.get("resultados", []):
                cursor.execute(idx)

            conn.commit()
            logger.info("✓ Todas as migrations executadas com sucesso")
        except Exception as exc:
            logger.error("✗ Erro ao executar migrations: %s", exc)
            conn.rollback()
            raise


def create_hall_da_fama_table() -> None:
    try:
        with get_pool().get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS hall_da_fama (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    temporada TEXT NOT NULL,
                    posicao_final INTEGER NOT NULL,
                    pontos REAL DEFAULT 0,
                    UNIQUE(usuario_id, temporada),
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                )
                """
            )
            conn.commit()
            logger.info("✓ Tabela hall_da_fama criada com sucesso")
    except Exception as exc:
        logger.error("Erro ao criar tabela hall_da_fama: %s", exc)
        raise


try:
    create_hall_da_fama_table()
except Exception:
    pass
