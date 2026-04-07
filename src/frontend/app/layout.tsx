import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { AppShell } from "@/components/layout/app-shell";

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
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
