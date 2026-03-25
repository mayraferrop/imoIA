import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";

export const metadata: Metadata = {
  title: "ImoIA — Gestao de Investimento Imobiliario",
  description: "Plataforma de gestao de investimento imobiliario fix and flip",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt">
      <body className="antialiased">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 bg-slate-50 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
