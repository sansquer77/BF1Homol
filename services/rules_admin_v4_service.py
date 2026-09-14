"""Gestão V4 das regras, preservando o contrato PostgreSQL legado."""
from __future__ import annotations

import json
from typing import Any

from services.access_control import AuthenticatedContext, authorize_context

RULE_FIELDS = (
    "nome_regra", "quantidade_fichas", "fichas_por_piloto", "mesma_equipe", "descarte",
    "pontos_pole", "pontos_vr", "pontos_posicoes", "pontos_11_colocado", "regra_sprint",
    "pontos_sprint_pole", "pontos_sprint_vr", "pontos_sprint_posicoes", "pontos_dobrada",
    "bonus_vencedor", "bonus_podio_completo", "bonus_podio_qualquer", "qtd_minima_pilotos",
    "penalidade_abandono", "pontos_penalidade", "penalidade_auto_percent",
    "pontos_campeao", "pontos_vice", "pontos_equipe",
)
BOOLEAN_FIELDS = {"mesma_equipe", "descarte", "regra_sprint", "pontos_dobrada", "penalidade_abandono"}
POSITION_FIELDS = {"pontos_posicoes", "pontos_sprint_posicoes"}


def _master(context: AuthenticatedContext, season: str | None = None) -> None:
    authorize_context(context, frozenset({"master"}), season=season)


def _decode_rule(row: Any, columns: list[str]) -> dict[str, Any]:
    data = dict(row) if hasattr(row, "keys") else dict(zip(columns, row))
    for field in POSITION_FIELDS:
        value = data.get(field)
        if isinstance(value, str):
            try:
                data[field] = json.loads(value)
            except (TypeError, ValueError):
                data[field] = []
        elif not isinstance(value, list):
            data[field] = list(value or [])
    for field in BOOLEAN_FIELDS:
        data[field] = bool(data.get(field))
    return data


def _validated_fields(fields: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in RULE_FIELDS if field not in fields]
    if missing:
        raise ValueError(f"Campo obrigatório ausente: {missing[0]}.")
    clean = {field: fields[field] for field in RULE_FIELDS}
    clean["nome_regra"] = str(clean["nome_regra"]).strip()
    if not clean["nome_regra"]:
        raise ValueError("Nome da regra é obrigatório.")
    for field in POSITION_FIELDS:
        if not isinstance(clean[field], list) or not clean[field] or len(clean[field]) > 20:
            raise ValueError("Tabelas de pontuação devem conter entre 1 e 20 posições.")
        clean[field] = [int(value) for value in clean[field]]
        if any(value < 0 for value in clean[field]):
            raise ValueError("Pontos por posição não podem ser negativos.")
    if int(clean["fichas_por_piloto"]) > int(clean["quantidade_fichas"]):
        raise ValueError("Máximo por piloto não pode superar a quantidade total de fichas.")
    return clean


def list_rules(context: AuthenticatedContext) -> list[dict[str, Any]]:
    _master(context)
    from db.db_schema import db_connect
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM regras ORDER BY id")
        rows, columns = cursor.fetchall(), [description[0] for description in cursor.description]
        cursor.execute("SELECT temporada, regra_id FROM temporadas_regras ORDER BY temporada")
        assignments = cursor.fetchall()
        cursor.close()
    seasons_by_rule: dict[int, list[str]] = {}
    for item in assignments:
        assignment = dict(item) if hasattr(item, "keys") else {"temporada": item[0], "regra_id": item[1]}
        seasons_by_rule.setdefault(int(assignment["regra_id"]), []).append(str(assignment["temporada"]))
    decoded = [_decode_rule(row, columns) for row in rows]
    for rule in decoded:
        rule["temporadas"] = seasons_by_rule.get(int(rule["id"]), [])
    return decoded


def save_rule(context: AuthenticatedContext, rule_id: int | None, fields: dict[str, Any]) -> None:
    _master(context)
    clean = _validated_fields(fields)
    from db.db_schema import db_connect
    values = [json.dumps(clean[f]) if f in POSITION_FIELDS else int(clean[f]) if f in BOOLEAN_FIELDS else clean[f] for f in RULE_FIELDS]
    with db_connect() as conn:
        cursor = conn.cursor()
        if rule_id is None:
            cursor.execute(f"INSERT INTO regras ({','.join(RULE_FIELDS)}) VALUES ({','.join(['%s'] * len(RULE_FIELDS))})", values)
        else:
            cursor.execute(f"UPDATE regras SET {','.join(f + '=%s' for f in RULE_FIELDS)} WHERE id=%s", values + [int(rule_id)])
            if cursor.rowcount != 1:
                raise ValueError("Regra não encontrada.")
        conn.commit()
        cursor.close()
    _clear_rule_caches()


def assign_rule(context: AuthenticatedContext, season: str, rule_id: int) -> None:
    _master(context, season)
    from db.db_schema import db_connect
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM regras WHERE id=%s", (rule_id,))
        if cursor.fetchone() is None:
            raise ValueError("Regra não encontrada.")
        cursor.execute("INSERT INTO temporadas_regras (temporada,regra_id) VALUES (%s,%s) ON CONFLICT (temporada) DO UPDATE SET regra_id=EXCLUDED.regra_id", (season, rule_id))
        conn.commit()
        cursor.close()
    _clear_rule_caches()


def clone_rule(context: AuthenticatedContext, rule_id: int, name: str) -> None:
    _master(context)
    name = str(name).strip()
    if not name:
        raise ValueError("Nome da cópia é obrigatório.")
    from db.db_schema import db_connect
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM regras WHERE id=%s", (rule_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Regra não encontrada.")
        data = _decode_rule(row, [description[0] for description in cursor.description])
        data["nome_regra"] = name
        values = [json.dumps(data[f]) if f in POSITION_FIELDS else data[f] for f in RULE_FIELDS]
        cursor.execute(f"INSERT INTO regras ({','.join(RULE_FIELDS)}) VALUES ({','.join(['%s'] * len(RULE_FIELDS))})", values)
        conn.commit()
        cursor.close()
    _clear_rule_caches()


def delete_rule(context: AuthenticatedContext, rule_id: int) -> None:
    _master(context)
    from db.db_schema import db_connect
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM temporadas_regras WHERE regra_id=%s", (rule_id,))
        count = cursor.fetchone()
        in_use = int(count["count"] if hasattr(count, "keys") else count[0])
        if in_use:
            raise ValueError("A regra está associada a uma temporada e não pode ser excluída.")
        cursor.execute("DELETE FROM regras WHERE id=%s", (rule_id,))
        if cursor.rowcount != 1:
            raise ValueError("Regra não encontrada.")
        conn.commit()
        cursor.close()
    _clear_rule_caches()


def save_position_points(context: AuthenticatedContext, season: str, race_type: str, points: list[int]) -> dict[str, Any]:
    """Atualiza a tabela e isola a temporada quando a regra é compartilhada."""
    _master(context, season)
    if race_type not in {"Normal", "Sprint"}:
        raise ValueError("Tipo de prova inválido.")
    if not points or len(points) > 20 or any(int(value) < 0 for value in points):
        raise ValueError("Informe entre 1 e 20 pontuações válidas.")
    padded = [int(value) for value in points] + [0] * (20 - len(points))
    target = "pontos_sprint_posicoes" if race_type == "Sprint" else "pontos_posicoes"
    from db.db_schema import db_connect
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT r.* FROM regras r JOIN temporadas_regras tr ON tr.regra_id=r.id WHERE tr.temporada=%s FOR UPDATE", (season,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("A temporada não possui regra associada.")
        data = _decode_rule(row, [description[0] for description in cursor.description])
        cursor.execute("SELECT COUNT(*) AS count FROM temporadas_regras WHERE regra_id=%s", (data["id"],))
        count = cursor.fetchone()
        shared = int(count["count"] if hasattr(count, "keys") else count[0]) > 1
        rule_id, cloned = int(data["id"]), False
        if shared:
            data["nome_regra"] = f"{data['nome_regra']} - {season}"
            values = [json.dumps(data[f]) if f in POSITION_FIELDS else data[f] for f in RULE_FIELDS]
            cursor.execute(f"INSERT INTO regras ({','.join(RULE_FIELDS)}) VALUES ({','.join(['%s'] * len(RULE_FIELDS))}) RETURNING id", values)
            inserted = cursor.fetchone()
            rule_id = int(inserted["id"] if hasattr(inserted, "keys") else inserted[0])
            cursor.execute("UPDATE temporadas_regras SET regra_id=%s WHERE temporada=%s", (rule_id, season))
            cloned = True
        cursor.execute(f"UPDATE regras SET {target}=%s WHERE id=%s", (json.dumps(padded), rule_id))
        conn.commit()
        cursor.close()
    _clear_rule_caches()
    return {"status": "ok", "rule_id": rule_id, "cloned": cloned}


def recalculate_season(context: AuthenticatedContext, season: str) -> None:
    _master(context, season)
    from services.bets_scoring import atualizar_classificacoes_todas_as_provas
    atualizar_classificacoes_todas_as_provas(temporada=season)
    _clear_rule_caches()


def _clear_rule_caches() -> None:
    from utils.cache_utils import clear_data_cache
    clear_data_cache("regras", "classificacao")


__all__ = ["assign_rule", "clone_rule", "delete_rule", "list_rules", "recalculate_season", "save_position_points", "save_rule"]
