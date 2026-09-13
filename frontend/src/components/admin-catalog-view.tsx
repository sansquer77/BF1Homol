"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ApiRequestError, apiRequest, type User as Identity } from "@/lib/api/client";

type Tab = "users" | "teams" | "drivers" | "races";
type User = { id: number; name: string; email: string; profile: string; status: string; must_change_password: boolean };
type Driver = { id: number; name: string; team: string; status: string; number: number };
type Race = { id: number; name: string; date: string; time: string; type: string; race_status: string; circuit_id: string | null };
type Circuit = { circuit_id: string; circuit_name: string; country: string; locality: string };
type Team = { id: number; name: string; primary_color: string; secondary_color: string | null; status: string };
type Item = User | Team | Driver | Race;
type FormState = Record<string, string | boolean>;

function circuitLabel(circuit: Circuit) {
  const place = [circuit.locality, circuit.country].filter(Boolean).join(", ");
  return `${circuit.circuit_name}${place ? ` (${place})` : ""} — ${circuit.circuit_id}`;
}

export function AdminCatalogView() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [tab, setTab] = useState<Tab>("drivers");
  const [items, setItems] = useState<Item[]>([]);
  const [circuits, setCircuits] = useState<Circuit[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshingCircuits, setRefreshingCircuits] = useState(false);
  const [season, setSeason] = useState(String(new Date().getFullYear()));
  const [form, setForm] = useState<FormState>({});
  const [editingId, setEditingId] = useState<number | null>(null);

  const canEdit = identity?.perfil === "master";
  const value = (key: string) => String(form[key] ?? "");
  const set = (key: string, next: string | boolean) => setForm((current) => ({ ...current, [key]: next }));
  const cancelEdit = () => { setEditingId(null); setForm({}); setError(""); };

  const load = useCallback(() => {
    if (!identity) return;
    const path = tab === "users" ? "/api/v1/admin/users" : tab === "teams" ? "/api/v1/admin/teams" : tab === "drivers" ? "/api/v1/admin/drivers" : `/api/v1/admin/races?season=${season}`;
    setError("");
    apiRequest<Item[]>(path as `/api/v1/${string}`).then(setItems).catch((reason) => setError(reason instanceof ApiRequestError && reason.status === 403 ? "Seu perfil não tem permissão para este cadastro." : "O servidor não conseguiu carregar os registros administrativos."));
  }, [identity, season, tab]);

  const loadTeams = useCallback(() => {
    if (!identity) return;
    apiRequest<Team[]>("/api/v1/admin/teams").then(setTeams).catch(() => setTeams([]));
  }, [identity]);

  const loadCircuits = useCallback(() => {
    if (!identity || tab !== "races") return;
    apiRequest<Circuit[]>("/api/v1/admin/circuits").then(setCircuits).catch((reason) => setError(reason instanceof ApiRequestError && reason.status === 403 ? "Seu perfil não permite consultar os circuitos." : "Não foi possível carregar a base de circuitos."));
  }, [identity, tab]);

  useEffect(() => {
    apiRequest<Identity>("/api/v1/auth/me").then((user) => {
      setIdentity(user);
      setTab(user.perfil === "master" ? "users" : "drivers");
    }).catch(() => setError("Não foi possível validar sua sessão."));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadTeams(); }, [loadTeams]);
  useEffect(() => { loadCircuits(); }, [loadCircuits]);

  function selectTab(next: Tab) { setTab(next); setEditingId(null); setForm({}); setNotice(""); }

  function startEdit(item: Item) {
    if (!canEdit) return;
    setEditingId(item.id); setError(""); setNotice("");
    if (tab === "users") {
      const user = item as User;
      setForm({ name: user.name, email: user.email, profile: user.profile, status: user.status, must_change_password: user.must_change_password });
    } else if (tab === "teams") {
      const team = item as Team;
      setForm({ name: team.name, primary_color: team.primary_color, secondary_color: team.secondary_color ?? "", status: team.status });
    } else if (tab === "drivers") {
      const driver = item as Driver;
      setForm({ name: driver.name, team: driver.team, number: String(driver.number), status: driver.status });
    } else {
      const race = item as Race;
      setForm({ name: race.name, date: race.date.slice(0, 10), time: race.time.slice(0, 5), type: race.type, status: race.race_status, circuit_id: race.circuit_id ?? "" });
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function refreshCircuits() {
    setError(""); setNotice(""); setRefreshingCircuits(true);
    try {
      const stats = await apiRequest<{ temporadas: number; circuitos: number }>(`/api/v1/admin/circuits/refresh?season=${season}`, { method: "POST" });
      setCircuits(await apiRequest<Circuit[]>("/api/v1/admin/circuits"));
      setNotice(`Base atualizada: ${stats.circuitos} circuitos de ${stats.temporadas} temporada(s).`);
    } catch (reason) {
      setError(reason instanceof ApiRequestError && reason.status === 403 ? "Seu perfil não permite atualizar os circuitos." : "Não foi possível atualizar a base de circuitos pela API.");
    } finally { setRefreshingCircuits(false); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setNotice("");
    try {
      if (tab === "users") {
        if (editingId !== null) {
          await apiRequest(`/api/v1/admin/users/${editingId}`, { method: "PATCH", body: JSON.stringify({ name: value("name"), email: value("email"), profile: value("profile") || "participante", user_status: value("status") || "ativo", must_change_password: Boolean(form.must_change_password) }) });
        } else {
          await apiRequest("/api/v1/admin/users", { method: "POST", body: JSON.stringify({ name: value("name"), email: value("email"), password: value("password"), profile: value("profile") || "participante", user_status: value("status") || "ativo" }) });
        }
      } else if (tab === "teams") {
        const path = editingId === null ? "/api/v1/admin/teams" : `/api/v1/admin/teams/${editingId}`;
        await apiRequest(path as `/api/v1/${string}`, { method: editingId === null ? "POST" : "PUT", body: JSON.stringify({ name: value("name"), primary_color: value("primary_color"), secondary_color: value("secondary_color") || null, status: value("status") || "Ativa" }) });
      } else if (tab === "drivers") {
        const path = editingId === null ? "/api/v1/admin/drivers" : `/api/v1/admin/drivers/${editingId}`;
        await apiRequest(path as `/api/v1/${string}`, { method: editingId === null ? "POST" : "PUT", body: JSON.stringify({ name: value("name"), team: value("team"), status: value("status") || "Ativo", number: Number(value("number") || 0) }) });
      } else {
        const path = editingId === null ? `/api/v1/admin/races?season=${season}` : `/api/v1/admin/races/${editingId}?season=${season}`;
        await apiRequest(path as `/api/v1/${string}`, { method: editingId === null ? "POST" : "PUT", body: JSON.stringify({ name: value("name"), date: value("date"), time: value("time"), type: value("type") || "Normal", race_status: value("status") || "Pendente", circuit_id: value("circuit_id") || null }) });
      }
      const edited = editingId !== null;
      setEditingId(null); setForm({}); load(); loadTeams(); setNotice(edited ? "Registro atualizado." : "Registro salvo.");
    } catch (reason) {
      setError(reason instanceof ApiRequestError && reason.status === 403 ? "A edição é exclusiva do usuário Master." : "Não foi possível salvar o registro.");
    }
  }

  const tabs: [Tab, string][] = canEdit ? [["users", "Usuários"], ["teams", "Equipes"], ["drivers", "Pilotos"], ["races", "Provas"]] : [["teams", "Equipes"], ["drivers", "Pilotos"], ["races", "Provas"]];
  const selectedCircuitIsLegacy = Boolean(value("circuit_id") && !circuits.some((circuit) => circuit.circuit_id === value("circuit_id")));
  const entityLabel = tab === "users" ? "usuário" : tab === "teams" ? "equipe" : tab === "drivers" ? "piloto" : "prova";
  const title = editingId !== null ? `Editar ${entityLabel}` : tab === "users" ? "Convidar usuário" : tab === "teams" ? "Adicionar equipe" : tab === "drivers" ? "Adicionar piloto" : "Adicionar prova";

  return <div className="admin-catalog-view">
    <header className="institutional-hero"><p className="eyebrow">Administração</p><h1>Cadastros do campeonato.</h1><p>Novos registros seguem as permissões vigentes; editar registros existentes é exclusivo do Master.</p></header>
    <div className="admin-tabs" role="tablist">
      {tabs.map(([key, label]) => <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? "admin-tab admin-tab--active" : "admin-tab"} onClick={() => selectTab(key)}>{label}</button>)}
      {tab === "races" ? <><label className="admin-season">Temporada<input inputMode="numeric" pattern="[0-9]{4}" value={season} onChange={(event) => { setSeason(event.target.value); cancelEdit(); }} /></label><button type="button" className="admin-tab" disabled={refreshingCircuits || !/^\d{4}$/.test(season)} onClick={refreshCircuits}>{refreshingCircuits ? "Atualizando…" : "Atualizar circuitos"}</button></> : null}
    </div>
    {error ? <div className="calendar-state calendar-state--error" role="alert">{error}</div> : null}
    {notice ? <div className="calendar-state" role="status">{notice}</div> : null}
    {tab === "teams" && !canEdit ? null : <section className="panel admin-form"><div className="panel__heading"><h2>{title}</h2>{editingId !== null ? <button type="button" className="table-action" onClick={cancelEdit}>Cancelar edição</button> : null}</div><form className="admin-fields" onSubmit={submit}>
      <label>Nome<input required value={value("name")} onChange={(event) => set("name", event.target.value)} /></label>
      {tab === "users" ? <><label>Email<input required type="email" value={value("email")} onChange={(event) => set("email", event.target.value)} /></label>{editingId === null ? <label>Senha temporária<input required minLength={8} type="password" value={value("password")} onChange={(event) => set("password", event.target.value)} /></label> : null}<label>Perfil<select value={value("profile") || "participante"} onChange={(event) => set("profile", event.target.value)}><option value="participante">participante</option><option value="admin">admin</option><option value="master">master</option><option value="inativo">inativo</option></select></label><label>Status<select value={value("status") || "ativo"} onChange={(event) => set("status", event.target.value)}><option value="ativo">ativo</option><option value="inativo">inativo</option></select></label>{editingId !== null ? <label className="check-field"><input type="checkbox" checked={Boolean(form.must_change_password)} onChange={(event) => set("must_change_password", event.target.checked)} />Exigir troca de senha</label> : null}</> : tab === "teams" ? <><label>Cor principal<input required type="color" value={value("primary_color") || "#687284"} onChange={(event) => set("primary_color", event.target.value)} /></label><label>Cor secundária<input type="color" value={value("secondary_color") || "#687284"} onChange={(event) => set("secondary_color", event.target.value)} /></label><label className="check-field"><input type="checkbox" checked={!value("secondary_color")} onChange={(event) => set("secondary_color", event.target.checked ? "" : "#687284")} />Sem cor secundária</label><label>Status<select value={value("status") || "Ativa"} onChange={(event) => set("status", event.target.value)}><option value="Ativa">Ativa</option><option value="Inativa">Inativa</option></select></label></> : tab === "drivers" ? <><label>Equipe<select value={value("team")} onChange={(event) => set("team", event.target.value)}><option value="">Sem equipe</option>{value("team") && !teams.some((team) => team.name === value("team")) ? <option value={value("team")}>{value("team")} (legada)</option> : null}{teams.filter((team) => team.status === "Ativa" || team.name === value("team")).map((team) => <option key={team.id} value={team.name}>{team.name}</option>)}</select></label><label>Número<input type="number" min="0" max="99" value={value("number")} onChange={(event) => set("number", event.target.value)} /></label><label>Status<select value={value("status") || "Ativo"} onChange={(event) => set("status", event.target.value)}><option value="Ativo">Ativo</option><option value="Inativo">Inativo</option></select></label></> : <><label>Data<input required type="date" value={value("date")} onChange={(event) => set("date", event.target.value)} /></label><label>Horário<input type="time" value={value("time")} onChange={(event) => set("time", event.target.value)} /></label><label>Tipo<select value={value("type") || "Normal"} onChange={(event) => set("type", event.target.value)}><option value="Normal">Normal</option><option value="Sprint">Sprint</option></select></label><label>Status<select value={value("status") || "Pendente"} onChange={(event) => set("status", event.target.value)}><option value="Pendente">Pendente</option><option value="Ativa">Ativa</option><option value="Encerrada">Encerrada</option></select></label><label>Circuito<select value={value("circuit_id")} onChange={(event) => set("circuit_id", event.target.value)}><option value="">Sem vínculo</option>{selectedCircuitIsLegacy ? <option value={value("circuit_id")}>Circuito legado — {value("circuit_id")}</option> : null}{circuits.map((circuit) => <option key={circuit.circuit_id} value={circuit.circuit_id}>{circuitLabel(circuit)}</option>)}</select></label></>}
      <button className="primary-action">{editingId !== null ? "Salvar alterações" : "Salvar"}</button>
    </form></section>}
    <section className="panel admin-list"><h2>Registros <small>{items.length} itens</small></h2><div className="table-scroll"><table><thead><tr><th>Nome</th>{tab === "users" ? <><th>Email</th><th>Perfil</th><th>Status</th></> : tab === "teams" ? <><th>Cores</th><th>Status</th></> : tab === "drivers" ? <><th>Equipe</th><th>Número</th><th>Status</th></> : <><th>Data</th><th>Horário</th><th>Tipo</th><th>Status</th><th>Circuito</th></>}{canEdit ? <th>Ações</th> : null}</tr></thead><tbody>{items.map((item) => tab === "users" ? <tr key={item.id}><td>{(item as User).name}</td><td>{(item as User).email}</td><td>{(item as User).profile}</td><td>{(item as User).status}</td>{canEdit ? <td><button type="button" className="table-action" onClick={() => startEdit(item)}>Editar</button></td> : null}</tr> : tab === "teams" ? <tr key={item.id}><td>{(item as Team).name}</td><td><span className="team-color-preview" style={{ background: (item as Team).secondary_color ? `linear-gradient(90deg, ${(item as Team).primary_color} 50%, ${(item as Team).secondary_color} 50%)` : (item as Team).primary_color }} />{(item as Team).primary_color}{(item as Team).secondary_color ? ` / ${(item as Team).secondary_color}` : ""}</td><td>{(item as Team).status}</td>{canEdit ? <td><button type="button" className="table-action" onClick={() => startEdit(item)}>Editar</button></td> : null}</tr> : tab === "drivers" ? <tr key={item.id}><td>{(item as Driver).name}</td><td>{(item as Driver).team}</td><td>{(item as Driver).number}</td><td>{(item as Driver).status}</td>{canEdit ? <td><button type="button" className="table-action" onClick={() => startEdit(item)}>Editar</button></td> : null}</tr> : <tr key={item.id}><td>{(item as Race).name}</td><td>{(item as Race).date}</td><td>{(item as Race).time}</td><td>{(item as Race).type}</td><td>{(item as Race).race_status}</td><td>{(item as Race).circuit_id || "Sem vínculo"}</td>{canEdit ? <td><button type="button" className="table-action" onClick={() => startEdit(item)}>Editar</button></td> : null}</tr>)}</tbody></table></div></section>
  </div>;
}
