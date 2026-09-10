import type { Metadata } from "next";import{AppShell}from"@/components/app-shell";import{RaceBetForm}from"@/components/race-bet-form";
export const metadata:Metadata={title:"Fazer minha aposta"};
export default function BetsPage(){return <AppShell><RaceBetForm/></AppShell>}
