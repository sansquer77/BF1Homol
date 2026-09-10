"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { ApiRequestError, apiRequest } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";
import { getOptionalTeamMarkerBackground } from "@/lib/team-colors";

type Driver = { name: string; team: string };
type Race = { id: number; name: string; type: string; date: string; time: string; is_open: boolean; deadline: string | null; deadline_message: string };
type Rules = { total_chips: number; max_chips_per_driver: number; minimum_drivers: number; same_team_allowed: boolean };
type Allocation = { driver: string; chips: number };
type Snapshot = { season: string; races: Race[]; selected_race: Race | null; drivers: Driver[]; rules: Rules; current_bet: { allocations: Allocation[]; eleventh_driver: string; submitted_at: string | null } | null };

export function RaceBetForm() {
  const { season } = useSeason();
  const [data, setData] = useState<Snapshot | null>(null);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [eleventh, setEleventh] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  function applySnapshot(snapshot: Snapshot) {
    setData(snapshot);
    setAllocations(snapshot.current_bet?.allocations ?? []);
    setEleventh(snapshot.current_bet?.eleventh_driver ?? "");
  }
  async function load(raceId?: number) {
    setLoading(true); setNotice(null);
    try {
      const query = new URLSearchParams({ season });
      if (raceId) query.set("race_id", String(raceId));
      applySnapshot(await apiRequest<Snapshot>(`/api/v1/race-bets?${query}`));
    } catch { setNotice({ kind: "error", text: "Não foi possível carregar o formulário de apostas." }); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [season]);

  const used = useMemo(() => new Set(allocations.map((item) => item.driver)), [allocations]);
  const total = allocations.reduce((sum, item) => sum + item.chips, 0);
  const available = data?.drivers.filter((driver) => !used.has(driver.name)) ?? [];
  const eleventhOptions = data?.drivers.filter((driver) => !used.has(driver.name)) ?? [];
  const selectedRace = data?.selected_race;
  const selectedTeams = allocations.map((allocation) => data?.drivers.find((driver) => driver.name === allocation.driver)?.team).filter(Boolean);
  const teamsValid = Boolean(data?.rules.same_team_allowed || new Set(selectedTeams).size === selectedTeams.length);
  const valid = Boolean(selectedRace?.is_open && allocations.length >= (data?.rules.minimum_drivers ?? 1) && total === data?.rules.total_chips && allocations.every((item) => item.chips > 0 && item.chips <= data!.rules.max_chips_per_driver) && teamsValid && eleventh && !used.has(eleventh));

  function addDriver() {
    const driver = available[0];
    if (driver) setAllocations((current) => [...current, { driver: driver.name, chips: 1 }]);
  }
  function update(index: number, patch: Partial<Allocation>) { setAllocations((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item)); }
  function remove(index: number) { setAllocations((current) => current.filter((_, itemIndex) => itemIndex !== index)); }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!selectedRace || !valid) return;
    setSaving(true); setNotice(null);
    try {
      await apiRequest(`/api/v1/race-bets?season=${season}`, { method: "POST", body: JSON.stringify({ race_id: selectedRace.id, allocations, eleventh_driver: eleventh }) });
      setNotice({ kind: "success", text: "Aposta registrada com sucesso. Você pode alterá-la até o prazo da prova." });
      await load(selectedRace.id);
      setNotice({ kind: "success", text: "Aposta registrada com sucesso. Você pode alterá-la até o prazo da prova." });
    } catch (reason) {
      setNotice({ kind: "error", text: reason instanceof ApiRequestError && reason.status === 403 ? "O prazo desta aposta está encerrado." : "A aposta foi recusada. Confira fichas, pilotos e regras da prova." });
    } finally { setSaving(false); }
  }

  return <div className="betting-page"><header className="institutional-hero"><div><p className="eyebrow">Apostas · Temporada {season}</p><h1>Monte sua estratégia.</h1><p>Distribua as fichas entre os pilotos e indique quem termina em 11º.</p></div></header>
    {notice ? <div className={`bet-notice bet-notice--${notice.kind}`} role="alert">{notice.text}</div> : null}
    {loading ? <div className="calendar-state" role="status">Carregando regras e provas…</div> : null}
    {!loading && data ? <form onSubmit={submit} className="bet-layout"><section className="panel bet-main"><div className="panel__heading"><div><p className="eyebrow">Etapa</p><h2>Prova selecionada</h2></div></div><label className="bet-race-select">Prova<select value={selectedRace?.id ?? ""} onChange={(event) => void load(Number(event.target.value))}>{data.races.map((race) => <option key={race.id} value={race.id}>{race.name} · {race.is_open ? "aberta" : "encerrada"}</option>)}</select></label>{selectedRace ? <div className={selectedRace.is_open ? "deadline deadline--open" : "deadline deadline--closed"}><strong>{selectedRace.type}</strong><span>{selectedRace.deadline_message}</span></div> : <p className="panel-empty">Nenhuma prova cadastrada nesta temporada.</p>}
      <div className="bet-section-heading"><div><p className="eyebrow">Distribuição</p><h2>Pilotos e fichas</h2></div><button className="secondary-action" type="button" onClick={addDriver} disabled={!available.length || !selectedRace?.is_open}>Adicionar piloto</button></div>
      <div className="bet-allocations">{allocations.map((allocation, index) => { const driver = data.drivers.find((item) => item.name === allocation.driver); return <div className="bet-allocation" key={`${allocation.driver}-${index}`}><span className="team-marker" style={{ background: getOptionalTeamMarkerBackground(driver?.team) }} aria-hidden="true" /><label>Piloto<select value={allocation.driver} onChange={(event) => update(index, { driver: event.target.value })} disabled={!selectedRace?.is_open}><option value={allocation.driver}>{allocation.driver}</option>{available.map((item) => <option key={item.name} value={item.name}>{item.name} · {item.team}</option>)}</select></label><label>Fichas<input type="number" min="1" max={data.rules.max_chips_per_driver} value={allocation.chips} onChange={(event) => update(index, { chips: Number(event.target.value) })} disabled={!selectedRace?.is_open} /></label><button type="button" className="table-action" onClick={() => remove(index)} disabled={!selectedRace?.is_open} aria-label={`Remover ${allocation.driver}`}>Remover</button></div>; })}</div>
      <label className="bet-eleventh">Palpite para o 11º colocado<select required value={eleventh} onChange={(event) => setEleventh(event.target.value)} disabled={!selectedRace?.is_open}><option value="">Selecione um piloto…</option>{eleventhOptions.map((driver) => <option key={driver.name} value={driver.name}>{driver.name} · {driver.team}</option>)}</select></label>
      <button className="primary-action bet-submit" type="submit" disabled={!valid || saving}>{saving ? "Registrando…" : data.current_bet ? "Atualizar minha aposta" : "Registrar minha aposta"}</button></section>
      <aside className="panel bet-summary"><p className="eyebrow">Regras vigentes</p><h2>Conferência</h2><dl><div><dt>Fichas distribuídas</dt><dd className={total === data.rules.total_chips ? "rule-ok" : ""}>{total}/{data.rules.total_chips}</dd></div><div><dt>Mínimo de pilotos</dt><dd className={allocations.length >= data.rules.minimum_drivers ? "rule-ok" : ""}>{allocations.length}/{data.rules.minimum_drivers}</dd></div><div><dt>Máximo por piloto</dt><dd>{data.rules.max_chips_per_driver}</dd></div><div><dt>Mesma equipe</dt><dd>{data.rules.same_team_allowed ? "Permitida" : "Não permitida"}</dd></div></dl>{data.current_bet ? <p className="bet-saved">Aposta já registrada para esta prova. Um novo envio substituirá a aposta vigente e manterá o log.</p> : null}</aside></form> : null}
  </div>;
}
