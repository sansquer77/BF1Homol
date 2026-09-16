"use client";

import { FormEvent, useEffect, useState } from "react";
import { ApiRequestError, apiRequest } from "@/lib/api/client";

type Participant = { id: number; name: string };
type RecordItem = { id: number; user_id: number; participant: string; season: string; position: number; points: number };
type Payload = { records: RecordItem[]; participants: Participant[] };

const EMPTY_FORM = { user_id: "", season: String(new Date().getFullYear()), position: "1", points: "0" };

export function HallAdminView() {
  const [data, setData] = useState<Payload | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  function load() { apiRequest<Payload>("/api/v1/admin/hall-of-fame").then((value) => { setError(""); setData(value); }).catch((reason) => setError(reason instanceof ApiRequestError && reason.status === 403 ? "Seu perfil não tem permissão para administrar o Hall da Fama." : "O servidor não conseguiu carregar a gestão do Hall da Fama.")); }
  useEffect(load, []);

  function startEdit(record: RecordItem) {
    setEditingId(record.id);
    setForm({
      user_id: String(record.user_id),
      season: record.season,
      position: String(record.position),
      points: String(record.points),
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body = {
      user_id: Number(form.user_id),
      season: form.season,
      position: Number(form.position),
      points: Number(form.points),
    };
    try {
      if (editingId !== null) {
        await apiRequest(`/api/v1/admin/hall-of-fame/${editingId}`, { method: "PUT", body: JSON.stringify({ season: body.season, position: body.position, points: body.points }) });
      } else {
        await apiRequest("/api/v1/admin/hall-of-fame", { method: "POST", body: JSON.stringify(body) });
      }
      setEditingId(null);
      setForm(EMPTY_FORM);
      load();
    } catch {
      setError(editingId !== null ? "Não foi possível atualizar o registro." : "Não foi possível salvar o registro.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    if (!window.confirm("Remover esta colocação histórica?")) return;
    try {
      await apiRequest(`/api/v1/admin/hall-of-fame/${id}`, { method: "DELETE" });
      if (editingId === id) cancelEdit();
      load();
    } catch {
      setError("Não foi possível remover o registro.");
    }
  }

  return <div className="hall-admin-view"><header className="institutional-hero"><div><p className="eyebrow">Administração</p><h1>Gestão do Hall da Fama.</h1><p>Inclua, edite e remova colocações históricas sem alterar usuários ou apostas.</p></div></header>
    {error ? <div className="calendar-state calendar-state--error" role="alert">{error}</div> : null}
    <section className="panel hall-admin-form"><div className="panel__heading"><div><p className="eyebrow">Master</p><h2>{editingId !== null ? "Editar colocação" : "Nova colocação"}</h2></div><small>Atualização idempotente por participante e temporada</small></div>
      <form className="hall-admin-fields" onSubmit={submit}>
        <label>Participante<select required disabled={editingId !== null} value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })}><option value="">Selecione…</option>{data?.participants.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label>Temporada<input required pattern="[0-9]{4}" value={form.season} onChange={(e) => setForm({ ...form, season: e.target.value })} /></label>
        <label>Posição<input required type="number" min="1" max="1000" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} /></label>
        <label>Pontos<input required type="number" min="0" step="0.01" value={form.points} onChange={(e) => setForm({ ...form, points: e.target.value })} /></label>
        <div className="hall-admin-form-actions">
          <button className="primary-action" disabled={busy} type="submit">{busy ? "Salvando…" : editingId !== null ? "Atualizar colocação" : "Salvar colocação"}</button>
          {editingId !== null ? <button className="secondary-action" type="button" onClick={cancelEdit}>Cancelar</button> : null}
        </div>
      </form>
    </section>
    <section className="panel hall-admin-list"><div className="panel__heading"><div><p className="eyebrow">Histórico</p><h2>Registros atuais</h2></div><small>{data?.records.length ?? 0} registros</small></div>{!data ? <div className="calendar-state">Carregando…</div> : <div className="table-scroll"><table><thead><tr><th>Temporada</th><th>Participante</th><th>Posição</th><th>Pontos</th><th /></tr></thead><tbody>{data.records.map((r) => <tr key={r.id}><td>{r.season}</td><td>{r.participant}</td><td>{r.position}º</td><td>{r.points}</td><td className="hall-admin-actions"><button className="table-action" type="button" onClick={() => startEdit(r)}>Editar</button><button className="table-action table-action--danger" type="button" onClick={() => remove(r.id)}>Remover</button></td></tr>)}</tbody></table></div>}</section>
  </div>;
}
