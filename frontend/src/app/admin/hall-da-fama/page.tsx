import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { HallAdminView } from "@/components/hall-admin-view";

export const metadata: Metadata = { title: "Gestão do Hall da Fama" };

export default function HallAdminPage() {
  return <AppShell><HallAdminView /></AppShell>;
}
