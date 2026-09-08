import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { ClassificationView } from "@/components/classification-view";

export const metadata: Metadata = { title: "Classificação" };

export default function ClassificationPage() {
  return <AppShell><ClassificationView /></AppShell>;
}
