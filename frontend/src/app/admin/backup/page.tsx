import type { Metadata } from "next";import{AppShell}from"@/components/app-shell";import{BackupAdminView}from"@/components/backup-admin-view";
export const metadata:Metadata={title:"Backup e restauração"};export default function BackupPage(){return <AppShell><BackupAdminView/></AppShell>}
