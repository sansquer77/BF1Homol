"use client";

import { useEffect, useState } from "react";
import { ApiRequestError, apiRequest } from "@/lib/api/client";

type MessageKind = "info" | "success" | "error";
type ExcelRestoreResult = { table: string; rows: number; mode: "replace" | "upsert" };

function saveResponse(response: Response, fallbackName: string) {
  return response.blob().then((blob) => {
    const disposition = response.headers.get("content-disposition") || "";
    const filename = disposition.match(/filename="([^"]+)"/)?.[1] || fallbackName;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = filename; anchor.click();
    URL.revokeObjectURL(url);
  });
}

export function BackupAdminView() {
  const [sqlFile, setSqlFile] = useState<File | null>(null);
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [excelTables, setExcelTables] = useState<string[]>([]);
  const [excelTable, setExcelTable] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<MessageKind>("info");
  const [busy, setBusy] = useState(false);
  const notify = (text: string, kind: MessageKind = "info") => { setMessage(text); setMessageKind(kind); };

  useEffect(() => {
    apiRequest<string[]>("/api/v1/backup/excel/tables").then((tables) => {
      setExcelTables(tables); setExcelTable((current) => current || tables[0] || "");
    }).catch(() => notify("Não foi possível carregar as tabelas disponíveis para Excel.", "error"));
  }, []);

  const downloadSql = async () => {
    const response = await fetch("/api/v1/backup/sql", { credentials: "include" });
    if (!response.ok) { notify("Acesso restrito ao Master.", "error"); return; }
    await saveResponse(response, "bf1_backup_v4.sql");
  };

  const downloadExcel = async () => {
    if (!excelTable) { notify("Selecione uma tabela para exportar.", "error"); return; }
    const response = await fetch(`/api/v1/backup/excel/${encodeURIComponent(excelTable)}`, { credentials: "include" });
    if (!response.ok) { notify("Não foi possível exportar a tabela em Excel.", "error"); return; }
    await saveResponse(response, `${excelTable}_backup_v4.xlsx`);
  };

  const reauthorize = () => apiRequest("/api/v1/backup/reauthorize", { method: "POST", body: JSON.stringify({ password }) });

  const restoreSql = async () => {
    if (!sqlFile) { notify("Selecione um arquivo SQL.", "error"); return; }
    if (!password) { notify("Informe a senha do Master para confirmar a restauração.", "error"); return; }
    setBusy(true); notify("Validando o arquivo SQL…");
    try {
      await apiRequest("/api/v1/backup/validate/sql", { method: "POST", body: sqlFile });
      notify("Confirmando a senha do Master…");
      await reauthorize();
      notify("Restaurando o banco…");
      await apiRequest("/api/v1/backup/restore/sql", { method: "POST", headers: { "X-File-Name": sqlFile.name }, body: sqlFile });
      setPassword(""); notify("Restauração SQL concluída. Valide o schema e as comparações da homologação.", "success");
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 403) notify("Senha do Master não confirmada ou autorização expirada.", "error");
      else notify(error instanceof ApiRequestError ? `A restauração SQL foi recusada (${error.status}). Consulte os logs administrativos.` : "Não foi possível concluir a restauração SQL.", "error");
    } finally { setBusy(false); }
  };

  const restoreExcel = async () => {
    if (!excelTable) { notify("Selecione a tabela de destino.", "error"); return; }
    if (!excelFile) { notify("Selecione um arquivo Excel.", "error"); return; }
    if (!password) { notify("Informe a senha do Master para confirmar a restauração.", "error"); return; }
    const tablePath = encodeURIComponent(excelTable);
    setBusy(true); notify("Validando o arquivo Excel e suas colunas…");
    try {
      await apiRequest(`/api/v1/backup/validate/excel/${tablePath}`, { method: "POST", body: excelFile });
      notify("Confirmando a senha do Master…");
      await reauthorize();
      notify(`Restaurando a tabela ${excelTable}…`);
      const result = await apiRequest<ExcelRestoreResult>(`/api/v1/backup/restore/excel/${tablePath}`, { method: "POST", headers: { "X-File-Name": excelFile.name }, body: excelFile });
      setPassword("");
      notify(`Tabela ${result.table} restaurada: ${result.rows} linha(s), modo ${result.mode === "upsert" ? "atualização segura" : "substituição"}.`, "success");
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 403) notify("Senha do Master não confirmada ou autorização expirada.", "error");
      else notify(error instanceof ApiRequestError ? `O Excel foi recusado pelo servidor (${error.status}). Confira a tabela selecionada e os logs.` : "Não foi possível restaurar o arquivo Excel.", "error");
    } finally { setBusy(false); }
  };

  return <div className="admin-catalog-view backup-admin-view">
    <header className="institutional-hero"><p className="eyebrow">Continuidade</p><h1>Backup e restauração.</h1><p>Exporte o PostgreSQL ou tabelas Excel e restaure artefatos V3.x após reautenticação do Master.</p></header>
    {message && <div className={`backup-notice backup-notice--${messageKind}`} role={messageKind === "error" ? "alert" : "status"} aria-live="polite">{message}</div>}
    <div className="backup-admin-grid">
      <section className="panel backup-card">
        <div className="backup-card__heading"><span>01</span><div><h2>Exportar backup SQL</h2><p>Gere uma cópia integral antes de iniciar qualquer restauração.</p></div></div>
        <button className="primary-action" type="button" onClick={downloadSql}>Baixar backup SQL</button>
      </section>
      <section className="panel backup-card">
        <div className="backup-card__heading"><span>02</span><div><h2>Exportar tabela Excel</h2><p>Mantenha o formato de um arquivo por tabela usado pela versão 3.x.</p></div></div>
        <label className="backup-select"><span>Tabela</span><select value={excelTable} onChange={(event) => setExcelTable(event.target.value)}>{excelTables.map((table) => <option key={table} value={table}>{table}</option>)}</select></label>
        <button className="primary-action" type="button" disabled={!excelTable} onClick={downloadExcel}>Baixar tabela Excel</button>
      </section>
      <section className="panel backup-card backup-card--danger">
        <div className="backup-card__heading"><span>03</span><div><h2>Restaurar backup SQL</h2><p>Substitui os dados compatíveis do banco a partir do arquivo V3.x.</p></div></div>
        <div className="backup-form-fields"><label><span>Senha do Master</span><input type="password" autoComplete="current-password" value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} /></label><label><span>Arquivo SQL</span><input type="file" accept=".sql,text/plain,application/sql" disabled={busy} onChange={(event) => setSqlFile(event.target.files?.[0] || null)} /></label></div>
        <div className="backup-card__action"><button className="primary-action" type="button" disabled={busy} onClick={restoreSql}>{busy ? "Processando…" : "Reautenticar e restaurar SQL"}</button><small>O conteúdo do arquivo não é registrado nos logs.</small></div>
      </section>
      <section className="panel backup-card backup-card--danger">
        <div className="backup-card__heading"><span>04</span><div><h2>Restaurar tabela Excel</h2><p>Selecione explicitamente a tabela correspondente ao arquivo exportado pela V3.x.</p></div></div>
        <div className="backup-form-fields"><label><span>Senha do Master</span><input type="password" autoComplete="current-password" value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} /></label><label><span>Tabela de destino</span><select value={excelTable} disabled={busy} onChange={(event) => setExcelTable(event.target.value)}>{excelTables.map((table) => <option key={table} value={table}>{table}</option>)}</select></label><label><span>Arquivo Excel</span><input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={busy} onChange={(event) => setExcelFile(event.target.files?.[0] || null)} /></label></div>
        <div className="backup-card__action"><button className="primary-action" type="button" disabled={busy || !excelTable} onClick={restoreExcel}>{busy ? "Processando…" : "Reautenticar e restaurar Excel"}</button><small>FKs, limites, colunas obrigatórias e tipos PostgreSQL são validados antes da gravação.</small></div>
      </section>
    </div>
  </div>;
}
