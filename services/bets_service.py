import pandas as pd
import json
import logging
from datetime import datetime
from typing import Optional
from db.db_utils import db_connect, get_table_columns

logger = logging.getLogger(__name__)


def _to_int(v) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return None


def _safe_list(v) -> list:
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            r = json.loads(v)
            return r if isinstance(r, list) else []
        except Exception:
            return [x.strip() for x in v.split(',') if x.strip()]
    return []


def _safe_fichas(v) -> list:
    raw = _safe_list(v)
    result = []
    for x in raw:
        try:
            result.append(int(x))
        except Exception:
            result.append(0)
    return result


def get_aposta_usuario(usuario_id: int, prova_id: int, temporada: Optional[str] = None) -> Optional[dict]:
    """Retorna a aposta de um usuário para uma prova, ou None."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'apostas')
            if 'temporada' in cols and temporada:
                c.execute(
                    'SELECT * FROM apostas WHERE usuario_id = %s AND prova_id = %s AND temporada = %s',
                    (usuario_id, prova_id, temporada)
                )
            else:
                c.execute(
                    'SELECT * FROM apostas WHERE usuario_id = %s AND prova_id = %s',
                    (usuario_id, prova_id)
                )
            row = c.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.exception('Erro ao buscar aposta: %s', e)
        return None


def salvar_aposta(
    usuario_id: int,
    prova_id: int,
    pilotos: list,
    fichas: list,
    piloto_11: str,
    nome_prova: str = '',
    automatica: int = 0,
    temporada: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> bool:
    """Salva ou atualiza a aposta de um usuário."""
    try:
        temporada_val = temporada or str(datetime.now().year)
        pilotos_json = json.dumps(pilotos, ensure_ascii=False)
        fichas_json = json.dumps(fichas, ensure_ascii=False)
        data_envio = datetime.now().isoformat()

        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'apostas')

            # Verificar se já existe
            if 'temporada' in cols:
                c.execute(
                    'SELECT id FROM apostas WHERE usuario_id = %s AND prova_id = %s AND temporada = %s',
                    (usuario_id, prova_id, temporada_val)
                )
            else:
                c.execute(
                    'SELECT id FROM apostas WHERE usuario_id = %s AND prova_id = %s',
                    (usuario_id, prova_id)
                )
            existing = c.fetchone()

            if existing:
                aposta_id = existing[0] if not hasattr(existing, 'keys') else existing['id']
                if 'temporada' in cols:
                    c.execute(
                        '''UPDATE apostas SET pilotos=%s, fichas=%s, piloto_11=%s,
                           nome_prova=%s, automatica=%s, data_envio=%s
                           WHERE id=%s''',
                        (pilotos_json, fichas_json, piloto_11, nome_prova, automatica, data_envio, aposta_id)
                    )
                else:
                    c.execute(
                        '''UPDATE apostas SET pilotos=%s, fichas=%s, piloto_11=%s,
                           nome_prova=%s, automatica=%s, data_envio=%s
                           WHERE id=%s''',
                        (pilotos_json, fichas_json, piloto_11, nome_prova, automatica, data_envio, aposta_id)
                    )
            else:
                if 'temporada' in cols:
                    c.execute(
                        '''INSERT INTO apostas
                           (usuario_id, prova_id, pilotos, fichas, piloto_11, nome_prova, automatica, data_envio, temporada)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (usuario_id, prova_id, pilotos_json, fichas_json, piloto_11,
                         nome_prova, automatica, data_envio, temporada_val)
                    )
                else:
                    c.execute(
                        '''INSERT INTO apostas
                           (usuario_id, prova_id, pilotos, fichas, piloto_11, nome_prova, automatica, data_envio)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (usuario_id, prova_id, pilotos_json, fichas_json, piloto_11,
                         nome_prova, automatica, data_envio)
                    )
            conn.commit()

        # Registrar no log
        _registrar_log_aposta(
            usuario_id=usuario_id,
            prova_id=prova_id,
            pilotos=pilotos,
            fichas=fichas,
            piloto_11=piloto_11,
            nome_prova=nome_prova,
            automatica=automatica,
            temporada=temporada_val,
            ip_address=ip_address,
        )
        return True
    except Exception as e:
        logger.exception('Erro ao salvar aposta: %s', e)
        return False


def _registrar_log_aposta(
    usuario_id: int,
    prova_id: int,
    pilotos: list,
    fichas: list,
    piloto_11: str,
    nome_prova: str = '',
    automatica: int = 0,
    temporada: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Insere entrada no log de apostas."""
    try:
        temporada_val = temporada or str(datetime.now().year)
        data_str = datetime.now().strftime('%Y-%m-%d')
        horario_str = datetime.now().strftime('%H:%M:%S')
        pilotos_str = ', '.join(str(p) for p in pilotos) if pilotos else ''
        fichas_str = ', '.join(str(f) for f in fichas) if fichas else ''

        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'log_apostas')

            if not cols:
                c.execute('''
                    CREATE TABLE IF NOT EXISTS log_apostas (
                        id SERIAL PRIMARY KEY,
                        usuario_id INTEGER,
                        prova_id INTEGER,
                        apostador TEXT,
                        aposta TEXT,
                        nome_prova TEXT,
                        pilotos TEXT,
                        piloto_11 TEXT,
                        tipo_aposta INTEGER DEFAULT 0,
                        automatica INTEGER DEFAULT 0,
                        data TEXT,
                        horario TEXT,
                        ip_address TEXT,
                        temporada TEXT,
                        status TEXT DEFAULT \'Registrada\',
                        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cols = get_table_columns(conn, 'log_apostas')

            insert_cols = ['usuario_id', 'prova_id', 'pilotos', 'aposta', 'piloto_11',
                           'nome_prova', 'automatica', 'data', 'horario']
            insert_vals = [usuario_id, prova_id, pilotos_str, fichas_str, piloto_11,
                           nome_prova, automatica, data_str, horario_str]

            if 'ip_address' in cols:
                insert_cols.append('ip_address')
                insert_vals.append(ip_address)
            if 'temporada' in cols:
                insert_cols.append('temporada')
                insert_vals.append(temporada_val)
            if 'status' in cols:
                insert_cols.append('status')
                insert_vals.append('Registrada')

            ph = ', '.join(['%s'] * len(insert_cols))
            c.execute(
                f'INSERT INTO log_apostas ({chr(44).join(insert_cols)}) VALUES ({ph})',
                tuple(insert_vals)
            )
            conn.commit()
    except Exception as e:
        logger.warning('Erro ao registrar log de aposta: %s', e)


def excluir_aposta(usuario_id: int, prova_id: int, temporada: Optional[str] = None) -> bool:
    """Remove a aposta de um usuário para uma prova."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'apostas')
            if 'temporada' in cols and temporada:
                c.execute(
                    'DELETE FROM apostas WHERE usuario_id = %s AND prova_id = %s AND temporada = %s',
                    (usuario_id, prova_id, temporada)
                )
            else:
                c.execute(
                    'DELETE FROM apostas WHERE usuario_id = %s AND prova_id = %s',
                    (usuario_id, prova_id)
                )
            conn.commit()
            return True
    except Exception as e:
        logger.exception('Erro ao excluir aposta: %s', e)
        return False


def get_apostas_prova_df(prova_id: int, temporada: Optional[str] = None) -> pd.DataFrame:
    """Retorna DataFrame com todas as apostas de uma prova."""
    try:
        with db_connect() as conn:
            cols = get_table_columns(conn, 'apostas')
            if 'temporada' in cols and temporada:
                df = pd.read_sql_query(
                    'SELECT * FROM apostas WHERE prova_id = %s AND temporada = %s',
                    conn, params=(prova_id, temporada)
                )
            else:
                df = pd.read_sql_query(
                    'SELECT * FROM apostas WHERE prova_id = %s',
                    conn, params=(prova_id,)
                )
            return df
    except Exception as e:
        logger.exception('Erro ao buscar apostas da prova: %s', e)
        return pd.DataFrame()


def get_apostas_usuario_df(usuario_id: int, temporada: Optional[str] = None) -> pd.DataFrame:
    """Retorna DataFrame com todas as apostas de um usuário."""
    try:
        with db_connect() as conn:
            cols = get_table_columns(conn, 'apostas')
            if 'temporada' in cols and temporada:
                df = pd.read_sql_query(
                    'SELECT * FROM apostas WHERE usuario_id = %s AND temporada = %s',
                    conn, params=(usuario_id, temporada)
                )
            else:
                df = pd.read_sql_query(
                    'SELECT * FROM apostas WHERE usuario_id = %s',
                    conn, params=(usuario_id,)
                )
            return df
    except Exception as e:
        logger.exception('Erro ao buscar apostas do usuário: %s', e)
        return pd.DataFrame()


def get_todas_apostas_df(temporada: Optional[str] = None) -> pd.DataFrame:
    """Retorna DataFrame com todas as apostas."""
    try:
        with db_connect() as conn:
            cols = get_table_columns(conn, 'apostas')
            if 'temporada' in cols and temporada:
                df = pd.read_sql_query(
                    'SELECT * FROM apostas WHERE temporada = %s',
                    conn, params=(temporada,)
                )
            else:
                df = pd.read_sql_query('SELECT * FROM apostas', conn)
            return df
    except Exception as e:
        logger.exception('Erro ao buscar apostas: %s', e)
        return pd.DataFrame()


def get_log_apostas_df(temporada: Optional[str] = None) -> pd.DataFrame:
    """Retorna DataFrame do log de apostas."""
    try:
        with db_connect() as conn:
            cols = get_table_columns(conn, 'log_apostas')
            if not cols:
                return pd.DataFrame()
            if 'temporada' in cols and temporada:
                df = pd.read_sql_query(
                    'SELECT * FROM log_apostas WHERE temporada = %s ORDER BY data_criacao DESC',
                    conn, params=(temporada,)
                )
            else:
                df = pd.read_sql_query(
                    'SELECT * FROM log_apostas ORDER BY data_criacao DESC', conn
                )
            return df
    except Exception as e:
        logger.exception('Erro ao buscar log de apostas: %s', e)
        return pd.DataFrame()


def aposta_existe(usuario_id: int, prova_id: int, temporada: Optional[str] = None) -> bool:
    """Verifica se existe aposta para usuário em uma prova."""
    try:
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'apostas')
            if 'temporada' in cols and temporada:
                c.execute(
                    'SELECT 1 FROM apostas WHERE usuario_id = %s AND prova_id = %s AND temporada = %s',
                    (usuario_id, prova_id, temporada)
                )
            else:
                c.execute(
                    'SELECT 1 FROM apostas WHERE usuario_id = %s AND prova_id = %s',
                    (usuario_id, prova_id)
                )
            return c.fetchone() is not None
    except Exception as e:
        logger.exception('Erro ao verificar aposta: %s', e)
        return False


def calcular_pontos_aposta(
    pilotos: list,
    fichas: list,
    piloto_11: str,
    resultado: dict,
    regras: Optional[dict] = None,
) -> dict:
    """
    Calcula os pontos de uma aposta dado o resultado da prova.

    resultado: {posição (int): nome_piloto (str)}
    regras: dicionário com configurações de pontuação (opcional)

    Retorna: {'pontos_total': float, 'detalhes': list, 'bonus': dict}
    """
    if regras is None:
        regras = {}

    pontos_posicoes = regras.get('pontos_posicoes')
    if isinstance(pontos_posicoes, str):
        try:
            pontos_posicoes = json.loads(pontos_posicoes)
        except Exception:
            pontos_posicoes = None
    if not pontos_posicoes:
        pontos_posicoes = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]

    pontos_11_colocado = int(regras.get('pontos_11_colocado', 25))
    bonus_vencedor = int(regras.get('bonus_vencedor', 0))
    bonus_podio_completo = int(regras.get('bonus_podio_completo', 0))
    bonus_podio_qualquer = int(regras.get('bonus_podio_qualquer', 0))

    # Inverter resultado para busca rápida: piloto -> posição
    posicao_por_piloto = {v: k for k, v in resultado.items() if v}

    total = 0.0
    detalhes = []
    pilotos_no_podio = []

    for i, (piloto, ficha) in enumerate(zip(pilotos, fichas)):
        ficha_val = _to_int(ficha) or 0
        posicao_real = posicao_por_piloto.get(piloto)

        if posicao_real is not None and posicao_real <= len(pontos_posicoes):
            pts_base = pontos_posicoes[posicao_real - 1]
            pts = pts_base * ficha_val
            if posicao_real <= 3:
                pilotos_no_podio.append(piloto)
        else:
            pts_base = 0
            pts = 0

        total += pts
        detalhes.append({
            'piloto': piloto,
            'ficha': ficha_val,
            'posicao_real': posicao_real,
            'pts_base': pts_base,
            'pts': pts,
        })

    # Bônus válido pelo 11º colocado
    bonus = {}
    piloto_11_real = resultado.get(11, '')
    if piloto_11 and piloto_11 == piloto_11_real:
        total += pontos_11_colocado
        bonus['piloto_11'] = pontos_11_colocado

    # Bônus vencedor (apostou no 1º colocado com qualquer ficha)
    vencedor_real = resultado.get(1, '')
    if bonus_vencedor and vencedor_real and vencedor_real in pilotos:
        total += bonus_vencedor
        bonus['vencedor'] = bonus_vencedor

    # Bônus pódio
    if bonus_podio_completo and len(pilotos_no_podio) == 3:
        total += bonus_podio_completo
        bonus['podio_completo'] = bonus_podio_completo
    elif bonus_podio_qualquer and len(pilotos_no_podio) >= 1:
        total += bonus_podio_qualquer
        bonus['podio_qualquer'] = bonus_podio_qualquer

    return {'pontos_total': total, 'detalhes': detalhes, 'bonus': bonus}


def get_ranking_temporada(temporada: Optional[str] = None) -> pd.DataFrame:
    """Retorna DataFrame com ranking de pontuação da temporada."""
    temporada_val = temporada or str(datetime.now().year)
    try:
        with db_connect() as conn:
            apostas_cols = get_table_columns(conn, 'apostas')
            usuarios_cols = get_table_columns(conn, 'usuarios')

            if 'pontos' not in apostas_cols:
                return pd.DataFrame()

            if 'temporada' in apostas_cols:
                df = pd.read_sql_query(
                    '''
                    SELECT u.nome, u.id as usuario_id,
                           SUM(a.pontos) as total_pontos,
                           COUNT(a.id) as total_apostas
                    FROM apostas a
                    JOIN usuarios u ON a.usuario_id = u.id
                    WHERE a.temporada = %s
                    GROUP BY u.id, u.nome
                    ORDER BY total_pontos DESC
                    ''',
                    conn, params=(temporada_val,)
                )
            else:
                df = pd.read_sql_query(
                    '''
                    SELECT u.nome, u.id as usuario_id,
                           SUM(a.pontos) as total_pontos,
                           COUNT(a.id) as total_apostas
                    FROM apostas a
                    JOIN usuarios u ON a.usuario_id = u.id
                    GROUP BY u.id, u.nome
                    ORDER BY total_pontos DESC
                    ''',
                    conn
                )
            return df
    except Exception as e:
        logger.exception('Erro ao buscar ranking: %s', e)
        return pd.DataFrame()


def registrar_aposta_automatica(
    usuario_id: int,
    prova_id: int,
    nome_prova: str,
    temporada: Optional[str] = None,
) -> bool:
    """
    Registra aposta automática (cópia da última aposta do usuário com penalidade).
    Retorna True se sucesso, False caso contrário.
    """
    try:
        temporada_val = temporada or str(datetime.now().year)

        # Buscar última aposta do usuário na temporada
        with db_connect() as conn:
            c = conn.cursor()
            cols = get_table_columns(conn, 'apostas')
            if 'temporada' in cols:
                c.execute(
                    '''SELECT pilotos, fichas, piloto_11
                       FROM apostas
                       WHERE usuario_id = %s AND temporada = %s
                       ORDER BY data_envio DESC LIMIT 1''',
                    (usuario_id, temporada_val)
                )
            else:
                c.execute(
                    '''SELECT pilotos, fichas, piloto_11
                       FROM apostas
                       WHERE usuario_id = %s
                       ORDER BY data_envio DESC LIMIT 1''',
                    (usuario_id,)
                )
            row = c.fetchone()

        if not row:
            logger.warning('Sem aposta anterior para automatica: usuario %s', usuario_id)
            return False

        pilotos = _safe_list(row[0] if not hasattr(row, 'keys') else row['pilotos'])
        fichas = _safe_fichas(row[1] if not hasattr(row, 'keys') else row['fichas'])
        piloto_11 = str(row[2] if not hasattr(row, 'keys') else row['piloto_11'] or '')

        return salvar_aposta(
            usuario_id=usuario_id,
            prova_id=prova_id,
            pilotos=pilotos,
            fichas=fichas,
            piloto_11=piloto_11,
            nome_prova=nome_prova,
            automatica=2,
            temporada=temporada_val,
        )
    except Exception as e:
        logger.exception('Erro ao registrar aposta automática: %s', e)
        return False
