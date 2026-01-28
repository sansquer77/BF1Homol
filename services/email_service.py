import streamlit as st
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

EMAIL_REMETENTE = st.secrets["EMAIL_REMETENTE"] or os.environ.get("EMAIL_REMETENTE", "")
SENHA_REMETENTE = st.secrets["SENHA_EMAIL"] or os.environ.get("SENHA_EMAIL", "")
EMAIL_ADMIN = st.secrets.get("EMAIL_ADMIN", "") or os.environ.get("EMAIL_ADMIN", "")

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

def enviar_email_recuperacao_senha(email_usuario: str, nome_usuario: str, nova_senha: str):
    """Envia e-mail com senha temporária para o usuário."""
    corpo_html = f"""
    <h3>Recuperação de Senha - BF1Dev</h3>
    <p>Olá, {nome_usuario}!</p>
    <p>Sua nova senha temporária é: <b>{nova_senha}</b></p>
    <p>Faça login e altere sua senha imediatamente após o acesso.</p>
    """
    enviar_email(email_usuario, "Recuperação de Senha - BF1Dev", corpo_html)
