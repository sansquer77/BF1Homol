import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_frontend_uses_next_app_router_typescript_and_standalone_output():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    config = (FRONTEND / "next.config.ts").read_text(encoding="utf-8")

    assert package["dependencies"]["next"]
    assert package["dependencies"]["react"]
    assert package["scripts"]["typecheck"] == "tsc --noEmit"
    assert (FRONTEND / "src/app/layout.tsx").is_file()
    assert (FRONTEND / "src/app/page.tsx").is_file()
    assert (FRONTEND / "src/app/login/page.tsx").is_file()
    assert 'output: "standalone"' in config


def test_apexcharts_is_shared_responsive_and_has_text_alternative():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    chart = (FRONTEND / "src/components/accessible-chart.tsx").read_text(encoding="utf-8")

    assert package["dependencies"]["apexcharts"]
    assert package["dependencies"]["react-apexcharts"]
    assert 'dynamic(() => import("react-apexcharts")' in chart
    assert "responsive:" in chart
    assert 'role="img"' in chart
    assert "Ver dados do gráfico em tabela" in chart
    assert "<caption" in chart


def test_mobile_first_contract_has_360px_without_page_overflow():
    css = (FRONTEND / "src/app/globals.css").read_text(encoding="utf-8")

    assert "@media (max-width: 430px)" in css
    assert "min-width: 0" in css
    assert "overflow-x: auto" in css
    assert "prefers-reduced-motion" in css
    assert "44px" in css


def test_typed_client_is_generated_from_versioned_openapi_and_uses_secure_transport():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    client = (FRONTEND / "src/lib/api/client.ts").read_text(encoding="utf-8")
    generated = (FRONTEND / "src/lib/api/schema.d.ts").read_text(encoding="utf-8")
    openapi = json.loads((ROOT / "api/openapi-v1.json").read_text(encoding="utf-8"))

    assert package["scripts"]["generate:api"]
    assert openapi["openapi"].startswith("3.")
    assert openapi["info"]["version"] == "4.0.0"
    assert "This file was auto-generated" in generated
    assert 'credentials: "include"' in client
    assert '"x-csrf-token"' not in client.lower() or "X-CSRF-Token" in client
    assert "localStorage" not in client


def test_v4_python_runtime_has_no_legacy_ui_or_plotly_dependencies():
    requirements = (ROOT / "requirements-api.txt").read_text(encoding="utf-8").lower()
    transitional = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()

    assert "fastapi" in requirements
    assert "uvicorn" in requirements
    assert "streamlit" not in requirements
    assert "streamlit-calendar" not in requirements
    assert "plotly" not in requirements
    assert "streamlit-calendar" in transitional
    assert "ponte será removida no cutover" in transitional


def test_login_is_invite_only_and_calendar_contract_is_preserved():
    login = (FRONTEND / "src/app/login/page.tsx").read_text(encoding="utf-8")
    readme = (FRONTEND / "README.md").read_text(encoding="utf-8")

    assert "Não existe cadastro público" in login
    assert "streamlit-calendar" in readme
    assert "será implementada em React" in readme
    assert "fuso" in readme


def test_v4_uses_official_identity_telemetry_name_and_accessible_team_palette():
    layout = (FRONTEND / "src/app/layout.tsx").read_text(encoding="utf-8")
    brand = (FRONTEND / "src/components/brand-mark.tsx").read_text(encoding="utf-8")
    shell = (FRONTEND / "src/components/app-shell.tsx").read_text(encoding="utf-8")
    dashboard = (FRONTEND / "src/components/dashboard-overview.tsx").read_text(encoding="utf-8")
    palette = (FRONTEND / "src/lib/team-colors.ts").read_text(encoding="utf-8")
    css = (FRONTEND / "src/app/globals.css").read_text(encoding="utf-8")
    spec = (ROOT / "docs/specs/migracao-v4-nextjs-fastapi.md").read_text(encoding="utf-8")

    assert (FRONTEND / "public/bf1-icon.png").is_file()
    assert (FRONTEND / "src/app/icon.png").is_file()
    assert 'src="/bf1-icon.png"' in brand
    assert 'icons: { icon: "/bf1-icon.png"' in layout
    assert '{ label: "Telemetria", href: "/"' in shell
    assert "Participante” é apresentado como **Telemetria**" in spec

    assert "--red: #e10600" in css
    assert "--success: #00e073" in css
    assert "#dfff3f" not in css.lower()
    assert "team-marker" in dashboard
    assert "aria-label={`Equipe ${person.team}`}" in dashboard

    expected_colors = {
        "#DC0000", "#FF8700", "#0A1B40", "#00A39A", "#005F41",
        "#005BA9", "#FF80BD", "#1868DB", "#6C98FF", "#01C00E",
        "#9C9FA2", "#EB0A1E",
    }
    assert expected_colors.issubset(set(palette.split('"')))


def test_regulation_and_about_pages_preserve_institutional_contract():
    regulation = (FRONTEND / "src/app/regulamento/page.tsx").read_text(encoding="utf-8")
    about = (FRONTEND / "src/app/sobre/page.tsx").read_text(encoding="utf-8")
    tenor = (FRONTEND / "src/components/tenor-embed.tsx").read_text(encoding="utf-8")
    about_version = (FRONTEND / "src/components/about-version.tsx").read_text(encoding="utf-8")
    spec = (ROOT / "docs/specs/conteudo-institucional-v4.md").read_text(encoding="utf-8")
    css = (FRONTEND / "src/app/globals.css").read_text(encoding="utf-8")

    for marker in ("Regulamento BF1-2026", "Inscrições", "Ausências e penalizações", "Regra de descarte", "Critérios de desempate", "Pagamento e premiação"):
        assert marker in regulation
    assert "14649753" in tenor
    assert "sandbox=" in tenor
    assert 'loading="lazy"' in tenor
    assert "iframe" in tenor
    assert "Next.js, TypeScript e ApexCharts" in about
    assert '"/api/v1/content/about"' in about_version
    assert "Versão V4" in about_version
    assert "sem overflow horizontal" in spec
    assert ".tenor-frame iframe" in css
    assert ".about-grid" in css


def test_calendar_uses_canonical_circuit_ids_and_vetted_track_sources():
    calendar = (FRONTEND / "src/components/calendar-view.tsx").read_text(encoding="utf-8")
    assets = (FRONTEND / "src/lib/track-assets.ts").read_text(encoding="utf-8")
    page = (FRONTEND / "src/app/calendario/page.tsx").read_text(encoding="utf-8")
    css = (FRONTEND / "src/app/globals.css").read_text(encoding="utf-8")

    assert '"/api/v1/calendar?season=" + DEFAULT_SEASON' in calendar
    assert 'alt={"Desenho da pista de " + race.name}' in calendar
    assert "f1laps/f1-track-vectors" not in calendar
    assert "julesr0y/f1-circuits-svg" not in calendar
    assert "julesr0y/f1-circuits-svg" in assets
    assert "albert_park" in assets
    assert "red_bull_ring" in assets
    assert (FRONTEND / "public/tracks/albert_park.svg").is_file()
    assert (FRONTEND / "public/tracks/baku-1.svg").is_file()
    assert "race-grid" in css
    assert "calendar-view" in page
    attribution = FRONTEND / "public/tracks/ATTRIBUTION.md"
    assert attribution.is_file()
    assert "Creative Commons Attribution 4.0" in attribution.read_text(encoding="utf-8")
