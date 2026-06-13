"""Utilities para conversão de timestamps para timezone do cliente."""

from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def get_client_timezone() -> str:
    """
    Obtém o timezone do cliente armazenado em st.session_state.
    Se não estiver disponível, retorna 'UTC'.
    """
    import streamlit as st
    return st.session_state.get("client_timezone", "UTC")


def convert_utc_to_client_tz(
    utc_timestamp: object,
    client_tz: str = None,
    format_str: str = "%d/%m/%Y %H:%M:%S"
) -> str:
    """
    Converte um timestamp UTC para timezone do cliente no formato especificado.
    
    Args:
        utc_timestamp: timestamp UTC (datetime, str, ou None)
        client_tz: timezone do cliente (ex: 'America/Sao_Paulo')
                   Se None, tenta obter de st.session_state
        format_str: formato da saída (default: "31/12/2026 14:30:45")
    
    Returns:
        String com timestamp convertido no formato especificado,
        ou string vazia se input inválido
    """
    # Tratamento de None e NaN
    if utc_timestamp is None or (isinstance(utc_timestamp, float) and pd.isna(utc_timestamp)):
        return ""
    
    # Se client_tz não fornecido, tenta obter do session_state
    if client_tz is None:
        client_tz = get_client_timezone()
    
    # Validação de timezone
    try:
        tz_obj = ZoneInfo(client_tz)
    except Exception as e:
        logger.warning(f"Timezone inválido '{client_tz}': {e}. Usando UTC.")
        tz_obj = ZoneInfo("UTC")
    
    # Parse do timestamp
    try:
        if isinstance(utc_timestamp, str):
            # Tenta diferentes formatos de string
            dt = pd.to_datetime(utc_timestamp, errors="coerce")
            if pd.isna(dt):
                return str(utc_timestamp)
            dt = dt.to_pydatetime()
        elif isinstance(utc_timestamp, datetime):
            dt = utc_timestamp
        else:
            # Tenta converter para datetime via pandas
            dt = pd.to_datetime(utc_timestamp, errors="coerce")
            if pd.isna(dt):
                return str(utc_timestamp)
            dt = dt.to_pydatetime()
    except Exception as e:
        logger.debug(f"Erro ao fazer parse de timestamp '{utc_timestamp}': {e}")
        return str(utc_timestamp)
    
    # Se datetime é naive (sem timezone), assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    
    # Converte para timezone do cliente
    try:
        dt_local = dt.astimezone(tz_obj)
        return dt_local.strftime(format_str)
    except Exception as e:
        logger.warning(f"Erro ao converter para timezone '{client_tz}': {e}")
        return str(utc_timestamp)


def convert_dataframe_timestamps(
    df: pd.DataFrame,
    timestamp_columns: list[str],
    client_tz: str = None,
    format_str: str = "%d/%m/%Y %H:%M:%S"
) -> pd.DataFrame:
    """
    Converte múltiplas colunas de timestamp em um DataFrame.
    
    Args:
        df: DataFrame contendo as colunas de timestamp
        timestamp_columns: lista de nomes de colunas a converter
        client_tz: timezone do cliente (se None, obtém de st.session_state)
        format_str: formato da saída
    
    Returns:
        DataFrame com colunas de timestamp convertidas
    """
    df_copy = df.copy()
    
    if client_tz is None:
        client_tz = get_client_timezone()
    
    for col in timestamp_columns:
        if col in df_copy.columns:
            df_copy[col] = df_copy[col].apply(
                lambda x: convert_utc_to_client_tz(x, client_tz, format_str)
            )
    
    return df_copy


__all__ = [
    "get_client_timezone",
    "convert_utc_to_client_tz",
    "convert_dataframe_timestamps",
]
