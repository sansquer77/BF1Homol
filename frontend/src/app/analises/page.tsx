import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { BetsAnalysisView } from "@/components/bets-analysis-view";

export const metadata: Metadata = { title: "Análise de Apostas" };

export default function AnalysisPage() {
  return <AppShell><BetsAnalysisView /></AppShell>;
}
