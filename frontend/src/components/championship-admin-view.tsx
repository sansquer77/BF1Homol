"use client";

import dynamic from "next/dynamic";
import { FormEvent, useEffect, useMemo, useState } from "react";
import type { ApexOptions } from "apexcharts";
import { ApiRequestError, apiRequest } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";
import { useTimezone } from "@/lib/timezone-context";

const ApexChart = dynamic(() => import("react-apexcharts"), { ssr: false, loading: () => <div className="chart-skeleton" aria-hidden="true" /> });
type Bet = { user_id: number; user_nome: string; champion: string; vice: string; team: string; season: string | number; bet_time: string | null };
type Distribution = { label: string; count: number };
type OfficialResult = { season: string; champion: string; vice: string; team: string };
type Snapshot = {
  season: string; eligible_count: number; bet_count: number; pending_count: number; completion_percent: number;
  pending: { user_id: number; name: string }[]; bets: Bet[]; history: Bet[];
  champion_distribution: Distribution[]; vice_distribution: Distribution[]; team_distribution: Distribution[];
  official_result: OfficialResult | null; drivers: string[]; teams: string[];
  can_bet: boolean; deadline_message: string; deadline: string | null;
};

export function ChampionshipAdminView() {
  const { season } = useSeason();
  const { formatDateTime } = useTimezone();
  const formatTimestamp = useFormatTimestamp();
  const [data, setData] = useState<Snapshot | null>(null);
  const [form, setForm] = useState({ champion: "", vice: "", team: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const snapshot = await apiRequest<Snapshot>(`/api/v1/championship/admin?season=${season}`);
      setData(snapshot);
      setForm({ champion: snapshot.official_result?.champion ?? snapshot.drivers[0] ?? "", vice: snapshot.official_result?.vice ?? snapshot.drivers[1] ?? "", team: snapshot.official_result?.team ?? snapshot.teams[0] ?? "" });
    } catch (error) {
      setData(null);
      setNotice({ kind: "error", text: error instanceof ApiRequestError && error.status === 403 ? "Acesso restrito a Admin ou Master." : "Não foi possível carregar as apostas do campeonato." });
    } finally { setLoading(false); }
  }
  useEffect(() => { setNotice(null); void load(); }, [season]);

  async function saveResult(event: FormEvent) {
    event.preventDefault();
    if (!form.champion || !form.vice || !form.team || form.champion === form.vice) {
      setNotice({ kind: "error", text: "Selecione campeão e vice diferentes e a equipe campeã." }); return;
    }
    setSaving(true); setNotice(null);
    try {
      await apiRequest(`/api/v1/championship/result?season=${season}`, { method: "POST", body: JSON.stringify(form) });
      await load();
      setNotice({ kind: "success", text: "Resultado oficial salvo e classificação invalidada para recálculo." });
    } catch { setNotice({ kind: "error", text: "Não foi possível salvar o resultado oficial." }); }
    finally { setSaving(false); }
  }

  const latestChangeByUser = useMemo(() => {
    const counts = new Map<number, number>();
    for (const row of data?.history ?? []) counts.set(row.user_id, (counts.get(row.user_id) ?? 0) + 1);
    return counts;
  }, [data]);

  return <div className="championship-admin-view admin-catalog-view">
    <header className="institutional-hero"><div><p className="eyebrow">Administração · {season}</p><h1>Apostas do campeonato.</h1><p>Acompanhe adesão, escolhas, alterações e o resultado oficial da temporada.</p></div></header>
    {notice ? <div className={`bet-notice bet-notice--${notice.kind}`} role="alert">{notice.text}</div> : null}
    {loading ? <div className="calendar-state" role="status">Consolidando apostas…</div> : null}
    {data && !loading ? <>
      <section className="championship-admin-metrics" aria-label="Resumo das apostas"><article><span>Elegíveis</span><strong>{data.eligible_count}</strong><small>Participantes ativos</small></article><article><span>Apostaram</span><strong>{data.bet_count}</strong><small>{data.completion_percent.toLocaleString("pt-BR", { minimumFractionDigits: 1 })}% de adesão</small></article><article><span>Pendentes</span><strong>{data.pending_count}</strong><small>{data.can_bet ? "Prazo ainda aberto" : "Prazo encerrado"}</small></article><article><span>Alterações</span><strong>{data.history.length}</strong><small>Registros auditáveis</small></article></section>
      <div className={data.can_bet ? "deadline deadline--open" : "deadline deadline--closed"}><strong>{data.can_bet ? "Apostas abertas" : "Apostas encerradas"}</strong><span>{data.deadline_message}</span>{data.deadline ? <small>{formatDateTime(data.deadline)}</small> : null}</div>
      <section className="championship-admin-charts"><DistributionChart title="Palpites de campeão" rows={data.champion_distribution} /><DistributionChart title="Palpites de vice" rows={data.vice_distribution} /><DistributionChart title="Equipes campeãs" rows={data.team_distribution} /></section>
      <section className="panel championship-admin-list"><div className="panel__heading"><div><p className="eyebrow">Acompanhamento</p><h2>Apostas vigentes</h2></div><small>{data.bets.length} registros</small></div>{data.bets.length ? <div className="table-scroll" tabIndex={0}><table className="championship-table"><thead><tr><th>Participante</th><th>Campeão</th><th>Vice</th><th>Equipe</th><th>Atualizada em</th><th>Versões</th></tr></thead><tbody>{data.bets.map((row) => <tr key={row.user_id}><td>{row.user_nome}</td><td>{row.champion}</td><td>{row.vice}</td><td>{row.team}</td><td>{formatTimestamp(row.bet_time)}</td><td>{latestChangeByUser.get(row.user_id) ?? 1}</td></tr>)}</tbody></table></div> : <p className="panel-empty">Nenhuma aposta registrada.</p>}</section>
      <div className="championship-admin-lower"><section className="panel"><div className="panel__heading"><div><p className="eyebrow">Pendências</p><h2>Ainda não apostaram</h2></div></div>{data.pending.length ? <ul className="championship-pending-list">{data.pending.map((item) => <li key={item.user_id}>{item.name}</li>)}</ul> : <p className="panel-empty">Todos os participantes elegíveis já apostaram.</p>}</section><section className="panel"><div className="panel__heading"><div><p className="eyebrow">Gestão</p><h2>Resultado oficial</h2></div></div><form className="championship-result-form" onSubmit={saveResult}><label>Campeão<select value={form.champion} onChange={(event) => setForm({ ...form, champion: event.target.value })}>{data.drivers.map((driver) => <option key={driver}>{driver}</option>)}</select></label><label>Vice<select value={form.vice} onChange={(event) => setForm({ ...form, vice: event.target.value })}>{data.drivers.map((driver) => <option key={driver}>{driver}</option>)}</select></label><label>Equipe campeã<select value={form.team} onChange={(event) => setForm({ ...form, team: event.target.value })}>{data.teams.map((team) => <option key={team}>{team}</option>)}</select></label><button className="primary-action" type="submit" disabled={saving || !data.drivers.length || !data.teams.length}>{saving ? "Salvando…" : data.official_result ? "Atualizar resultado" : "Salvar resultado"}</button></form></section></div>
      <section className="panel championship-admin-history"><details><summary>Histórico completo de alterações ({data.history.length})</summary>{data.history.length ? <div className="table-scroll" tabIndex={0}><table className="championship-table"><thead><tr><th>Participante</th><th>Campeão</th><th>Vice</th><th>Equipe</th><th>Registro</th></tr></thead><tbody>{data.history.map((row, index) => <tr key={`${row.user_id}-${row.bet_time}-${index}`}><td>{row.user_nome}</td><td>{row.champion}</td><td>{row.vice}</td><td>{row.team}</td><td>{formatTimestamp(row.bet_time)}</td></tr>)}</tbody></table></div> : <p className="panel-empty">Sem alterações registradas.</p>}</details></section>
    </> : null}
  </div>;
}

function useFormatTimestamp() {
  const { formatDateTime } = useTimezone();
  return (value: string | null) => {
    if (!value) return "—";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : formatDateTime(parsed);
  };
}
function DistributionChart({ title, rows }: { title: string; rows: Distribution[] }) {
  const shown = rows.slice(0, 8);
  const options: ApexOptions = { chart: { toolbar: { show: false }, foreColor: "#8A94A6" }, colors: ["#E10600"], dataLabels: { enabled: true }, grid: { borderColor: "rgba(255,255,255,.08)" }, plotOptions: { bar: { horizontal: true, borderRadius: 3 } }, xaxis: { categories: shown.map((row) => row.label), min: 0, tickAmount: Math.max(1, Math.min(5, ...shown.map((row) => row.count))) } };
  return <section className="panel"><div className="panel__heading"><h2>{title}</h2></div>{shown.length ? <ApexChart options={options} series={[{ name: "Apostas", data: shown.map((row) => row.count) }]} type="bar" height={Math.max(240, shown.length * 34)} /> : <p className="panel-empty">Sem apostas para consolidar.</p>}</section>;
}
