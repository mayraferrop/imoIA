"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "📊" },
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

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar-nav min-h-screen bg-white border-r border-slate-200 flex flex-col">
      <div className="sidebar-header p-6 border-b border-slate-200">
        <h1 className="text-xl font-bold text-teal-700">ImoIA</h1>
        <p className="sidebar-subtitle text-xs text-slate-500 mt-1">
          Gestao de Investimento Imobiliario
        </p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
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
      </nav>

      <div className="p-4 border-t border-slate-200 text-xs text-slate-400">
        ImoIA v0.2.0
      </div>
    </aside>
  );
}
