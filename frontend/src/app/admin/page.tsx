import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { AdminCatalogView } from "@/components/admin-catalog-view";
export const metadata: Metadata = { title: "Gestão administrativa" };
export default function AdminPage() { return <AppShell><AdminCatalogView /></AppShell>; }
