import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from io import BytesIO
import matplotlib.image as mpimg
import datetime as dt
import ast
from zoneinfo import ZoneInfo
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from services.data_access_core import (
    db_connect,
)
from services.data_access_apostas import (
    get_apostas_df,
    get_participantes_temporada_df,
    get_posicoes_participantes_df,
)
from services.data_access_provas import (
    get_provas_df,
    get_resultados_df,
)
from services.data_access_auth import (
    usuarios_status_historico_disponivel,
)
from services.championship_service import get_championship_bets_df, get_final_results
from services.rules_service import get_regras_aplicaveis
from services.bets_scoring import _parse_datetime_sp, calcular_pontuacao_lote
from utils.helpers import render_page_header
from utils.season_utils import get_default_season_index, get_season_options
from utils.dataframe_contracts import (
    APOSTAS_COLUMNS,
    CHAMPIONSHIP_BETS_COLUMNS,
    POSICOES_COLUMNS,
    PROVAS_COLUMNS,
    RESULTADOS_COLUMNS,
    USUARIOS_COLUMNS,
    with_required_columns,
)


def _normalizar_ids_numericos(df: pd.DataFrame, *columns: str) -> pd.DataFrame:
    """Descarta IDs ausentes/inválidos antes de conversões e agrupamentos."""
    result = df.copy()
    for column in columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=list(columns)).copy()
    for column in columns:
        result[column] = result[column].astype(int)
    return result


def _table_height(total_rows: int, row_height: int = 38, max_height: int = 700) -> int:
    return min(max_height, 40 + (max(total_rows, 1) * row_height))


def _montar_pontos_por_participante(
    apostas_pontos_df: pd.DataFrame,
    df_class: pd.DataFrame,
    provas_df: pd.DataFrame,
) -> pd.DataFrame:
    """Monta a grade com participantes nas linhas e provas nas colunas."""
    participantes_ordem = df_class[["usuario_id", "Participante"]].drop_duplicates("usuario_id")
    provas_ordem = provas_df[["id", "nome"]].drop_duplicates("id").sort_values("id")

    if apostas_pontos_df.empty:
        pontos = pd.DataFrame()
    else:
        pontos = apostas_pontos_df.pivot_table(
            index="usuario_id",
            columns="prova_id",
            values="__pontos_calculados",
            aggfunc="last",
            fill_value=0,
        )

    pontos = pontos.reindex(
        index=participantes_ordem["usuario_id"].tolist(),
        columns=provas_ordem["id"].tolist(),
        fill_value=0,
    )
    pontos.index = participantes_ordem["Participante"].tolist()
    pontos.index.name = "Participante"
    pontos.columns = provas_ordem["nome"].tolist()
    return pontos.apply(pd.to_numeric, errors="coerce").fillna(0.0)

def formatar_brasileiro(valor):
    try:
        return f"{valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
    except:
        return valor

def gerar_imagem_tabela_ajustada(df, colunas):
    df_exibicao = df[colunas].astype(str).copy()

    max_larguras = []
    for col in colunas:
        max_len = df_exibicao[col].map(len).max()
        max_len = max(max_len, len(col))
        max_larguras.append(max_len)

    total_chars = sum(max_larguras) if sum(max_larguras) > 0 else 1
    col_widths = [max_len / total_chars for max_len in max_larguras]

    largura_figura = max(16.0, total_chars * 0.14)
    altura_figura = max(4.8, len(df_exibicao) * 0.62 + 2.2)
    fig, ax = plt.subplots(figsize=(largura_figura, altura_figura), dpi=200)
    ax.axis('off')

    fonte_tabela = 13 if len(df_exibicao) <= 20 else 11
    try:
        logo = mpimg.imread("BF1.jpg")
        logo_img = OffsetImage(logo, zoom=0.18)
        ab = AnnotationBbox(logo_img, (0, 1), xycoords='axes fraction', frameon=False, box_alignment=(0, 1), pad=0.03)
        ax.add_artist(ab)
    except Exception:
        pass

    tabela = ax.table(
        cellText=df_exibicao.values.tolist(),
        colLabels=colunas,
        cellLoc='center',
        loc='center',
        colWidths=col_widths
    )
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(fonte_tabela)
    tabela.scale(1.15, 1.55)

    for (row, col), cell in tabela.get_celld().items():
        if row == 0:
            cell.set_text_props(weight='bold', color='white')
            cell.set_facecolor('#1f4e79')
        else:
            cell.set_facecolor('#f6f9fc' if row % 2 == 0 else 'white')
        cell.set_edgecolor('#b8c4d0')
        cell.set_linewidth(0.7)

    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=320)
    plt.close(fig)
    buffer.seek(0)
    return buffer

def gerar_imagem_prova(df_cruzada, prova_selecionada, apostas_df=None, resultados_df=None, provas_df=None, df_class=None):
    if prova_selecionada not in df_cruzada.index:
        return None

    def parse_num(x):
        try:
            if pd.isna(x):
                return 0.0
        except Exception:
            pass
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == '' or s == '-' or s.lower() in ['none', 'nan']:
            return 0.0
        s2 = s.replace('.', '').replace(',', '.')
        try:
            return float(s2)
        except Exception:
            try:
                return float(s)
            except Exception:
                return 0.0

    dados_prova = df_cruzada.loc[prova_selecionada]

    # map participante -> usuario_id a partir de df_class se disponível
    name_to_uid = {}
    if df_class is not None and 'Participante' in df_class.columns and 'usuario_id' in df_class.columns:
        try:
            name_to_uid = pd.Series(df_class['usuario_id'].values, index=df_class['Participante'].values).to_dict()
        except Exception:
            name_to_uid = {}

    # identificar prova_id para consultar apostas/resultados
    prova_id = None
    if provas_df is not None and 'nome' in provas_df.columns and 'id' in provas_df.columns:
        tmp = provas_df[provas_df['nome'] == prova_selecionada]
        if not tmp.empty:
            try:
                prova_id = int(tmp.iloc[0]['id'])
            except Exception:
                prova_id = None

    piloto_11_real = None
    if resultados_df is not None and prova_id is not None and 'prova_id' in resultados_df.columns:
        rr = resultados_df[resultados_df['prova_id'] == prova_id]
        if not rr.empty:
            try:
                pos = ast.literal_eval(rr.iloc[0]['posicoes'])
                piloto_11_real = str(pos.get(11, '')).strip()
            except Exception:
                piloto_11_real = None

    rows = []
    for participante in dados_prova.index.tolist():
        raw_val = dados_prova[participante]
        pontos_val = parse_num(raw_val)

        uid = name_to_uid.get(participante)
        data_envio = None
        acerto_11 = 0
        if apostas_df is not None and uid is not None and prova_id is not None:
            ap = apostas_df[(apostas_df['usuario_id'] == uid) & (apostas_df['prova_id'] == prova_id)]
            if not ap.empty:
                ap_sorted = ap.copy()
                if 'data_envio' in ap_sorted.columns:
                    ap_sorted['__dt'] = pd.to_datetime(ap_sorted['data_envio'], errors='coerce')
                    ap_sorted = ap_sorted.sort_values('__dt')
                ap_row = ap_sorted.iloc[0]
                data_envio = ap_row.get('data_envio')
                try:
                    if piloto_11_real is not None:
                        acerto_11 = 1 if str(ap_row.get('piloto_11', '')).strip() == piloto_11_real else 0
                except Exception:
                    acerto_11 = 0

        overall_total = 0.0
        if df_class is not None and 'Participante' in df_class.columns and 'Total Geral' in df_class.columns:
            try:
                match = df_class[df_class['Participante'] == participante]
                if not match.empty:
                    overall_total = float(match['Total Geral'].iloc[0])
            except Exception:
                overall_total = 0.0

        rows.append({
            'Participante': participante,
            'pontos': pontos_val,
            'data_envio': pd.to_datetime(data_envio, errors='coerce') if data_envio is not None else pd.NaT,
            'acerto_11': int(acerto_11),
            'overall_total': overall_total,
        })

    df_p = pd.DataFrame(rows)
    if df_p.empty:
        return None

    df_p['data_envio_sort'] = df_p['data_envio'].fillna(pd.Timestamp.max)
    df_p = df_p.sort_values(by=['pontos', 'data_envio_sort', 'acerto_11', 'overall_total'], ascending=[False, True, False, False]).reset_index(drop=True)
    df_p['pontos_fmt'] = df_p['pontos'].apply(lambda x: formatar_brasileiro(float(x)))

    df_prova = pd.DataFrame({prova_selecionada: df_p['pontos_fmt'].values}, index=df_p['Participante'].tolist())

    linhas = len(df_prova)
    max_nome = max(df_prova.index.astype(str).map(len).max(), len("Participante")) if linhas > 0 else len("Participante")
    max_valor = max(df_prova[prova_selecionada].astype(str).map(len).max(), len(prova_selecionada)) if linhas > 0 else len(prova_selecionada)
    total_chars = max_nome + max_valor
    largura_figura = max(8.8, total_chars * 0.2)
    altura_figura = max(4.6, linhas * 0.62 + 2.2)
    fig, ax = plt.subplots(figsize=(largura_figura, altura_figura), dpi=200)
    ax.axis('off')

    fonte_tabela = 13 if linhas <= 20 else 11
    try:
        logo = mpimg.imread("BF1.jpg")
        logo_img = OffsetImage(logo, zoom=0.16)
        ab = AnnotationBbox(logo_img, (0, 1), xycoords='axes fraction', frameon=False, box_alignment=(0, 1), pad=0.03)
        ax.add_artist(ab)
    except Exception:
        pass

    table = ax.table(
        cellText=df_prova.astype(str).values.tolist(),
        rowLabels=df_prova.index.astype(str).tolist(),
        colLabels=[prova_selecionada],
        cellLoc='center',
        loc='center',
        colWidths=[0.54]
    )

    table.auto_set_font_size(False)
    table.set_fontsize(fonte_tabela)
    table.scale(1.2, 1.55)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight='bold', color='white')
            cell.set_facecolor('#1f4e79')
        elif col == -1:
            cell.set_text_props(weight='bold')
            cell.set_facecolor('#eef3f8')
        else:
            cell.set_facecolor('#f6f9fc' if row % 2 == 0 else 'white')
        cell.set_edgecolor('#b8c4d0')
        cell.set_linewidth(0.7)

    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=320)
    plt.close(fig)
    buffer.seek(0)
    return buffer

def main():
    render_page_header(st, "Classificação Geral do Bolão")

    current_year = dt.datetime.now().year
    season_options = get_season_options(fallback_years=["2025", "2026"])
    if not season_options:
        st.info("Não há temporadas disponíveis para consulta no seu histórico de status.")
        return
    default_index = get_default_season_index(season_options, current_year=str(current_year))

    season = st.selectbox("Temporada", season_options, index=default_index, key="classificacao_season")
    st.session_state['temporada'] = season

    if not usuarios_status_historico_disponivel():
        st.warning(
            "⚠️ Aviso técnico: histórico de status de usuários indisponível. "
            "Para temporadas anteriores, os participantes podem refletir o status atual."
        )

    try:
        season_int = int(season)
    except (TypeError, ValueError):
        season_int = current_year

    usuarios_df = with_required_columns(get_participantes_temporada_df(season), USUARIOS_COLUMNS)
    provas_df = with_required_columns(get_provas_df(season), PROVAS_COLUMNS)
    apostas_df = with_required_columns(get_apostas_df(season), APOSTAS_COLUMNS)
    resultados_df = with_required_columns(get_resultados_df(season), RESULTADOS_COLUMNS)

    usuarios_df = _normalizar_ids_numericos(usuarios_df, "id")
    provas_df = _normalizar_ids_numericos(provas_df, "id")
    apostas_df = _normalizar_ids_numericos(apostas_df, "usuario_id", "prova_id")
    resultados_df = _normalizar_ids_numericos(resultados_df, "prova_id")

    # Garante IDs únicos em provas_df (evita ValueError no set_index/to_dict)
    if not provas_df.empty and provas_df['id'].duplicated().any():
        provas_df = provas_df.drop_duplicates(subset='id', keep='first')

    participantes = usuarios_df[
        usuarios_df["nome"].notna() & (usuarios_df['nome'].astype(str) != 'Master')
    ]
    provas_df = provas_df.sort_values('data')
    perfil_usuario = st.session_state.get("user_role", "usuario").strip().lower()

    apostas_pontos_df = apostas_df.copy()
    if not apostas_pontos_df.empty:
        pontos_calculados = calcular_pontuacao_lote(
            apostas_pontos_df,
            resultados_df,
            provas_df,
            temporada_descarte=season,
        )
        apostas_pontos_df["__pontos_calculados"] = [
            0 if p is None else float(p) for p in pontos_calculados
        ]
        apostas_pontos_df["__pontos_calculados"] = pd.to_numeric(
            apostas_pontos_df["__pontos_calculados"], errors="coerce"
        ).fillna(0.0)
    else:
        apostas_pontos_df["__pontos_calculados"] = []

    pontos_por_usuario = {}
    if not apostas_pontos_df.empty:
        pontos_por_usuario = apostas_pontos_df.groupby("usuario_id")["__pontos_calculados"].sum().to_dict()

    resultado_campeonato = get_final_results(season_int)
    championship_bets_map = {}
    if resultado_campeonato:
        championship_bets_df = with_required_columns(
            get_championship_bets_df(season_int), CHAMPIONSHIP_BETS_COLUMNS
        )
        championship_bets_df = _normalizar_ids_numericos(championship_bets_df, "user_id")
        if not championship_bets_df.empty:
            championship_bets_map = {
                int(row['user_id']): {
                    'champion': row.get('champion'),
                    'vice': row.get('vice'),
                    'team': row.get('team'),
                }
                for _, row in championship_bets_df.iterrows()
            }

    tabela_classificacao = []

    regras_temporada = get_regras_aplicaveis(str(season), "Normal")
    pontos_campeao = regras_temporada.get('pontos_campeao', 150)
    pontos_vice = regras_temporada.get('pontos_vice', 100)
    pontos_equipe = regras_temporada.get('pontos_equipe', 80)

    acertos_11_por_usuario = {}
    apostas_no_prazo_por_usuario = {}
    apostas_latest = apostas_df.copy()
    if not apostas_latest.empty:
        if 'data_envio' in apostas_latest.columns:
            apostas_latest['__envio_dt'] = pd.to_datetime(apostas_latest['data_envio'], errors='coerce')
            apostas_latest = apostas_latest.sort_values('__envio_dt')
        apostas_latest = apostas_latest.drop_duplicates(subset=['usuario_id', 'prova_id'], keep='last')

    if not resultados_df.empty and not apostas_latest.empty:
        res_11 = []
        for _, r in resultados_df.iterrows():
            try:
                posicoes = ast.literal_eval(r['posicoes'])
                piloto_11_real = str(posicoes.get(11, '')).strip()
            except Exception:
                piloto_11_real = ''
            if piloto_11_real:
                res_11.append({'prova_id': r['prova_id'], 'piloto_11_real': piloto_11_real})
        if res_11:
            res_11_df = pd.DataFrame(res_11)
            merged_11 = apostas_latest.merge(res_11_df, on='prova_id', how='inner')
            merged_11['acerto_11'] = merged_11.apply(
                lambda row: str(row.get('piloto_11', '')).strip() == str(row.get('piloto_11_real', '')).strip(),
                axis=1
            )
            acertos_11_por_usuario = merged_11.groupby('usuario_id')['acerto_11'].sum().to_dict()

    if not apostas_latest.empty and not provas_df.empty:
        provas_map = provas_df.set_index('id').to_dict('index')
        for _, ap in apostas_latest.iterrows():
            prova = provas_map.get(ap['prova_id'])
            if not prova:
                continue
            data_str = prova.get('data')
            hora_str = prova.get('horario_prova', '00:00') or '00:00'
            if not data_str:
                continue
            try:
                cutoff = _parse_datetime_sp(str(data_str), str(hora_str))
                raw_envio = ap.get('data_envio')
                if raw_envio is None:
                    continue
                envio = pd.to_datetime(str(raw_envio), errors='coerce')
                if pd.isna(envio) or not isinstance(envio, pd.Timestamp):
                    continue
                envio_dt = envio.to_pydatetime()
                if envio_dt.tzinfo is None:
                    envio_dt = envio_dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
                if envio_dt.astimezone(ZoneInfo("UTC")) <= cutoff.astimezone(ZoneInfo("UTC")):
                    uid = int(ap['usuario_id'])
                    apostas_no_prazo_por_usuario[uid] = apostas_no_prazo_por_usuario.get(uid, 0) + 1
            except (TypeError, ValueError, KeyError):
                continue

    for idx, part in participantes.iterrows():
        uid_part = int(part['id'])
        apostas_part = apostas_pontos_df[apostas_pontos_df['usuario_id'] == part['id']]
        apostas_part = apostas_part.sort_values(by='prova_id') if not apostas_part.empty else apostas_part
        total_provas = float(pontos_por_usuario.get(uid_part, 0) or 0)

        bonus_campeao = 0
        bonus_vice = 0
        bonus_equipe = 0
        acertou_campeao = 0
        acertou_vice = 0
        acertou_equipe = 0
        if resultado_campeonato:
            aposta_camp = championship_bets_map.get(uid_part)
            if aposta_camp:
                if resultado_campeonato.get("champion") == aposta_camp.get("champion"):
                    bonus_campeao = pontos_campeao
                    acertou_campeao = 1
                if resultado_campeonato.get("vice") == aposta_camp.get("vice"):
                    bonus_vice = pontos_vice
                    acertou_vice = 1
                if resultado_campeonato.get("team") == aposta_camp.get("team"):
                    bonus_equipe = pontos_equipe
                    acertou_equipe = 1
        pontos_campeonato = bonus_campeao + bonus_vice + bonus_equipe
        acertos_11 = int(acertos_11_por_usuario.get(uid_part, 0))
        apostas_no_prazo = int(apostas_no_prazo_por_usuario.get(uid_part, 0))

        tabela_classificacao.append({
            "Participante": part['nome'],
            "usuario_id": uid_part,
            "Pontos Provas": total_provas,
            "Bônus Campeão": bonus_campeao,
            "Bônus Vice": bonus_vice,
            "Bônus Equipe": bonus_equipe,
            "Pontos Campeonato": pontos_campeonato,
            "Total Geral": total_provas + pontos_campeonato,
            "Acertos 11": acertos_11,
            "Acertou Campeao": acertou_campeao,
            "Acertou Equipe": acertou_equipe,
            "Acertou Vice": acertou_vice,
            "Apostas no Prazo": apostas_no_prazo
        })

    df_class = pd.DataFrame(tabela_classificacao)
    if df_class.empty:
        st.info("Nenhuma pontuação disponível para a temporada selecionada.")
        return

    df_class = df_class.sort_values(
        ["Total Geral", "Acertos 11", "Acertou Campeao", "Acertou Equipe", "Acertou Vice", "Apostas no Prazo"],
        ascending=[False, False, False, False, False, False]
    ).reset_index(drop=True)
    df_class['Posição'] = df_class.index + 1

    provas_realizadas = provas_df[provas_df['id'].isin(resultados_df['prova_id'])]
    if len(provas_realizadas) > 1:
        penultima_prova_id = provas_realizadas.iloc[-2]['id']
        provas_ate_penultima = provas_realizadas[provas_realizadas['id'] <= penultima_prova_id]['id'].tolist()
        tabela_anterior = []
        for idx, part in participantes.iterrows():
            uid_part = int(part['id'])
            apostas_anteriores = apostas_pontos_df[
                (apostas_pontos_df['usuario_id'] == part['id']) &
                (apostas_pontos_df['prova_id'].isin(provas_ate_penultima))
            ]
            total_anteriores = (
                float(apostas_anteriores["__pontos_calculados"].sum())
                if not apostas_anteriores.empty else 0.0
            )

            tabela_anterior.append({
                "Participante": part['nome'],
                "usuario_id": uid_part,
                "Total Geral": total_anteriores
            })
        df_class_anterior = pd.DataFrame(tabela_anterior)
        df_class_anterior = df_class_anterior.sort_values("Total Geral", ascending=False).reset_index(drop=True)
        df_class_anterior['Posição Anterior'] = df_class_anterior.index + 1
        df_class = df_class.merge(
            df_class_anterior[['usuario_id', 'Posição Anterior']],
            on='usuario_id',
            how='left'
        )
        def movimento(row):
            if pd.isnull(row['Posição Anterior']):
                return "Novo"
            diff = int(row['Posição Anterior']) - int(row['Posição'])
            if diff > 0:
                return f"Subiu {diff}"
            elif diff < 0:
                return f"Caiu {abs(diff)}"
            else:
                return "Permaneceu"
        df_class['Movimentação'] = df_class.apply(movimento, axis=1)
    else:
        df_class['Movimentação'] = "Novo"

    diferencas = [0]
    totals = df_class["Total Geral"].tolist()
    for i in range(1, len(totals)):
        diferencas.append(totals[i-1] - totals[i])
    df_class["Diferença"] = ["-" if i == 0 else formatar_brasileiro(d) for i, d in enumerate(diferencas)]

    df_display = df_class.copy()
    for col in ["Pontos Provas", "Bônus Campeão", "Bônus Vice", "Bônus Equipe", "Pontos Campeonato", "Total Geral"]:
        df_display[col] = df_display[col].apply(lambda x: formatar_brasileiro(float(x)))

    colunas_ordem = [
        "Posição",
        "Participante",
        "Pontos Provas",
        "Bônus Campeão",
        "Bônus Vice",
        "Bônus Equipe",
        "Pontos Campeonato",
        "Total Geral",
        "Diferença",
        "Movimentação"
    ]
    st.subheader("Classificação Geral (Provas + Campeonato)")
    total_rows = len(df_display.index)
    table_height = _table_height(total_rows)
    class_config = {
        "Posição": st.column_config.NumberColumn("Posição", format="%d", width="small"),
        "Participante": st.column_config.TextColumn("Participante", width="medium"),
        "Pontos Provas": st.column_config.TextColumn("Pontos Provas", width="small"),
        "Bônus Campeão": st.column_config.TextColumn("Bônus Campeão", width="small"),
        "Bônus Vice": st.column_config.TextColumn("Bônus Vice", width="small"),
        "Bônus Equipe": st.column_config.TextColumn("Bônus Equipe", width="small"),
        "Pontos Campeonato": st.column_config.TextColumn("Pontos Campeonato", width="small"),
        "Total Geral": st.column_config.TextColumn("Total Geral", width="small"),
        "Diferença": st.column_config.TextColumn("Diferença", width="small"),
        "Movimentação": st.column_config.TextColumn("Movimentação", width="small"),
    }
    st.dataframe(
        df_display[colunas_ordem],
        hide_index=True,
        width="stretch",
        height=table_height,
        row_height=38,
        column_config=class_config,
    )

    csv_classificacao = df_display[colunas_ordem].to_csv(index=False)
    st.download_button(
        label="Baixar tabela da classificação (CSV)",
        data=csv_classificacao,
        file_name="classificacao_geral.csv",
        mime="text/csv",
        on_click="ignore",
    )

    if perfil_usuario in ['admin', 'master']:
        if st.button("Preparar imagem da tabela", key="preparar_imagem_classificacao"):
            with st.spinner("Gerando imagem da classificação..."):
                st.session_state["imagem_classificacao_geral"] = (
                    season,
                    gerar_imagem_tabela_ajustada(df_display, colunas_ordem).getvalue(),
                )
        imagem_gerada = st.session_state.get("imagem_classificacao_geral")
        if imagem_gerada and imagem_gerada[0] == season:
            st.download_button(
                label='Baixar imagem da tabela',
                data=imagem_gerada[1],
                file_name='classificacao_geral.png',
                mime='image/png',
                on_click="ignore",
            )

    st.subheader("Pontuação por Prova")
    provas_df_ord = provas_df.sort_values('id')
    df_por_participante = _montar_pontos_por_participante(
        apostas_pontos_df,
        df_class,
        provas_df_ord,
    )
    # As rotinas de gráfico e imagem trabalham com uma prova por linha.
    df_cruzada = df_por_participante.T
    df_formatado = df_por_participante.map(lambda x: formatar_brasileiro(float(x)))
    prova_config = {
        "_index": st.column_config.TextColumn("Participante", width="medium"),
        **{col: st.column_config.TextColumn(str(col), width="medium") for col in df_formatado.columns},
    }
    st.dataframe(
        df_formatado,
        width="stretch",
        height=_table_height(len(df_formatado), max_height=700),
        column_config=prova_config,
    )

    st.subheader("Imagem da classificação de uma prova específica")
    prova_selecionada = st.selectbox(
        "Selecione a prova para gerar imagem da classificação:",
        options=df_cruzada.index.tolist()
    )
    if perfil_usuario in ['admin', 'master']:
        if st.button("Gerar imagem da prova selecionada"):
            imagem_buffer_prova = gerar_imagem_prova(
                df_cruzada,
                prova_selecionada,
                apostas_df=apostas_df,
                resultados_df=resultados_df,
                provas_df=provas_df,
                df_class=df_class,
            )
            if imagem_buffer_prova:
                st.download_button(
                    label=f"Baixar imagem da classificação da prova {prova_selecionada}",
                    data=imagem_buffer_prova,
                    file_name=f'classificacao_{prova_selecionada}.png',
                    mime='image/png',
                    on_click="ignore",
                )
            else:
                st.warning("Prova selecionada não contém dados para gerar imagem.")

    st.subheader("Evolução da Pontuação Acumulada")
    provas_com_resultado_ids = resultados_df['prova_id'].unique()
    provas_com_resultado_nomes = provas_df[provas_df['id'].isin(provas_com_resultado_ids)].sort_values('id')['nome'].tolist()
    df_grafico = df_cruzada.loc[df_cruzada.index.isin(provas_com_resultado_nomes)]
    df_grafico = df_grafico.reindex(provas_com_resultado_nomes)
    def texto_para_float(x):
        if isinstance(x, float): return x
        return float(str(x).replace('.', '').replace(',', '.'))
    df_grafico_float = df_grafico.map(texto_para_float)
    if not df_grafico_float.empty:
        fig = go.Figure()
        for participante in df_grafico_float.columns:
            pontos_acumulados = df_grafico_float[participante].cumsum()
            fig.add_trace(go.Scatter(
                x=df_grafico_float.index.tolist(),
                y=pontos_acumulados,
                mode='lines+markers',
                name=participante
            ))
        fig.update_layout(
            title="Evolução da Pontuação Acumulada",
            xaxis_title="Prova",
            yaxis_title="Pontuação Acumulada",
            xaxis_tickangle=-45,
            margin=dict(l=40, r=20, t=60, b=80),
            plot_bgcolor='#000000',
            paper_bgcolor='#000000',
            font=dict(color='#F5F7FA'),
            xaxis=dict(
                tickfont=dict(color='#F5F7FA'),
                title_font=dict(color='#F5F7FA'),
                gridcolor='rgba(255,255,255,0.16)'
            ),
            yaxis=dict(
                tickformat=',.0f',
                tickfont=dict(color='#F5F7FA'),
                title_font=dict(color='#F5F7FA'),
                gridcolor='rgba(255,255,255,0.16)',
                zerolinecolor='rgba(255,255,255,0.25)'
            ),
            legend=dict(
                font=dict(color='#F5F7FA'),
                bgcolor='rgba(0,0,0,0.35)'
            )
        )
        st.plotly_chart(fig, width="stretch")

    st.subheader("Classificação de Cada Participante ao Longo do Campeonato")
    # fix #5: substituir query raw por helper de repositório — elimina conexão extra e duplicação de SQL
    df_posicoes = with_required_columns(get_posicoes_participantes_df(season), POSICOES_COLUMNS)
    df_posicoes = _normalizar_ids_numericos(df_posicoes, "usuario_id", "prova_id")
    fig_all = go.Figure()
    for part in participantes['nome']:
        u_id = participantes[participantes['nome'] == part].iloc[0]['id']
        if df_posicoes.empty:
            continue
        posicoes_part_raw = df_posicoes[df_posicoes['usuario_id'] == u_id]
        if isinstance(posicoes_part_raw, pd.Series):
            posicoes_part = pd.DataFrame([posicoes_part_raw])
        else:
            posicoes_part = posicoes_part_raw
        posicoes_part = posicoes_part.sort_values(by='prova_id')
        if not posicoes_part.empty:
            x_vals = []
            for pid in posicoes_part['prova_id']:
                p_name_arr = provas_df[provas_df['id'] == pid]['nome'].values
                x_vals.append(p_name_arr[0] if len(p_name_arr) > 0 else f"ID {pid}")
            fig_all.add_trace(go.Scatter(
                x=x_vals,
                y=posicoes_part['posicao'],
                mode='lines+markers',
                name=part
            ))
    fig_all.update_yaxes(autorange="reversed")
    fig_all.update_layout(xaxis_title="Prova", yaxis_title="Posição", legend_title="Participante")
    st.plotly_chart(fig_all, width="stretch")

if __name__ == "__main__":
    main()
