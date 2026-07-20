"""Contratos tabulares compartilhados entre serviços e telas."""

import pandas as pd

APOSTAS_COLUMNS = (
    "id", "usuario_id", "prova_id", "data_envio", "pilotos", "fichas",
    "piloto_11", "nome_prova", "automatica", "temporada",
)

PILOTOS_COLUMNS = ("id", "nome", "equipe", "status", "numero")

PROVAS_COLUMNS = (
    "id", "nome", "data", "horario_prova", "tipo", "status", "temporada", "circuit_id",
)

RESULTADOS_COLUMNS = (
    "prova_id", "posicoes", "abandono_pilotos", "posicoes_jsonb", "abandono_arr",
)

USUARIOS_COLUMNS = (
    "id", "nome", "email", "senha_hash", "perfil", "status",
    "must_change_password", "faltas", "criado_em", "session_version",
)

POSICOES_COLUMNS = ("id", "prova_id", "usuario_id", "posicao", "pontos", "temporada")

CHAMPIONSHIP_BETS_COLUMNS = (
    "user_id", "user_nome", "champion", "vice", "team", "season", "bet_time",
)

CHAMPIONSHIP_RESULTS_COLUMNS = ("season", "champion", "vice", "team")


def with_required_columns(df, columns) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()
    result = df.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = pd.Series(index=result.index, dtype="object")
    return result
