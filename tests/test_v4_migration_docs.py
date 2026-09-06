import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/specs/migracao-v4-nextjs-fastapi.md"
INVENTORY = ROOT / "docs/inventario-v4.md"
ADR = ROOT / "docs/adr/0003-nextjs-fastapi-e-compatibilidade-de-dados.md"
BACKUP_MANIFEST = ROOT / "tests/fixtures/backups/v3_5_0/manifest.json"


def test_v4_foundation_documents_exist_and_are_indexed():
    readme = (ROOT / "docs/README.md").read_text(encoding="utf-8")

    assert SPEC.is_file()
    assert INVENTORY.is_file()
    assert ADR.is_file()
    assert "[[inventario-v4]]" in readme
    assert "[[specs/migracao-v4-nextjs-fastapi|" in readme
    assert "[[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados|" in readme


def test_v4_spec_keeps_backup_compatibility_as_primary_contract():
    spec = SPEC.read_text(encoding="utf-8")

    assert "Nenhuma etapa pode impedir a restauração de backups 3.x suportados" in spec
    assert "PostgreSQL atual: fonte de verdade e contrato primário de compatibilidade" in spec
    assert "ApexCharts" in spec
    assert "autorização por objeto" in spec
    assert "força bruta" in spec
    assert "logs, métricas e erros em arquivos" in spec


def test_v4_inventory_covers_every_current_route():
    inventory = INVENTORY.read_text(encoding="utf-8")
    expected_routes = {
        "Login",
        "Painel do Participante",
        "Calendário",
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
    }

    for route in expected_routes:
        assert f"| {route} |" in inventory


def test_v4_adr_preserves_layer_boundaries_and_legacy_columns():
    adr = ADR.read_text(encoding="utf-8")

    assert "`services/` como núcleo das regras" in adr
    assert "`db/` como persistência" in adr
    assert "migrations aditivas/idempotentes" in adr
    assert "colunas legadas" in adr


def test_v4_uses_same_origin_and_has_no_streamlit_runtime():
    spec = SPEC.read_text(encoding="utf-8")
    adr = ADR.read_text(encoding="utf-8")

    assert "mesma origem" in spec
    assert "`/api/*` ao FastAPI" in spec
    assert "sem runtime, rota, dependência ou mecanismo de sessão do Streamlit" in spec
    assert "sem runtime ou compatibilidade de UI/sessão" in adr


def test_v3_5_backup_source_is_registered_without_raw_sensitive_dump():
    manifest = json.loads(BACKUP_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["source_version"] == "3.5.0"
    assert manifest["source_sha256"] == "a46cb07266875ca11701d1dfad462de79eae2cfeb64c0d09ef60ed0246b2d78d"
    assert manifest["insert_count"] == sum(manifest["tables"].values())
    assert manifest["contains_sensitive_data"] is True
    assert manifest["raw_source_must_not_be_committed"] is True
    assert not list(BACKUP_MANIFEST.parent.glob("*.sql"))


def test_v4_records_invite_only_master_bootstrap_and_log_download():
    spec = SPEC.read_text(encoding="utf-8")

    assert "Não existe cadastro público" in spec
    assert "`MASTER_EMAIL`, `MASTER_PASSWORD` e `MASTER_NOME`" in spec
    assert "reinícios nunca redefinem" in spec
    assert "O Master pode baixar arquivos de log" in spec
    assert "allowlist de arquivos" in spec
    assert "Nenhuma pendência bloqueante conhecida" in spec
