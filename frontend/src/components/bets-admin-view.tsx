"use client";

import { useEffect, useMemo, useState } from "react";
import { ApiRequestError, apiRequest } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";

type Tab = "race" | "user" | "reports";
type Participant = { user_id: number; name: string; email: string };
type Race = { race_id: number; name: string; date: string; time: string; type: string };
type Bet = { user_id: number; race_id: number; drivers: string[]; chips: number[]; eleventh_driver: string; submitted_at: string | null; automatic_generation: number };
type Report = { user_id: number; name: string; bets_total: number; manual_total: number; automatic_total: number; missing_total: number; manual_races: string[]; automatic_races: string[]; missing_races: string[] };
type Snapshot = { season: string; participants: Participant[]; races: Race[]; bets: Bet[]; reports: Report[] };

export function BetsAdminView() {
  const { season } = useSeason();
  const [tab, setTab] = useState<Tab>("race");
  const [data, setData] = useState<Snapshot>();
  const [raceId, setRaceId] = useState<number>();
  const [userId, setUserId] = useState<number>();
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<{ kind: "error" | "success"; text: string }>();

  async function load() {
    setNotice(undefined);
    try {
      const snapshot = await apiRequest<Snapshot>(`/api/v1/admin/bets?season=${season}`);
      setData(snapshot);
      setRaceId((current) => snapshot.races.some((race) => race.race_id === current) ? current : snapshot.races[0]?.race_id);
      setUserId((current) => snapshot.participants.some((participant) => participant.user_id === current) ? current : snapshot.participants[0]?.user_id);
    } catch {
      setData(undefined);
      setNotice({ kind: "error", text: "Acesso restrito a Admin e Master ou serviço indisponível." });
    }
  }

  useEffect(() => { void load(); }, [season]);

  const betMap = useMemo(() => new Map(data?.bets.map((bet) => [`${bet.user_id}:${bet.race_id}`, bet]) ?? []), [data]);
  async function action(kind: "generate" | "reminder", targetUserId?: number) {
    if (!raceId) return;
    const key = `${kind}:${targetUserId ?? "all"}:${raceId}`;
    if (!window.confirm(kind === "generate" ? "Gerar a aposta automática para este participante?" : targetUserId ? "Enviar o lembrete somente ao participante selecionado?" : "Enviar o lembrete em CCO a todos os participantes pendentes desta prova?")) return;
    setBusy(key); setNotice(undefined);
    try {
      const response = await apiRequest<{ message: string; recipients?: number }>(`/api/v1/admin/bets/${kind}`, {
        method: "POST",
        body: JSON.stringify({ season, race_id: raceId, user_id: targetUserId ?? null }),
      });
      await load();
      setNotice({ kind: "success", text: response.recipients ? `${response.message} Destinatários: ${response.recipients}.` : response.message });
    } catch (reason) {
      const detail = reason instanceof ApiRequestError && typeof reason.detail === "string" ? reason.detail : "A operação não pôde ser concluída.";
      setNotice({ kind: "error", text: detail });
    } finally { setBusy(""); }
  }

  return <div className="admin-catalog-view bets-admin-view">
    <header className="institutional-hero"><p className="eyebrow">Administração</p><h1>Gestão de apostas.</h1><p>Acompanhe registros, lembre participantes e gere apostas automáticas na temporada {season}.</p></header>
    <div className="admin-tabs" role="tablist" aria-label="Visões da gestão de apostas">
      {([['race', 'Por prova'], ['user', 'Por usuário'], ['reports', 'Relatórios']] as [Tab, string][]).map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "admin-tab admin-tab--active" : "admin-tab"} onClick={() => setTab(key)}>{label}</button>)}
    </div>
    {notice ? <div className={`bet-notice bet-notice--${notice.kind}`} role="alert">{notice.text}</div> : null}
    {!data && !notice ? <div className="calendar-state" role="status">Carregando apostas…</div> : null}
    {data && tab === "race" ? <ByRace data={data} raceId={raceId} setRaceId={setRaceId} betMap={betMap} busy={busy} action={action} /> : null}
    {data && tab === "user" ? <ByUser data={data} raceId={raceId} setRaceId={setRaceId} userId={userId} setUserId={setUserId} betMap={betMap} busy={busy} action={action} /> : null}
    {data && tab === "reports" ? <Reports reports={data.reports} racesTotal={data.races.length} season={data.season} onNotice={setNotice} /> : null}
  </div>;
}

function SelectRace({ races, value, onChange }: { races: Race[]; value?: number; onChange: (id: number) => void }) {
  return <label>Prova<select value={value ?? ""} onChange={(event) => onChange(Number(event.target.value))}>{races.map((race) => <option key={race.race_id} value={race.race_id}>{race.name} · {race.date} {race.time.slice(0, 5)}</option>)}</select></label>;
}

function ByRace({ data, raceId, setRaceId, betMap, busy, action }: { data: Snapshot; raceId?: number; setRaceId: (id: number) => void; betMap: Map<string, Bet>; busy: string; action: (kind: "generate" | "reminder", userId?: number) => void }) {
  const race = data.races.find((item) => item.race_id === raceId);
  const pending = data.participants.filter((participant) => !betMap.has(`${participant.user_id}:${raceId}`));
  return <><section className="panel bets-admin-toolbar"><SelectRace races={data.races} value={raceId} onChange={setRaceId} /><div><span>{pending.length} participante(s) sem aposta</span><button type="button" className="secondary-action" disabled={!raceId || !pending.length || Boolean(busy)} onClick={() => action("reminder")}>{busy.startsWith("reminder:all") ? "Enviando…" : "Enviar lembrete em CCO"}</button></div></section>
    <section className="panel admin-list"><div className="panel__heading"><div><p className="eyebrow">{race?.type ?? "Prova"}</p><h2>{race?.name ?? "Nenhuma prova cadastrada"}</h2></div><small>{data.participants.length - pending.length}/{data.participants.length} apostas</small></div><div className="table-scroll" tabIndex={0}><table><caption className="sr-only">Apostas dos participantes na prova selecionada</caption><thead><tr><th>Participante</th><th>Situação</th><th>Composição</th><th>11º</th><th>Envio</th><th>Ação</th></tr></thead><tbody>{data.participants.map((participant) => { const bet = betMap.get(`${participant.user_id}:${raceId}`); return <BetRow key={participant.user_id} participant={participant} bet={bet} busy={busy} onGenerate={() => action("generate", participant.user_id)} />; })}</tbody></table></div></section></>;
}

function ByUser({ data, raceId, setRaceId, userId, setUserId, betMap, busy, action }: { data: Snapshot; raceId?: number; setRaceId: (id: number) => void; userId?: number; setUserId: (id: number) => void; betMap: Map<string, Bet>; busy: string; action: (kind: "generate" | "reminder", userId?: number) => void }) {
  const user = data.participants.find((participant) => participant.user_id === userId);
  const selectedBet = betMap.get(`${userId}:${raceId}`);
  return <><section className="panel bets-admin-toolbar bets-admin-toolbar--user"><label>Participante<select value={userId ?? ""} onChange={(event) => setUserId(Number(event.target.value))}>{data.participants.map((participant) => <option key={participant.user_id} value={participant.user_id}>{participant.name}</option>)}</select></label><SelectRace races={data.races} value={raceId} onChange={setRaceId} /><div><button type="button" className="secondary-action" disabled={!user || Boolean(selectedBet) || Boolean(busy)} onClick={() => user && action("reminder", user.user_id)}>{busy.startsWith(`reminder:${userId}`) ? "Enviando…" : "Enviar lembrete individual"}</button><button type="button" className="primary-action" disabled={!user || Boolean(selectedBet && selectedBet.automatic_generation === 0) || Boolean(busy)} onClick={() => user && action("generate", user.user_id)}>{busy.startsWith(`generate:${userId}`) ? "Gerando…" : "Gerar aposta automática"}</button></div></section>
    <section className="panel admin-list"><div className="panel__heading"><div><p className="eyebrow">Temporada {data.season}</p><h2>{user?.name ?? "Participante"}</h2></div><small>{data.races.filter((race) => betMap.has(`${userId}:${race.race_id}`)).length}/{data.races.length} apostas</small></div><div className="table-scroll" tabIndex={0}><table><caption className="sr-only">Apostas do participante selecionado por prova</caption><thead><tr><th>Prova</th><th>Data</th><th>Situação</th><th>Composição</th><th>11º</th></tr></thead><tbody>{data.races.map((race) => { const bet = betMap.get(`${userId}:${race.race_id}`); return <tr key={race.race_id}><td>{race.name}</td><td>{race.date}</td><td><BetStatus bet={bet} /></td><td>{formatComposition(bet)}</td><td>{bet?.eleventh_driver || "—"}</td></tr>; })}</tbody></table></div></section></>;
}

function BetRow({ participant, bet, busy, onGenerate }: { participant: Participant; bet?: Bet; busy: string; onGenerate: () => void }) {
  return <tr><td><strong>{participant.name}</strong><small className="bets-admin-email">{participant.email || "Sem email"}</small></td><td><BetStatus bet={bet} /></td><td>{formatComposition(bet)}</td><td>{bet?.eleventh_driver || "—"}</td><td>{bet?.submitted_at || "—"}</td><td><button type="button" className="table-action" disabled={Boolean(bet && bet.automatic_generation === 0) || Boolean(busy)} onClick={onGenerate}>{busy.startsWith(`generate:${participant.user_id}`) ? "Gerando…" : "Gerar automática"}</button></td></tr>;
}

function BetStatus({ bet }: { bet?: Bet }) {
  if (!bet) return <span className="status-pill status-pill--pending">Sem aposta</span>;
  return bet.automatic_generation > 0 ? <span className="status-pill status-pill--automatic">Automática {bet.automatic_generation}</span> : <span className="status-pill status-pill--paid">Manual</span>;
}

function formatComposition(bet?: Bet) {
  return bet ? bet.drivers.map((driver, index) => `${driver} (${bet.chips[index] ?? 0})`).join(" · ") : "—";
}

function Reports({ reports, racesTotal, season, onNotice }: { reports: Report[]; racesTotal: number; season: string; onNotice: (notice: { kind: "error" | "success"; text: string }) => void }) {
  const [downloading, setDownloading] = useState(false);

  async function downloadImage() {
    setDownloading(true);
    try {
      const response = await fetch(`/api/v1/admin/bets/report-image?season=${encodeURIComponent(season)}`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({ detail: "Erro ao gerar relatório." }));
        throw new Error(body.detail || "Erro ao gerar relatório.");
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `bf1-cobertura-apostas-${season}.png`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      onNotice({ kind: "success", text: "Imagem do relatório baixada com sucesso." });
    } catch (reason) {
      onNotice({ kind: "error", text: reason instanceof Error ? reason.message : "Erro ao baixar relatório." });
    } finally {
      setDownloading(false);
    }
  }

  return <section className="panel admin-list bets-report"><div className="panel__heading"><div><p className="eyebrow">Resumo analítico</p><h2>Cobertura de apostas por participante</h2></div><div className="bets-report-actions"><small>{racesTotal} provas na temporada</small><button type="button" className="secondary-action" disabled={downloading} onClick={downloadImage}>{downloading ? "Gerando imagem…" : "Baixar imagem"}</button></div></div><div className="table-scroll" tabIndex={0}><table><caption className="sr-only">Resumo anual de apostas manuais, automáticas e ausentes</caption><thead><tr><th>Participante</th><th>Total</th><th>Manuais</th><th>Automáticas</th><th>Sem registro</th></tr></thead><tbody>{reports.map((report) => <tr key={report.user_id}><td><strong>{report.name}</strong></td><td>{report.bets_total}/{racesTotal}</td><td><RaceList count={report.manual_total} races={report.manual_races} empty="Nenhuma" /></td><td><RaceList count={report.automatic_total} races={report.automatic_races} empty="Nenhuma" automatic /></td><td><RaceList count={report.missing_total} races={report.missing_races} empty="Completo" /></td></tr>)}</tbody></table></div></section>;
}

function RaceList({ count, races, empty, automatic = false }: { count: number; races: string[]; empty: string; automatic?: boolean }) {
  return <details className="bets-report-list"><summary className={automatic && count ? "bets-report-auto" : ""}>{count} · {count ? "ver provas" : empty}</summary>{count ? <ul>{races.map((race) => <li key={race}>{race}</li>)}</ul> : null}</details>;
}
