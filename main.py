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
import os
import logging
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

# ============ INICIALIZAÇÃO DO BANCO ============
from db.db_utils import init_db
from db.migrations import run_migrations
from db.master_user_manager import MasterUserManager

logger.info("🚀 Inicializando BF1 3.0...")
init_db()
logger.info("✓ Banco de dados inicializado")

try:
    run_migrations()
except Exception as e:
    logger.warning(f"⚠️ Migrations já executadas: {e}")

MasterUserManager.create_master_user()

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
from services.auth_service import decode_token

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
        "Gestão de Regras",
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
        st.session_state['pagina'] = "Login"
        st.stop()
    payload = decode_token(token)
    if not payload:
        st.session_state['pagina'] = "Login"
        st.session_state['token'] = None
        st.stop()
    return payload

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
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.sidebar.success("Logout realizado com sucesso.")
        st.rerun()
        return
    
    # EXECUTA A VIEW
    if pagina in PAGES:
        PAGES[pagina]()
    else:
        st.error("Página não encontrada.")

if __name__ == "__main__":
    main()
