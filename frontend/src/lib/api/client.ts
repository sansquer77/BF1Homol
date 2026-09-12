import type { components } from "./schema";

export type User = components["schemas"]["UserResponse"];
export type LoginPayload = components["schemas"]["LoginRequest"];
export type About = components["schemas"]["AboutResponse"];
export type Race = components["schemas"]["RaceResponse"];
export type Telemetry = components["schemas"]["TelemetryResponse"];
export type Classification = components["schemas"]["ClassificationResponse"];
export type BetsAnalysis = components["schemas"]["BetsAnalysisResponse"];
export type HallOfFame = components["schemas"]["HallOfFameResponse"];
export type BettingLogs = components["schemas"]["BettingLogsResponse"];
export type AccessLogs = components["schemas"]["AccessLogsResponse"];
export type F1Dashboard = components["schemas"]["F1DashboardResponse"];
export type Championship = components["schemas"]["ChampionshipResponse"];
export type ChampionshipBetRecord = components["schemas"]["ChampionshipBetRecord"];
export type ParticipantOption = components["schemas"]["AdminParticipant"];
export type ApiError = { detail?: string; request_id?: string };

const CSRF_COOKIE = "bf1_csrf";

function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie.split("; ").find((item) => item.startsWith(prefix))?.slice(prefix.length);
}

export class ApiRequestError extends Error {
  constructor(public readonly status: number, public readonly requestId?: string) {
    super(status === 401 ? "Sua sessão expirou. Entre novamente." : "Não foi possível concluir a solicitação.");
  }
}

export async function apiRequest<T>(path: `/api/v1/${string}`, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  // JSON payloads are serialized strings; File/Blob uploads must preserve their
  // binary media type instead of being mislabeled as application/json.
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }
  const response = await fetch(path, { ...init, method, headers, credentials: "include", cache: "no-store" });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as Partial<ApiError>;
    throw new ApiRequestError(response.status, body.request_id ?? response.headers.get("X-Request-ID") ?? undefined);
  }
  return response.json() as Promise<T>;
}

export function login(payload: LoginPayload): Promise<User> {
  return apiRequest<User>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(payload) });
}
