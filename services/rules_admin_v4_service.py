"""Gestão V4 das regras, preservando o contrato PostgreSQL legado."""
from __future__ import annotations
from typing import Any
from services.access_control import AuthenticatedContext, authorize_context

RULE_FIELDS = ("nome_regra","quantidade_fichas","fichas_por_piloto","mesma_equipe","descarte","pontos_pole","pontos_vr","pontos_posicoes","pontos_11_colocado","regra_sprint","pontos_sprint_pole","pontos_sprint_vr","pontos_sprint_posicoes","pontos_dobrada","bonus_vencedor","bonus_podio_completo","bonus_podio_qualquer","qtd_minima_pilotos","penalidade_abandono","pontos_penalidade","penalidade_auto_percent","pontos_campeao","pontos_vice","pontos_equipe")
def _master(context: AuthenticatedContext, season: str|None=None): authorize_context(context,frozenset({"master"}),season=season)
def list_rules(context: AuthenticatedContext) -> list[dict[str,Any]]:
 _master(context)
 from db.db_schema import db_connect
 with db_connect() as conn:
  c=conn.cursor(); c.execute("SELECT * FROM regras ORDER BY id"); rows=c.fetchall(); cols=[d[0] for d in c.description]; c.close()
 return [dict(r) if hasattr(r, "keys") else dict(zip(cols,r)) for r in rows]
def save_rule(context: AuthenticatedContext, rule_id: int|None, fields: dict[str,Any]) -> None:
 _master(context); clean={k:fields[k] for k in RULE_FIELDS if k in fields}; name=str(clean.get("nome_regra","")).strip()
 if not name or int(clean.get("quantidade_fichas",0))<1 or int(clean.get("fichas_por_piloto",0))<1 or int(clean.get("qtd_minima_pilotos",0))<1: raise ValueError("Parâmetros básicos da regra inválidos.")
 for key in ("pontos_posicoes","pontos_sprint_posicoes"):
  if not isinstance(clean.get(key),list) or not clean[key]: raise ValueError("Tabelas de pontuação são obrigatórias.")
 import json
 from db.db_schema import db_connect
 with db_connect() as conn:
  c=conn.cursor(); values=[json.dumps(clean[x]) if x in ("pontos_posicoes","pontos_sprint_posicoes") else (int(clean[x]) if x in ("mesma_equipe","descarte","regra_sprint","pontos_dobrada","penalidade_abandono") else clean[x]) for x in RULE_FIELDS]
  if rule_id is None: c.execute(f"INSERT INTO regras ({','.join(RULE_FIELDS)}) VALUES ({','.join(['%s']*len(RULE_FIELDS))})",values)
  else: c.execute(f"UPDATE regras SET {','.join(x+'=%s' for x in RULE_FIELDS)} WHERE id=%s",values+[int(rule_id)])
  conn.commit(); c.close()
 from utils.cache_utils import clear_data_cache
 clear_data_cache("regras","classificacao")

def assign_rule(context: AuthenticatedContext, season: str, rule_id: int) -> None:
 _master(context,season)
 from db.db_schema import db_connect
 with db_connect() as conn:
  c=conn.cursor(); c.execute("SELECT 1 FROM regras WHERE id=%s",(rule_id,))
  if c.fetchone() is None: raise ValueError("Regra não encontrada.")
  c.execute("INSERT INTO temporadas_regras (temporada,regra_id) VALUES (%s,%s) ON CONFLICT (temporada) DO UPDATE SET regra_id=EXCLUDED.regra_id",(season,rule_id)); conn.commit(); c.close()
 from utils.cache_utils import clear_data_cache
 clear_data_cache("regras","classificacao")

def clone_rule(context: AuthenticatedContext, rule_id: int, name: str) -> None:
 _master(context)
 name=str(name).strip()
 if not name: raise ValueError("Nome da cópia é obrigatório.")
 from db.db_schema import db_connect
 import json
 with db_connect() as conn:
  c=conn.cursor(); c.execute("SELECT * FROM regras WHERE id=%s",(rule_id,)); row=c.fetchone()
  if not row: raise ValueError("Regra não encontrada.")
  cols=[d[0] for d in c.description]; data=dict(row) if hasattr(row,"keys") else dict(zip(cols,row)); data["nome_regra"]=name
  fields=[x for x in RULE_FIELDS]; vals=[json.dumps(data[x]) if x in ("pontos_posicoes","pontos_sprint_posicoes") and isinstance(data[x],list) else data[x] for x in fields]
  c.execute(f"INSERT INTO regras ({','.join(fields)}) VALUES ({','.join(['%s']*len(fields))})",vals); conn.commit(); c.close()
