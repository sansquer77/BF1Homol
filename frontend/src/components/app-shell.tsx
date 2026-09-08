"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { BrandMark } from "./brand-mark";
import { CalendarIcon, ChartIcon, CloseIcon, GridIcon, MenuIcon, TrophyIcon } from "./icons";

const primaryNavigation = [
  { label: "Telemetria", href: "/", icon: GridIcon },
  { label: "Calendário", href: "#calendario", icon: CalendarIcon },
  { label: "Classificação", href: "#classificacao", icon: TrophyIcon },
  { label: "Análises", href: "#analises", icon: ChartIcon },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <div className="app-shell">
    <a className="skip-link" href="#conteudo">Ir para o conteúdo</a>
    <header className="mobile-header"><BrandMark compact /><button className="icon-button" type="button" aria-label={open ? "Fechar menu" : "Abrir menu"} aria-expanded={open} onClick={() => setOpen((value) => !value)}>{open ? <CloseIcon /> : <MenuIcon />}</button></header>
    <button className={open ? "nav-scrim nav-scrim--open" : "nav-scrim"} aria-label="Fechar menu" type="button" onClick={() => setOpen(false)} />
    <aside className={open ? "sidebar sidebar--open" : "sidebar"} aria-label="Navegação principal">
      <BrandMark />
      <nav><p className="eyebrow">Campeonato 2026</p>{primaryNavigation.map(({ label, href, icon: Icon }, index) => <Link key={label} href={href} className={index === 0 ? "nav-link nav-link--active" : "nav-link"} onClick={() => setOpen(false)}><Icon /><span>{label}</span></Link>)}</nav>
      <div className="sidebar__footer"><span className="avatar" aria-hidden="true">MS</span><span><strong>Marcos Silva</strong><small>Participante</small></span><Link href="/login" className="text-link">Sair</Link></div>
    </aside>
    <main id="conteudo" className="main-content">{children}</main>
  </div>;
}
