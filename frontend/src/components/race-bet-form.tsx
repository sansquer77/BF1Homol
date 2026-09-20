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

function normalizeDriverQuery(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("pt-BR").replace(/\s+/g, " ");
}

function resolveDriverName(value: string, drivers: Driver[]) {
  const query = normalizeDriverQuery(value);
  if (!query) return "";
  const exact = drivers.filter((driver) => normalizeDriverQuery(driver.name) === query);
  if (exact.length === 1) return exact[0].name;
  const byToken = drivers.filter((driver) => normalizeDriverQuery(driver.name).split(" ").includes(query));
  return byToken.length === 1 ? byToken[0].name : value;
}

export function RaceBetForm() {
  const { season } = useSeason();
  const [data, setData] = useState<Snapshot | null>(null);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [eleventh, setEleventh] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
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

  const canonicalAllocations = useMemo(() => allocations.map((item) => ({ ...item, driver: resolveDriverName(item.driver, data?.drivers ?? []) })), [allocations, data?.drivers]);
  const used = useMemo(() => new Set(canonicalAllocations.map((item) => item.driver).filter((name) => data?.drivers.some((driver) => driver.name === name))), [canonicalAllocations, data?.drivers]);
  const total = allocations.reduce((sum, item) => sum + item.chips, 0);
  const totalOverLimit = Boolean(data && total > data.rules.total_chips);
  const driversOverLimit = allocations.filter((item) => item.chips > (data?.rules.max_chips_per_driver ?? Number.POSITIVE_INFINITY));
  const hasDriverOverLimit = driversOverLimit.length > 0;
  const available = data?.drivers.filter((driver) => !used.has(driver.name)) ?? [];
  const eleventhOptions = data?.drivers.filter((driver) => !used.has(driver.name)) ?? [];
  const canonicalEleventh = resolveDriverName(eleventh, data?.drivers ?? []);
  const eleventhConflicts = Boolean(canonicalEleventh && used.has(canonicalEleventh));
  const driversKnown = Boolean(data && canonicalAllocations.every((allocation) => data.drivers.some((driver) => driver.name === allocation.driver)));
  const driversUnique = new Set(canonicalAllocations.map((allocation) => allocation.driver)).size === canonicalAllocations.length;
  const eleventhKnown = Boolean(data?.drivers.some((driver) => driver.name === canonicalEleventh));
  const selectedRace = data?.selected_race;
  const selectedTeams = canonicalAllocations.map((allocation) => data?.drivers.find((driver) => driver.name === allocation.driver)?.team).filter(Boolean);
  const teamsValid = Boolean(data?.rules.same_team_allowed || new Set(selectedTeams).size === selectedTeams.length);
  const valid = Boolean(selectedRace?.is_open && allocations.length >= (data?.rules.minimum_drivers ?? 1) && total === data?.rules.total_chips && allocations.every((item) => item.chips > 0 && item.chips <= data!.rules.max_chips_per_driver) && driversKnown && driversUnique && teamsValid && eleventhKnown && !eleventhConflicts);

  function addDriver() {
    const driver = available[0];
    if (driver) setAllocations((current) => [...current, { driver: driver.name, chips: 1 }]);
  }
  function update(index: number, patch: Partial<Allocation>) { setAllocations((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item)); }
  function canonicalizeAllocation(index: number) { update(index, { driver: resolveDriverName(allocations[index]?.driver ?? "", data?.drivers ?? []) }); }
  function canonicalizeEleventh() { setEleventh(resolveDriverName(eleventh, data?.drivers ?? [])); }
  function remove(index: number) { setAllocations((current) => current.filter((_, itemIndex) => itemIndex !== index)); }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!selectedRace || !valid) return;
    setSaving(true); setNotice(null);
    try {
      await apiRequest(`/api/v1/race-bets?season=${season}`, { method: "POST", body: JSON.stringify({ race_id: selectedRace.id, allocations: canonicalAllocations, eleventh_driver: canonicalEleventh }) });
      setNotice({ kind: "success", text: "Aposta registrada com sucesso. Você pode alterá-la até o prazo da prova." });
      await load(selectedRace.id);
      setNotice({ kind: "success", text: "Aposta registrada com sucesso. Você pode alterá-la até o prazo da prova." });
    } catch (reason) {
      setNotice({ kind: "error", text: reason instanceof ApiRequestError && reason.status === 403 ? "O prazo desta aposta está encerrado." : "A aposta foi recusada. Confira fichas, pilotos e regras da prova." });
    } finally { setSaving(false); }
  }
  async function generateBet() {
    if (!selectedRace?.is_open) return;
    setGenerating(true); setNotice(null);
    try {
      const response = await apiRequest<{ message: string }>(`/api/v1/race-bets/generate?season=${season}`, { method: "POST", body: JSON.stringify({ race_id: selectedRace.id }) });
      await load(selectedRace.id);
      setNotice({ kind: "success", text: response.message });
    } catch (reason) {
      setNotice({ kind: "error", text: reason instanceof ApiRequestError && reason.status === 403 ? "O prazo desta aposta está encerrado." : "Não foi possível gerar uma aposta válida para esta prova." });
    } finally { setGenerating(false); }
  }

  return <div className="betting-page"><header className="institutional-hero"><div><p className="eyebrow">Apostas · Temporada {season}</p><h1>Monte sua estratégia.</h1><p>Distribua as fichas entre os pilotos e indique quem termina em 11º.</p></div></header>
    {notice ? <div className={`bet-notice bet-notice--${notice.kind}`} role="alert">{notice.text}</div> : null}
    {loading ? <div className="calendar-state" role="status">Carregando regras e provas…</div> : null}
    {!loading && data ? <form onSubmit={submit} className="bet-layout"><section className="panel bet-main"><div className="panel__heading"><div><p className="eyebrow">Etapa</p><h2>Prova selecionada</h2></div><button className="secondary-action" type="button" onClick={() => void generateBet()} disabled={!selectedRace?.is_open || generating || saving}>{generating ? "Gerando…" : "Sem ideias"}</button></div><label className="bet-race-select">Prova<select value={selectedRace?.id ?? ""} onChange={(event) => void load(Number(event.target.value))}>{data.races.map((race) => <option key={race.id} value={race.id}>{race.name} · {race.is_open ? "aberta" : "encerrada"}</option>)}</select></label>{selectedRace ? <div className={selectedRace.is_open ? "deadline deadline--open" : "deadline deadline--closed"}><strong>{selectedRace.type}</strong><span>{selectedRace.deadline_message}</span></div> : <p className="panel-empty">Nenhuma prova cadastrada nesta temporada.</p>}
      <div className="bet-section-heading"><div><p className="eyebrow">Distribuição</p><h2>Pilotos e fichas</h2></div><button className="secondary-action" type="button" onClick={addDriver} disabled={!available.length || !selectedRace?.is_open}>Adicionar piloto</button></div>
      <div className="bet-allocations">{allocations.map((allocation, index) => {
        const canonicalName = canonicalAllocations[index]?.driver ?? allocation.driver;
        const driver = data.drivers.find((item) => item.name === canonicalName);
        const otherDrivers = new Set(canonicalAllocations.filter((_, itemIndex) => itemIndex !== index).map((item) => item.driver));
        const rowOptions = data.drivers.filter((item) => !otherDrivers.has(item.name));
        const overLimit = allocation.chips > data.rules.max_chips_per_driver;
        const unknownDriver = Boolean(allocation.driver && !driver);
        return <div className={overLimit || unknownDriver ? "bet-allocation bet-allocation--invalid" : "bet-allocation"} key={index}>
          <span className="team-marker" style={{ background: getOptionalTeamMarkerBackground(driver?.team) }} aria-hidden="true" />
          <label>Piloto
            <input list={`bet-driver-options-${index}`} value={allocation.driver} onChange={(event) => update(index, { driver: event.target.value })} onBlur={() => canonicalizeAllocation(index)} disabled={!selectedRace?.is_open} placeholder="Digite o nome ou sobrenome" autoComplete="off" aria-invalid={unknownDriver} />
            <datalist id={`bet-driver-options-${index}`}>{rowOptions.map((item) => <option key={item.name} value={item.name}>{item.team}</option>)}</datalist>
            {unknownDriver ? <small className="bet-field-error">Selecione um piloto disponível.</small> : null}
          </label>
          <label>Fichas<input type="number" min="1" max={data.rules.max_chips_per_driver} value={allocation.chips} onChange={(event) => update(index, { chips: Number(event.target.value) })} disabled={!selectedRace?.is_open} aria-invalid={overLimit} aria-describedby={overLimit ? `chips-error-${index}` : undefined} />{overLimit ? <small className="bet-field-error" id={`chips-error-${index}`}>Máximo: {data.rules.max_chips_per_driver}</small> : null}</label>
          <button type="button" className="table-action" onClick={() => remove(index)} disabled={!selectedRace?.is_open} aria-label={`Remover ${allocation.driver}`}>Remover</button>
        </div>;
      })}</div>
      <label className={eleventhConflicts || (eleventh !== "" && !eleventhKnown) ? "bet-eleventh bet-eleventh--invalid" : "bet-eleventh"}>Palpite para o 11º colocado
        <input required list="bet-eleventh-options" value={eleventh} onChange={(event) => setEleventh(event.target.value)} onBlur={canonicalizeEleventh} disabled={!selectedRace?.is_open} placeholder="Digite o nome ou sobrenome" autoComplete="off" aria-invalid={Boolean(eleventh && (eleventhConflicts || !eleventhKnown))} aria-describedby={eleventhConflicts ? "eleventh-error" : undefined} />
        <datalist id="bet-eleventh-options">{eleventhOptions.map((driver) => <option key={driver.name} value={driver.name}>{driver.team}</option>)}</datalist>
        {eleventhConflicts ? <small className="bet-field-error" id="eleventh-error">O piloto do 11º não pode estar entre os apostados.</small> : eleventh && !eleventhKnown ? <small className="bet-field-error">Selecione um piloto disponível.</small> : null}
      </label>
      <button className="primary-action bet-submit" type="submit" disabled={!valid || saving}>{saving ? "Registrando…" : data.current_bet ? "Atualizar minha aposta" : "Registrar minha aposta"}</button></section>
      <aside className="panel bet-summary"><p className="eyebrow">Regras vigentes</p><h2>Conferência</h2><dl><div className={totalOverLimit ? "rule-row--error" : ""}><dt>Fichas distribuídas</dt><dd className={totalOverLimit ? "rule-error" : total === data.rules.total_chips ? "rule-ok" : ""}>{total}/{data.rules.total_chips}</dd></div><div><dt>Mínimo de pilotos</dt><dd className={allocations.length >= data.rules.minimum_drivers ? "rule-ok" : ""}>{allocations.length}/{data.rules.minimum_drivers}</dd></div><div className={hasDriverOverLimit ? "rule-row--error" : ""}><dt>Máximo por piloto</dt><dd className={hasDriverOverLimit ? "rule-error" : ""}>{data.rules.max_chips_per_driver}{hasDriverOverLimit ? ` · ${driversOverLimit.length} fora da regra` : ""}</dd></div><div className={eleventhConflicts ? "rule-row--error" : ""}><dt>Piloto do 11º</dt><dd className={eleventhConflicts ? "rule-error" : eleventh ? "rule-ok" : ""}>{eleventhConflicts ? "Também apostado" : eleventh ? "Válido" : "Pendente"}</dd></div><div className={!teamsValid ? "rule-row--error" : ""}><dt>Mesma equipe</dt><dd className={!teamsValid ? "rule-error" : ""}>{data.rules.same_team_allowed ? "Permitida" : !teamsValid ? "Pilotos repetidos" : "Não permitida"}</dd></div></dl>{data.current_bet ? <p className="bet-saved">Aposta já registrada para esta prova. Um novo envio substituirá a aposta vigente e manterá o log.</p> : null}</aside></form> : null}
  </div>;
}
