"""Controller de regras de negócio do Hall da Fama.

Contém helpers de fonte de dados e consultas para manter a UI enxuta.
"""

from db.db_schema import table_exists


def table_height(total_rows: int, row_height: int = 36, max_height: int = 620) -> int:
    return min(max_height, 42 + (max(total_rows, 1) * row_height))


def resolve_hall_source(conn) -> tuple[str, str]:
    """Define a tabela fonte do Hall da Fama com fallback para legado."""
    c = conn.cursor()
    has_hall = table_exists(conn, "hall_da_fama")
    if has_hall:
        c.execute("SELECT COUNT(*) AS cnt FROM hall_da_fama")
        hall_count = int(c.fetchone()["cnt"] or 0)
        if hall_count > 0:
            return "hall_da_fama", "posicao_final"

    has_legacy = table_exists(conn, "posicoes_participantes")
    if has_legacy:
        c.execute("SELECT COUNT(*) AS cnt FROM posicoes_participantes")
        legacy_count = int(c.fetchone()["cnt"] or 0)
        if legacy_count > 0:
            return "posicoes_participantes", "posicao"

    return "hall_da_fama", "posicao_final"


def hall_queries(source_table: str) -> dict[str, str]:
    if source_table == "posicoes_participantes":
        return {
            "seasons": (
                "SELECT DISTINCT temporada FROM posicoes_participantes "
                "WHERE temporada IS NOT NULL AND trim(cast(temporada as text)) != '' "
                "ORDER BY temporada DESC"
            ),
            "user_pos": (
                "SELECT posicao, pontos "
                "FROM posicoes_participantes "
                "WHERE usuario_id = %s AND temporada = %s "
                "LIMIT 1"
            ),
            "all_user_positions": (
                "SELECT usuario_id, temporada, posicao AS posicao, pontos "
                "FROM posicoes_participantes"
            ),
            "count_seasons": "SELECT COUNT(DISTINCT temporada) AS cnt FROM posicoes_participantes",
            "top_winners": (
                "SELECT u.nome, COUNT(*) as vitorias "
                "FROM posicoes_participantes hf "
                "JOIN usuarios u ON hf.usuario_id = u.id "
                "WHERE hf.posicao = 1 AND LOWER(u.perfil) != 'master' "
                "GROUP BY hf.usuario_id, u.nome "
                "ORDER BY vitorias DESC, u.nome ASC "
                "LIMIT 3"
            ),
            "season_stats": (
                "SELECT COUNT(DISTINCT usuario_id) as participants, "
                "MAX(pontos) as best_points, "
                "AVG(pontos) as avg_points "
                "FROM posicoes_participantes "
                "WHERE temporada = %s"
            ),
            "position_distribution": (
                "SELECT u.nome as nome, pp.posicao as posicao "
                "FROM posicoes_participantes pp "
                "JOIN usuarios u ON pp.usuario_id = u.id "
                "WHERE LOWER(u.perfil) != 'master'"
            ),
        }

    return {
        "seasons": (
            "SELECT DISTINCT temporada FROM hall_da_fama "
            "WHERE temporada IS NOT NULL AND trim(cast(temporada as text)) != '' "
            "ORDER BY temporada DESC"
        ),
        "user_pos": (
            "SELECT posicao_final, pontos "
            "FROM hall_da_fama "
            "WHERE usuario_id = %s AND temporada = %s "
            "LIMIT 1"
        ),
        "all_user_positions": (
            "SELECT usuario_id, temporada, posicao_final AS posicao, pontos "
            "FROM hall_da_fama"
        ),
        "count_seasons": "SELECT COUNT(DISTINCT temporada) AS cnt FROM hall_da_fama",
        "top_winners": (
            "SELECT u.nome, COUNT(*) as vitorias "
            "FROM hall_da_fama hf "
            "JOIN usuarios u ON hf.usuario_id = u.id "
            "WHERE hf.posicao_final = 1 AND LOWER(u.perfil) != 'master' "
            "GROUP BY hf.usuario_id, u.nome "
            "ORDER BY vitorias DESC, u.nome ASC "
            "LIMIT 3"
        ),
        "season_stats": (
            "SELECT COUNT(DISTINCT usuario_id) as participants, "
            "MAX(pontos) as best_points, "
            "AVG(pontos) as avg_points "
            "FROM hall_da_fama "
            "WHERE temporada = %s"
        ),
        "position_distribution": (
            "SELECT u.nome as nome, pp.posicao_final as posicao "
            "FROM hall_da_fama pp "
            "JOIN usuarios u ON pp.usuario_id = u.id "
            "WHERE LOWER(u.perfil) != 'master'"
        ),
    }


__all__ = ["table_height", "resolve_hall_source", "hall_queries"]
