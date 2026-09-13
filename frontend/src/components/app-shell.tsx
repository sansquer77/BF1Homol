"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { apiRequest, type User } from "@/lib/api/client";
import { SeasonProvider, SeasonSelector } from "@/lib/season-context";
import { BrandMark } from "./brand-mark";
import { BookIcon, CalendarIcon, ChartIcon, CloseIcon, FlagIcon, GridIcon, InfoIcon, MenuIcon, TrophyIcon } from "./icons";

type Item = { label: string; href: string; icon: typeof GridIcon; roles?: string[] };
type Group = { label: string; items: Item[] };
const groups: Group[] = [
  { label: "Corrida", items: [{ label: "Telemetria", href: "/", icon: GridIcon }, { label: "Fazer minha aposta", href: "/apostas", icon: TrophyIcon }, { label: "Calendário", href: "/calendario", icon: CalendarIcon }, { label: "Classificação", href: "/classificacao", icon: TrophyIcon }] },
  { label: "Status BF1", items: [{ label: "Análises", href: "/analises", icon: ChartIcon }, { label: "Campeonato", href: "/campeonato", icon: TrophyIcon }] },
  { label: "História", items: [{ label: "Hall da Fama", href: "/hall-da-fama", icon: TrophyIcon }, { label: "Dashboard F1", href: "/dashboard-f1", icon: ChartIcon }] },
  { label: "Informações", items: [{ label: "Logs", href: "/logs", icon: BookIcon }, { label: "Regulamento", href: "/regulamento", icon: BookIcon }, { label: "Sobre", href: "/sobre", icon: InfoIcon }] },
  { label: "Administração", items: [{ label: "Cadastros", href: "/admin", icon: GridIcon, roles: ["admin", "master"] }, { label: "Resultados", href: "/admin/resultados", icon: FlagIcon, roles: ["admin", "master"] }, { label: "Regras", href: "/admin/regras", icon: BookIcon, roles: ["master"] }, { label: "Financeiro", href: "/admin/financeiro", icon: ChartIcon, roles: ["master"] }, { label: "Hall da Fama", href: "/admin/hall-da-fama", icon: TrophyIcon, roles: ["master"] }, { label: "Backup e restauração", href: "/admin/backup", icon: BookIcon, roles: ["master"] }] },
];

function itemIsActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const activeGroup = useMemo(() => groups.find((group) => group.items.some((item) => itemIsActive(pathname, item.href)))?.label ?? "Corrida", [pathname]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => ({ [activeGroup]: true }));

  useEffect(() => { let active = true; apiRequest<User>("/api/v1/auth/me").then((value) => { if (active) setUser(value); }).catch(() => router.replace("/login")); return () => { active = false; }; }, [router]);
  useEffect(() => { setExpanded((current) => ({ ...current, [activeGroup]: true })); }, [activeGroup]);
  async function logout() { try { await apiRequest("/api/v1/auth/logout", { method: "POST" }); } finally { router.replace("/login"); router.refresh(); } }
  if (!user) return <main className="status-page" aria-busy="true"><BrandMark /><p>Validando sua sessão…</p></main>;
  const initials = user.nome.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();

  return <SeasonProvider><div className="app-shell"><a className="skip-link" href="#conteudo">Ir para o conteúdo</a><header className="mobile-header"><BrandMark compact /><button type="button" className="icon-button" aria-label={mobileOpen ? "Fechar menu" : "Abrir menu"} onClick={() => setMobileOpen((value) => !value)}>{mobileOpen ? <CloseIcon /> : <MenuIcon />}</button></header><button type="button" className={mobileOpen ? "nav-scrim nav-scrim--open" : "nav-scrim"} aria-label="Fechar menu" onClick={() => setMobileOpen(false)} /><aside className={mobileOpen ? "sidebar sidebar--open" : "sidebar"}><BrandMark /><nav aria-label="Navegação principal">{groups.map((group) => { const items = group.items.filter((item) => !item.roles || item.roles.includes(user.perfil)); if (!items.length) return null; const isExpanded = Boolean(expanded[group.label]); const containsActive = items.some((item) => itemIsActive(pathname, item.href)); return <section className={isExpanded ? "nav-group nav-group--expanded" : "nav-group"} key={group.label}><button type="button" className="nav-group__toggle" aria-expanded={isExpanded} onClick={() => setExpanded((current) => ({ ...current, [group.label]: !isExpanded }))}><span className="eyebrow">{group.label}</span><span className="nav-group__chevron" aria-hidden="true">›</span>{containsActive && !isExpanded ? <span className="sr-only">contém a página atual</span> : null}</button><div className="nav-group__items" hidden={!isExpanded}>{items.map(({ label, href, icon: Icon }) => { const active = itemIsActive(pathname, href); return <Link key={`${group.label}-${label}`} href={href} aria-current={active ? "page" : undefined} className={active ? "nav-link nav-link--active" : "nav-link"} onClick={() => setMobileOpen(false)}><Icon /><span>{label}</span></Link>; })}</div></section>; })}</nav><SeasonSelector /><div className="sidebar__footer"><span className="avatar">{initials}</span><span><strong>{user.nome}</strong><small>{user.perfil}</small></span><button type="button" className="text-link" onClick={logout}>Sair</button></div></aside><main id="conteudo" className="main-content">{children}</main></div></SeasonProvider>;
}
