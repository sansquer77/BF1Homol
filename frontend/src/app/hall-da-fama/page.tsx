import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { HallOfFameView } from "@/components/hall-of-fame-view";

export const metadata: Metadata = { title: "Hall da Fama" };

export default function HallOfFamePage() {
  return <AppShell><HallOfFameView /></AppShell>;
}
