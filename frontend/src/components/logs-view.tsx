"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest, type AccessLogs, type BettingLogs, type User } from "@/lib/api/client";

const SEASON = String(new Date().getFullYear());
const INITIAL_START = isoDay(-7);
const INITIAL_END = isoDay();
const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" });

function isoDay(offset = 0) {
  const value = new Date();
  value.setDate(value.getDate() + offset);
  return value.toISOString().slice(0, 10);
}

export function LogsView() {
  const [user, setUser] = useState<User | null>(null);
  const [bets, setBets] = useState<BettingLogs | null>(null);
  const [access, setAccess] = useState<AccessLogs | null>(null);
  const [error, setError] = useState(false);
  const [betPage, setBetPage] = useState(1);
  const [accessPage, setAccessPage] = useState(1);
  const [bettor, setBettor] = useState("");
  const [automaticOnly, setAutomaticOnly] = useState(false);
  const [start, setStart] = useState(INITIAL_START);
  const [end, setEnd] = useState(INITIAL_END);
  const [userFilter, setUserFilter] = useState("");

  const loadBets = useCallback((page = 1) => {
    const query = new URLSearchParams({ season: SEASON, page: String(page), page_size: "50" });
    if (bettor.trim()) query.set("bettor", bettor.trim());
    if (automaticOnly) query.set("automatic_only", "true");
    setError(false);
    apiRequest<BettingLogs>(`/api/v1/logs/bets?${query}`).then(setBets).catch(() => setError(true));
  }, [automaticOnly, bettor]);

  const loadAccess = useCallback((page = 1) => {
    const query = new URLSearchParams({ start, end, page: String(page), page_size: "50" });
    if (userFilter.trim()) query.set("user_contains", userFilter.trim());
    apiRequest<AccessLogs>(`/api/v1/logs/access?${query}`).then(setAccess).catch(() => setError(true));
  }, [end, start, userFilter]);

  useEffect(() => {
    let active = true;
    Promise.all([apiRequest<User>("/api/v1/auth/me"), apiRequest<BettingLogs>(`/api/v1/logs/bets?season=${SEASON}&page=1&page_size=50`)])
      .then(([identity, betting]) => { if (active) { setUser(identity); setBets(betting); if (identity.perfil === "master") apiRequest<AccessLogs>(`/api/v1/logs/access?start=${INITIAL_START}&end=${INITIAL_END}&page=1&page_size=50`).then((value) => { if (active) setAccess(value); }).catch(() => { if (active) setError(true); }); } })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);

  function applyBets(event: FormEvent) { event.preventDefault(); setBetPage(1); loadBets(1); }
  function applyAccess(event: FormEvent) { event.preventDefault(); setAccessPage(1); loadAccess(1); }
  function changeBetPage(page: number) { setBetPage(page); loadBets(page); }
  function changeAccessPage(page: number) { setAccessPage(page); loadAccess(page); }

  return <div className="logs-view"><header className="institutional-hero"><div><p className="eyebrow">Monitoramento</p><h1>Logs e auditoria.</h1><p>Histórico rastreável, filtrado no servidor e limitado ao seu nível de acesso.</p></div></header>
    {error ? <div className="calendar-state calendar-state--error" role="alert">Não foi possível carregar os logs.</div> : null}
    <section className="logs-section" aria-labelledby="bet-logs-title"><div className="panel__heading"><div><p className="eyebrow">Apostas</p><h2 id="bet-logs-title">Log de apostas</h2></div>{bets ? <small>{bets.pagination.total} registros · {bets.scope === "individual" ? "Meu histórico" : "Visão consolidada"}</small> : null}</div>
      <form className="logs-filters" onSubmit={applyBets}><label>Apostador<input value={bettor} onChange={(event) => setBettor(event.target.value)} placeholder="Nome" disabled={bets?.scope === "individual"} /></label><label className="check-field"><input type="checkbox" checked={automaticOnly} onChange={(event) => setAutomaticOnly(event.target.checked)} />Somente automáticas</label><button className="secondary-action" type="submit">Aplicar filtros</button></form>
      {!bets ? <div className="calendar-state" role="status">Carregando apostas…</div> : <div className="table-scroll" tabIndex={0}><table className="logs-table"><caption className="sr-only">Registros do log de apostas</caption><thead><tr><th>Data</th><th>Apostador</th><th>Prova</th><th>Pilotos</th><th>11º</th><th>Tipo</th><th>Status</th></tr></thead><tbody>{bets.items.map((item) => <tr key={item.id}><td>{item.data ?? "—"}<small>{item.horario ?? ""}</small></td><td>{item.apostador ?? "—"}</td><td>{item.nome_prova ?? "—"}</td><td>{item.pilotos ?? "—"}<small>{item.aposta ?? ""}</small></td><td>{item.piloto_11 ?? "—"}</td><td>{item.automatica ? "Automática" : item.tipo_aposta === 1 ? "Fora do prazo" : "No prazo"}</td><td><span className="log-status">{item.status ?? "Registrada"}</span></td></tr>)}</tbody></table></div>}
      {bets ? <Pagination page={betPage} pages={bets.pagination.total_pages} onChange={changeBetPage} /> : null}
    </section>
    {user?.perfil === "master" ? <section className="logs-section" aria-labelledby="access-logs-title"><div className="panel__heading"><div><p className="eyebrow">Segurança</p><h2 id="access-logs-title">Log de acessos</h2></div><small>Exclusivo do Master</small></div>
      <form className="logs-filters logs-filters--access" onSubmit={applyAccess}><label>Início<input type="date" value={start} onChange={(event) => setStart(event.target.value)} /></label><label>Fim<input type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></label><label>Usuário ou email<input value={userFilter} onChange={(event) => setUserFilter(event.target.value)} placeholder="Buscar" /></label><button className="secondary-action" type="submit">Aplicar filtros</button></form>
      {access ? <><div className="log-summary"><span><strong>{access.pagination.total}</strong>Total</span><span><strong>{access.successes}</strong>Sucessos</span><span><strong>{access.failures}</strong>Falhas</span></div><div className="table-scroll" tabIndex={0}><table className="logs-table"><caption className="sr-only">Registros do log de acessos</caption><thead><tr><th>Instante</th><th>Evento</th><th>Usuário</th><th>Perfil</th><th>Resultado</th><th>IP</th></tr></thead><tbody>{access.items.map((item) => <tr key={item.id}><td>{dateTime.format(new Date(item.created_at))}</td><td>{item.evento ?? "—"}</td><td>{item.nome ?? item.email ?? "—"}<small>{item.nome ? item.email : ""}</small></td><td>{item.perfil ?? "—"}</td><td><span className={item.sucesso ? "log-status" : "log-status log-status--failure"}>{item.sucesso ? "Sucesso" : "Falha"}</span></td><td>{item.ip_address ?? "—"}</td></tr>)}</tbody></table></div><Pagination page={accessPage} pages={access.pagination.total_pages} onChange={changeAccessPage} /></> : <div className="calendar-state" role="status">Carregando acessos…</div>}
    </section> : null}
  </div>;
}

function Pagination({ page, pages, onChange }: { page: number; pages: number; onChange: (page: number) => void }) {
  return <nav className="pagination" aria-label="Paginação"><button type="button" disabled={page <= 1} onClick={() => onChange(page - 1)}>Anterior</button><span>Página {page} de {pages}</span><button type="button" disabled={page >= pages} onClick={() => onChange(page + 1)}>Próxima</button></nav>;
}
