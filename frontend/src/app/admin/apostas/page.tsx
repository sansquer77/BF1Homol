import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { BetsAdminView } from "@/components/bets-admin-view";

export const metadata: Metadata = { title: "Gestão de apostas" };

export default function BetsAdminPage() {
  return <AppShell><BetsAdminView /></AppShell>;
}
