"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiRequest } from "@/lib/api/client";

type SeasonContextValue = { season: string; seasons: string[]; setSeason: (value: string) => void };
const SeasonContext = createContext<SeasonContextValue | null>(null);
const fallback = String(new Date().getFullYear());

export function SeasonProvider({ children }: { children: ReactNode }) {
  const [seasons, setSeasons] = useState<string[]>([fallback]);
  const [season, setSeasonState] = useState(fallback);
  useEffect(() => {
    apiRequest<string[]>("/api/v1/calendar/seasons").then((available) => {
      if (!available.length) return;
      setSeasons(available);
      const saved = window.localStorage.getItem("bf1-season");
      setSeasonState(saved && available.includes(saved) ? saved : available[0]);
    }).catch(() => undefined);
  }, []);
  const setSeason = (value: string) => { setSeasonState(value); window.localStorage.setItem("bf1-season", value); };
  const value = useMemo(() => ({ season, seasons, setSeason }), [season, seasons]);
  return <SeasonContext.Provider value={value}>{children}</SeasonContext.Provider>;
}

export function useSeason() {
  const value = useContext(SeasonContext);
  if (!value) throw new Error("useSeason requer SeasonProvider");
  return value;
}

export function SeasonSelector() {
  const { season, seasons, setSeason } = useSeason();
  return <label className="global-season"><span>Temporada</span><select value={season} onChange={(event) => setSeason(event.target.value)}>{seasons.map((item) => <option key={item}>{item}</option>)}</select></label>;
}
