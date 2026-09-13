export const TEAM_COLORS = {
  Ferrari: ["#DC0000"],
  McLaren: ["#FF8700"],
  "Red Bull Racing": ["#0A1B40"],
  Mercedes: ["#00A39A"],
  "Aston Martin": ["#005F41"],
  Alpine: ["#005BA9", "#FF80BD"],
  Williams: ["#1868DB"],
  "RB (VCARB)": ["#6C98FF"],
  "Kick Sauber": ["#01C00E"],
  Haas: ["#9C9FA2", "#EB0A1E"],
} as const;

export type TeamName = keyof typeof TEAM_COLORS;

type ManagedTeamColor = { name: string; primary_color: string; secondary_color: string | null };
let managedColors = new Map<string, readonly string[]>();

export function setManagedTeamColors(teams: ManagedTeamColor[]): void {
  managedColors = new Map(teams.map((team) => [team.name.toLocaleLowerCase("pt-BR"), [team.primary_color, ...(team.secondary_color ? [team.secondary_color] : [])]]));
}

export function getTeamMarkerBackground(team: TeamName): string {
  const colors: readonly string[] = TEAM_COLORS[team];
  return colors.length === 1
    ? colors[0]
    : `linear-gradient(to bottom, ${colors[0]} 0 50%, ${colors[1]} 50% 100%)`;
}

export function getOptionalTeamMarkerBackground(team?: string | null): string {
  if (!team) return "#687284";
  const managed = managedColors.get(team.toLocaleLowerCase("pt-BR"));
  if (managed) return managed.length === 1 ? managed[0] : `linear-gradient(to bottom, ${managed[0]} 0 50%, ${managed[1]} 50% 100%)`;
  if (!(team in TEAM_COLORS)) return "#687284";
  return getTeamMarkerBackground(team as TeamName);
}
