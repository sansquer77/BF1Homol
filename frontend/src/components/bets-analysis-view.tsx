"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import type { ApexOptions } from "apexcharts";
import { apiRequest, type BetsAnalysis } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";
import { getOptionalTeamMarkerBackground } from "@/lib/team-colors";

const ApexChart = dynamic(() => import("react-apexcharts"), { ssr: false, loading: () => <div className="chart-skeleton" aria-hidden="true" /> });

export function BetsAnalysisView() {
  const { season } = useSeason();
  const [data, setData] = useState<BetsAnalysis | null>(null);
  const [participantId, setParticipantId] = useState("");
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true; setData(null); setError(false);
    const query = new URLSearchParams({ season }); if (participantId) query.set("participant_id", participantId);
    apiRequest<BetsAnalysis>(`/api/v1/analysis/bets?${query}`).then((value) => { if (active) setData(value); }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [season, participantId]);
  const chartRows = useMemo(() => data?.by_driver.slice(0, 12) ?? [], [data]);
  const options: ApexOptions = { chart: { id: "bets-by-driver", toolbar: { show: false }, foreColor: "#8A94A6" }, colors: ["#E10600"], dataLabels: { enabled: false }, grid: { borderColor: "rgba(255,255,255,.08)" }, plotOptions: { bar: { borderRadius: 3, horizontal: chartRows.length > 8 } }, xaxis: { categories: chartRows.map((row) => row.driver) } };
  return <div className="analysis-view">
    <header className="institutional-hero"><div><p className="eyebrow">Análise de Apostas · {season}</p><h1>Onde estão as fichas?</h1><p>Distribuição real das escolhas da temporada, respeitando o escopo do seu perfil.</p></div></header>
    {data?.participants.length ? <label className="analysis-participant-filter">Participante<select value={participantId} onChange={(event) => setParticipantId(event.target.value)}><option value="">Todos os participantes</option>{data.participants.map((participant) => <option value={participant.id} key={participant.id}>{participant.name}</option>)}</select></label> : null}
    {error ? <div className="calendar-state calendar-state--error" role="alert">Não foi possível carregar a análise de apostas.</div> : null}{!data && !error ? <div className="calendar-state" role="status">Analisando apostas…</div> : null}
    {data ? <><section className="metric-grid" aria-label="Resumo da análise"><article className="metric-card"><p>Apostas analisadas</p><strong>{data.bet_count}</strong><small>{data.scope === "individual" ? "Participante selecionado" : "Todos os participantes autorizados"}</small></article><article className="metric-card"><p>Provas cadastradas</p><strong>{data.race_count}</strong><small>Temporada {data.season}</small></article><article className="metric-card"><p>Resultados disponíveis</p><strong>{data.result_count}</strong><small>Provas aptas para comparação</small></article></section>
    {data.by_driver.length ? <div className="analysis-grid"><section className="panel"><div className="panel__heading"><div><p className="eyebrow">Seleções</p><h2>Apostas por piloto</h2></div></div><div role="img" aria-label={`Gráfico com apostas distribuídas entre ${data.by_driver.length} pilotos.`}><ApexChart options={options} series={[{ name: "Apostas", data: chartRows.map((row) => row.bets) }]} type="bar" height={330} /></div></section><section className="panel"><div className="panel__heading"><h2>Pilotos escolhidos</h2></div><div className="table-scroll" tabIndex={0}><table className="analysis-table"><caption className="sr-only">Distribuição de apostas e fichas por piloto</caption><thead><tr><th>Piloto</th><th>Apostas</th><th>Fichas</th></tr></thead><tbody>{data.by_driver.map((row) => <tr key={row.driver}><td><span className="driver-with-team"><i style={{ background: getOptionalTeamMarkerBackground(row.team) }} aria-hidden="true" />{row.driver}<small>{row.team ?? "Equipe não informada"}</small></span></td><td>{row.bets}</td><td>{row.chips}</td></tr>)}</tbody></table></div></section><section className="panel analysis-grid__wide"><div className="panel__heading"><h2>Apostas para o 11º lugar</h2></div>{data.eleventh.length ? <div className="table-scroll"><table className="analysis-table"><thead><tr><th>Piloto</th><th>Total</th></tr></thead><tbody>{data.eleventh.map((row) => <tr key={row.driver}><td>{row.driver}</td><td>{row.bets}</td></tr>)}</tbody></table></div> : <p className="panel-empty">Nenhuma aposta de 11º lugar registrada.</p>}</section></div> : <div className="calendar-state">Ainda não há apostas cadastradas para análise.</div>}</> : null}
  </div>;
}
