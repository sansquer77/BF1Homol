import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { ChampionshipAdminView } from "@/components/championship-admin-view";

export const metadata: Metadata = { title: "Gestão das apostas do campeonato" };
export default function ChampionshipAdminPage() { return <AppShell><ChampionshipAdminView /></AppShell>; }
