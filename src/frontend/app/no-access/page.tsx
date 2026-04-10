"use client";

import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { t } from "@/lib/i18n";

export default function NoAccessPage() {
  const supabase = createClient();
  const router = useRouter();

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white rounded-xl border border-slate-200 p-8 max-w-md w-full text-center">
        <h2 className="text-xl font-bold text-slate-900 mb-2">
          {t("auth.no_access.title")}
        </h2>
        <p className="text-sm text-slate-600 mb-4">
          {t("auth.no_access.message")}
        </p>
        <p className="text-sm text-slate-500 mb-6">
          {t("auth.no_access.contact")}
        </p>
        <button
          onClick={handleLogout}
          className="py-2.5 px-6 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 transition-colors"
        >
          {t("auth.no_access.logout")}
        </button>
      </div>
    </div>
  );
}
