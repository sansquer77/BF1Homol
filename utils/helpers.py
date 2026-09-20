import unicodedata
import re
import base64
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

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


def parse_date(date_str: str, fmt: str = "%Y-%m-%d") -> Optional[datetime]:
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


@lru_cache(maxsize=1)
def _bf1_logo_data_uri() -> str:
    """Retorna logo BF1 como data URI para evitar dependência do media handler em memória."""
    # Tentar carregar BF1 2.0.png (versão profissional) primeiro
    logo_path = Path(__file__).resolve().parents[1] / "BF1 2.0.png"
    if not logo_path.exists():
        # Fallback para BF1.jpg se o novo não existir
        logo_path = Path(__file__).resolve().parents[1] / "BF1.jpg"
    
    if not logo_path.exists():
        return ""
    
    content = logo_path.read_bytes()
    encoded = base64.b64encode(content).decode("ascii")
    
    # Determinar tipo MIME baseado na extensão
    file_ext = logo_path.suffix.lower()
    mime_type = "image/png" if file_ext == ".png" else "image/jpeg"
    
    return f"data:{mime_type};base64,{encoded}"


def get_bf1_logo_data_uri() -> str:
    """Retorna o logo BF1 como data URI para uso em emails e outras aplicações.
    
    O data URI contém a imagem codificada em base64 e pode ser usada diretamente
    em tags <img> sem depender de URLs externas.
    
    Returns:
        str: Data URI da imagem BF1 (ex: data:image/png;base64,...)
    """
    return _bf1_logo_data_uri()
