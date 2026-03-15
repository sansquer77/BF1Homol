"""
main.py - Versão 3.0
Melhorias:
- Pool de conexões
- Bcrypt para senhas
- Master user manager
- Rate limiting
- Tema Liquid Glass (responsivo mobile/desktop)
"""
import streamlit as st
import logging
import datetime
import json
from pathlib import Path

# ============ CONFIGURAR PÁGINA PRIMEIRO ============
st.set_page_config(
    page_title="BF1",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="auto"
)

# ============ CARREGAR ESTILOS CSS LIQUID GLASS ============
def load_css():
    """Carrega o arquivo CSS customizado com tema Liquid Glass."""
    css_file = Path(__file__).parent / "assets" / "styles.css"
    if css_file.exists():
        with open(css_file, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def load_pwa_meta_tags():
    """Adiciona meta tags para PWA e iOS Add to Home Screen."""
    import base64
    from pathlib import Path
    
    # Carregar ícone 180x180 como base64 (tamanho ideal para iOS)
    icon_path = Path(__file__).parent / "static" / "apple-touch-icon-180.png"
    if not icon_path.exists():
        icon_path = Path(__file__).parent / "static" / "apple-touch-icon.png"
    
    icon_base64 = ""
    if icon_path.exists():
        with open(icon_path, "rb") as f:
            icon_base64 = base64.b64encode(f.read()).decode()
    
    # Usar JavaScript para injetar as meta tags no <head> do documento
    if icon_base64:
        icon_data_uri = f"data:image/png;base64,{icon_base64}"
        st.markdown(f"""
            <script>
            (function() {{
                // Remover meta tags antigas se existirem
                document.querySelectorAll('link[rel="apple-touch-icon"]').forEach(el => el.remove());
                
                // Criar e adicionar novas meta tags no head
                var head = document.getElementsByTagName('head')[0];
                
                // Apple Touch Icon
                var link = document.createElement('link');
                link.rel = 'apple-touch-icon';
                link.href = '{icon_data_uri}';
                head.appendChild(link);
                
                var link180 = document.createElement('link');
                link180.rel = 'apple-touch-icon';
                link180.sizes = '180x180';
                link180.href = '{icon_data_uri}';
                head.appendChild(link180);
                
                // Verificar/adicionar meta tags PWA
                if (!document.querySelector('meta[name="apple-mobile-web-app-capable"]')) {{
                    var meta1 = document.createElement('meta');
                    meta1.name = 'apple-mobile-web-app-capable';
                    meta1.content = 'yes';
                    head.appendChild(meta1);
                }}
                
                if (!document.querySelector('meta[name="apple-mobile-web-app-title"]')) {{
                    var meta2 = document.createElement('meta');
                    meta2.name = 'apple-mobile-web-app-title';
                    meta2.content = 'BF1';
                    head.appendChild(meta2);
                }}
                
                if (!document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]')) {{
                    var meta3 = document.createElement('meta');
                    meta3.name = 'apple-mobile-web-app-status-bar-style';
                    meta3.content = 'black-translucent';
                    head.appendChild(meta3);
                }}
            }})();
            </script>
        """, unsafe_allow_html=True)
    
    st.markdown("""
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="theme-color" content="#0a0a0f">
    """, unsafe_allow_html=True)

load_css()
load_pwa_meta_tags()

# ============ CONFIGURAÇÃO DE LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ TRIGGER TÉCNICO DE BACKUP (INTERNO) ============
from services.backup_trigger_service import execute_backup_trigger


def _get_query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""

    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    return str(value).strip()


def _handle_internal_backup_trigger() -> bool:
    """
    Fallback compatível com Streamlit para gatilho interno de backup.

    Chamada esperada:
      /?internal_route=/internal/backup/run
    """
    internal_route = _get_query_param("internal_route")
    if internal_route != "/internal/backup/run":
        return False

    headers: dict[str, str] = {}
    try:
        headers = {k: str(v) for k, v in st.context.headers.items()}
    except Exception:
        headers = {}

    query_token = _get_query_param("token")
    status_code, payload = execute_backup_trigger(headers=headers, query_token=query_token)

    # Streamlit não expõe status HTTP customizado para páginas de app;
    # retornamos status_code no corpo para consumo por automação.
    payload = {
        **payload,
        "status_code": status_code,
        "route": "/internal/backup/run",
        "method": "POST (preferencial) / GET(query fallback)",
    }

    st.title("Internal Backup Trigger")
    st.code(json.dumps(payload, ensure_ascii=False), language="json")
    st.stop()
    return True


_handle_internal_backup_trigger()

# ============ INICIALIZAÇÃO DO BANCO ============
from db.db_utils import init_db, get_user_by_id, get_usuario_temporadas_ativas
from db.migrations import run_migrations
from db.master_user_manager import MasterUserManager
from db.db_config import DB_PATH, DB_PATH_SOURCE

@st.cache_resource(show_spinner=False)
def bootstrap_app() -> bool:
    logger.info("🚀 Inicializando BF1 3.0...")
    logger.info("📦 Banco SQLite configurado em %s (source=%s)", DB_PATH, DB_PATH_SOURCE)
    init_db()
    logger.info("✓ Banco de dados inicializado")
    run_migrations()
    MasterUserManager.create_master_user()
    return True


bootstrap_app()

# ============ IMPORTAÇÃO DAS VIEWS ============
from ui.login import login_view
from ui.painel import participante_view
from ui.usuarios import main as usuarios_view
from ui.gestao_resultados import resultados_view
from ui.calendario import main as calendario_view
from ui.championship_bets import main as championship_bets_view
from ui.championship_results import main as championship_results_view
from ui.gestao_apostas import main as gestao_apostas_view
from ui.analysis import main as analysis_view
from ui.regulamento import main as regulamento_view
from ui.classificacao import main as classificacao_view
from ui.log_apostas import main as log_apostas_view
from ui.gestao_provas import main as gestao_provas_view
from ui.gestao_regras import main as gestao_regras_view
from ui.gestao_pilotos import main as gestao_pilotos_view
from ui.backup import main as backup_view
from ui.dashboard import main as dashboard_view
from ui.sobre import main as sobre_view
from ui.hall_da_fama import hall_da_fama
from services.auth_service import decode_token, clear_auth_cookies, get_auth_cookie_token

# ============ ESTADO INICIAL DA SESSÃO ============
if 'pagina' not in st.session_state:
    st.session_state['pagina'] = "Login"
if 'token' not in st.session_state:
    st.session_state['token'] = None

# ============ MENUS POR PERFIL ============
def _calendario_label():
    return f"Calendário ({datetime.datetime.now().year})"

def menu_master():
    return [
        "Painel do Participante",
        _calendario_label(),
        "Gestão de Usuários",
        "Gestão de Pilotos",
        "Gestão de Provas",
        "Gestão de Regras",
        "Gestão de Apostas",
        "Análise de Apostas",
        "Atualização de resultados",
        "Apostas Campeonato",
        "Resultado Campeonato",
        "Log de Apostas",
        "Classificação",
        "Hall da Fama",
        "Dashboard F1",
        "Backup dos Bancos de Dados",
        "Regulamento",
        "Sobre",
        "Logout"
    ]

def menu_admin():
    return [
        "Painel do Participante",
        _calendario_label(),
        "Gestão de Apostas",
        "Gestão de Pilotos",
        "Gestão de Provas",
        "Análise de Apostas",
        "Atualização de resultados",
        "Apostas Campeonato",
        "Resultado Campeonato",
        "Log de Apostas",
        "Classificação",
        "Hall da Fama",
        "Dashboard F1",
        "Regulamento",
        "Sobre",
        "Logout"
    ]

def menu_participante():
    return [
        "Painel do Participante",
        _calendario_label(),
        "Apostas Campeonato",
        "Análise de Apostas",
        "Log de Apostas",
        "Classificação",
        "Hall da Fama",
        "Dashboard F1",
        "Regulamento",
        "Sobre",
        "Logout"
    ]

def get_payload():
    token = st.session_state.get('token')
    if not token:
        token = get_auth_cookie_token()
        if token:
            st.session_state['token'] = token
    if not token:
        st.session_state['pagina'] = "Login"
        st.stop()
    payload = decode_token(token)
    if not payload:
        clear_auth_cookies()
        st.session_state['pagina'] = "Login"
        st.session_state['token'] = None
        st.stop()
    return payload


ROLE_GUARDS = {
    "Gestão de Usuários": ("master",),
    "Gestão de Regras": ("master",),
    "Backup dos Bancos de Dados": ("master",),
    "Gestão de Pilotos": ("admin", "master"),
    "Gestão de Provas": ("admin", "master"),
    "Gestão de Apostas": ("admin", "master"),
    "Atualização de resultados": ("admin", "master"),
    "Resultado Campeonato": ("admin", "master"),
}

INATIVO_ALLOWED_PAGES = {
    "Painel do Participante",
    "Calendário (" + str(datetime.datetime.now().year) + ")",
    "Apostas Campeonato",
    "Análise de Apostas",
    "Log de Apostas",
    "Classificação",
    "Hall da Fama",
    "Dashboard F1",
    "Regulamento",
    "Sobre",
}


def _clear_session_and_redirect_login(msg: str):
    clear_auth_cookies()
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state["pagina"] = "Login"
    st.warning(msg)
    st.stop()


def _ensure_token_from_cookie() -> bool:
    """Restaura token de cookie para sessão, quando houver."""
    token = st.session_state.get("token")
    if token:
        return True
    cookie_token = get_auth_cookie_token()
    if cookie_token:
        st.session_state["token"] = cookie_token
        return True
    return False


def _enforce_route_guard(pagina: str):
    if pagina in ("Login", "Logout"):
        return

    _ensure_token_from_cookie()
    token = st.session_state.get("token")
    if not token:
        _clear_session_and_redirect_login("Sessão ausente. Faça login novamente.")

    payload = decode_token(token)
    if not payload:
        _clear_session_and_redirect_login("Sessão expirada ou inválida. Faça login novamente.")

    perfil = str(payload.get("perfil", "participante")).strip().lower()
    user_id = payload.get("user_id")

    if not user_id:
        _clear_session_and_redirect_login("Sessão inválida. Faça login novamente.")

    user = get_user_by_id(int(user_id))
    if not user:
        _clear_session_and_redirect_login("Usuário não encontrado. Faça login novamente.")

    status_usuario = str(user.get("status", "")).strip().lower()

    # Sincroniza sessão com claims assinadas do JWT a cada rota.
    st.session_state["user_id"] = user_id
    st.session_state["user_role"] = perfil
    st.session_state["user_nome"] = payload.get("nome", st.session_state.get("user_nome"))
    st.session_state["user_status"] = status_usuario

    if status_usuario != "ativo":
        st.session_state["allowed_seasons"] = get_usuario_temporadas_ativas(int(user_id))
        if pagina not in INATIVO_ALLOWED_PAGES:
            st.error("Usuário inativo possui acesso somente para consulta das temporadas em que esteve ativo.")
            st.session_state["pagina"] = "Painel do Participante"
            st.stop()
    else:
        st.session_state["allowed_seasons"] = []

    allowed_roles = ROLE_GUARDS.get(pagina)
    if allowed_roles and perfil not in allowed_roles:
        st.error("Acesso negado: você não possui permissão para esta página.")
        st.session_state["pagina"] = "Painel do Participante"
        st.stop()

# ============ DICIONÁRIO DE ROTAS ============
PAGES = {
    "Login": login_view,
    "Painel do Participante": participante_view,
    _calendario_label(): calendario_view,
    "Gestão de Usuários": usuarios_view,
    "Gestão de Pilotos": gestao_pilotos_view,
    "Gestão de Provas": gestao_provas_view,
    "Gestão de Apostas": gestao_apostas_view,
    "Gestão de Regras": gestao_regras_view,
    "Análise de Apostas": analysis_view,
    "Atualização de resultados": resultados_view,
    "Apostas Campeonato": championship_bets_view,
    "Resultado Campeonato": championship_results_view,
    "Log de Apostas": log_apostas_view,
    "Classificação": classificacao_view,
    "Hall da Fama": hall_da_fama,
    "Dashboard F1": dashboard_view,
    "Backup dos Bancos de Dados": backup_view,
    "Regulamento": regulamento_view,
    "Sobre": sobre_view,
}

# ============ MENU LATERAL ============
def sidebar_menu():
    _ensure_token_from_cookie()
    token = st.session_state.get("token")
    if not token:
        menu_items = ["Login"]
    else:
        perfil = st.session_state.get("user_role", "participante")
        if perfil == "master":
            menu_items = menu_master()
        elif perfil == "admin":
            menu_items = menu_admin()
        else:
            menu_items = menu_participante()
    
    escolha = st.sidebar.radio("Menu", menu_items, key="menu_lateral")
    st.session_state["pagina"] = escolha

# ============ APP PRINCIPAL ============
def main():
    sidebar_menu()
    pagina = st.session_state["pagina"]
    
    # LOGOUT
    if pagina == "Logout":
        clear_auth_cookies()
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.sidebar.success("Logout realizado com sucesso.")
        st.rerun()
        return

    _enforce_route_guard(pagina)
    
    # EXECUTA A VIEW
    if pagina in PAGES:
        PAGES[pagina]()
    else:
        st.error("Página não encontrada.")

if __name__ == "__main__":
    main()
