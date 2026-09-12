"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api/client";

type Participant = { user_id: number; name: string; email: string; paid: boolean };
type Summary = { participants_total: number; paid_total: number; pending_total: number; collected: number; outstanding: number; total_due: number };
type Prizes = { winner: number; runner_up: number; third: number; administration: number };
type Finance = { season: string; fee: number; participants: Participant[]; summary: Summary; prizes: Prizes };

const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const emptySummary: Summary = { participants_total: 0, paid_total: 0, pending_total: 0, collected: 0, outstanding: 0, total_due: 0 };
const emptyPrizes: Prizes = { winner: 0, runner_up: 0, third: 0, administration: 0 };

export function FinancialAdminView() {
  const [season, setSeason] = useState(String(new Date().getFullYear()));
  const [fee, setFee] = useState("0");
  const [rows, setRows] = useState<Participant[]>([]);
  const [summary, setSummary] = useState(emptySummary);
  const [prizes, setPrizes] = useState(emptyPrizes);
  const [pendingOnly, setPendingOnly] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const applyResponse = useCallback((value: Finance) => {
    setFee(String(value.fee));
    setRows(value.participants);
    setSummary(value.summary);
    setPrizes(value.prizes);
  }, []);

  const load = useCallback(async () => {
    if (!/^\d{4}$/.test(season)) return;
    setBusy(true); setError(""); setNotice("");
    try { applyResponse(await apiRequest<Finance>(`/api/v1/admin/financial?season=${season}`)); }
    catch { setError("Acesso restrito ao Master ou serviço indisponível."); }
    finally { setBusy(false); }
  }, [applyResponse, season]);

  useEffect(() => { void load(); }, [load]);

  const visibleRows = useMemo(() => pendingOnly ? rows.filter((item) => !item.paid) : rows, [pendingOnly, rows]);
  const toggle = (id: number) => setRows((current) => current.map((item) => item.user_id === id ? { ...item, paid: !item.paid } : item));

  const save = async () => {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest("/api/v1/admin/financial", { method: "PUT", body: JSON.stringify({ season, fee: Number(fee), payments: rows.map((item) => ({ user_id: item.user_id, paid: item.paid })) }) });
      applyResponse(await apiRequest<Finance>(`/api/v1/admin/financial?season=${season}`));
      setNotice("Financeiro salvo com sucesso.");
    } catch { setError("Não foi possível salvar o financeiro."); }
    finally { setBusy(false); }
  };

  const remind = async () => {
    if (!window.confirm(`Enviar lembrete aos ${summary.pending_total} participantes pendentes de ${season}?`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<{ recipients: number }>(`/api/v1/admin/financial/reminder?season=${season}`, { method: "POST" });
      setNotice(`Lembrete enviado em CCO para ${result.recipients} participante(s).`);
    } catch { setError("Não foi possível enviar o lembrete aos participantes pendentes."); }
    finally { setBusy(false); }
  };

  return <div className="admin-catalog-view financial-admin-view">
    <header className="institutional-hero"><p className="eyebrow">Administração</p><h1>Financeiro da temporada.</h1><p>Controle a taxa, pagamentos, fundo previsto e distribuição da premiação.</p></header>
    <div className="admin-tabs financial-toolbar">
      <label className="admin-season">Temporada<input inputMode="numeric" maxLength={4} value={season} onChange={(event) => setSeason(event.target.value.replace(/\D/g, ""))}/></label>
      <label className="admin-season">Taxa individual<input type="number" min="0" step="0.01" value={fee} onChange={(event) => setFee(event.target.value)}/></label>
      <button className="primary-action" disabled={busy || !/^\d{4}$/.test(season)} onClick={save}>{busy ? "Aguarde…" : "Salvar financeiro"}</button>
    </div>
    {error && <div className="calendar-state calendar-state--error" role="alert">{error}</div>}
    {notice && <div className="bet-notice bet-notice--success" role="status">{notice}</div>}

    <section className="financial-metrics" aria-label="Resumo financeiro">
      <article><span>Participantes</span><strong>{summary.participants_total}</strong></article><article><span>Pagos</span><strong>{summary.paid_total}</strong></article><article><span>Pendentes</span><strong>{summary.pending_total}</strong></article>
      <article><span>Total previsto</span><strong>{currency.format(summary.total_due)}</strong></article><article><span>Arrecadado</span><strong>{currency.format(summary.collected)}</strong></article><article><span>A receber</span><strong>{currency.format(summary.outstanding)}</strong></article>
    </section>

    <section className="financial-grid">
      <article className="panel financial-prizes"><div className="panel__heading"><h2>Distribuição prevista</h2><small>Sobre o fundo total</small></div><dl><div><dt>Campeão · 40%</dt><dd>{currency.format(prizes.winner)}</dd></div><div><dt>Vice · 30%</dt><dd>{currency.format(prizes.runner_up)}</dd></div><div><dt>3º colocado · 20%</dt><dd>{currency.format(prizes.third)}</dd></div><div><dt>Administração · 10%</dt><dd>{currency.format(prizes.administration)}</dd></div></dl></article>
      <article className="panel financial-reminder"><p className="eyebrow">Cobrança</p><h2>Lembrete aos pendentes</h2><p>O servidor seleciona somente os participantes não pagos com e-mail válido e envia a mensagem em CCO.</p><button className="secondary-action" disabled={busy || summary.pending_total === 0} onClick={remind}>Enviar lembrete</button></article>
    </section>

    <section className="panel admin-list"><div className="panel__heading"><div><p className="eyebrow">Pagamentos</p><h2>Participantes da temporada</h2></div><label className="financial-filter"><input type="checkbox" checked={pendingOnly} onChange={(event) => setPendingOnly(event.target.checked)}/> Mostrar apenas pendentes</label></div>
      <div className="table-scroll"><table><thead><tr><th>Participante</th><th>E-mail</th><th>Status</th><th>Ação</th></tr></thead><tbody>{visibleRows.map((item) => <tr key={item.user_id}><td>{item.name}</td><td>{item.email || "—"}</td><td><span className={item.paid ? "status-pill status-pill--paid" : "status-pill status-pill--pending"}>{item.paid ? "Pago" : "Pendente"}</span></td><td><button className="table-action" onClick={() => toggle(item.user_id)}>{item.paid ? "Marcar pendente" : "Marcar pago"}</button></td></tr>)}{!busy && visibleRows.length === 0 && <tr><td colSpan={4}>Nenhum participante encontrado para este filtro.</td></tr>}</tbody></table></div>
    </section>
  </div>;
}
