"use client";

import dynamic from "next/dynamic";
import type { ApexOptions } from "apexcharts";

export type EvolutionPoint = {
  race_id: number;
  race_name: string;
  points: number;
  cumulative_points: number;
  position?: number | null;
};

function shortRaceName(name: string): string {
  return name.replace(/^Grande Prêmio\s+(?:d(?:a|e|o|as|os)\s+)?/i, "").replace(/^GP\s+(?:d(?:a|e|o|as|os)\s+)?/i, "");
}

const ApexChart = dynamic(() => import("react-apexcharts"), {
  ssr: false,
  loading: () => <div className="chart-skeleton" aria-hidden="true" />,
});

export function AccessibleChart({ points }: { points: EvolutionPoint[] }) {
  const options: ApexOptions = {
    chart: { id: "bf1-evolution", toolbar: { show: false }, zoom: { enabled: false }, fontFamily: "Manrope, sans-serif", foreColor: "#8A94A6" },
    colors: ["#E10600", "#6C98FF"],
    dataLabels: { enabled: false },
    fill: { opacity: [0.72, 1] },
    grid: { borderColor: "rgba(255,255,255,.08)", strokeDashArray: 4, padding: { left: 8, right: 8 } },
    legend: { position: "top", horizontalAlign: "left" },
    markers: { size: [0, 4], hover: { size: 6 } },
    plotOptions: { bar: { borderRadius: 3, columnWidth: "52%" } },
    stroke: { curve: "smooth", width: [0, 3] },
    tooltip: { theme: "dark", x: { show: true }, shared: true },
    xaxis: { categories: points.map((item) => shortRaceName(item.race_name)), axisBorder: { show: false }, axisTicks: { show: false }, labels: { hideOverlappingLabels: true, trim: true } },
    yaxis: [
      { seriesName: "Pontos na prova", min: 0, title: { text: "Pontos" }, labels: { formatter: (value) => `${Math.round(value)} pts` } },
      { seriesName: "Posição", opposite: true, reversed: true, min: 1, forceNiceScale: true, title: { text: "Posição" }, labels: { formatter: (value) => `${Math.round(value)}º` } },
    ],
    responsive: [{ breakpoint: 480, options: { chart: { height: 270 }, xaxis: { labels: { rotate: -35, rotateAlways: true } } } }],
  };
  const description = points.length
    ? `Gráfico combinado de pontuação e posição em ${points.length} provas. A posição usa escala invertida, com o primeiro lugar no topo.`
    : "Ainda não há pontos registrados para esta temporada.";
  const series: ApexOptions["series"] = [
    { name: "Pontos na prova", type: "column", data: points.map((item) => item.points) },
    { name: "Posição", type: "line", data: points.map((item) => item.position ?? null) },
  ];

  return <section className="panel chart-panel" id="analises" aria-labelledby="chart-title"><div className="panel__heading"><div><p className="eyebrow">Performance</p><h2 id="chart-title">Evolução da posição e pontuação</h2></div></div>{points.length ? <><div role="img" aria-label={description}><ApexChart options={options} series={series} type="line" height={310} /></div><details className="chart-data"><summary>Ver dados do gráfico em tabela</summary><div className="table-scroll" tabIndex={0}><table><caption className="sr-only">Pontuação e posição por etapa</caption><thead><tr><th scope="col">Etapa</th><th scope="col">Pontos</th><th scope="col">Posição</th></tr></thead><tbody>{points.map((item) => <tr key={item.race_id}><td>{item.race_name}</td><td>{item.points}</td><td>{item.position ? `${item.position}º` : "—"}</td></tr>)}</tbody></table></div></details></> : <p className="panel-empty">Ainda não há resultados para formar o gráfico.</p>}</section>;
}
