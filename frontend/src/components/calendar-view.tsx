"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { apiRequest, type Race } from "@/lib/api/client";
import { TRACK_ASSETS } from "@/lib/track-assets";

const DEFAULT_SEASON = "2026";

function formatDate(date: string, time: string | null): string {
  const value = new Date(date + "T" + (time ?? "23:59") + ":00-03:00");
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric" }).format(value);
}

function formatTime(date: string, time: string | null): string {
  if (!time) return "Horário a confirmar";
  const value = new Date(date + "T" + time + ":00-03:00");
  return new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", timeZoneName: "short" }).format(value);
}

export function CalendarView() {
  const [races, setRaces] = useState<Race[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    apiRequest<Race[]>(("/api/v1/calendar?season=" + DEFAULT_SEASON) as `/api/v1/${string}`)
      .then((response) => { if (active) setRaces(response); })
      .catch(() => { if (active) setError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const nextRaceId = useMemo(() => {
    const now = Date.now();
    return races.find((race) => new Date(race.date + "T" + (race.time ?? "23:59") + ":00-03:00").getTime() >= now)?.id;
  }, [races]);

  return (
    <div className="calendar-view">
      <header className="institutional-hero calendar-hero">
        <div><p className="eyebrow">Calendário · Temporada {DEFAULT_SEASON}</p><h1>O mapa da temporada.</h1><p>Datas, horários e circuitos de cada largada, convertidos para o fuso de São Paulo.</p></div>
      </header>
      {loading ? <div className="calendar-state" role="status">Carregando provas…</div> : null}
      {error ? <div className="calendar-state calendar-state--error" role="alert">Não foi possível carregar o calendário. Tente novamente após autenticar.</div> : null}
      {!loading && !error && races.length === 0 ? <div className="calendar-state">Nenhuma prova disponível para esta temporada.</div> : null}
      <div className="race-grid">
        {races.map((race, index) => {
          const track = race.circuit_id ? TRACK_ASSETS[race.circuit_id] : undefined;
          return <article className={race.id === nextRaceId ? "race-card race-card--next" : "race-card"} key={race.id}>
            <div className="race-card__art">{track ? <Image src={track.src} alt={"Desenho da pista de " + race.name} fill sizes="(max-width: 760px) 100vw, 280px" /> : <span aria-hidden="true">BF1</span>}</div>
            <div className="race-card__body"><div className="race-card__top"><span className="race-round">R{String(index + 1).padStart(2, "0")}</span><span className={race.type.toLowerCase() === "sprint" ? "race-type race-type--sprint" : "race-type"}>{race.type}</span></div><h2>{race.name.replace("Grande Prêmio", "GP")}</h2><dl><div><dt>Data</dt><dd>{formatDate(race.date, race.time ?? null)}</dd></div><div><dt>Largada</dt><dd>{formatTime(race.date, race.time ?? null)}</dd></div></dl>{race.id === nextRaceId ? <span className="next-badge">Próxima prova</span> : null}</div>
          </article>;
        })}
      </div>
    </div>
  );
}
