"use client";

import dynamic from "next/dynamic";
import type { ApexOptions } from "apexcharts";

const ApexChart = dynamic(() => import("react-apexcharts"), { ssr: false, loading: () => <div className="chart-skeleton" aria-hidden="true" /> });
const points = [{ etapa: "Austrália", pontos: 88 }, { etapa: "China", pontos: 124 }, { etapa: "Japão", pontos: 109 }, { etapa: "Bahrein", pontos: 151 }, { etapa: "Miami", pontos: 173 }, { etapa: "Ímola", pontos: 212 }];
const options: ApexOptions = {
  chart: { id: "bf1-evolution", toolbar: { show: false }, zoom: { enabled: false }, fontFamily: "Manrope, sans-serif", foreColor: "#8A94A6" },
  colors: ["#E10600"], dataLabels: { enabled: false },
  fill: { type: "gradient", gradient: { shadeIntensity: 0, opacityFrom: 0.38, opacityTo: 0.02, stops: [0, 100] } },
  grid: { borderColor: "rgba(255,255,255,.08)", strokeDashArray: 4, padding: { left: 8, right: 8 } },
  markers: { size: 0, hover: { size: 5 } }, stroke: { curve: "smooth", width: 3 }, tooltip: { theme: "dark", x: { show: true } },
  xaxis: { categories: points.map((item) => item.etapa), axisBorder: { show: false }, axisTicks: { show: false }, labels: { hideOverlappingLabels: true, trim: true } },
  yaxis: { min: 0, labels: { formatter: (value) => `${Math.round(value)} pts` } },
  responsive: [{ breakpoint: 480, options: { chart: { height: 245 }, xaxis: { labels: { rotate: -35, rotateAlways: true } } } }],
};

export function AccessibleChart() {
  return <section className="panel chart-panel" id="analises" aria-labelledby="chart-title"><div className="panel__heading"><div><p className="eyebrow">Performance</p><h2 id="chart-title">Evolução na temporada</h2></div><span className="trend">+18,4%</span></div><div role="img" aria-label="Gráfico de área mostrando evolução de 88 pontos na Austrália para 212 pontos em Ímola."><ApexChart options={options} series={[{ name: "Pontos", data: points.map((item) => item.pontos) }]} type="area" height={290} /></div><details className="chart-data"><summary>Ver dados do gráfico em tabela</summary><div className="table-scroll" tabIndex={0}><table><caption className="sr-only">Pontos acumulados por etapa</caption><thead><tr><th scope="col">Etapa</th><th scope="col">Pontos</th></tr></thead><tbody>{points.map((item) => <tr key={item.etapa}><td>{item.etapa}</td><td>{item.pontos}</td></tr>)}</tbody></table></div></details></section>;
}
