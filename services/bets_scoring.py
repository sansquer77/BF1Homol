"""Cálculo de pontuação e classificação de apostas."""

from __future__ import annotations

import ast
from datetime import datetime
from typing import Any, Optional, TypedDict, cast
from collections import defaultdict

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


class PontuacaoLinha(TypedDict):
    piloto: str
    fichas: int
    posicao_real: str
    dnf: str
    pontos: float


class PontuacaoDetalhada(TypedDict):
    prova_nome: str
    tipo_prova: str
    temporada: str
    linhas: list[PontuacaoLinha]
    piloto_11_apostado: str
    piloto_11_real: str
    pontos_11: float
    penalidade_abandono: float
    pilotos_abandonados: list[str]
    multiplicador_sprint: int
    penalidade_auto: float
    total_pontos: float


def _parse_posicoes(raw: Any, none_on_error: bool = False) -> dict | None:
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = ast.literal_eval(str(raw or "{}"))
        except Exception:
            if none_on_error:
                return None
            return {}
    if not isinstance(parsed, dict):
        if none_on_error:
            return None
        return {}
    normalizado = {}
    for chave, valor in parsed.items():
        try:
            normalizado[int(chave)] = valor
        except Exception:
            normalizado[chave] = valor
    return normalizado


def _tipo_prova(prova_nome: Any, tipo_raw: Any) -> str:
    tipo = str(tipo_raw or "").strip()
    if tipo.lower() == "sprint" or "sprint" in str(prova_nome or "").lower():
        return "Sprint"
    return "Normal"


def _pontos_lista(tipo_prova: str, regras: dict) -> list:
    pontos_f1 = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    pontos_sprint = [8, 7, 6, 5, 4, 3, 2, 1]
    if tipo_prova == "Sprint":
        return list(regras.get("pontos_sprint_posicoes") or regras.get("pontos_posicoes") or pontos_sprint)
    return list(regras.get("pontos_posicoes") or pontos_f1)


def _resolve_temporada_aposta(aposta: pd.Series, prova: pd.Series | dict, temporada: Optional[str] = None) -> str:
    if temporada is not None and str(temporada).strip() != "":
        return str(temporada)
    temporada_aposta = aposta.get("temporada", None)
    if temporada_aposta is not None and str(temporada_aposta).strip() != "" and not pd.isna(temporada_aposta):
        return str(temporada_aposta)
    temporada_prova = prova.get("temporada", str(datetime.now().year))
    if temporada_prova is not None and str(temporada_prova).strip() != "":
        return str(temporada_prova)
    return str(datetime.now().year)


def detalhar_pontuacao_aposta(
    aposta: pd.Series,
    prova: pd.Series | dict,
    resultado: pd.Series | dict,
    temporada: Optional[str] = None,
) -> PontuacaoDetalhada:
    """Calcula a pontuacao de uma aposta e retorna seus componentes."""
    prova_nome = str(aposta.get("nome_prova") or prova.get("nome") or "Prova")
    tipo_prova = _tipo_prova(prova_nome, prova.get("tipo", "Normal"))
    temporada_resolvida = _resolve_temporada_aposta(aposta, prova, temporada)
    regras = get_regras_aplicaveis(temporada_resolvida, tipo_prova)
    pontos_por_posicao = _pontos_lista(tipo_prova, regras)
    posicoes_dict = _parse_posicoes(resultado.get("posicoes"))
    piloto_para_pos = {str(v).strip(): int(k) for k, v in posicoes_dict.items() if str(v).strip()}

    pilotos_apostados = [p.strip() for p in str(aposta.get("pilotos", "")).split(",")]
    fichas = []
    for raw in str(aposta.get("fichas", "")).split(","):
        try:
            fichas.append(int(raw))
        except Exception:
            fichas.append(0)

    abandonos: set[str] = set()
    if regras.get("penalidade_abandono"):
        raw_aband = resultado.get("abandono_pilotos", "") or ""
        abandonos = {p.strip() for p in str(raw_aband).split(",") if p and p.strip()}

    linhas = []
    total_pontos = 0.0
    for idx, piloto in enumerate(pilotos_apostados):
        ficha = fichas[idx] if idx < len(fichas) else 0
        pos_real = piloto_para_pos.get(str(piloto).strip())
        pontos = 0.0
        if pos_real is not None and 1 <= pos_real <= len(pontos_por_posicao):
            pontos = float(ficha) * float(pontos_por_posicao[pos_real - 1])
            total_pontos += pontos
        linhas.append(
            {
                "piloto": piloto,
                "fichas": ficha,
                "posicao_real": str(pos_real) if pos_real is not None else "-",
                "dnf": "DNF" if str(piloto).strip() in abandonos else "-",
                "pontos": pontos,
            }
        )

    piloto_11_apostado = str(aposta.get("piloto_11", "") or "").strip()
    piloto_11_real = str(posicoes_dict.get(11, "") or "").strip()
    bonus_11 = float(regras.get("pontos_11_colocado", 25) or 0)
    pontos_11 = bonus_11 if piloto_11_apostado == piloto_11_real else 0.0
    total_pontos += pontos_11

    penalidade_abandono = 0.0
    pilotos_abandonados = []
    if abandonos:
        pilotos_abandonados = [p for p in pilotos_apostados if p.strip() in abandonos]
        penalidade_abandono = float(regras.get("pontos_penalidade", 0) or 0) * len(pilotos_abandonados)
        total_pontos -= penalidade_abandono

    multiplicador_sprint = 1
    if tipo_prova == "Sprint" and regras.get("pontos_dobrada"):
        multiplicador_sprint = 2
        total_pontos *= multiplicador_sprint

    penalidade_auto = 0.0
    try:
        automatica = int(aposta.get("automatica", 0) or 0)
    except Exception:
        automatica = 0
    if automatica >= 2:
        fator = max(0, 1 - (float(regras.get("penalidade_auto_percent", 20) or 20) / 100))
        total_com_desconto = round(total_pontos * fator, 2)
        penalidade_auto = round(total_pontos - total_com_desconto, 2)
        total_pontos = total_com_desconto

    return {
        "prova_nome": prova_nome,
        "tipo_prova": tipo_prova,
        "temporada": temporada_resolvida,
        "linhas": linhas,
        "piloto_11_apostado": piloto_11_apostado,
        "piloto_11_real": piloto_11_real,
        "pontos_11": pontos_11,
        "penalidade_abandono": penalidade_abandono,
        "pilotos_abandonados": pilotos_abandonados,
        "multiplicador_sprint": multiplicador_sprint,
        "penalidade_auto": penalidade_auto,
        "total_pontos": round(float(total_pontos), 2),
    }


def calcular_pontuacao_detalhada_lote(ap_df, res_df, prov_df, temporada: Optional[str] = None) -> list[PontuacaoDetalhada | None]:
    """Calcula pontuacao em lote preservando o detalhe de cada aposta."""
    resultados_map = {}
    for _, resultado in res_df.iterrows():
        posicoes = _parse_posicoes(resultado.get("posicoes"), none_on_error=True)
        if posicoes is None:
            continue
        dados_resultado = dict(resultado)
        dados_resultado["posicoes"] = posicoes
        resultados_map[resultado["prova_id"]] = dados_resultado

    provas_map = {}
    for _, prova in prov_df.iterrows():
        prova_dict = dict(prova)
        prova_nome = prova_dict.get("nome", "")
        prova_dict["tipo"] = _tipo_prova(prova_nome, prova_dict.get("tipo", "Normal"))
        provas_map[prova["id"]] = prova_dict

    detalhes = []
    for _, aposta in ap_df.iterrows():
        prova_id = aposta["prova_id"]
        resultado = resultados_map.get(prova_id)
        prova = provas_map.get(prova_id)
        if resultado is None or prova is None:
            detalhes.append(None)
            continue
        detalhes.append(detalhar_pontuacao_aposta(aposta, prova, resultado, temporada))
    return detalhes


def calcular_pontuacao_lote(ap_df, res_df, prov_df, temporada_descarte=None):
    """
    Calcula pontuação usando:
    - Tabelas de pontos da REGRA (Normal/Sprint), com fallback FIA hardcoded
    - Fichas DINAMICAS da aposta do usuário
    - Bonus 11o DINAMICO da regra da temporada
    - Penalidades DINAMICAS das regras

    Formula: Pontos = (Pontos_Regra x Fichas) + Bonus_11o - Penalidades
    """
    # Parametro legado mantido porque painel/classificacao ja chamam esta API com ele.
    detalhes = calcular_pontuacao_detalhada_lote(ap_df, res_df, prov_df)
    return [None if detalhe is None else detalhe["total_pontos"] for detalhe in detalhes]


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
    import traceback
    try:
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

        # normalizar colunas categóricas (podem vir do adaptador DB como Categorical)
        for _df in (usrs, provs, apts, ress):
            if _df is None or _df.empty:
                continue
            for _col in list(_df.columns):
                try:
                    if pd.api.types.is_categorical_dtype(_df[_col]):
                        _df[_col] = _df[_col].astype(object)
                except Exception:
                    try:
                        _df[_col] = _df[_col].astype(object)
                    except Exception:
                        pass

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

        # process provas in chronological order so we can use prior cumulative totals as tertiary desempate
        if "data" in provs.columns:
            provs_proc = provs.copy()
            provs_proc["__data_dt"] = pd.to_datetime(provs_proc["data"], errors="coerce")
            provs_proc = provs_proc.sort_values(by=["__data_dt", "id"]).reset_index(drop=True)
        else:
            provs_proc = provs.sort_values(by=["id"]).reset_index(drop=True)

        # cumulative totals per temporada (used as tertiary desempate)
        cum_totals_per_temp: dict[str, dict[int, float]] = defaultdict(dict)

        for _, pr in provs_proc.iterrows():
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

                # cumulative total up to (but not including) this prova for the user's temporada
                try:
                    temporada_key = str(temporada_prova)
                except Exception:
                    temporada_key = str(datetime.now().year)
                cum_total = float(cum_totals_per_temp.get(temporada_key, {}).get(int(u["id"]), 0) or 0)

                tab.append(
                    {
                        "usuario_id": u["id"],
                        "pontos": pontos_val,
                        "data_envio": data_envio,
                        "acerto_11": acerto_11,
                        "cum_total": cum_total,
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

            # ordenar de forma robusta usando chaves Python para evitar problemas com Categorical
            def _safe_float(v):
                try:
                    return float(v)
                except Exception:
                    try:
                        s = str(v).replace(',', '.')
                        return float(s)
                    except Exception:
                        return 0.0

            def _timestamp_ns(ts):
                try:
                    if pd.isna(ts):
                        return 10 ** 30
                    # pd.Timestamp.value retorna ns since epoch (UTC-aware)
                    return int(pd.to_datetime(ts).value)
                except Exception:
                    return 10 ** 30

            keys = []
            for i, row in df.iterrows():
                pontos_n = _safe_float(row.get('pontos', 0))
                dt_ns = _timestamp_ns(row.get('data_envio'))
                ac11 = int(_safe_float(row.get('acerto_11', 0)))
                cum = _safe_float(row.get('cum_total', 0))
                # chave para ordenação: menor é melhor
                keys.append(( -pontos_n, dt_ns, -ac11, -cum, i ))

            order = [t[-1] for t in sorted(keys)]
            df = df.iloc[order].reset_index(drop=True)
            df["posicao"] = df.index + 1
            salvar_classificacao_prova(pid, df, temporada_prova)

            # Atualiza os totais acumulados para a temporada (usados como desempate em provas futuras)
            temporada_key = str(temporada_prova)
            if temporada_key not in cum_totals_per_temp:
                cum_totals_per_temp[temporada_key] = {}
            for _, r in df.iterrows():
                try:
                    uid = int(r["usuario_id"])
                    pontos_r = float(r["pontos"] or 0)
                    prev = float(cum_totals_per_temp[temporada_key].get(uid, 0) or 0)
                    cum_totals_per_temp[temporada_key][uid] = prev + pontos_r
                except Exception:
                    continue
    except Exception:
        try:
            with open('/tmp/bets_scoring_trace.log', 'w') as _f:
                _f.write(traceback.format_exc())
        except Exception:
            pass
        raise


__all__ = [
    "_parse_datetime_sp",
    "PontuacaoDetalhada",
    "PontuacaoLinha",
    "detalhar_pontuacao_aposta",
    "calcular_pontuacao_detalhada_lote",
    "calcular_pontuacao_lote",
    "salvar_classificacao_prova",
    "atualizar_classificacoes_todas_as_provas",
]
