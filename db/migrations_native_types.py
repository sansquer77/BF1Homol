"""
Migração de tipos nativos - BF1 v3.1
======================================
Adição de colunas com tipos PostgreSQL nativos em paralelo às colunas TEXT
existentes. As colunas TEXT originais NÃO são removidas, garantindo:

  - Zero risco de perda de dados
  - Zero quebra de código legado (continua lendo TEXT)
  - Ganho imediato de performance via índices nos novos campos tipados
  - Rollback trivial (basta ignorar as novas colunas)

Colunas adicionadas:
  provas.data          TEXT  →  provas.data_date       DATE
  provas.horario_prova TEXT  →  provas.horario_ts      TIME
  apostas.data_envio   TEXT  →  apostas.data_envio_ts  TIMESTAMPTZ
  apostas.pilotos      TEXT  →  apostas.pilotos_arr    TEXT[]   (array nativo)
  apostas.fichas       TEXT  →  apostas.fichas_arr     INTEGER[]
  resultados.posicoes  TEXT  →  resultados.posicoes_jsonb  JSONB
  resultados.abandono_pilotos TEXT → resultados.abandono_arr TEXT[]
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from db.connection_pool import get_pool
from db.db_utils import get_table_columns, table_exists

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de conversão (TEXT → tipo nativo)
# ---------------------------------------------------------------------------

def _safe_date(txt: Optional[str]) -> Optional[str]:
    """Converte string 'YYYY-MM-DD' (ou ISO) para DATE-compatível, ou None."""
    if not txt:
        return None
    s = str(txt).strip()
    # Aceita YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS...
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return s[:10]
    return None


def _safe_time(txt: Optional[str]) -> Optional[str]:
    """Converte string 'HH:MM' ou 'HH:MM:SS' para TIME-compatível, ou None."""
    if not txt:
        return None
    s = str(txt).strip()
    # HH:MM:SS
    if len(s) >= 8 and s[2] == ':' and s[5] == ':':
        return s[:8]
    # HH:MM
    if len(s) >= 5 and s[2] == ':':
        return s[:5] + ':00'
    return None


def _safe_timestamptz(txt: Optional[str]) -> Optional[str]:
    """Converte ISO-like string para TIMESTAMPTZ-compatível, ou None."""
    if not txt:
        return None
    s = str(txt).strip()
    if not s or s in ('None', 'NaT', 'nan'):
        return None
    # Aceita ISO 8601
    try:
        import datetime
        # Remove trailing Z → +00:00
        s_norm = s.replace('Z', '+00:00')
        dt = datetime.datetime.fromisoformat(s_norm)
        return dt.isoformat()
    except Exception:
        pass
    # Aceita 'YYYY-MM-DD HH:MM:SS'
    try:
        import datetime
        dt = datetime.datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
        return dt.isoformat()
    except Exception:
        pass
    return None


def _safe_text_array(csv: Optional[str]) -> Optional[list]:
    """Converte 'a, b, c' para ['a', 'b', 'c'], ou None."""
    if not csv:
        return None
    s = str(csv).strip()
    if not s:
        return None
    return [p.strip() for p in s.split(',') if p.strip()]


def _safe_int_array(csv: Optional[str]) -> Optional[list]:
    """Converte '7, 7, 1' para [7, 7, 1], ou None."""
    if not csv:
        return None
    parts = [p.strip() for p in str(csv).split(',') if p.strip()]
    try:
        return [int(p) for p in parts]
    except Exception:
        return None


def _safe_jsonb(txt: Optional[str]) -> Optional[str]:
    """
    Converte repr de dict Python ou JSON-string para JSON canônico válido.
    Ex.: "{1: 'Verstappen', 2: 'Hamilton'}" → '{"1": "Verstappen", "2": "Hamilton"}'
    """
    if not txt:
        return None
    s = str(txt).strip()
    if not s or s in ('None', 'null', '{}'):
        return None
    # Tenta JSON direto
    try:
        obj = json.loads(s)
        return json.dumps({str(k): v for k, v in obj.items()}, ensure_ascii=False)
    except Exception:
        pass
    # Tenta ast.literal_eval (formato Python dict legado)
    try:
        import ast
        obj = ast.literal_eval(s)
        if isinstance(obj, dict):
            return json.dumps({str(k): v for k, v in obj.items()}, ensure_ascii=False)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Funções públicas de acesso compatível (usadas pelos services)
# ---------------------------------------------------------------------------

def parse_posicoes_safe(raw: Optional[str]) -> dict:
    """
    Lê posições de qualquer formato (TEXT/JSON/repr Python) e retorna
    dict com chaves int.
    """
    if not raw:
        return {}
    s = str(raw).strip()
    # JSON
    try:
        obj = json.loads(s)
        return {int(k): v for k, v in obj.items()}
    except Exception:
        pass
    # Python repr (legado)
    try:
        import ast
        obj = ast.literal_eval(s)
        if isinstance(obj, dict):
            return {int(k): v for k, v in obj.items()}
    except Exception:
        pass
    return {}


def posicoes_to_json(posicoes: dict) -> str:
    """Serializa posições para JSON canônico (chaves como string)."""
    return json.dumps({str(k): v for k, v in posicoes.items()}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# DDL helpers
# ---------------------------------------------------------------------------

def _add_col_if_missing(cursor, conn, table: str, column: str, ddl: str) -> bool:
    cols = get_table_columns(conn, table)
    if column not in cols:
        cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN {ddl}')
        logger.info('✓ Coluna `%s.%s` adicionada', table, column)
        return True
    return False


# ---------------------------------------------------------------------------
# Migration principal
# ---------------------------------------------------------------------------

def run_native_types_migration() -> None:
    """
    Executa a migração de tipos nativos em três etapas:
    1. Adiciona colunas novas (sem remover as antigas)
    2. Converte os dados existentes para os novos tipos
    3. Cria índices nas colunas novas

    É idempotente: pode ser chamada múltiplas vezes com segurança.
    """
    logger.info('▶ Iniciando migração de tipos nativos...')
    pool = get_pool()

    with pool.get_connection() as conn:
        cur = conn.cursor()

        # ------------------------------------------------------------------ #
        # ETAPA 1 – Adicionar colunas novas                                   #
        # ------------------------------------------------------------------ #
        try:
            if table_exists(conn, 'provas'):
                _add_col_if_missing(cur, conn, 'provas', 'data_date',
                                    'data_date DATE')
                _add_col_if_missing(cur, conn, 'provas', 'horario_ts',
                                    'horario_ts TIME')

            if table_exists(conn, 'apostas'):
                _add_col_if_missing(cur, conn, 'apostas', 'data_envio_ts',
                                    'data_envio_ts TIMESTAMPTZ')
                _add_col_if_missing(cur, conn, 'apostas', 'pilotos_arr',
                                    'pilotos_arr TEXT[]')
                _add_col_if_missing(cur, conn, 'apostas', 'fichas_arr',
                                    'fichas_arr INTEGER[]')

            if table_exists(conn, 'resultados'):
                _add_col_if_missing(cur, conn, 'resultados', 'posicoes_jsonb',
                                    'posicoes_jsonb JSONB')
                _add_col_if_missing(cur, conn, 'resultados', 'abandono_arr',
                                    'abandono_arr TEXT[]')

            conn.commit()
            logger.info('  ✓ Etapa 1 concluída (colunas adicionadas)')
        except Exception as exc:
            conn.rollback()
            logger.error('  ✗ Etapa 1 falhou: %s', exc)
            raise

        # ------------------------------------------------------------------ #
        # ETAPA 2 – Migrar dados existentes                                   #
        # ------------------------------------------------------------------ #
        _migrate_provas_dates(conn)
        _migrate_apostas_types(conn)
        _migrate_resultados_jsonb(conn)

        # ------------------------------------------------------------------ #
        # ETAPA 3 – Criar índices nas colunas nativas                         #
        # ------------------------------------------------------------------ #
        try:
            indices = [
                # provas
                'CREATE INDEX IF NOT EXISTS idx_provas_data_date '
                'ON provas(data_date)',
                'CREATE INDEX IF NOT EXISTS idx_provas_data_date_status '
                'ON provas(data_date, status)',
                'CREATE INDEX IF NOT EXISTS idx_provas_data_date_temporada '
                'ON provas(temporada, data_date)',
                # apostas
                'CREATE INDEX IF NOT EXISTS idx_apostas_data_envio_ts '
                'ON apostas(data_envio_ts)',
                # resultados
                'CREATE INDEX IF NOT EXISTS idx_resultados_posicoes_jsonb '
                'ON resultados USING GIN(posicoes_jsonb)',
                'CREATE INDEX IF NOT EXISTS idx_resultados_abandono_arr '
                'ON resultados USING GIN(abandono_arr)',
            ]
            for idx_sql in indices:
                cur.execute(idx_sql)
            conn.commit()
            logger.info('  ✓ Etapa 3 concluída (índices criados)')
        except Exception as exc:
            conn.rollback()
            logger.error('  ✗ Etapa 3 falhou (índices): %s', exc)
            raise

    logger.info('✅ Migração de tipos nativos concluída.')


# ---------------------------------------------------------------------------
# Funções internas de migração de dados
# ---------------------------------------------------------------------------

def _migrate_provas_dates(conn) -> None:
    """Preenche data_date e horario_ts a partir de data/horario_prova TEXT."""
    cur = conn.cursor()
    try:
        cols = get_table_columns(conn, 'provas')
        if 'data_date' not in cols:
            return  # colunas ainda não foram criadas

        has_horario = 'horario_prova' in cols

        # Só processa linhas onde data_date ainda é NULL
        if has_horario:
            cur.execute(
                'SELECT id, data, horario_prova FROM provas '
                'WHERE data_date IS NULL AND data IS NOT NULL'
            )
        else:
            cur.execute(
                'SELECT id, data FROM provas '
                'WHERE data_date IS NULL AND data IS NOT NULL'
            )

        rows = cur.fetchall() or []
        updates = 0
        for row in rows:
            pid = row['id']
            data_txt = row.get('data')
            horario_txt = row.get('horario_prova') if has_horario else None

            date_val = _safe_date(data_txt)
            time_val = _safe_time(horario_txt)

            if date_val is None:
                continue  # dados impróprios — não força conversão

            if time_val is not None:
                cur.execute(
                    'UPDATE provas SET data_date = %s, horario_ts = %s WHERE id = %s',
                    (date_val, time_val, pid)
                )
            else:
                cur.execute(
                    'UPDATE provas SET data_date = %s WHERE id = %s',
                    (date_val, pid)
                )
            updates += 1

        conn.commit()
        logger.info('  ✓ provas: %d linha(s) migradas para DATE/TIME', updates)
    except Exception as exc:
        conn.rollback()
        logger.error('  ✗ Falha ao migrar provas: %s', exc)
        raise


def _migrate_apostas_types(conn) -> None:
    """Preenche data_envio_ts, pilotos_arr e fichas_arr a partir de TEXT."""
    cur = conn.cursor()
    try:
        cols = get_table_columns(conn, 'apostas')
        if 'data_envio_ts' not in cols:
            return

        cur.execute(
            'SELECT id, data_envio, pilotos, fichas FROM apostas '
            'WHERE data_envio_ts IS NULL'
        )
        rows = cur.fetchall() or []
        updates = 0
        for row in rows:
            aid = row['id']
            ts_val = _safe_timestamptz(row.get('data_envio'))
            pilotos_val = _safe_text_array(row.get('pilotos'))
            fichas_val = _safe_int_array(row.get('fichas'))

            cur.execute(
                'UPDATE apostas SET data_envio_ts = %s, pilotos_arr = %s, fichas_arr = %s '
                'WHERE id = %s',
                (ts_val, pilotos_val, fichas_val, aid)
            )
            updates += 1

        conn.commit()
        logger.info('  ✓ apostas: %d linha(s) migradas para TIMESTAMPTZ/TEXT[]/INTEGER[]', updates)
    except Exception as exc:
        conn.rollback()
        logger.error('  ✗ Falha ao migrar apostas: %s', exc)
        raise


def _migrate_resultados_jsonb(conn) -> None:
    """Preenche posicoes_jsonb e abandono_arr a partir de TEXT."""
    cur = conn.cursor()
    try:
        cols = get_table_columns(conn, 'resultados')
        if 'posicoes_jsonb' not in cols:
            return

        has_abandono_col = 'abandono_pilotos' in cols

        if has_abandono_col:
            cur.execute(
                'SELECT prova_id, posicoes, abandono_pilotos FROM resultados '
                'WHERE posicoes_jsonb IS NULL'
            )
        else:
            cur.execute(
                'SELECT prova_id, posicoes FROM resultados '
                'WHERE posicoes_jsonb IS NULL'
            )

        rows = cur.fetchall() or []
        updates = 0
        for row in rows:
            pid = row['prova_id']
            jsonb_val = _safe_jsonb(row.get('posicoes'))
            abandono_val = _safe_text_array(row.get('abandono_pilotos')) if has_abandono_col else None

            if jsonb_val is None:
                continue  # não força conversão de dados ilegíveis

            cur.execute(
                'UPDATE resultados SET posicoes_jsonb = %s::jsonb, abandono_arr = %s '
                'WHERE prova_id = %s',
                (jsonb_val, abandono_val, pid)
            )
            updates += 1

        conn.commit()
        logger.info('  ✓ resultados: %d linha(s) migradas para JSONB/TEXT[]', updates)
    except Exception as exc:
        conn.rollback()
        logger.error('  ✗ Falha ao migrar resultados: %s', exc)
        raise


# ---------------------------------------------------------------------------
# Sync helpers — chamados por serviços ao GRAVAR novos registros
# ---------------------------------------------------------------------------

def sync_aposta_native(conn, aposta_id: int) -> None:
    """
    Sincroniza as colunas nativas de uma aposta recém-inserida/atualizada.
    Deve ser chamado após INSERT/UPDATE em `apostas`.
    """
    try:
        cur = conn.cursor()
        cols = get_table_columns(conn, 'apostas')
        if 'data_envio_ts' not in cols:
            return
        cur.execute(
            'SELECT data_envio, pilotos, fichas FROM apostas WHERE id = %s',
            (aposta_id,)
        )
        row = cur.fetchone()
        if not row:
            return
        cur.execute(
            'UPDATE apostas SET data_envio_ts = %s, pilotos_arr = %s, fichas_arr = %s '
            'WHERE id = %s',
            (
                _safe_timestamptz(row['data_envio']),
                _safe_text_array(row['pilotos']),
                _safe_int_array(row['fichas']),
                aposta_id,
            )
        )
        # Não faz commit aqui — responsabilidade do caller
    except Exception as exc:
        logger.debug('sync_aposta_native falhou para id=%s: %s', aposta_id, exc)


def sync_resultado_native(conn, prova_id: int) -> None:
    """
    Sincroniza as colunas nativas de um resultado recém-inserido/atualizado.
    Deve ser chamado após INSERT/UPDATE em `resultados`.
    """
    try:
        cur = conn.cursor()
        cols = get_table_columns(conn, 'resultados')
        if 'posicoes_jsonb' not in cols:
            return
        has_abandono = 'abandono_pilotos' in cols
        if has_abandono:
            cur.execute(
                'SELECT posicoes, abandono_pilotos FROM resultados WHERE prova_id = %s',
                (prova_id,)
            )
        else:
            cur.execute(
                'SELECT posicoes FROM resultados WHERE prova_id = %s',
                (prova_id,)
            )
        row = cur.fetchone()
        if not row:
            return
        jsonb_val = _safe_jsonb(row['posicoes'])
        abandono_val = _safe_text_array(row.get('abandono_pilotos')) if has_abandono else None
        if jsonb_val is None:
            return
        cur.execute(
            'UPDATE resultados SET posicoes_jsonb = %s::jsonb, abandono_arr = %s '
            'WHERE prova_id = %s',
            (jsonb_val, abandono_val, prova_id)
        )
        # Não faz commit aqui — responsabilidade do caller
    except Exception as exc:
        logger.debug('sync_resultado_native falhou para prova_id=%s: %s', prova_id, exc)


def sync_prova_native(conn, prova_id: int) -> None:
    """
    Sincroniza as colunas nativas de uma prova recém-inserida/atualizada.
    Deve ser chamado após INSERT/UPDATE em `provas`.
    """
    try:
        cur = conn.cursor()
        cols = get_table_columns(conn, 'provas')
        if 'data_date' not in cols:
            return
        has_horario = 'horario_prova' in cols
        if has_horario:
            cur.execute(
                'SELECT data, horario_prova FROM provas WHERE id = %s', (prova_id,)
            )
        else:
            cur.execute('SELECT data FROM provas WHERE id = %s', (prova_id,))
        row = cur.fetchone()
        if not row:
            return
        date_val = _safe_date(row['data'])
        time_val = _safe_time(row.get('horario_prova')) if has_horario else None
        if date_val is None:
            return
        cur.execute(
            'UPDATE provas SET data_date = %s, horario_ts = %s WHERE id = %s',
            (date_val, time_val, prova_id)
        )
        # Não faz commit aqui — responsabilidade do caller
    except Exception as exc:
        logger.debug('sync_prova_native falhou para id=%s: %s', prova_id, exc)
