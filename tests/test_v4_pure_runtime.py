import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_legacy_streamlit_application_is_absent():
    assert not (ROOT / "main.py").exists()
    assert not (ROOT / "ui").exists()
    assert not (ROOT / ".streamlit").exists()


def test_python_runtime_has_no_streamlit_imports():
    violations = []
    for layer in ("api", "services", "db", "utils"):
        for path in (ROOT / layer).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = ""
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                else:
                    continue
                if any(value == "streamlit" or value.startswith("streamlit.") for value in modules):
                    violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_dependency_manifests_have_no_streamlit_packages():
    manifests = [ROOT / "requirements.txt", ROOT / "requirements-api.txt", FRONTEND / "package.json"]
    for path in manifests:
        assert "streamlit" not in path.read_text(encoding="utf-8").lower()


def test_frontend_owns_global_season_state():
    provider = (FRONTEND / "src/lib/season-context.tsx").read_text(encoding="utf-8")
    shell = (FRONTEND / "src/components/app-shell.tsx").read_text(encoding="utf-8")
    assert "SeasonProvider" in provider
    assert "useSeason" in provider
    assert "SeasonProvider" in shell


def test_frontend_persists_timezone_through_authenticated_api():
    source = (FRONTEND / "src/lib/timezone-context.tsx").read_text(encoding="utf-8")
    assert "/api/v1/auth/account/timezone" in source
    assert 'localStorage.setItem("bf1-timezone"' in source
    assert "safeTimezone(user.timezone)" in source


def test_heavy_charts_are_loaded_lazily():
    chart = (FRONTEND / "src/components/accessible-chart.tsx").read_text(encoding="utf-8")
    assert 'dynamic(() => import("react-apexcharts")' in chart
    assert "ssr: false" in chart


def test_frontend_has_no_database_driver_dependency():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    forbidden = {"pg", "postgres", "psycopg", "sqlite3", "better-sqlite3"}
    assert forbidden.isdisjoint(dependencies)


def test_api_is_the_only_python_web_entrypoint():
    source = (ROOT / "bf1homol-v4.yaml").read_text(encoding="utf-8")
    assert "uvicorn api.main:app" in source
    assert "streamlit" not in source.lower()
