import unicodedata
import re
from datetime import datetime, timedelta

def normalize_str(text: str) -> str:
    """
    Remove acentos/diacríticos, espaços extras e converte string para minúsculas.
    Útil para comparações e buscas insensíveis a acentuação.
    """
    if not isinstance(text, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).strip().lower()


def contains_html(text: str) -> bool:
    """
    Detecta se uma string contém conteúdo HTML básico.
    """
    if not isinstance(text, str):
        return False
    return bool(re.search(r"<.*?>", text))


def safe_str(obj) -> str:
    """
    Converte qualquer objeto para string, tratando exceções.
    """
    try:
        return str(obj)
    except Exception:
        return ""


def format_datetime(dt: datetime, fmt: str = "%d/%m/%Y %H:%M") -> str:
    """
    Formata um objeto datetime para string no formato desejado.
    """
    if not isinstance(dt, datetime):
        return ""
    return dt.strftime(fmt)


def parse_date(date_str: str, fmt: str = "%Y-%m-%d") -> datetime | None:
    """
    Converte texto em objeto datetime. Retorna None se inválido.
    """
    try:
        return datetime.strptime(date_str, fmt)
    except (ValueError, TypeError):
        return None


def is_recent(ts: datetime, minutes: int = 30) -> bool:
    """
    Verifica se o timestamp informado é recente em relação ao horário atual.
    """
    if not isinstance(ts, datetime):
        return False
    return (datetime.now(ts.tzinfo) - ts) <= timedelta(minutes=minutes)


def list_diff(a: list, b: list) -> list:
    """
    Retorna itens em 'a' que não estão em 'b'.
    """
    return list(set(a) - set(b))


def remove_duplicates(seq: list) -> list:
    """
    Remove duplicidades, preservando ordem.
    """
    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]


def dict_to_query_params(params: dict) -> str:
    """
    Converte um dicionário simples em string de query params GET.
    """
    return "&".join(f"{k}={v}" for k, v in params.items() if v is not None)

