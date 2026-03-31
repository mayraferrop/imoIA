import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { RenderWake } from "@/components/render-wake";

export const metadata: Metadata = {
  title: "ImoIA — Gestão de Investimento Imobiliário",
  description: "Plataforma de gestão de investimento imobiliário fix and flip",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt">
      <body className="antialiased">
        <RenderWake />
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 bg-slate-50 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
