from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ("EMAIL_MASTER", "SENHA_MASTER", "USUARIO_MASTER")


def test_v4_preserves_digitalocean_master_variable_names():
    manager = (ROOT / "db/master_user_manager.py").read_text(encoding="utf-8")
    spec = (ROOT / "docs/specs/migracao-v4-nextjs-fastapi.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for variable in EXPECTED:
        assert variable in manager
        assert variable in spec
        assert f"{variable}=" in env_example

    for invented_name in ("MASTER_EMAIL", "MASTER_PASSWORD", "MASTER_NOME"):
        assert invented_name not in spec
        assert f"{invented_name}=" not in env_example
