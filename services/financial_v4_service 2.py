"""Financeiro V4: taxa da temporada e situação de pagamento."""
from __future__ import annotations
from typing import Any
from services.access_control import AuthenticatedContext, authorize_context

def _master(context: AuthenticatedContext, season: str) -> None:
    authorize_context(context, frozenset({"master"}), season=season)

def get_financial(context: AuthenticatedContext, season: str) -> dict[str, Any]:
    _master(context, season)
    from db.db_schema import db_connect
    with db_connect() as conn:
        cur=conn.cursor(); cur.execute("SELECT valor_taxa FROM financeiro_config_temporada WHERE temporada=%s",(season,)); fee=cur.fetchone(); cur.execute("""SELECT u.id,u.nome,u.email,COALESCE(f.pago,FALSE) AS pago FROM usuarios u LEFT JOIN financeiro_participantes f ON f.usuario_id=u.id AND f.temporada=%s WHERE LOWER(COALESCE(u.status,'ativo'))='ativo' ORDER BY u.nome""",(season,)); rows=cur.fetchall(); cur.close()
    return {"season":season,"fee":float(fee["valor_taxa"]) if fee else 0.0,"participants":[{"user_id":r["id"],"name":r["nome"],"email":r["email"],"paid":bool(r["pago"])} for r in rows]}

def save_financial(context: AuthenticatedContext, season: str, fee: float, payments: dict[int,bool]) -> None:
    _master(context, season)
    if fee < 0 or len(payments)>500: raise ValueError("Dados financeiros inválidos.")
    from db.db_schema import db_connect
    with db_connect() as conn:
        cur=conn.cursor(); cur.execute("""INSERT INTO financeiro_config_temporada (temporada,valor_taxa,atualizado_em) VALUES (%s,%s,CURRENT_TIMESTAMP) ON CONFLICT(temporada) DO UPDATE SET valor_taxa=EXCLUDED.valor_taxa,atualizado_em=CURRENT_TIMESTAMP""",(season,float(fee)))
        for uid, paid in payments.items(): cur.execute("""INSERT INTO financeiro_participantes (usuario_id,temporada,pago,atualizado_em) VALUES (%s,%s,%s,CURRENT_TIMESTAMP) ON CONFLICT(usuario_id,temporada) DO UPDATE SET pago=EXCLUDED.pago,atualizado_em=CURRENT_TIMESTAMP""",(int(uid),season,1 if paid else 0))
        conn.commit(); cur.close()
