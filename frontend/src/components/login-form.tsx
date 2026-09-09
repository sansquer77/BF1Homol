"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiRequest, login } from "@/lib/api/client";

type Mode = "login" | "request" | "confirm";

export function LoginForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login"); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [email, setEmail] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const submittedEmail = String(form.get("email") ?? email); setEmail(submittedEmail); setBusy(true); setError(""); setNotice("");
    try {
      if (mode === "login") { await login({ email: submittedEmail, password: String(form.get("password") ?? "") }); router.replace("/"); router.refresh(); return; }
      if (mode === "request") { await apiRequest("/api/v1/auth/password-reset", { method: "POST", body: JSON.stringify({ email: submittedEmail }) }); setMode("confirm"); setNotice("Se o e-mail estiver cadastrado, as instruções foram enviadas."); }
      else { await apiRequest("/api/v1/auth/password-reset/confirm", { method: "POST", body: JSON.stringify({ email: submittedEmail, token: String(form.get("token") ?? ""), new_password: String(form.get("new_password") ?? "") }) }); setMode("login"); setNotice("Senha redefinida. Entre com a nova senha."); }
    } catch (reason) { const status = typeof reason === "object" && reason && "status" in reason ? Number(reason.status) : 0; setError(status === 429 ? "Muitas tentativas. Aguarde 15 minutos e tente novamente." : mode === "login" ? "Não foi possível entrar. Confira os dados e tente novamente." : "Não foi possível concluir a recuperação."); }
    finally { setBusy(false); }
  }
  return <form className="login-form" onSubmit={submit}>{notice ? <p className="form-notice" role="status">{notice}</p> : null}<div className="field"><label htmlFor="email">E-mail</label><input id="email" name="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></div>{mode === "login" ? <div className="field"><div className="field__label"><label htmlFor="password">Senha</label><button className="text-link" type="button" onClick={() => setMode("request")}>Esqueci minha senha</button></div><input id="password" name="password" type="password" autoComplete="current-password" required /></div> : null}{mode === "confirm" ? <><div className="field"><label htmlFor="token">Código recebido</label><input id="token" name="token" autoComplete="one-time-code" required minLength={16} /></div><div className="field"><label htmlFor="new_password">Nova senha</label><input id="new_password" name="new_password" type="password" autoComplete="new-password" required minLength={8} /></div></> : null}{error ? <p className="form-error" role="alert">{error}</p> : null}<button className="login-button" type="submit" disabled={busy}>{busy ? "Aguarde…" : mode === "login" ? "Entrar" : mode === "request" ? "Enviar código" : "Redefinir senha"}<span aria-hidden="true">→</span></button>{mode !== "login" ? <button className="text-link" type="button" onClick={() => { setMode("login"); setError(""); }}>Voltar ao login</button> : null}</form>;
}
