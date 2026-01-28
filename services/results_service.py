import pandas as pd
from datetime import datetime
from db.db_utils import db_connect, get_provas_df, get_resultados_df

def salvar_resultado_prova(prova_id: int, posicoes: dict) -> bool:
    """
    Salva ou atualiza o resultado de uma prova no banco.
    posicoes: dicionário {posição (int): nome_piloto (str)}, sendo 1 ao 11.
    """
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute(
            'REPLACE INTO resultados (prova_id, posicoes) VALUES (?, ?)',
            (prova_id, str(posicoes))
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao salvar resultado: {e}")
        return False
    finally:
        conn.close()

def obter_resultados():
    """Retorna todos os resultados de todas as provas como DataFrame pandas."""
    return get_resultados_df()

def obter_resultado_prova(prova_id: int):
    """Retorna o resultado de uma prova específica (dict) ou None."""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT posicoes FROM resultados WHERE prova_id = ?", (prova_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        try:
            return eval(row[0])
        except Exception:
            return None
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
        try:
            posicoes = eval(res['posicoes'])
        except Exception:
            posicoes = {}
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
