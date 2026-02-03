import streamlit as st
import smtplib
import os
import logging
import html
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Tentar obter credenciais de email de secrets ou environment variables
try:
    EMAIL_REMETENTE = st.secrets.get("EMAIL_REMETENTE")
except (FileNotFoundError, KeyError):
    EMAIL_REMETENTE = None

try:
    SENHA_REMETENTE = st.secrets.get("SENHA_EMAIL")
except (FileNotFoundError, KeyError):
    SENHA_REMETENTE = None

try:
    EMAIL_ADMIN = st.secrets.get("EMAIL_ADMIN")
except (FileNotFoundError, KeyError):
    EMAIL_ADMIN = None

try:
    PERPLEXITY_API_KEY = st.secrets.get("PERPLEXITY_API_KEY")
except (FileNotFoundError, KeyError):
    PERPLEXITY_API_KEY = None

try:
    PERPLEXITY_MODEL = st.secrets.get("PERPLEXITY_MODEL")
except (FileNotFoundError, KeyError):
    PERPLEXITY_MODEL = None

EMAIL_REMETENTE = EMAIL_REMETENTE or os.environ.get("EMAIL_REMETENTE", "")
SENHA_REMETENTE = SENHA_REMETENTE or os.environ.get("SENHA_EMAIL", "")
EMAIL_ADMIN = EMAIL_ADMIN or os.environ.get("EMAIL_ADMIN", "")
PERPLEXITY_API_KEY = PERPLEXITY_API_KEY or os.environ.get("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL = PERPLEXITY_MODEL or os.environ.get("PERPLEXITY_MODEL", "sonar")

def enviar_email(destinatario: str, assunto: str, corpo_html: str) -> bool:
    """Envia um e-mail HTML para o destinatário informado."""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_REMETENTE
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo_html, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_REMETENTE, SENHA_REMETENTE)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Erro no envio para {destinatario}: {str(e)}")
        return False

def gerar_previsao_sarcastica(nome_usuario: str, nome_prova: str, pilotos: list[str], fichas: list[int], piloto_11: str) -> str:
    """Gera um texto divertido e sarcástico usando a API da Perplexity.

    Retorna string vazia quando a API não estiver configurada ou em caso de erro.
    """
    if not PERPLEXITY_API_KEY:
        return ""

    try:
        pilotos_fmt = ", ".join([html.escape(p) for p in pilotos])
        fichas_fmt = ", ".join([str(f) for f in fichas])
        payload = {
            "model": PERPLEXITY_MODEL,
            "temperature": 0.85,
            "max_tokens": 120,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Você é um especialista em F1 divertido e levemente sarcástico. "
                        "Faça uma previsão humorada e amigável sobre a aposta do participante, "
                        "sem ofensas pessoais, sem palavrões e sem humilhações. "
                        "Use 1 a 2 frases curtas."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Participante: {nome_usuario}. Prova: {nome_prova}. "
                        f"Pilotos: {pilotos_fmt}. Fichas: {fichas_fmt}. "
                        f"Palpite 11º: {piloto_11}."
                    )
                }
            ]
        }

        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        texto = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return texto.strip()
    except Exception as e:
        logger.warning(f"Falha ao gerar previsão sarcástica: {e}")
        return ""

def enviar_email_recuperacao_senha(email_usuario: str, nome_usuario: str, nova_senha: str):
    """Envia e-mail com senha temporária para o usuário."""
    corpo_html = f"""
    <h3>Recuperação de Senha - BF1</h3>
    <p>Olá, {nome_usuario}!</p>
    <p>Sua nova senha temporária é: <b>{nova_senha}</b></p>
    <p>Faça login e altere sua senha imediatamente após o acesso.</p>
    """
    enviar_email(email_usuario, "Recuperação de Senha - BF1", corpo_html)
