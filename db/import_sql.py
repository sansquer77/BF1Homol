"""Importador SQL para PostgreSQL.

Mantido para compatibilidade de chamadas antigas.
"""

from pathlib import Path

from db.db_utils import db_connect


def import_sql_file(sql_file_path, target_path=None):
    """Importa arquivo SQL no banco PostgreSQL configurado.

    Args:
        sql_file_path: Caminho do arquivo .sql
        target_path: Ignorado (compatibilidade legada)

    Returns:
        tuple: (success: bool, message: str, stats: dict)
    """
    _ = target_path

    try:
        sql_content = Path(sql_file_path).read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"❌ Erro ao ler SQL: {exc}", {}

    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    stats = {
        "total_statements": len(statements),
        "successful": 0,
        "failed": 0,
        "errors": [],
    }

    try:
        with db_connect() as conn:
            c = conn.cursor()
            for statement in statements:
                try:
                    c.execute(statement)
                    stats["successful"] += 1
                except Exception as exc:
                    stats["failed"] += 1
                    stats["errors"].append(f"{str(exc)[:160]} | SQL: {statement[:120]}")
            conn.commit()

        return (
            True,
            f"✅ Importação concluída: {stats['successful']} comandos executados, {stats['failed']} erros",
            stats,
        )
    except Exception as exc:
        return False, f"❌ Erro ao importar SQL: {exc}", stats


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        success, msg, stats = import_sql_file(sys.argv[1])
        print(msg)
        if stats.get("errors"):
            print("\nErros encontrados:")
            for err in stats["errors"][:10]:
                print(err)
