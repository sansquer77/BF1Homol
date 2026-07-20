"""Contratos tabulares compartilhados entre serviços e telas."""

import pandas as pd

APOSTAS_COLUMNS = (
    "id", "usuario_id", "prova_id", "data_envio", "pilotos", "fichas",
    "piloto_11", "nome_prova", "automatica", "temporada",
)


def with_required_columns(df, columns) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()
    result = df.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = pd.Series(index=result.index, dtype="object")
    return result

