"use client";

import { useAuth } from "@/lib/auth-context";
import { t } from "@/lib/i18n";

export function OrganizationSwitcher() {
  const { organizations, activeOrg, setActiveOrg } = useAuth();

  // Esconder quando so tem 1 org (ou 0)
  if (organizations.length <= 1) return null;

  return (
    <div className="px-3 py-2">
      <label className="block text-xs font-medium text-slate-400 mb-1 px-3">
        {t("org_switcher.label")}
      </label>
      <select
        value={activeOrg?.id ?? ""}
        onChange={(e) => {
          const org = organizations.find((o) => o.id === e.target.value);
          if (org) setActiveOrg(org);
        }}
        className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-500"
      >
        {organizations.map((org) => (
          <option key={org.id} value={org.id}>
            {org.name}
          </option>
        ))}
      </select>
    </div>
  );
}
