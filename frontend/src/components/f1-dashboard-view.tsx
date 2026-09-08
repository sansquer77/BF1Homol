"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import type { ApexOptions } from "apexcharts";
import { apiRequest, type F1Dashboard } from "@/lib/api/client";
import { getOptionalTeamMarkerBackground } from "@/lib/team-colors";

const ApexChart = dynamic(() => import("react-apexcharts"), { ssr: false, loading: () => <div className="chart-skeleton" aria-hidden="true" /> });
const CURRENT_YEAR = new Date().getFullYear();
const years = Array.from({ length: CURRENT_YEAR - 1949 }, (_, index) => CURRENT_YEAR - index);
const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const SERIES_COLORS = ["#E10600", "#FF8700", "#6C98FF", "#00A39A", "#DC0000", "#1868DB", "#FF80BD", "#01C00E", "#A8B0BC", "#E1B84B"];

export function F1DashboardView() {
  const [season, setSeason] = useState(CURRENT_YEAR);
  const [data, setData] = useState<F1Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(false);
    apiRequest<F1Dashboard>(`/api/v1/f1-dashboard?season=${season}`)
      .then((value) => { if (active) setData(value); })
      .catch(() => { if (active) { setData(null); setError(true); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [season]);

  const topDrivers = useMemo(() => (data?.driver_standings ?? []).slice(0, 10).map((item) => item.driver), [data]);
  const progressionOptions: ApexOptions = {
    chart: { id: "f1-points-progression", toolbar: { show: false }, zoom: { enabled: false }, foreColor: "#8A94A6", fontFamily: "Manrope, sans-serif" },
    colors: SERIES_COLORS, dataLabels: { enabled: false }, stroke: { curve: "smooth", width: 2 }, markers: { size: 0 },
    grid: { borderColor: "rgba(255,255,255,.08)" }, legend: { position: "top", horizontalAlign: "left" },
    xaxis: { categories: (data?.progression ?? []).map((point) => point.race), labels: { hideOverlappingLabels: true, trim: true } },
    yaxis: { min: 0, labels: { formatter: (value) => `${Math.round(value)} pts` } },
    responsive: [{ breakpoint: 600, options: { chart: { height: 330 }, legend: { position: "bottom" }, xaxis: { labels: { rotate: -40, rotateAlways: true } } } }],
  };
  const progressionSeries = topDrivers.map((driver) => ({ name: driver, data: (data?.progression ?? []).map((point) => point.points[driver] ?? 0) }));
  const delta = data?.qualifying_vs_race ?? [];
  const deltaOptions: ApexOptions = {
    chart: { id: "f1-grid-delta", toolbar: { show: false }, foreColor: "#8A94A6", fontFamily: "Manrope, sans-serif" },
    colors: ["#E10600"], dataLabels: { enabled: false }, plotOptions: { bar: { horizontal: true, borderRadius: 2 } },
    grid: { borderColor: "rgba(255,255,255,.08)" }, xaxis: { categories: delta.map((item) => item.driver), title: { text: "Posições ganhas ou perdidas" } },
    responsive: [{ breakpoint: 600, options: { chart: { height: Math.max(360, delta.length * 28) } } }],
  };

  return <div className="f1-view"><header className="f1-hero"><div><p className="eyebrow">Mundial de Fórmula 1</p><h1>Dashboard F1.</h1><p>Classificação, evolução e dados da última prova em uma leitura única.</p></div><label className="f1-season">Temporada<select value={season} onChange={(event) => setSeason(Number(event.target.value))}>{years.map((year) => <option key={year} value={year}>{year}</option>)}</select><small>{season === CURRENT_YEAR ? "Temporada atual" : "Histórico"}</small></label></header>
    {error ? <div className="calendar-state calendar-state--error" role="alert">Não foi possível consultar os dados oficiais desta temporada.</div> : null}
    {loading ? <div className="calendar-state" role="status">Carregando estatísticas da Fórmula 1…</div> : null}
    {data && !loading ? <>
      <section className="f1-leaders" aria-label="Líderes da temporada"><Leader title="Líder dos pilotos" name={data.driver_standings[0]?.driver} detail={data.driver_standings[0] ? `${number.format(data.driver_standings[0].points)} pontos · ${data.driver_standings[0].constructor}` : undefined} /><Leader title="Líder dos construtores" name={data.constructor_standings[0]?.constructor} detail={data.constructor_standings[0] ? `${number.format(data.constructor_standings[0].points)} pontos · ${data.constructor_standings[0].wins} vitórias` : undefined} /><Leader title="Volta mais rápida" name={data.fastest_laps[0]?.driver} detail={data.fastest_laps[0]?.time} /></section>
      <div className="f1-grid"><section className="panel f1-grid__wide"><div className="panel__heading"><div><p className="eyebrow">Campeonato</p><h2>Progressão de pontos</h2></div><small>Top 10 da classificação</small></div>{progressionSeries.length && data.progression.length ? <><div role="img" aria-label={`Progressão acumulada dos ${topDrivers.length} primeiros pilotos em ${data.progression.length} provas.`}><ApexChart options={progressionOptions} series={progressionSeries} type="line" height={390} /></div><ChartTable data={data} drivers={topDrivers} /></> : <Empty text="Nenhuma corrida realizada nesta temporada." />}</section>
        <Standings title="Campeonato de pilotos" rows={data.driver_standings.map((item) => ({ key: item.driver, position: item.position, name: item.driver, team: item.constructor, points: item.points, wins: item.wins }))} />
        <Standings title="Campeonato de construtores" rows={data.constructor_standings.map((item) => ({ key: item.constructor, position: item.position, name: item.constructor, team: item.nationality, points: item.points, wins: item.wins }))} />
        <section className="panel"><div className="panel__heading"><div><p className="eyebrow">Última prova</p><h2>Classificação × corrida</h2></div></div>{delta.length ? <div role="img" aria-label="Diferença entre posição de largada e chegada na última prova."><ApexChart options={deltaOptions} series={[{ name: "Delta", data: delta.map((item) => item.delta) }]} type="bar" height={Math.max(360, delta.length * 26)} /></div> : <Empty text="Comparação ainda indisponível." />}</section>
        <section className="panel"><div className="panel__heading"><div><p className="eyebrow">Última prova</p><h2>Voltas mais rápidas</h2></div></div><SimpleTable headers={["Piloto", "Tempo"]} rows={data.fastest_laps.map((item) => [item.driver, item.time])} empty="Voltas rápidas indisponíveis." /></section>
        <section className="panel"><div className="panel__heading"><div><p className="eyebrow">Última prova</p><h2>Pit stops</h2></div>{data.average_stops != null ? <small>Média: {number.format(data.average_stops)} por piloto</small> : null}</div><SimpleTable headers={["Piloto", "Volta", "Parada", "Tempo"]} rows={data.pit_stops.map((item) => [item.driver, item.lap, item.stop, item.time])} empty={season < 2011 ? "Pit stops disponíveis a partir de 2011." : "Pit stops indisponíveis."} /></section>
      </div>
      <p className="f1-source">Dados oficiais consultados pela integração histórica da aplicação. Algumas temporadas antigas podem ter informações incompletas.</p>
    </> : null}
  </div>;
}

function Leader({ title, name, detail }: { title: string; name?: string; detail?: string }) { return <article className="f1-leader"><span>{title}</span><strong>{name ?? "Indisponível"}</strong><small>{detail ?? "Sem dados para esta temporada"}</small></article>; }
function Empty({ text }: { text: string }) { return <p className="panel-empty">{text}</p>; }

function Standings({ title, rows }: { title: string; rows: { key: string; position: number; name: string; team: string; points: number; wins: number }[] }) {
  return <section className="panel"><div className="panel__heading"><div><p className="eyebrow">Classificação</p><h2>{title}</h2></div></div>{rows.length ? <div className="table-scroll" tabIndex={0}><table className="f1-table"><caption className="sr-only">{title}</caption><thead><tr><th>Pos.</th><th>Competidor</th><th>Pontos</th><th>Vitórias</th></tr></thead><tbody>{rows.map((row) => <tr key={row.key}><td>{row.position}</td><td><span className="driver-with-team">{getOptionalTeamMarkerBackground(row.team) ? <i style={{ background: getOptionalTeamMarkerBackground(row.team) }} aria-hidden="true" /> : null}<strong>{row.name}</strong><small>{row.team}</small></span></td><td>{number.format(row.points)}</td><td>{row.wins}</td></tr>)}</tbody></table></div> : <Empty text="Classificação indisponível." />}</section>;
}

function SimpleTable({ headers, rows, empty }: { headers: string[]; rows: (string | number)[][]; empty: string }) { return rows.length ? <div className="table-scroll" tabIndex={0}><table className="f1-table"><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row[0]}-${index}`}>{row.map((value, column) => <td key={`${column}-${value}`}>{value}</td>)}</tr>)}</tbody></table></div> : <Empty text={empty} />; }

function ChartTable({ data, drivers }: { data: F1Dashboard; drivers: string[] }) { return <details><summary>Ver dados do gráfico em tabela</summary><div className="table-scroll" tabIndex={0}><table className="f1-table"><caption className="sr-only">Pontuação acumulada por prova</caption><thead><tr><th>Prova</th>{drivers.map((driver) => <th key={driver}>{driver}</th>)}</tr></thead><tbody>{data.progression.map((point) => <tr key={point.round}><td>{point.race}</td>{drivers.map((driver) => <td key={driver}>{number.format(point.points[driver] ?? 0)}</td>)}</tr>)}</tbody></table></div></details>; }
