"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSeason } from "@/lib/season-context";

export function ParticipantTabs() {
  const pathname = usePathname(); const { season } = useSeason();
  const tabs = [{ href: "/", label: "Visão geral" }, { href: "/telemetria/apostas", label: `Apostas - ${season}` }, { href: "/telemetria/historico", label: "Histórico" }, { href: "/telemetria/minha-conta", label: "Minha conta" }];
  return <nav className="participant-tabs" aria-label="Áreas da Telemetria">{tabs.map((tab) => <Link key={tab.href} href={tab.href} aria-current={pathname === tab.href ? "page" : undefined} className={pathname === tab.href ? "participant-tab participant-tab--active" : "participant-tab"}>{tab.label}</Link>)}</nav>;
}
