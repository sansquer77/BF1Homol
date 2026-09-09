"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { AccessibleChart } from "./accessible-chart";
import { CalendarIcon, FlagIcon, TrophyIcon } from "./icons";
import { apiRequest, type Telemetry } from "@/lib/api/client";
import { TRACK_ASSETS } from "@/lib/track-assets";
import { useSeason } from "@/lib/season-context";

function formatPoints(value: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(value);
}

function formatRaceDate(date: string, time: string): string {
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" }).format(new Date(`${date}T${time}:00-03:00`));
}

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "BF";
}

function countdown(target?: string): { days: string; hours: string; minutes: string; label: string } {
  const remaining = target ? Math.max(0, new Date(target).getTime() - Date.now()) : 0;
  const days = Math.floor(remaining / 86_400_000);
  const hours = Math.floor((remaining % 86_400_000) / 3_600_000);
  const minutes = Math.floor((remaining % 3_600_000) / 60_000);
  return { days: String(days).padStart(2, "0"), hours: String(hours).padStart(2, "0"), minutes: String(minutes).padStart(2, "0"), label: `Faltam ${days} dias, ${hours} horas e ${minutes} minutos` };
}

export function DashboardOverview() {
  const { season } = useSeason();
  const [data, setData] = useState<Telemetry | null>(null);
  const [error, setError] = useState(false);
  const [clock, setClock] = useState(0);

  useEffect(() => {
    let active = true;
    setData(null); setError(false);
    apiRequest<Telemetry>(("/api/v1/telemetry?season=" + season) as `/api/v1/${string}`)
      .then((snapshot) => { if (active) setData(snapshot); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [season]);

  useEffect(() => {
    if (!data?.next_race) return;
    const timer = window.setInterval(() => setClock((value) => value + 1), 60_000);
    return () => window.clearInterval(timer);
  }, [data?.next_race]);

  const remaining = useMemo(() => countdown(data?.next_race?.starts_at), [data?.next_race?.starts_at, clock]);
  const nextRace = data?.next_race;
  const track = nextRace?.circuit_id ? TRACK_ASSETS[nextRace.circuit_id] : undefined;

  if (error) return <div className="dashboard"><div className="calendar-state calendar-state--error" role="alert">Não foi possível carregar a Telemetria. Confirme sua autenticação e tente novamente.</div></div>;
  if (!data) return <div className="dashboard"><div className="calendar-state" role="status">Carregando Telemetria…</div></div>;

  return <div className="dashboard">
    <header className="page-header"><div><p className="eyebrow">Telemetria · Olá, {data.user_name}</p><h1>A corrida começa antes da largada.</h1><p>{nextRace ? `Acompanhe sua estratégia para ${nextRace.name}.` : "Acompanhe seu desempenho na temporada."}</p></div><div className="season-select" aria-label={`Temporada selecionada: ${data.season}`}><span>Temporada</span><strong>{data.season}</strong></div></header>
    {nextRace ? <section className="race-hero" id="calendario" aria-labelledby="next-race-title"><div className="race-hero__glow" aria-hidden="true" /><div className="race-hero__content"><p className="eyebrow"><span className="live-dot" /> Próxima prova · Rodada {nextRace.round}</p><h2 id="next-race-title">{nextRace.name.replace("Grande Prêmio", "GP")}</h2><div className="race-meta"><span><CalendarIcon /> {formatRaceDate(nextRace.date, nextRace.time)}</span><span><FlagIcon /> {nextRace.circuit_id?.replaceAll("_", " ") ?? "Circuito não informado"}</span></div><div className="countdown" aria-label={remaining.label}><span><strong>{remaining.days}</strong><small>dias</small></span><i>:</i><span><strong>{remaining.hours}</strong><small>horas</small></span><i>:</i><span><strong>{remaining.minutes}</strong><small>min</small></span></div><a className="primary-action" href="/apostas">Fazer minha aposta <span aria-hidden="true">→</span></a></div><div className="track-art">{track ? <Image src={track.src} alt={`Circuito de ${nextRace.name}`} fill sizes="(max-width: 760px) 100vw, 42vw" /> : <FlagIcon />}<small>{nextRace.name}</small></div></section> : <section className="calendar-state"><strong>Nenhuma próxima prova cadastrada.</strong><p>O calendário da temporada não possui evento futuro disponível.</p></section>}
    <section className="metric-grid" aria-label="Resumo da temporada"><article className="metric-card"><span className="metric-icon"><TrophyIcon /></span><p>Sua posição registrada</p><strong>{data.metrics.current_position ? `${data.metrics.current_position}º` : "—"}</strong><small>Última prova com classificação</small></article><article className="metric-card"><span className="metric-icon"><FlagIcon /></span><p>Pontuação acumulada</p><strong>{formatPoints(data.metrics.points)}</strong><small>Pontos materializados na temporada</small></article><article className="metric-card"><span className="metric-icon"><CalendarIcon /></span><p>Apostas na temporada</p><strong>{data.metrics.bets_submitted}/{data.metrics.races_total}</strong><small>Provas com aposta registrada</small></article></section>
    <div className="content-grid"><AccessibleChart points={data.evolution} /><section className="panel ranking-panel" id="classificacao" aria-labelledby="ranking-title"><div className="panel__heading"><div><p className="eyebrow">Campeonato</p><h2 id="ranking-title">Classificação resumida</h2></div></div>{data.ranking.length ? <ol className="ranking-list">{data.ranking.map((person) => <li key={`${person.position}-${person.name}`} className={person.is_current_user ? "ranking-row ranking-row--current" : "ranking-row"}><strong className="position">{person.position}</strong><span className="avatar avatar--small">{initials(person.name)}</span><span className="driver"><strong>{person.name}</strong><small>{person.is_current_user ? "Você" : "Participante"}</small></span><span className="points"><strong>{formatPoints(person.points)}</strong><small>pts</small></span></li>)}</ol> : <p className="panel-empty">Ainda não há classificação registrada.</p>}</section></div>
    <footer className="prototype-note"><span>BF1 4.0</span><p>Dados da temporada carregados pela API segura</p></footer>
  </div>;
}
