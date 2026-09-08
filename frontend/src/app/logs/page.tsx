import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { LogsView } from "@/components/logs-view";

export const metadata: Metadata = { title: "Logs e auditoria" };

export default function LogsPage() {
  return <AppShell><LogsView /></AppShell>;
}
