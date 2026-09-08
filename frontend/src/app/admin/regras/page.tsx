import type { Metadata } from "next"; import { AppShell } from "@/components/app-shell"; import { RulesAdminView } from "@/components/rules-admin-view";
export const metadata: Metadata={title:"Gestão de regras"}; export default function RulesPage(){return <AppShell><RulesAdminView/></AppShell>}
