"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { OrganizationSwitcher } from "./organization-switcher";
import { t } from "@/lib/i18n";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/strategy", label: "Estrategia IA", icon: "🎯" },
  { href: "/properties", label: "M1 — Propriedades", icon: "🏠" },
  { href: "/market", label: "M2 — Mercado", icon: "📈" },
  { href: "/financial", label: "M3 — Financeiro", icon: "💰" },
  { href: "/pipeline", label: "M4 — Pipeline", icon: "🔄" },
  { href: "/due-diligence", label: "M5 — Due Diligence", icon: "📋" },
  { href: "/renovation", label: "M6 — Obra", icon: "🔨" },
  { href: "/marketing", label: "M7 — Marketing", icon: "📣" },
  { href: "/leads", label: "M8 — Leads CRM", icon: "👥" },
  { href: "/closing", label: "M9 — Fecho + P&L", icon: "✅" },
];

const ADMIN_ITEMS = [
  { href: "/admin/invites", label: "Convites", icon: "✉️" },
  { href: "/admin/members", label: "Membros", icon: "🔑" },
  { href: "/admin/runs", label: "Execucoes Pipeline", icon: "📜" },
  { href: "/admin/dlq", label: "Dead-letter Queue", icon: "🪣" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, activeOrg, signOut } = useAuth();

  return (
    <aside className="sidebar-nav min-h-screen bg-white border-r border-slate-200 flex flex-col">
      <div className="sidebar-header p-6 border-b border-slate-200">
        <h1 className="text-xl font-bold text-teal-700">ImoIA</h1>
        <p className="sidebar-subtitle text-xs text-slate-500 mt-1">
          {activeOrg?.name ?? t("app.tagline")}
        </p>
      </div>

      <OrganizationSwitcher />

      <nav className="flex-1 p-3 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors whitespace-nowrap overflow-hidden",
                isActive
                  ? "bg-teal-50 text-teal-700 font-medium"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              )}
            >
              <span className="text-base flex-shrink-0">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}

        {/* Admin: visivel apenas para admin/owner */}
        {(activeOrg?.role === "admin" || activeOrg?.role === "owner") && (
          <>
            <div className="pt-3 pb-1 px-3">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Admin
              </span>
            </div>
            {ADMIN_ITEMS.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors whitespace-nowrap overflow-hidden",
                    isActive
                      ? "bg-teal-50 text-teal-700 font-medium"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  )}
                >
                  <span className="text-base flex-shrink-0">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </>
        )}
      </nav>

      {/* Footer: user + logout */}
      <div className="p-4 border-t border-slate-200">
        {user && (
          <div className="flex items-center justify-between">
            <span
              className="text-xs text-slate-500 truncate max-w-[160px]"
              title={user.email ?? ""}
            >
              {user.email}
            </span>
            <button
              onClick={signOut}
              className="text-xs text-slate-400 hover:text-red-600 transition-colors"
            >
              {t("auth.logout")}
            </button>
          </div>
        )}
        <p className="text-xs text-slate-400 mt-2">ImoIA v0.3.0</p>
      </div>
    </aside>
  );
}
