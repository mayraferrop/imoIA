"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Sidebar } from "./sidebar";
import { RenderWake } from "@/components/render-wake";
import { t } from "@/lib/i18n";

const AUTH_PAGES = ["/login", "/signup"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading } = useAuth();

  // Paginas de auth: sem sidebar, sem loading gate
  if (AUTH_PAGES.includes(pathname)) {
    return <>{children}</>;
  }

  // Enquanto o auth context carrega
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <p className="text-slate-400 text-sm">{t("common.loading")}</p>
      </div>
    );
  }

  return (
    <>
      <RenderWake />
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 bg-slate-50 p-8">{children}</main>
      </div>
    </>
  );
}
