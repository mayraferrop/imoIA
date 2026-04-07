"use client";

import { useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { t } from "@/lib/i18n";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [orgName, setOrgName] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const supabase = createClient();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    // signInWithOtp cria o user se nao existir (magic link).
    // O metadata org_name e passado ao trigger handle_new_user
    // que cria a organizacao automaticamente.
    const { error: signUpError } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
        shouldCreateUser: true,
        data: {
          org_name: orgName || undefined,
        },
      },
    });

    if (signUpError) {
      setError(t("auth.signup.error_generic"));
    } else {
      setSent(true);
    }
    setLoading(false);
  }

  if (sent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="bg-white rounded-xl border border-slate-200 p-8 max-w-md w-full text-center">
          <h2 className="text-xl font-bold text-teal-700 mb-2">
            {t("auth.signup.success_title")}
          </h2>
          <p className="text-sm text-slate-600">
            {t("auth.signup.success_message")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white rounded-xl border border-slate-200 p-8 max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-teal-700">{t("app.name")}</h1>
          <p className="text-sm text-slate-500 mt-1">{t("app.tagline")}</p>
        </div>

        <h2 className="text-lg font-semibold text-slate-900 mb-1">
          {t("auth.signup.title")}
        </h2>
        <p className="text-sm text-slate-500 mb-6">
          {t("auth.signup.subtitle")}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("auth.signup.email_placeholder")}
            required
            className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
          />

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("auth.signup.org_name_label")}
            </label>
            <input
              type="text"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder={t("auth.signup.org_name_placeholder")}
              className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
            />
            <p className="text-xs text-slate-400 mt-1">
              {t("auth.signup.org_name_hint")}
            </p>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
          >
            {loading ? t("auth.signup.creating") : t("auth.signup.submit")}
          </button>
        </form>

        <p className="text-sm text-slate-500 text-center mt-6">
          {t("auth.signup.has_account")}{" "}
          <Link
            href="/login"
            className="text-teal-700 font-medium hover:underline"
          >
            {t("auth.signup.login_link")}
          </Link>
        </p>
      </div>
    </div>
  );
}
