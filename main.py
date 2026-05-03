"""
main.py - Versão 3.0
Melhorias:
- Pool de conexões
- Bcrypt para senhas
- Master user manager
- Rate limiting
- Tema Liquid Glass (responsivo mobile/desktop)
- Detecção automática de Timezone do cliente
"""
import streamlit as st
import logging
import datetime
from pathlib import Path

# ============ CONFIGURAR PÁGINA PRIMEIRO ============
st.set_page_config(
    page_title="BF1",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="auto",
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
    
    # Carregar favicon como base64
    favicon_path = Path(__file__).parent / "static" / "favicon.ico"
    
    icon_base64 = ""
    favicon_base64 = ""
    
    if icon_path.exists():
        with open(icon_path, "rb") as f:
            icon_base64 = base64.b64encode(f.read()).decode()
    
    if favicon_path.exists():
        with open(favicon_path, "rb") as f:
            favicon_base64 = base64.b64encode(f.read()).decode()
    
    # Usar JavaScript para injetar as meta tags no <head> do documento
    if icon_base64 or favicon_base64:
        icon_data_uri = f"data:image/png;base64,{icon_base64}" if icon_base64 else ""
        favicon_data_uri = f"data:image/x-icon;base64,{favicon_base64}" if favicon_base64 else ""
        st.markdown(f"""
            <script>
            (function() {{
                var head = document.getElementsByTagName('head')[0];
                
                // Remover meta tags antigas se existirem
                document.querySelectorAll('link[rel="apple-touch-icon"]').forEach(el => el.remove());
                document.querySelectorAll('link[rel="icon"]').forEach(el => el.remove());
                document.querySelectorAll('link[rel="manifest"]').forEach(el => el.remove());
                
                // Favicon via data URI
                var favicon = document.createElement('link');
                favicon.rel = 'icon';
                favicon.type = 'image/x-icon';
                favicon.href = '{favicon_data_uri}';
                head.appendChild(favicon);
                
                // Manifest para PWA
                var manifest = document.createElement('link');
                manifest.rel = 'manifest';
                manifest.href = '/static/manifest.json';
                head.appendChild(manifest);
                
                // Apple Touch Icon (múltiplos tamanhos)
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
        <meta name="theme-color" content="#d32f2f">
        <meta name="description" content="BF1 - Bolão de Fórmula 1 - Sistema de gerenciamento de apostas de F1">
    """, unsafe_allow_html=True)


# Timezones válidos reconhecidos pelo seletor da sidebar.
# Usado para validar o valor capturado via JS antes de gravar na session.
_VALID_TIMEZONES: set[str] = {
    "America/Sao_Paulo",
    "America/Recife",
    "America/Manaus",
    "America/Rio_Branco",
    "UTC",
    "Europe/London",
    "Europe/Paris",
    "Asia/Tokyo",
    "Asia/Dubai",
    "Australia/Sydney",
}

_TZ_DEFAULT = "America/Sao_Paulo"


def _inject_html(html_code: str) -> None:
    """Injeta HTML/JS no app usando a API não-depreciada disponível.

    Hierarquia de preferência:
      1. ``st.html()``        — disponível a partir do Streamlit 1.36+
      2. ``st.markdown()``    — fallback universal; requer unsafe_allow_html=True

    ``streamlit.components.v1.html`` foi depreciado e será removido após
    2026-06-01 (aviso nos logs a partir de ~mai/2026).
    """
    if hasattr(st, "html"):
        # st.html() é a API atual e recomendada (Streamlit >= 1.36)
        st.html(html_code)
    else:
        # Fallback para versões anteriores ao 1.36
        st.markdown(html_code, unsafe_allow_html=True)


def load_timezone_detector():
    """Detecta o timezone do cliente via JS e sincroniza com session_state.

    Estratégia de comunicação JS → Python:
      1. O script JS lê `Intl.DateTimeFormat().resolvedOptions().timeZone`.
      2. Compara com o parâmetro `tz` já presente na URL para evitar recargas
         desnecessárias.
      3. Se divergir, atualiza `window.location.search` com `?tz=<valor>`,
         o que provoca um rerun natural do Streamlit.
      4. No lado Python, `st.query_params.get("tz")` captura o valor e o
         armazena em `st.session_state["client_timezone"]`.

    Fallback: se o TZ detectado não estiver na lista _VALID_TIMEZONES, o
    padrão `America/Sao_Paulo` é usado para garantir consistência com o banco.
    """
    # ── Lado Python: lê o TZ da query string (enviado pelo JS no rerun) ──────
    tz_from_url = st.query_params.get("tz", "").strip()
    if tz_from_url and tz_from_url in _VALID_TIMEZONES:
        # Só grava se ainda não estiver definido ou se diferir do atual,
        # evitando reruns em cascata.
        if st.session_state.get("client_timezone") != tz_from_url:
            st.session_state["client_timezone"] = tz_from_url
    elif "client_timezone" not in st.session_state:
        st.session_state["client_timezone"] = _TZ_DEFAULT

    # ── Lado JS: detecta TZ do browser e injeta na URL se necessário ─────────
    current_tz_py = st.session_state["client_timezone"]
    html_code = f"""
    <script>
    (function() {{
        var detected = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
        if (!detected) return;

        // Timezones aceitos pelo backend (deve espelhar _VALID_TIMEZONES)
        var validSet = new Set({list(_VALID_TIMEZONES)});
        var tz = validSet.has(detected) ? detected : '{_TZ_DEFAULT}';

        // TZ já confirmado pelo Python neste ciclo — sem rerun necessário
        var confirmedByPy = '{current_tz_py}';
        if (tz === confirmedByPy) return;

        // Verifica o parâmetro atual da URL para não recarregar à toa
        var params = new URLSearchParams(window.location.search);
        if (params.get('tz') === tz) return;

        // Atualiza a URL com o TZ detectado → Streamlit faz rerun e lê query_params
        params.set('tz', tz);
        var newUrl = window.location.pathname + '?' + params.toString() + window.location.hash;
        window.location.replace(newUrl);
    }})();
    </script>
    """
    _inject_html(html_code)


load_css()
load_pwa_meta_tags()
load_timezone_detector()

# ============ SINCRONIZAÇÃO DE TIMEZONE PARA SESSION STATE ============
def _sync_timezone_to_session():
    """Garante que client_timezone esteja sempre definido na sessão."""
    if "client_timezone" not in st.session_state:
        st.session_state["client_timezone"] = _TZ_DEFAULT

# ============ CONFIGURAÇÃO DE LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ INICIALIZAÇÃO DO BANCO ============
from db.repo_users import get_user_by_id, get_usuario_temporadas_ativas
from db.migrations import run_migrations
from db.master_user_manager import MasterUserManager

@st.cache_resource(show_spinner=False)
def bootstrap_app() -> bool:
    logger.info("🚀 Inicializando BF1 3.0...")
    run_migrations()
    logger.info("✓ Banco de dados/migrations inicializados")
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
from ui.log_acessos import main as log_acessos_view
from ui.gestao_provas import main as gestao_provas_view
from ui.gestao_regras import main as gestao_regras_view
from ui.gestao_pilotos import main as gestao_pilotos_view
from ui.backup import main as backup_view
from ui.dashboard import main as dashboard_view
from ui.sobre import main as sobre_view
from ui.hall_da_fama import hall_da_fama
from services.auth_service import decode_token, clear_auth_cookies

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
        "Log de Acessos",
        "Classificação",
        "Hall da Fama",
        "Dashboard F1",
        "Backup dos Bancos de Dados",
        "Regulamento",
        "Sobre",
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
    ]


def menu_inativo(has_history: bool):
    base = [
        "Painel do Participante",
        _calendario_label(),
        "Hall da Fama",
        "Dashboard F1",
    ]
    if has_history:
        base.extend([
            "Análise de Apostas",
            "Log de Apostas",
            "Classificação",
            "Regulamento",
            "Sobre",
        ])
    return base


def grouped_menu_master():
    return {
        "Participante": [
            "Painel do Participante",
            _calendario_label(),
            "Logout",
        ],
        "Operação": [
            "Gestão de Apostas",
            "Atualização de resultados",
            "Apostas Campeonato",
            "Resultado Campeonato",
        ],
        "Gestão": [
            "Gestão de Usuários",
            "Gestão de Pilotos",
            "Gestão de Provas",
            "Gestão de Regras",
        ],
        "Monitoramento": [
            "Análise de Apostas",
            "Log de Apostas",
            "Log de Acessos",
            "Classificação",
            "Hall da Fama",
            "Dashboard F1",
        ],
        "Sistema": [
            "Backup dos Bancos de Dados",
            "Regulamento",
            "Sobre",
        ],
    }


def grouped_menu_admin():
    return {
        "Participante": [
            "Painel do Participante",
            _calendario_label(),
            "Logout",
        ],
        "Operação": [
            "Gestão de Apostas",
            "Atualização de resultados",
            "Apostas Campeonato",
            "Resultado Campeonato",
        ],
        "Gestão": [
            "Gestão de Pilotos",
            "Gestão de Provas",
        ],
        "Monitoramento": [
            "Análise de Apostas",
            "Log de Apostas",
            "Classificação",
            "Hall da Fama",
            "Dashboard F1",
        ],
        "Sistema": [
            "Regulamento",
            "Sobre",
        ],
    }


def grouped_menu_participante():
    return {
        "Participante": [
            "Painel do Participante",
            _calendario_label(),
            "Regulamento",
            "Logout",
        ],
        "Acompanhamento": [
            "Apostas Campeonato",
            "Análise de Apostas",
            "Log de Apostas",
            "Classificação",
            "Hall da Fama",
            "Dashboard F1",
        ],
        "Sistema": [
            "Sobre",
        ],
    }


def grouped_menu_inativo(has_history: bool):
    menu = {
        "Participante": [
            "Painel do Participante",
            _calendario_label(),
            "Logout",
        ],
        "Monitoramento": [
            "Hall da Fama",
            "Dashboard F1",
        ],
    }
    if has_history:
        menu["Monitoramento"] = [
            "Análise de Apostas",
            "Log de Apostas",
            "Classificação",
            "Hall da Fama",
            "Dashboard F1",
        ]
        menu["Sistema"] = [
            "Regulamento",
            "Sobre",
        ]
    return menu


def _flatten_grouped_menu(grouped_menu: dict[str, list[str]]) -> list[str]:
    flattened: list[str] = []
    for items in grouped_menu.values():
        flattened.extend(items)
    return flattened


def _normalize_grouped_menu(menu_items: list[str], grouped_menu: dict[str, list[str]]) -> tuple[list[str], dict[str, list[str]]]:
    normalized_menu = {section: list(items) for section, items in grouped_menu.items()}

    # Remove duplicatas mantendo a ordem por seção.
    for section_name, items in normalized_menu.items():
        seen: set[str] = set()
        deduped: list[str] = []
        for item in items:
            if item in seen:
                continue
            deduped.append(item)
            seen.add(item)
        normalized_menu[section_name] = deduped

    has_logout = "Logout" in menu_items or any("Logout" in items for items in normalized_menu.values())
    if has_logout:
        for section_name, items in normalized_menu.items():
            normalized_menu[section_name] = [item for item in items if item != "Logout"]

        participante_items = normalized_menu.setdefault("Participante", [])
        participante_items.append("Logout")

    # Garante consistência entre menu linear e agrupado.
    grouped_items = _flatten_grouped_menu(normalized_menu)
    for item in menu_items:
        if item not in grouped_items:
            normalized_menu.setdefault("Outros", []).append(item)
            grouped_items.append(item)

    return _flatten_grouped_menu(normalized_menu), normalized_menu


def _default_group_for_page(grouped_menu: dict[str, list[str]], page: str) -> str:
    for section_name, items in grouped_menu.items():
        if page in items:
            return section_name
    return next(iter(grouped_menu.keys()))

def get_payload():
    token = st.session_state.get('token')
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
    "Log de Acessos": ("master",),
    "Gestão de Pilotos": ("admin", "master"),
    "Gestão de Provas": ("admin", "master"),
    "Gestão de Apostas": ("admin", "master"),
    "Atualização de resultados": ("admin", "master"),
    "Resultado Campeonato": ("admin", "master"),
}

INATIVO_ALLOWED_PAGES_WITH_HISTORY = {
    "Painel do Participante",
    "Calendário (" + str(datetime.datetime.now().year) + ")",
    "Análise de Apostas",
    "Log de Apostas",
    "Classificação",
    "Hall da Fama",
    "Dashboard F1",
    "Regulamento",
    "Sobre",
}

INATIVO_ALLOWED_PAGES_NO_HISTORY = {
    "Painel do Participante",
    "Calendário (" + str(datetime.datetime.now().year) + ")",
    "Hall da Fama",
    "Dashboard F1",
}


def _clear_session_and_redirect_login(msg: str):
    clear_auth_cookies()
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state["pagina"] = "Login"
    st.warning(msg)
    st.stop()


def _ensure_token_from_cookie() -> bool:
    """Valida existência de token na sessão atual (sem restauração por cookie)."""
    token = st.session_state.get("token")
    return bool(token)


def _sync_session_from_token() -> bool:
    """Sincroniza dados básicos da sessão a partir do token antes de renderizar o menu."""
    if not _ensure_token_from_cookie():
        st.session_state.pop("user_role", None)
        st.session_state.pop("user_id", None)
        st.session_state.pop("user_nome", None)
        return False

    token = st.session_state.get("token")
    payload = decode_token(token) if token else None
    if not payload:
        st.session_state.pop("user_role", None)
        st.session_state.pop("user_id", None)
        st.session_state.pop("user_nome", None)
        return False

    perfil = str(payload.get("perfil", "participante")).strip().lower()
    user_id = payload.get("user_id")

    st.session_state["user_id"] = user_id
    st.session_state["user_nome"] = payload.get("nome", st.session_state.get("user_nome"))

    user = get_user_by_id(int(user_id)) if user_id else None
    if not user:
        st.session_state["user_role"] = perfil
        st.session_state["user_status"] = str(payload.get("status", "")).strip().lower()
        st.session_state["allowed_seasons"] = []
        st.session_state["inactive_has_history"] = False
        return True

    status_usuario = str(user.get("status", "")).strip().lower()
    perfil_usuario = str(user.get("perfil", perfil)).strip().lower()
    usuario_inativo = (status_usuario != "ativo") or (perfil_usuario == "inativo")

    if usuario_inativo:
        allowed_seasons = get_usuario_temporadas_ativas(int(user_id))
        st.session_state["allowed_seasons"] = allowed_seasons
        st.session_state["inactive_has_history"] = bool(allowed_seasons)
        st.session_state["user_role"] = "inativo"
    else:
        st.session_state["allowed_seasons"] = []
        st.session_state["inactive_has_history"] = False
        st.session_state["user_role"] = perfil_usuario

    st.session_state["user_status"] = status_usuario
    return True


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
    perfil_usuario = str(user.get("perfil", perfil)).strip().lower()
    usuario_inativo = (status_usuario != "ativo") or (perfil_usuario == "inativo")

    # Sincroniza sessão com claims assinadas do JWT a cada rota.
    st.session_state["user_id"] = user_id
    st.session_state["user_role"] = "inativo" if usuario_inativo else perfil_usuario
    st.session_state["user_nome"] = payload.get("nome", st.session_state.get("user_nome"))
    st.session_state["user_status"] = status_usuario

    if usuario_inativo:
        allowed_seasons = get_usuario_temporadas_ativas(int(user_id))
        has_history = bool(allowed_seasons)
        allowed_pages = INATIVO_ALLOWED_PAGES_WITH_HISTORY if has_history else INATIVO_ALLOWED_PAGES_NO_HISTORY
        st.session_state["allowed_seasons"] = allowed_seasons
        st.session_state["inactive_has_history"] = has_history
        if pagina not in allowed_pages:
            st.error(
                "Usuário inativo possui acesso restrito."
                if has_history
                else "Usuário inativo sem histórico possui acesso apenas a Hall da Fama, Calendário, Dashboard F1 e Minha Conta."
            )
            st.session_state["pagina"] = "Painel do Participante"
            st.stop()
    else:
        st.session_state["allowed_seasons"] = []
        st.session_state["inactive_has_history"] = False

    allowed_roles = ROLE_GUARDS.get(pagina)
    perfil_efetivo = st.session_state.get("user_role", perfil_usuario)
    if allowed_roles and perfil_efetivo not in allowed_roles:
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
    "Log de Acessos": log_acessos_view,
    "Classificação": classificacao_view,
    "Hall da Fama": hall_da_fama,
    "Dashboard F1": dashboard_view,
    "Backup dos Bancos de Dados": backup_view,
    "Regulamento": regulamento_view,
    "Sobre": sobre_view,
}

# ============ MENU LATERAL ============
def sidebar_menu():
    token_ok = _sync_session_from_token()
    token = st.session_state.get("token")
    profile_key = "anon"
    if not token:
        menu_items = ["Login"]
        grouped_menu = {"Acesso": menu_items}
        st.session_state["pagina"] = "Login"
    else:
        perfil = st.session_state.get("user_role", "participante")
        profile_key = str(perfil).strip().lower() or "participante"
        if perfil == "master":
            menu_items = menu_master()
            grouped_menu = grouped_menu_master()
        elif perfil == "admin":
            menu_items = menu_admin()
            grouped_menu = grouped_menu_admin()
        elif perfil == "inativo":
            has_history = bool(st.session_state.get("inactive_has_history", False))
            menu_items = menu_inativo(has_history)
            grouped_menu = grouped_menu_inativo(has_history)
        else:
            menu_items = menu_participante()
            grouped_menu = grouped_menu_participante()

        if not token_ok:
            menu_items = ["Login"]
            grouped_menu = {"Acesso": menu_items}
            st.session_state["pagina"] = "Login"

    menu_items, grouped_menu = _normalize_grouped_menu(menu_items, grouped_menu)

    if "menu_lateral" in st.session_state and st.session_state["menu_lateral"] not in menu_items:
        del st.session_state["menu_lateral"]
    if st.session_state.get("pagina") not in menu_items:
        st.session_state["pagina"] = menu_items[0]

    current_page = st.session_state.get("pagina", menu_items[0])
    last_section_key = f"menu_secao_last_{profile_key}"
    persisted_section = st.session_state.get(last_section_key)
    default_section = persisted_section if persisted_section in grouped_menu else _default_group_for_page(grouped_menu, current_page)
    section_names = list(grouped_menu.keys())
    default_section_index = section_names.index(default_section) if default_section in section_names else 0

    if "menu_secao" in st.session_state and st.session_state["menu_secao"] not in section_names:
        del st.session_state["menu_secao"]

    chosen_section = st.sidebar.selectbox(
        "Seção",
        section_names,
        index=default_section_index,
        key="menu_secao",
    )
    st.session_state[last_section_key] = chosen_section

    section_items = grouped_menu.get(chosen_section, menu_items)
    if "menu_lateral" in st.session_state and st.session_state["menu_lateral"] not in section_items:
        del st.session_state["menu_lateral"]

    section_default = current_page if current_page in section_items else section_items[0]
    section_default_index = section_items.index(section_default)
    escolha = st.sidebar.radio(
        "Menu",
        section_items,
        index=section_default_index,
        key="menu_lateral",
    )
    st.session_state["pagina"] = escolha

    # ============ SELETOR DE TIMEZONE ============
    st.sidebar.divider()
    st.sidebar.markdown("### 🌍 Timezone")

    # Lista de timezones oferecidos — deve ser idêntica a _VALID_TIMEZONES (ordenada).
    common_timezones = sorted(_VALID_TIMEZONES)

    current_tz = st.session_state.get("client_timezone", _TZ_DEFAULT)
    # Garante que o valor atual esteja na lista (pode ter vindo de versão antiga).
    if current_tz not in common_timezones:
        current_tz = _TZ_DEFAULT
        st.session_state["client_timezone"] = current_tz
    tz_index = common_timezones.index(current_tz)

    selected_tz = st.sidebar.selectbox(
        "Selecione seu Timezone",
        common_timezones,
        index=tz_index,
        key="timezone_selector",
        help=(
            "Timezone usado para exibir horários no Calendário. "
            "Os dados são armazenados em America/Sao_Paulo."
        ),
    )

    if selected_tz != st.session_state.get("client_timezone"):
        st.session_state["client_timezone"] = selected_tz
        st.rerun()

# ============ APP PRINCIPAL ============
def main():
    # Garante client_timezone definido antes de qualquer view consumir.
    _sync_timezone_to_session()

    sidebar_menu()
    previous_page = st.session_state.get("_current_page")
    pagina = st.session_state["pagina"]
    st.session_state["_previous_page"] = previous_page
    st.session_state["_current_page"] = pagina

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
