"use client";

import { useState } from "react";
import { ApiRequestError, apiRequest } from "@/lib/api/client";

export function BackupAdminView() {
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"info" | "success" | "error">("info");
  const [busy, setBusy] = useState(false);
  const notify = (text: string, kind: "info" | "success" | "error" = "info") => { setMessage(text); setMessageKind(kind); };

  const download = async () => {
    const response = await fetch("/api/v1/backup/sql", { credentials: "include" });
    if (!response.ok) { notify("Acesso restrito ao Master.", "error"); return; }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "bf1_backup_v4.sql";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const restore = async () => {
    if (!file) { notify("Selecione um arquivo SQL.", "error"); return; }
    if (!password) { notify("Informe a senha do Master para confirmar a restauração.", "error"); return; }
    setBusy(true);
    notify("Validando o arquivo…");
    try {
      await apiRequest("/api/v1/backup/validate/sql", { method: "POST", body: file });
    } catch (error) {
      notify(error instanceof ApiRequestError ? `Backup recusado na validação (${error.status}).` : "Não foi possível validar o backup.", "error");
      setBusy(false);
      return;
    }
    notify("Confirmando a senha do Master…");
    try {
      await apiRequest("/api/v1/backup/reauthorize", { method: "POST", body: JSON.stringify({ password }) });
    } catch (error) {
      notify(error instanceof ApiRequestError && error.status === 403 ? "Senha do Master não confirmada." : "Não foi possível autorizar a restauração.", "error");
      setBusy(false);
      return;
    }
    notify("Restaurando o banco…");
    try {
      await apiRequest("/api/v1/backup/restore/sql", { method: "POST", headers: { "X-File-Name": file.name }, body: file });
      setPassword("");
      notify("Restauração concluída. Valide o schema e execute as comparações da homologação.", "success");
    } catch (error) {
      notify(error instanceof ApiRequestError ? `A restauração foi recusada pelo servidor (${error.status}). Consulte os logs administrativos.` : "Não foi possível concluir a restauração.", "error");
    } finally { setBusy(false); }
  };

  return <div className="admin-catalog-view backup-admin-view">
    <header className="institutional-hero"><p className="eyebrow">Continuidade</p><h1>Backup e restauração.</h1><p>Exporte o PostgreSQL e restaure um artefato V3.x após reautenticação do Master.</p></header>
    <div className="backup-admin-grid">
      <section className="panel backup-card">
        <div className="backup-card__heading"><span>01</span><div><h2>Exportar backup SQL</h2><p>Gere uma cópia do banco atual antes de iniciar qualquer restauração.</p></div></div>
        <button className="primary-action" type="button" onClick={download}>Baixar backup SQL</button>
      </section>
      <section className="panel backup-card backup-card--danger">
        <div className="backup-card__heading"><span>02</span><div><h2>Restaurar backup SQL</h2><p>Esta operação substitui dados. Confirme sua identidade e escolha o arquivo V3.x.</p></div></div>
        <div className="backup-form-fields">
          <label><span>Senha do Master</span><input type="password" autoComplete="current-password" value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} /></label>
          <label><span>Arquivo SQL</span><input type="file" accept=".sql,text/plain,application/sql" disabled={busy} onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
        </div>
        <div className="backup-card__action"><button className="primary-action" type="button" disabled={busy} onClick={restore}>{busy ? "Processando…" : "Reautenticar e restaurar"}</button><small>Limite configurado pelo servidor. O conteúdo do arquivo não é registrado nos logs.</small></div>
        {message && <div className={`backup-notice backup-notice--${messageKind}`} role={messageKind === "error" ? "alert" : "status"} aria-live="polite">{message}</div>}
      </section>
    </div>
  </div>;
}
