"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import type { ApexOptions } from "apexcharts";
import { apiRequest } from "@/lib/api/client";
import { ParticipantTabs } from "./participant-tabs";

const ApexChart = dynamic(() => import("react-apexcharts"), { ssr: false });
type Series = { season: string; drivers: Record<string, number> };
type Snapshot = { seasons_count: number; best_position: number | null; titles: number; podiums: number; best_points: number | null; series: Series[] };

export function PersonalHistoryView() {
  const [data, setData] = useState<Snapshot>();
  const [error, setError] = useState(false);
  useEffect(() => { apiRequest<Snapshot>("/api/v1/telemetry/history").then(setData).catch(() => setError(true)); }, []);
  const drivers = useMemo(() => [...new Set(data?.series.flatMap((item) => Object.keys(item.drivers)) ?? [])].sort(), [data]);
  const options: ApexOptions = { chart: { stacked: false, toolbar: { show: false }, foreColor: "#8A94A6" }, dataLabels: { enabled: true }, grid: { borderColor: "rgba(255,255,255,.08)" }, xaxis: { categories: drivers, title: { text: "Piloto" } }, yaxis: { min: 0, title: { text: "Total de fichas" } }, legend: { position: "top", horizontalAlign: "right" }, plotOptions: { bar: { columnWidth: "68%", borderRadius: 2 } } };
  const chartSeries = data?.series.map((item) => ({ name: item.season, data: drivers.map((driver) => item.drivers[driver] ?? 0) })) ?? [];

  return <div className="dashboard participant-area">
    <header className="page-header"><div><p className="eyebrow">Telemetria</p><h1>Histórico.</h1><p>Resultados do Hall da Fama e suas escolhas ao longo das temporadas.</p></div></header>
    <ParticipantTabs />
    {error ? <div className="calendar-state calendar-state--error">Não foi possível carregar seu histórico.</div> : null}
    {data ? <>
      <section className="history-metrics"><Metric label="Temporadas" value={data.seasons_count} help="Temporadas registradas no Hall da Fama." /><Metric label="Melhor posição" value={data.best_position ? `${data.best_position}º` : "—"} help="Sua melhor colocação final registrada." /><Metric label="Títulos" value={data.titles} help="Temporadas encerradas em primeiro lugar." /><Metric label="Pódios" value={data.podiums} help="Temporadas encerradas entre os três primeiros." /><Metric label="Maior pontuação" value={data.best_points?.toLocaleString("pt-BR") ?? "—"} help="Maior pontuação final registrada." /></section>
      <section className="panel"><div className="panel__heading"><div><p className="eyebrow">Últimas duas temporadas</p><h2>Apostas em pilotos por temporada</h2></div></div>{data.series.length ? <ApexChart options={options} series={chartSeries} type="bar" height={390} /> : <p className="panel-empty">Ainda não há dados históricos para o gráfico.</p>}</section>
    </> : !error ? <div className="calendar-state">Carregando histórico…</div> : null}
  </div>;
}

function Metric({ label, value, help }: { label:string; value:string|number; help:string }) {
  return <article className="metric-card history-metric"><button type="button" className="metric-help" title={help} aria-label={`${label}: ${help}`}>?</button><p>{label}</p><strong>{value}</strong><small>{help}</small></article>;
}
