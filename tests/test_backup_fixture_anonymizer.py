import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/anonymize_v3_backup_fixture.py"
SPEC = importlib.util.spec_from_file_location("backup_anonymizer", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_anonymizer_preserves_relations_and_redacts_sensitive_values():
    source = """-- BF1 POSTGRES DATA-ONLY DUMP
BEGIN;
INSERT INTO "usuarios" ("id", "nome", "email", "senha_hash", "perfil") VALUES (7, 'Pessoa Real', 'real@example.com', '$2b$hash-real', 'master');
INSERT INTO "access_logs" ("id", "user_id", "email", "nome", "ip_address", "detalhes") VALUES (9, 7, 'real@example.com', 'Pessoa Real', '203.0.113.9', 'texto privado');
INSERT INTO "auth_sessions" ("jti", "user_id") VALUES ('token-real', 7);
INSERT INTO "apostas" ("id", "usuario_id", "pilotos_arr", "fichas_arr") VALUES (11, 7, ARRAY['Piloto A','Piloto B'], ARRAY[10,5]);
COMMIT;
"""
    result = MODULE.anonymize_sql(source)
    for secret in ("Pessoa Real", "real@example.com", "$2b$hash-real", "203.0.113.9", "texto privado", "token-real"):
        assert secret not in result
    assert "fixture-" in result
    assert "@example.invalid" in result
    assert "192.0.2." in result
    assert "VALUES (11, 7, ARRAY['Piloto A','Piloto B'], ARRAY[10,5])" in result


def test_anonymizer_is_deterministic_and_rejects_unknown_format():
    source = "INSERT INTO usuarios (id, nome, email) VALUES (1, 'Nome', 'a@b.com');\n"
    assert MODULE.anonymize_sql(source) == MODULE.anonymize_sql(source)
    try:
        MODULE.anonymize_sql("SELECT 1;\n")
    except ValueError as exc:
        assert "Nenhum INSERT" in str(exc)
    else:
        raise AssertionError("Formato sem INSERT deveria ser recusado")
