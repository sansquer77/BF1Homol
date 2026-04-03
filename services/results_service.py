import pandas as pd
import json
import ast
from datetime import datetime
import logging
from db.db_schema import db_connect
from db.repo_races import get_provas_df, get_resultados_df
from db.migrations_native_types import (
    parse_posicoes_safe,
    posicoes_to_json,
    sync_resultado_native,
)


logger = logging.getLogger(__name__)


def _parse_posicoes(posicoes_str: str) -> dict:
    """
    Converte string de posições para dicionário de forma segura.
    Suporta formato JSON e formato Python dict (legado).
    
    Args:
        posicoes_str: String com posições (JSON ou repr de dict Python)
    
    Returns:
        Dicionário com posições {int: str}
    """
    return parse_posicoes_safe(posicoes_str)


def salvar_resultado_prova(prova_id: int, posicoes: dict) -> bool:
    """
    Salva ou atualiza o resultado de uma prova no banco.
    posicoes: dicionário {posição (int): nome_piloto (str)}, sendo 1 ao 11.

    Grava simultaneamente:
      - posicoes (TEXT, legado) — mantida para compatibilidade retroativa
      - posicoes_jsonb (JSONB)  — novo tipo nativo, quando a coluna existir
    """
    try:
        # Serializa para JSON canônico (chaves como string)
        posicoes_json_str = posicoes_to_json(posicoes)
        # Mantém repr Python legado na coluna TEXT para retrocompatibilidade
        posicoes_text_legacy = str(posicoes)

        with db_connect() as conn:
            c = conn.cursor()
            c.execute(
                '''
                INSERT INTO resultados (prova_id, posicoes)
                VALUES (%s, %s)
                ON CONFLICT (prova_id) DO UPDATE SET
                    posicoes = EXCLUDED.posicoes
                ''',
                (prova_id, posicoes_text_legacy)
            )
            # Sincroniza coluna JSONB nativa (sem rollback se coluna não existir)
            sync_resultado_native(conn, prova_id)
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Erro ao salvar resultado da prova %s: %s", prova_id, e)
        return False

def obter_resultados():
    """Retorna todos os resultados de todas as provas como DataFrame pandas."""
    return get_resultados_df()

def obter_resultado_prova(prova_id: int):
    """
    Retorna o resultado de uma prova específica (dict) ou None.

    Lê preferencialmente de `posicoes_jsonb` (mais eficiente) com
    fallback transparente para a coluna TEXT `posicoes`.
    """
    with db_connect() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT posicoes, posicoes_jsonb FROM resultados WHERE prova_id = %s",
            (prova_id,)
        )
        row = c.fetchone()
    if not row:
        return None

    # Tenta ler do JSONB nativo primeiro (mais rápido e seguro)
    jsonb_val = row.get('posicoes_jsonb') if row else None
    if isinstance(jsonb_val, dict) and jsonb_val:
        return {int(k): v for k, v in jsonb_val.items()}

    # Fallback: lê coluna TEXT legada
    if row.get('posicoes'):
        result = parse_posicoes_safe(row['posicoes'])
        return result if result else None
    return None

def listar_resultados_completos():
    """
    Retorna DataFrame com nomes das provas e posições dos pilotos (1º ao 11º).
    """
    resultados = get_resultados_df()
    provas = get_provas_df().set_index("id")
    lista = []
    for _, res in resultados.iterrows():
        prova_id = res['prova_id']

        # Prefere JSONB nativo quando disponível
        jsonb_val = res.get('posicoes_jsonb') if 'posicoes_jsonb' in res.index else None
        if isinstance(jsonb_val, dict) and jsonb_val:
            posicoes = {int(k): v for k, v in jsonb_val.items()}
        else:
            posicoes = parse_posicoes_safe(res.get('posicoes', ''))

        linha = {
            "Prova": provas.loc[prova_id]['nome'] if prova_id in provas.index else f"Prova {prova_id}",
            "Data": provas.loc[prova_id]['data'] if prova_id in provas.index else "",
        }
        for pos in range(1, 12):
            linha[f"{pos}º"] = posicoes.get(pos, "")
        lista.append(linha)
    return pd.DataFrame(lista)

def validar_resultado(posicoes: dict, pilotos_ativos=None) -> tuple:
    """
    Valida as posições informadas:
      - Sem repetição entre 1º e 10º.
      - Todos os campos preenchidos para 1-10.
      - 11º pode repetir piloto.
      - (opcional) Verifica se piloto existe na lista de ativos.
    Retorna (bool, str): (válido?, mensagem_erro)
    """
    pilotos = [posicoes.get(pos) for pos in range(1, 11)]
    if any(not p for p in pilotos):
        return False, "Preencha todos os campos de 1º ao 10º colocado."
    if len(set(pilotos)) < 10:
        return False, "Não é permitido repetir piloto entre 1º e 10º colocado."
    if not posicoes.get(11):
        return False, "Selecione o piloto para 11º colocado."
    if pilotos_ativos is not None:
        for p in pilotos + [posicoes.get(11)]:
            if p not in pilotos_ativos:
                return False, f"Piloto '{p}' não existe na lista de ativos."
    return True, "OK"
