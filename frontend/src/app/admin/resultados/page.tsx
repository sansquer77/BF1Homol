import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { ResultsAdminView } from "@/components/results-admin-view";

export const metadata: Metadata = { title: "Atualização de resultados" };
export default function ResultsAdminPage() { return <AppShell><ResultsAdminView /></AppShell>; }
