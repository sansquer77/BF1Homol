import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { CalendarView } from "@/components/calendar-view";

export const metadata: Metadata = { title: "Calendário" };

export default function CalendarPage() {
  return <AppShell><CalendarView /></AppShell>;
}
