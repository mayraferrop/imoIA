import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { AppShell } from "@/components/layout/app-shell";
import { SWRProvider } from "@/lib/swr-provider";

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
        <script
          dangerouslySetInnerHTML={{
            __html: `fetch("https://imoia.onrender.com/health",{method:"HEAD"}).catch(function(){})`,
          }}
        />
        <AuthProvider>
          <SWRProvider>
            <AppShell>{children}</AppShell>
          </SWRProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
