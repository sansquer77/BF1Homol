import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "@fontsource/space-grotesk/600.css";
import "@fontsource/space-grotesk/700.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/600.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "BF1", template: "%s · BF1" },
  description: "Bolão de Fórmula 1 — estratégia, palpites e campeonato entre amigos.",
  icons: { icon: "/bf1-icon.png", apple: "/bf1-icon.png" },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0d0f12" };

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <html lang="pt-BR"><body>{children}</body></html>;
}
