"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import type { ApexOptions } from "apexcharts";
import { apiRequest, type HallOfFame } from "@/lib/api/client";

const ApexChart = dynamic(() => import("react-apexcharts"), { ssr: false, loading: () => <div className="chart-skeleton" aria-hidden="true" /> });
const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

export function HallOfFameView() {
  const [data, setData] = useState<HallOfFame | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    apiRequest<HallOfFame>("/api/v1/hall-of-fame")
      .then((value) => { if (active) setData(value); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);

  const chartData = useMemo(() => (data?.distribution ?? []).map((row) => ({
    participant: row.participant,
    first: row.positions.find((item) => item.position === 1)?.count ?? 0,
    second: row.positions.find((item) => item.position === 2)?.count ?? 0,
    third: row.positions.find((item) => item.position === 3)?.count ?? 0,
  })).filter((row) => row.first + row.second + row.third > 0), [data]);
  const chartOptions: ApexOptions = {
    chart: { id: "hall-podiums", stacked: true, toolbar: { show: false }, foreColor: "#8A94A6", fontFamily: "Manrope, sans-serif" },
    colors: ["#E1B84B", "#A8B0BC", "#A76C3B"], dataLabels: { enabled: false },
    plotOptions: { bar: { horizontal: true, borderRadius: 2 } },
    xaxis: { categories: chartData.map((row) => row.participant), title: { text: "Pódios" } },
    grid: { borderColor: "rgba(255,255,255,.08)" }, legend: { position: "top" },
  };

  return <div className="hall-view"><header className="institutional-hero"><div><p className="eyebrow">Hall da Fama</p><h1>Histórias escritas em pontos.</h1><p>Campeões, pódios e classificações preservados temporada após temporada.</p></div></header>{error ? <div className="calendar-state calendar-state--error" role="alert">Não foi possível carregar o Hall da Fama.</div> : null}{!data && !error ? <div className="calendar-state" role="status">Carregando história…</div> : null}{data && !data.entries.length ? <div className="calendar-state">Nenhuma classificação histórica registrada.</div> : null}{data?.entries.length ? <><section className="hall-winners" aria-label="Maiores vencedores">{data.top_winners.map((winner, index) => <article className="winner-card" key={winner.participant}><span>{index === 0 ? "Maior vencedor" : `${index + 1}º em títulos`}</span><strong>{winner.participant}</strong><small>{winner.wins} {winner.wins === 1 ? "título" : "títulos"}</small></article>)}</section><section className="hall-seasons"><div className="panel__heading"><div><p className="eyebrow">Linha do tempo</p><h2>Campeões por temporada</h2></div></div><div className="champion-grid">{data.season_stats.filter((season) => season.champion).map((season) => <article className="champion-card" key={season.season}><span>{season.season}</span><strong>{season.champion?.participant}</strong><small>{number.format(season.champion?.points ?? 0)} pontos · {season.participants} participantes</small></article>)}</div></section><div className="hall-detail-grid"><section className="panel"><div className="panel__heading"><div><p className="eyebrow">Pódios</p><h2>Distribuição histórica</h2></div></div>{chartData.length ? <div role="img" aria-label="Gráfico empilhado com primeiros, segundos e terceiros lugares por participante."><ApexChart options={chartOptions} series={[{ name: "1º", data: chartData.map((row) => row.first) }, { name: "2º", data: chartData.map((row) => row.second) }, { name: "3º", data: chartData.map((row) => row.third) }]} type="bar" height={Math.max(320, chartData.length * 38)} /></div> : <p className="panel-empty">Ainda não há pódios para representar.</p>}</section><section className="panel"><div className="panel__heading"><div><p className="eyebrow">Temporadas</p><h2>Resumo histórico</h2></div></div><div className="table-scroll" tabIndex={0}><table className="analysis-table"><caption className="sr-only">Resumo estatístico das temporadas</caption><thead><tr><th>Temporada</th><th>Participantes</th><th>Maior pontuação</th><th>Média</th></tr></thead><tbody>{data.season_stats.map((season) => <tr key={season.season}><td>{season.season}</td><td>{season.participants}</td><td>{season.best_points == null ? "—" : number.format(season.best_points)}</td><td>{season.average_points == null ? "—" : number.format(season.average_points)}</td></tr>)}</tbody></table></div></section></div></> : null}</div>;
}
