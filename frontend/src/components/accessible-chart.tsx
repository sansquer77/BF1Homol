"use client";

import dynamic from "next/dynamic";
import type { ApexOptions } from "apexcharts";

export type EvolutionPoint = { race_id: number; race_name: string; cumulative_points: number };

const ApexChart = dynamic(() => import("react-apexcharts"), { ssr: false, loading: () => <div className="chart-skeleton" aria-hidden="true" /> });

export function AccessibleChart({ points }: { points: EvolutionPoint[] }) {
  const options: ApexOptions = {
    chart: { id: "bf1-evolution", toolbar: { show: false }, zoom: { enabled: false }, fontFamily: "Manrope, sans-serif", foreColor: "#8A94A6" },
    colors: ["#E10600"], dataLabels: { enabled: false },
    fill: { type: "gradient", gradient: { shadeIntensity: 0, opacityFrom: 0.38, opacityTo: 0.02, stops: [0, 100] } },
    grid: { borderColor: "rgba(255,255,255,.08)", strokeDashArray: 4, padding: { left: 8, right: 8 } },
    markers: { size: 0, hover: { size: 5 } }, stroke: { curve: "smooth", width: 3 }, tooltip: { theme: "dark", x: { show: true } },
    xaxis: { categories: points.map((item) => item.race_name), axisBorder: { show: false }, axisTicks: { show: false }, labels: { hideOverlappingLabels: true, trim: true } },
    yaxis: { min: 0, labels: { formatter: (value) => `${Math.round(value)} pts` } },
    responsive: [{ breakpoint: 480, options: { chart: { height: 245 }, xaxis: { labels: { rotate: -35, rotateAlways: true } } } }],
  };
  const first = points[0]?.cumulative_points ?? 0;
  const last = points.at(-1)?.cumulative_points ?? 0;
  const trend = first ? ((last - first) / Math.abs(first)) * 100 : null;
  const description = points.length ? `Gráfico de área com a pontuação acumulada em ${points.length} provas, terminando em ${last} pontos.` : "Ainda não há pontos registrados para esta temporada.";

  return <section className="panel chart-panel" id="analises" aria-labelledby="chart-title"><div className="panel__heading"><div><p className="eyebrow">Performance</p><h2 id="chart-title">Evolução na temporada</h2></div>{trend !== null ? <span className="trend">{trend >= 0 ? "+" : ""}{trend.toFixed(1).replace(".", ",")}%</span> : null}</div>{points.length ? <><div role="img" aria-label={description}><ApexChart options={options} series={[{ name: "Pontos acumulados", data: points.map((item) => item.cumulative_points) }]} type="area" height={290} /></div><details className="chart-data"><summary>Ver dados do gráfico em tabela</summary><div className="table-scroll" tabIndex={0}><table><caption className="sr-only">Pontos acumulados por etapa</caption><thead><tr><th scope="col">Etapa</th><th scope="col">Pontos</th></tr></thead><tbody>{points.map((item) => <tr key={item.race_id}><td>{item.race_name}</td><td>{item.cumulative_points}</td></tr>)}</tbody></table></div></details></> : <p className="panel-empty">Ainda não há resultados para formar o gráfico.</p>}</section>;
}
