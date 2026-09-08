import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { ChampionshipView } from "@/components/championship-view";

export const metadata: Metadata = { title: "Campeonato" };

export default function ChampionshipPage() {
  return <AppShell><ChampionshipView /></AppShell>;
}
