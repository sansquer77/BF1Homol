import type { Metadata } from "next";
import { BrandMark } from "@/components/brand-mark";
import { FlagIcon } from "@/components/icons";
import { LoginForm } from "@/components/login-form";

export const metadata: Metadata = { title: "Entrar" };

export default function LoginPage() {
  return <main className="login-page"><section className="login-visual" aria-label="BF1, o bolão de Fórmula 1"><BrandMark /><div className="login-visual__copy"><p className="eyebrow">Temporada 2026</p><h1>Seu palpite.<br />Sua estratégia.<br /><em>Sua corrida.</em></h1><p>Dezenas de pilotos, uma única decisão: quem você escala para vencer?</p></div><div className="finish-line" aria-hidden="true" /></section><section className="login-panel"><div className="login-card"><span className="mobile-login-brand"><BrandMark /></span><span className="login-icon" aria-hidden="true"><FlagIcon /></span><p className="eyebrow">Área do participante</p><h2>Bem-vindo de volta</h2><p className="login-card__intro">Entre com o acesso enviado pelo administrador do seu bolão.</p><LoginForm /><p className="invite-note">O BF1 é exclusivo para convidados.<br />Não existe cadastro público.</p></div><footer>© 2026 BF1 · Bolão Fórmula 1</footer></section></main>;
}
