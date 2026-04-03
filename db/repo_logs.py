"""Repositório focado em logs de aposta e acesso."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from db.db_schema import db_connect, get_table_columns

logger = logging.getLogger(__name__)


def registrar_log_aposta(
	usuario_id: int,
	prova_id: int,
	apostador: str,
	pilotos: str,
	aposta: str,
	nome_prova: str,
	piloto_11: str,
	tipo_aposta: int,
	automatica: int,
	horario,
	ip_address: Optional[str] = None,
	temporada: Optional[str] = None,
	status: str = "Registrada",
) -> None:
	try:
		horario_dt = horario if isinstance(horario, datetime) else None
		if horario_dt is None:
			try:
				horario_dt = pd.to_datetime(horario, errors="coerce").to_pydatetime() if horario is not None else None
			except Exception:
				horario_dt = None
		if horario_dt is None:
			logger.error(
				"registrar_log_aposta ignorado: horario ausente/invalido para usuario_id=%s prova_id=%s",
				usuario_id,
				prova_id,
			)
			return

		data_txt = horario_dt.strftime("%Y-%m-%d")

		with db_connect() as conn:
			cur = conn.cursor()
			cols = get_table_columns(conn, "log_apostas")
			if not cols:
				cur.close()
				return
			cur.execute(
				"""
				INSERT INTO log_apostas
					(usuario_id, prova_id, apostador, aposta, nome_prova,
					 pilotos, piloto_11, tipo_aposta, automatica, data, horario,
					 ip_address, temporada, status)
				VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
				""",
				(
					usuario_id,
					prova_id,
					apostador,
					aposta,
					nome_prova,
					pilotos,
					piloto_11,
					tipo_aposta,
					automatica,
					data_txt,
					horario_dt,
					ip_address,
					temporada,
					status,
				),
			)
			cur.close()
			conn.commit()
	except Exception as exc:
		logger.debug("registrar_log_aposta falhou: %s", exc)


def log_aposta_existe(usuario_id: int, prova_id: int, temporada: Optional[str] = None) -> bool:
	with db_connect() as conn:
		cur = conn.cursor()
		if temporada:
			cur.execute(
				"SELECT 1 FROM log_apostas WHERE usuario_id=%s AND prova_id=%s AND temporada=%s LIMIT 1",
				(usuario_id, prova_id, temporada),
			)
		else:
			cur.execute(
				"SELECT 1 FROM log_apostas WHERE usuario_id=%s AND prova_id=%s LIMIT 1",
				(usuario_id, prova_id),
			)
		exists = cur.fetchone() is not None
		cur.close()
		return exists

__all__ = ["registrar_log_aposta", "log_aposta_existe"]
