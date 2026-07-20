"""Normalizacao de identificadores usados em controles de seguranca."""

MAX_EMAIL_LENGTH = 254


def normalize_email_identifier(value: object) -> str:
    email = str(value or "").strip().lower()
    if not email or len(email) > MAX_EMAIL_LENGTH:
        raise ValueError("Email ausente ou acima do limite de 254 caracteres.")
    return email

