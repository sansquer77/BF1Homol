import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { FinancialAdminView } from "@/components/financial-admin-view";
export const metadata: Metadata = { title: "Gestão financeira" };
export default function FinancialPage(){return <AppShell><FinancialAdminView/></AppShell>}
