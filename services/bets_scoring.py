"""Cálculo de pontuação e classificação de apostas."""

from __future__ import annotations

import ast
from datetime import datetime
from typing import Optional, cast

import pandas as pd

from db.db_schema import db_connect, get_table_columns
from services.rules_service import get_regras_aplicaveis
from utils.datetime_utils import parse_datetime_sao_paulo


def _fetch_df(conn, query: str, params: tuple | None = None) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(query, params or ())
    rows = cur.fetchall() or []
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


def _parse_datetime_sp(date_str: str, time_str: str):
    return parse_datetime_sao_paulo(date_str, time_str)


def calcular_pontuacao_lote(ap_df, res_df, prov_df, temporada_descarte=None):
    """
    Calcula pontuação usando:
    - Tabelas de pontos da REGRA (Normal/Sprint), com fallback FIA hardcoded
    - Fichas DINAMICAS da aposta do usuário
    - Bonus 11o DINAMICO da regra da temporada
    - Penalidades DINAMICAS das regras

    Formula: Pontos = (Pontos_Regra x Fichas) + Bonus_11o - Penalidades
    """
    PONTOS_F1_NORMAL = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    PONTOS_SPRINT = [8, 7, 6, 5, 4, 3, 2, 1]

    ress_map = {}
    abandonos_map = {}
    for _, r in res_df.iterrows():
        try:
            ress_map[r["prova_id"]] = ast.literal_eval(r["posicoes"])
        except Exception:
            continue
        try:
            if "abandono_pilotos" in res_df.columns:
                raw = r.get("abandono_pilotos", "")
                if raw is None:
                    raw = ""
                aband_list = [p.strip() for p in str(raw).split(",") if p and p.strip()]
                abandonos_map[r["prova_id"]] = set(aband_list)
            else:
                abandonos_map[r["prova_id"]] = set()
        except Exception:
            abandonos_map[r["prova_id"]] = set()

    if "tipo" in prov_df.columns:
        tipos = prov_df["tipo"].fillna("").astype(str).tolist()
    else:
        tipos = [""] * len(prov_df)
    nomes = prov_df["nome"].fillna("").astype(str).tolist() if "nome" in prov_df.columns else [""] * len(prov_df)
    tipos_resolvidos = []
    for i in range(len(prov_df)):
        t = tipos[i].strip().lower()
        n = nomes[i].strip().lower()
        if t == "sprint" or ("sprint" in n):
            tipos_resolvidos.append("Sprint")
        else:
            tipos_resolvidos.append("Normal")
    tipos_prova = dict(zip(prov_df["id"], tipos_resolvidos))
    temporadas_prova = dict(
        zip(
            prov_df["id"],
            prov_df["temporada"] if "temporada" in prov_df.columns else [str(datetime.now().year)] * len(prov_df),
        )
    )
    has_temp_aposta = "temporada" in ap_df.columns

    pontos = []
    for _, aposta in ap_df.iterrows():
        prova_id = aposta["prova_id"]

        if prova_id not in ress_map:
            pontos.append(None)
            continue

        res = ress_map[prova_id]
        tipo = tipos_prova.get(prova_id, "Normal")
        temporada_aposta = None
        if has_temp_aposta:
            try:
                temporada_aposta = aposta.get("temporada", None)
            except Exception:
                temporada_aposta = None
        if temporada_aposta is not None and str(temporada_aposta).strip() != "" and not pd.isna(temporada_aposta):
            temporada_prova = str(temporada_aposta)
        else:
            temporada_prova = temporadas_prova.get(prova_id, str(datetime.now().year))

        regras = get_regras_aplicaveis(temporada_prova, tipo)

        if tipo == "Sprint":
            pontos_tabela = regras.get("pontos_sprint_posicoes") or regras.get("pontos_posicoes") or ([])
            if not pontos_tabela:
                pontos_tabela = PONTOS_SPRINT
        else:
            pontos_tabela = regras.get("pontos_posicoes") or ([])
            if not pontos_tabela:
                pontos_tabela = PONTOS_F1_NORMAL
        n_posicoes = len(pontos_tabela)

        bonus_11 = regras.get("pontos_11_colocado", 25)

        pilotos = [p.strip() for p in aposta["pilotos"].split(",")]
        fichas = list(map(int, aposta["fichas"].split(",")))
        piloto_11 = aposta["piloto_11"]
        automatica = int(aposta.get("automatica", 0))

        piloto_para_pos = {str(v).strip(): int(k) for k, v in res.items()}

        pt = 0
        for i in range(len(pilotos)):
            piloto = pilotos[i]
            ficha = fichas[i] if i < len(fichas) else 0
            pos_real = piloto_para_pos.get(piloto, None)

            if pos_real is not None and 1 <= pos_real <= n_posicoes:
                base = pontos_tabela[pos_real - 1]
                pt += ficha * base

        piloto_11_real = res.get(11, "")
        if piloto_11 == piloto_11_real:
            pt += bonus_11

        if regras.get("penalidade_abandono"):
            aband_prova = abandonos_map.get(prova_id, set())
            if aband_prova:
                num_aband_apostados = sum(1 for p in pilotos if p in aband_prova)
                deduz = regras.get("pontos_penalidade", 0) * num_aband_apostados
                if deduz:
                    pt -= deduz

        if tipo == "Sprint" and regras.get("pontos_dobrada"):
            pt = pt * 2

        if automatica >= 2:
            penalidade_auto_percent = regras.get("penalidade_auto_percent", 20)
            fator = max(0, 1 - (float(penalidade_auto_percent) / 100))
            pt = round(pt * fator, 2)

        pontos.append(pt)

    return pontos


def salvar_classificacao_prova(p_id, df_c, temp=None):
    if temp is None:
        temp = str(datetime.now().year)

    with db_connect() as conn:
        c = conn.cursor()
        cols = get_table_columns(conn, "posicoes_participantes")
        has_temporada = "temporada" in cols

        if has_temporada:
            c.execute("DELETE FROM posicoes_participantes WHERE prova_id=%s AND temporada=%s", (p_id, temp))
        else:
            c.execute("DELETE FROM posicoes_participantes WHERE prova_id=%s", (p_id,))

        for _, r in df_c.iterrows():
            if has_temporada:
                c.execute(
                    "INSERT INTO posicoes_participantes (prova_id, usuario_id, posicao, pontos, temporada) VALUES (%s,%s,%s,%s,%s)",
                    (p_id, int(r["usuario_id"]), int(r["posicao"]), float(r["pontos"]), temp),
                )
            else:
                c.execute(
                    "INSERT INTO posicoes_participantes (prova_id, usuario_id, posicao, pontos) VALUES (%s,%s,%s,%s)",
                    (p_id, int(r["usuario_id"]), int(r["posicao"]), float(r["pontos"])),
                )
        conn.commit()


def atualizar_classificacoes_todas_as_provas(temporada: Optional[str] = None):
    with db_connect() as conn:
        usrs = cast(
            pd.DataFrame,
            _fetch_df(
                conn,
                """
                SELECT id
                FROM usuarios
                WHERE lower(trim(coalesce(status, ''))) = 'ativo'
                """,
            ),
        )
        provs = cast(pd.DataFrame, _fetch_df(conn, "SELECT id, nome, data, tipo, temporada FROM provas"))
        apts = cast(
            pd.DataFrame,
            _fetch_df(conn, "SELECT usuario_id, prova_id, data_envio, pilotos, fichas, piloto_11, automatica, temporada FROM apostas"),
        )
        ress = cast(pd.DataFrame, _fetch_df(conn, "SELECT prova_id, posicoes, abandono_pilotos FROM resultados"))

        if temporada and "temporada" in provs.columns:
            provs = provs[provs["temporada"] == temporada]

        primeira_prova_por_temp = {}
        if not provs.empty:
            if "temporada" in provs.columns and "data" in provs.columns:
                provs_dt = provs.copy()
                provs_dt["__data_dt"] = pd.to_datetime(provs_dt["data"], errors="coerce")
                for temp_val, grp in provs_dt.groupby("temporada"):
                    grp = cast(pd.DataFrame, grp)
                    grp = grp.sort_values(by=["__data_dt"])
                    if not grp.empty:
                        primeira_prova_por_temp[str(temp_val)] = int(grp.iloc[0]["id"])
            elif "data" in provs.columns:
                provs_dt = cast(pd.DataFrame, provs.copy())
                provs_dt["__data_dt"] = pd.to_datetime(provs_dt["data"], errors="coerce")
                provs_dt = provs_dt.sort_values(by=["__data_dt"])
                if not provs_dt.empty:
                    primeira_prova_por_temp[str(datetime.now().year)] = int(provs_dt.iloc[0]["id"])
            elif not provs.empty:
                primeira_prova_por_temp[str(datetime.now().year)] = int(provs.iloc[0]["id"])

        for _, pr in provs.iterrows():
            pid = pr["id"]
            if pid not in ress["prova_id"].values:
                continue

            temporada_prova = pr.get("temporada", str(datetime.now().year))
            aps = apts[apts["prova_id"] == pid]
            if "temporada" in aps.columns:
                aps = aps[(aps["temporada"] == temporada_prova) | (aps["temporada"].isna())]
            if aps.empty:
                continue

            res_row = ress[ress["prova_id"] == pid].iloc[0]
            res_p = ast.literal_eval(res_row["posicoes"])
            piloto_11_real = res_p.get(11, "")

            tab = []
            first_no_base_flags = {}
            for _, u in usrs.iterrows():
                ap = aps[aps["usuario_id"] == u["id"]]

                if ap.empty:
                    pontos_val = 0
                    data_envio = None
                    acerto_11 = 0
                    if str(pid) == str(primeira_prova_por_temp.get(str(temporada_prova), None)):
                        first_no_base_flags[int(u["id"])] = True
                else:
                    p_list = calcular_pontuacao_lote(ap, ress, provs)
                    pontos_val = sum(p_list) if p_list else 0
                    data_envio = ap.iloc[0].get("data_envio", None)
                    acerto_11 = 1 if ap.iloc[0]["piloto_11"] == piloto_11_real else 0
                    if str(pid) == str(primeira_prova_por_temp.get(str(temporada_prova), None)):
                        try:
                            if int(ap.iloc[0].get("automatica", 0)) > 0:
                                first_no_base_flags[int(u["id"])] = True
                        except Exception:
                            pass

                tab.append(
                    {
                        "usuario_id": u["id"],
                        "pontos": pontos_val,
                        "data_envio": data_envio,
                        "acerto_11": acerto_11,
                    }
                )

            if first_no_base_flags:
                try:
                    pontos_validos = [
                        t["pontos"]
                        for t in tab
                        if t["pontos"] is not None and not first_no_base_flags.get(int(t["usuario_id"]), False)
                    ]
                    pior_pontuador = min(pontos_validos) if pontos_validos else 0
                except Exception:
                    pior_pontuador = 0
                for t in tab:
                    if first_no_base_flags.get(int(t["usuario_id"]), False):
                        t["pontos"] = round(pior_pontuador * 0.85, 2)

            df = pd.DataFrame(tab)
            df["data_envio"] = pd.to_datetime(df["data_envio"], errors="coerce")
            df = df.sort_values(by=["pontos", "acerto_11", "data_envio"], ascending=[False, False, True]).reset_index(drop=True)
            df["posicao"] = df.index + 1
            salvar_classificacao_prova(pid, df, temporada_prova)


__all__ = [
    "_parse_datetime_sp",
    "calcular_pontuacao_lote",
    "salvar_classificacao_prova",
    "atualizar_classificacoes_todas_as_provas",
]
