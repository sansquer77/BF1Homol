"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ApiRequestError, apiRequest } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";

type Driver = { id: number; name: string; team: string };
type Race = { id: number; name: string; date: string; time: string; type: string; has_result: boolean; positions: Record<string, string>; retirements: string[] };
type Snapshot = { season: string; selected_race_id: number | null; drivers: Driver[]; races: Race[] };
type Processed = { status: string; race_id: number; notifications: { sent: number; failed: number; skipped: number; warning: string | null } };

export function ResultsAdminView() {
  const { season } = useSeason();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [raceId, setRaceId] = useState<number | null>(null);
  const [positions, setPositions] = useState<Record<string, string>>({});
  const [retirements, setRetirements] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectRace = useCallback((id: number | null, data: Snapshot | null) => {
    setRaceId(id); setError("");
    const race = data?.races.find((item) => item.id === id);
    setPositions(race?.positions ?? {}); setRetirements(race?.retirements ?? []);
  }, []);

  const load = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const data = await apiRequest<Snapshot>(`/api/v1/admin/results?season=${season}`);
      setSnapshot(data);
      const preferred = data.selected_race_id ?? data.races[0]?.id ?? null;
      selectRace(preferred, data);
    } catch (reason) {
      setError(reason instanceof ApiRequestError && reason.status === 403 ? "Acesso restrito a Admin ou Master." : "Não foi possível carregar provas e pilotos para o resultado.");
    } finally { setBusy(false); }
  }, [season, selectRace]);

  useEffect(() => { void load(); }, [load]);
  const selectedRace = snapshot?.races.find((item) => item.id === raceId);
  const topTen = useMemo(() => new Set(Object.entries(positions).filter(([position]) => Number(position) <= 10).map(([, driver]) => driver).filter(Boolean)), [positions]);

  function setPosition(position: number, driver: string) {
    setPositions((current) => ({ ...current, [String(position)]: driver }));
  }
  function toggleRetirement(driver: string) {
    setRetirements((current) => current.includes(driver) ? current.filter((item) => item !== driver) : [...current, driver]);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!raceId || !selectedRace) return;
    if (selectedRace.has_result && !window.confirm("Esta prova já possui resultado. Deseja substituir e recalcular toda a temporada?")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<Processed>(`/api/v1/admin/races/${raceId}/result?season=${season}`, { method: "PUT", body: JSON.stringify({ positions, retirements }) });
      const email = result.notifications.warning ?? ` ${result.notifications.sent} notificação(ões) enviada(s).`;
      setNotice(`Resultado salvo e classificação recalculada.${email}`);
      await load();
    } catch (reason) {
      setError(reason instanceof ApiRequestError && reason.status === 422 ? "Confira as posições: é necessário preencher do 1º ao 11º sem repetir pilotos entre os dez primeiros." : "Não foi possível salvar e processar o resultado.");
    } finally { setBusy(false); }
  }

  return <div className="admin-catalog-view results-admin-view">
    <header className="institutional-hero"><p className="eyebrow">Administração · Temporada {season}</p><h1>Resultados das provas.</h1><p>Registre a chegada e os abandonos. Ao salvar, toda a classificação da temporada é recalculada.</p></header>
    {error && <div className="calendar-state calendar-state--error" role="alert">{error}</div>}
    {notice && <div className="bet-notice bet-notice--success" role="status">{notice}</div>}
    {!snapshot ? <div className="calendar-state">Carregando resultados…</div> : snapshot.races.length === 0 || snapshot.drivers.length === 0 ? <div className="calendar-state">Cadastre provas e pilotos ativos antes de lançar resultados.</div> : <form onSubmit={submit}>
      <section className="panel result-race-picker"><label>Prova<select value={raceId ?? ""} onChange={(event) => { setNotice(""); selectRace(Number(event.target.value), snapshot); }}>{snapshot.races.map((race) => <option key={race.id} value={race.id}>{race.name} · {race.type}{race.has_result ? " · resultado cadastrado" : " · pendente"}</option>)}</select></label>{selectedRace && <span className={selectedRace.has_result ? "status-pill status-pill--paid" : "status-pill status-pill--pending"}>{selectedRace.has_result ? "Resultado cadastrado" : "Pendente"}</span>}</section>
      <section className="panel"><div className="panel__heading"><div><p className="eyebrow">Ordem de chegada</p><h2>1º ao 11º colocado</h2></div><small>O 11º alimenta o bônus das apostas</small></div><div className="result-position-grid">{Array.from({ length: 11 }, (_, index) => index + 1).map((position) => <label key={position}><span>{position}º</span><select required value={positions[String(position)] ?? ""} onChange={(event) => setPosition(position, event.target.value)}><option value="">Selecione o piloto</option>{snapshot.drivers.filter((driver) => position === 11 || !topTen.has(driver.name) || positions[String(position)] === driver.name).map((driver) => <option key={driver.id} value={driver.name}>{driver.name} · {driver.team || "Sem equipe"}</option>)}</select></label>)}</div></section>
      <section className="panel result-retirements"><div className="panel__heading"><div><p className="eyebrow">DNF</p><h2>Pilotos que abandonaram</h2></div><small>Um piloto classificado também pode constar como DNF</small></div><div className="result-driver-checks">{snapshot.drivers.map((driver) => <label key={driver.id}><input type="checkbox" checked={retirements.includes(driver.name)} onChange={() => toggleRetirement(driver.name)}/><span><strong>{driver.name}</strong><small>{driver.team || "Sem equipe"}</small></span></label>)}</div></section>
      <div className="result-submit"><button className="primary-action" disabled={busy}>{busy ? "Processando…" : selectedRace?.has_result ? "Atualizar e recalcular" : "Salvar e processar resultado"}</button><p>O salvamento atualiza o resultado legado, os tipos nativos, a pontuação por prova e as notificações.</p></div>
    </form>}
  </div>;
}
