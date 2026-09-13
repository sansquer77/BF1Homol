"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiRequest } from "@/lib/api/client";
import { getOptionalTeamMarkerBackground, setManagedTeamColors } from "@/lib/team-colors";

type TeamPaletteEntry = { id: number; name: string; primary_color: string; secondary_color: string | null; status: string };
type Palette = Map<string, TeamPaletteEntry>;
const TeamPaletteContext = createContext<Palette>(new Map());

export function TeamPaletteProvider({ children }: { children: ReactNode }) {
  const [teams, setTeams] = useState<TeamPaletteEntry[]>([]);
  useEffect(() => {
    let active = true;
    apiRequest<TeamPaletteEntry[]>("/api/v1/teams").then((value) => { if (active) { setManagedTeamColors(value); setTeams(value); } }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  const palette = useMemo(() => new Map(teams.map((team) => [team.name.toLocaleLowerCase("pt-BR"), team])), [teams]);
  return <TeamPaletteContext.Provider value={palette}>{children}</TeamPaletteContext.Provider>;
}

export function useTeamMarkerBackground() {
  const palette = useContext(TeamPaletteContext);
  return useCallback((team?: string | null): string => {
    if (!team) return getOptionalTeamMarkerBackground(team);
    const entry = palette.get(team.toLocaleLowerCase("pt-BR"));
    if (!entry) return getOptionalTeamMarkerBackground(team);
    return entry.secondary_color
      ? `linear-gradient(to bottom, ${entry.primary_color} 0 50%, ${entry.secondary_color} 50% 100%)`
      : entry.primary_color;
  }, [palette]);
}
