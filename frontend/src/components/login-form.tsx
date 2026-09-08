"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api/client";

export function LoginForm() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await login({ email: String(form.get("email") ?? ""), password: String(form.get("password") ?? "") });
      router.replace("/");
      router.refresh();
    } catch {
      setError("Não foi possível entrar. Confira os dados e tente novamente.");
      setBusy(false);
    }
  }

  return <form className="login-form" onSubmit={handleSubmit} aria-describedby={error ? "login-error" : undefined}><div className="field"><label htmlFor="email">E-mail</label><input id="email" name="email" type="email" autoComplete="email" inputMode="email" placeholder="voce@exemplo.com" required /></div><div className="field"><div className="field__label"><label htmlFor="password">Senha</label><a href="#recuperar">Esqueci minha senha</a></div><input id="password" name="password" type="password" autoComplete="current-password" required /></div>{error ? <p id="login-error" className="form-error" role="alert">{error}</p> : null}<button className="login-button" type="submit" disabled={busy}>{busy ? "Entrando…" : "Entrar"}<span aria-hidden="true">→</span></button></form>;
}
