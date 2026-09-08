import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { F1DashboardView } from "@/components/f1-dashboard-view";

export const metadata: Metadata = { title: "Dashboard F1" };

export default function F1DashboardPage() {
  return <AppShell><F1DashboardView /></AppShell>;
}
