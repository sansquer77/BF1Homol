import streamlit as st
import smtplib
import os
import logging
import html
import httpx
import hashlib
import random
from typing import Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Tentar obter credenciais de email de secrets ou environment variables
try:
    EMAIL_REMETENTE_RAW: Optional[str] = st.secrets.get("EMAIL_REMETENTE")
except (FileNotFoundError, KeyError):
    EMAIL_REMETENTE_RAW = None

try:
    SENHA_REMETENTE_RAW: Optional[str] = st.secrets.get("SENHA_EMAIL")
except (FileNotFoundError, KeyError):
    SENHA_REMETENTE_RAW = None

try:
    EMAIL_ADMIN_RAW: Optional[str] = st.secrets.get("EMAIL_ADMIN")
except (FileNotFoundError, KeyError):
    EMAIL_ADMIN_RAW = None

try:
    PERPLEXITY_API_KEY_RAW: Optional[str] = st.secrets.get("PERPLEXITY_API_KEY")
except (FileNotFoundError, KeyError):
    PERPLEXITY_API_KEY_RAW = None

try:
    PERPLEXITY_MODEL_RAW: Optional[str] = st.secrets.get("PERPLEXITY_MODEL")
except (FileNotFoundError, KeyError):
    PERPLEXITY_MODEL_RAW = None

EMAIL_REMETENTE: str = EMAIL_REMETENTE_RAW or os.environ.get("EMAIL_REMETENTE", "")
SENHA_REMETENTE: str = SENHA_REMETENTE_RAW or os.environ.get("SENHA_EMAIL", "")
EMAIL_ADMIN: str = EMAIL_ADMIN_RAW or os.environ.get("EMAIL_ADMIN", "")
PERPLEXITY_API_KEY: str = PERPLEXITY_API_KEY_RAW or os.environ.get("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL: str = PERPLEXITY_MODEL_RAW or os.environ.get("PERPLEXITY_MODEL", "sonar")


def _gerar_previsao_fallback(nome_usuario: str, nome_prova: str, pilotos: list[str], fichas: list[int], piloto_11: str) -> str:
    """Gera previsão local quando a API externa não estiver disponível."""
    pilotos_fmt = ", ".join([p for p in pilotos if p])
    fichas_fmt = ", ".join([str(f) for f in fichas])
    assinatura = f"{nome_usuario}|{nome_prova}|{pilotos_fmt}|{fichas_fmt}|{piloto_11}"
    seed = int(hashlib.sha256(assinatura.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    modelos = [
        "{nome}, essa aposta para {prova} está com cara de gênio incompreendido: {pilotos}. Se der certo, vai ter discurso; se der errado, vai culpar a aerodinâmica.",
        "{nome}, o pacote em {prova} veio ousado: {pilotos}. Com fichas [{fichas}], você escolheu emoção em vez de paz de espírito.",
        "Em {prova}, {nome} foi full estratégia alternativa: {pilotos}. O palpite de 11º em {p11} é o toque de caos controlado.",
        "{nome}, sua combinação para {prova} parece laboratório de corrida: {pilotos} com fichas [{fichas}]. Pode virar obra-prima ou meme histórico.",
        "Previsão para {nome} em {prova}: {pilotos}. Se {p11} bater no 11º, você merece no mínimo um pódio moral.",
    ]
    template = modelos[rng.randrange(len(modelos))]
    return template.format(
        nome=nome_usuario or "Participante",
        prova=nome_prova or "a prova",
        pilotos=pilotos_fmt or "sem pilotos",
        fichas=fichas_fmt or "sem fichas",
        p11=piloto_11 or "(sem palpite)",
    )

def enviar_email(destinatario: str, assunto: str, corpo_html: str, cco: Optional[list[str]] = None) -> bool:
    """Envia um e-mail HTML para o destinatário informado com opção de CCO."""
    if not EMAIL_REMETENTE or not SENHA_REMETENTE:
        st.error("Credenciais de e-mail não configuradas.")
        return False

    cco = [e.strip() for e in (cco or []) if str(e).strip()]
    destinatarios_envio = []
    if destinatario and str(destinatario).strip():
        destinatarios_envio.append(str(destinatario).strip())
    destinatarios_envio.extend(cco)

    if not destinatarios_envio:
        st.error("Nenhum destinatário válido para envio de e-mail.")
        return False

    msg = MIMEMultipart()
    msg['From'] = EMAIL_REMETENTE
    msg['To'] = destinatario if destinatario and str(destinatario).strip() else EMAIL_REMETENTE
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo_html, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_REMETENTE, SENHA_REMETENTE)
            server.sendmail(EMAIL_REMETENTE, destinatarios_envio, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Erro no envio para {', '.join(destinatarios_envio)}: {str(e)}")
        return False

def gerar_previsao_sarcastica(nome_usuario: str, nome_prova: str, pilotos: list[str], fichas: list[int], piloto_11: str) -> str:
    """Gera um texto divertido e sarcástico usando a API da Perplexity.

    Faz fallback local quando a API não estiver configurada ou em caso de erro.
    """
    if not PERPLEXITY_API_KEY:
        logger.warning("PERPLEXITY_API_KEY não configurada. Usando fallback local para previsão sarcástica.")
        return _gerar_previsao_fallback(nome_usuario, nome_prova, pilotos, fichas, piloto_11)

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
                        "Você é um especialista em F1 divertido e sarcástico. "
                        "Faça uma previsão bem-humorada e ácida sobre a aposta do participante analisando os pilotos escolhidos e as fichas apostadas, "
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
        data = None
        last_error = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    break
            except Exception as retry_error:
                last_error = retry_error

        if data is None:
            raise RuntimeError(str(last_error) if last_error else "Falha sem detalhes da API")

        texto = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        texto = (texto or "").strip()
        if texto:
            return texto

        logger.warning("Perplexity retornou resposta vazia. Usando fallback local.")
        return _gerar_previsao_fallback(nome_usuario, nome_prova, pilotos, fichas, piloto_11)
    except Exception as e:
        logger.warning(f"Falha ao gerar previsão sarcástica: {e}")
        return _gerar_previsao_fallback(nome_usuario, nome_prova, pilotos, fichas, piloto_11)

def enviar_email_recuperacao_senha(email_usuario: str, nome_usuario: str, nova_senha: str):
    """Envia e-mail com senha temporária para o usuário."""
    corpo_html = f"""
    <h3>Recuperação de Senha - BF1</h3>
    <p>Olá, {nome_usuario}!</p>
    <p>Sua nova senha temporária é: <b>{nova_senha}</b></p>
    <p>Faça login e altere sua senha imediatamente após o acesso.</p>
    """
    enviar_email(email_usuario, "Recuperação de Senha - BF1", corpo_html)
