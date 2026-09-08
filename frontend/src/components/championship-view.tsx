"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiRequest, type Championship, type ChampionshipBetRecord } from "@/lib/api/client";
import { getOptionalTeamMarkerBackground } from "@/lib/team-colors";

const CURRENT_YEAR = new Date().getFullYear();
const years = Array.from({ length: CURRENT_YEAR - 1999 }, (_, index) => CURRENT_YEAR - index);

export function ChampionshipView() {
  const [season, setSeason] = useState(CURRENT_YEAR);
  const [data, setData] = useState<Championship | null>(null);
  const [form, setForm] = useState({ champion: "", vice: "", team: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function load(value: number) {
    setLoading(true); setError(""); setNotice("");
    apiRequest<Championship>(`/api/v1/championship?season=${value}`).then((snapshot) => {
      setData(snapshot);
      setForm({ champion: snapshot.current_bet?.champion ?? snapshot.drivers[0] ?? "", vice: snapshot.current_bet?.vice ?? snapshot.drivers[1] ?? snapshot.drivers[0] ?? "", team: snapshot.current_bet?.team ?? snapshot.teams[0] ?? "" });
    }).catch(() => { setData(null); setError("Não foi possível carregar o módulo de Campeonato."); }).finally(() => setLoading(false));
  }
  useEffect(() => { load(season); }, [season]);

  function submit(event: FormEvent) {
    event.preventDefault(); if (!data) return;
    setSaving(true); setError(""); setNotice("");
    apiRequest<ChampionshipBetRecord>(`/api/v1/championship/bet?season=${season}`, { method: "POST", body: JSON.stringify(form) })
      .then(() => { setNotice("Aposta de campeonato salva com sucesso."); load(season); })
      .catch(() => setError("Não foi possível salvar. Confira o prazo e se campeão e vice são diferentes."))
      .finally(() => setSaving(false));
  }

  return <div className="championship-view"><header className="championship-hero"><div><p className="eyebrow">Palpite de temporada</p><h1>Campeonato.</h1><p>Escolha o campeão, o vice e a equipe campeã de construtores.</p></div><label className="f1-season">Temporada<select value={season} onChange={(event) => setSeason(Number(event.target.value))}>{years.map((year) => <option key={year} value={year}>{year}</option>)}</select></label></header>
    {error ? <div className="calendar-state calendar-state--error" role="alert">{error}</div> : null}{notice ? <div className="calendar-state calendar-state--success" role="status">{notice}</div> : null}{loading ? <div className="calendar-state" role="status">Carregando campeonato…</div> : null}
    {data && !loading ? <><section className="championship-layout"><section className="panel"><div className="panel__heading"><div><p className="eyebrow">Sua aposta</p><h2>{data.current_bet ? "Aposta atual" : "Faça seu palpite"}</h2></div></div><div className={data.can_bet ? "deadline deadline--open" : "deadline deadline--closed"}>{data.deadline_message}{data.deadline ? <small>Data limite: {new Date(data.deadline).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })}</small> : null}</div><form className="championship-form" onSubmit={submit}><label>Piloto campeão<select value={form.champion} onChange={(event) => setForm({ ...form, champion: event.target.value })} disabled={!data.can_bet || saving}>{data.drivers.map((driver) => <option key={driver}>{driver}</option>)}</select></label><label>Piloto vice-campeão<select value={form.vice} onChange={(event) => setForm({ ...form, vice: event.target.value })} disabled={!data.can_bet || saving}>{data.drivers.map((driver) => <option key={driver}>{driver}</option>)}</select></label><label>Equipe campeã<select value={form.team} onChange={(event) => setForm({ ...form, team: event.target.value })} disabled={!data.can_bet || saving}>{data.teams.map((team) => <option key={team}>{team}</option>)}</select></label><button className="primary-action" type="submit" disabled={!data.can_bet || saving}>{saving ? "Salvando…" : "Salvar aposta"}</button></form></section><section className="panel"><div className="panel__heading"><div><p className="eyebrow">Registro</p><h2>Sua aposta atual</h2></div></div>{data.current_bet ? <BetCard record={data.current_bet} /> : <p className="panel-empty">Nenhuma aposta registrada para esta temporada.</p>}<h3 className="subheading">Histórico de alterações</h3><BetTable rows={data.history} /></section></section>{data.official_result ? <section className="panel championship-result"><div className="panel__heading"><div><p className="eyebrow">Resultado oficial</p><h2>Campeonato {season}</h2></div></div><BetCard record={{ ...data.official_result, season: data.official_result.season }} /></section> : null}{data.all_bets.length ? <section className="panel championship-all"><div className="panel__heading"><div><p className="eyebrow">Administração</p><h2>Todas as apostas</h2></div><small>{data.all_bets.length} participantes</small></div><BetTable rows={data.all_bets} showUser /></section> : null}</> : null}
  </div>;
}

function BetCard({ record }: { record: ChampionshipBetRecord }) { return <div className="bet-card"><div><span>Campeão</span><strong>{record.champion}</strong></div><div><span>Vice</span><strong>{record.vice}</strong></div><div><span>Equipe</span><strong><i style={{ background: getOptionalTeamMarkerBackground(record.team) }} aria-hidden="true" />{record.team}</strong></div>{record.bet_time ? <small>Registrada em {record.bet_time}</small> : null}</div>; }
function BetTable({ rows, showUser = false }: { rows: ChampionshipBetRecord[]; showUser?: boolean }) { return rows.length ? <div className="table-scroll" tabIndex={0}><table className="championship-table"><thead><tr>{showUser ? <th>Participante</th> : null}<th>Campeão</th><th>Vice</th><th>Equipe</th><th>Registro</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.user_nome ?? "self"}-${row.bet_time ?? index}`}>{showUser ? <td>{row.user_nome ?? "—"}</td> : null}<td>{row.champion}</td><td>{row.vice}</td><td>{row.team}</td><td>{row.bet_time ?? "—"}</td></tr>)}</tbody></table></div> : <p className="panel-empty">Nenhuma alteração registrada.</p>; }
