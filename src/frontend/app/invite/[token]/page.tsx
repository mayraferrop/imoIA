"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { API_BASE } from "@/lib/api";
import { t } from "@/lib/i18n";

interface InviteInfo {
  valid: boolean;
  organization_name?: string;
  role?: string;
  expires_at?: string;
  error?: string;
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  );
}

export default function InvitePage() {
  const params = useParams();
  const token = params.token as string;
  const [invite, setInvite] = useState<InviteInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [emailSent, setEmailSent] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [error, setError] = useState("");

  const supabase = createClient();

  useEffect(() => {
    async function validate() {
      try {
        const resp = await fetch(
          `${API_BASE}/api/v1/invites/validate/${token}`
        );
        if (resp.ok) {
          setInvite(await resp.json());
        } else {
          setInvite({ valid: false, error: t("auth.invite.invalid_message") });
        }
      } catch {
        setInvite({ valid: false, error: t("auth.invite.accept_error") });
      } finally {
        setLoading(false);
      }
    }
    validate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleGoogleLogin() {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback?next=/invite/${token}/accept`,
      },
    });
  }

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault();
    setSendingEmail(true);
    setError("");

    const { error: otpError } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback?next=/invite/${token}/accept`,
      },
    });

    if (otpError) {
      setError(t("auth.login.error_generic"));
    } else {
      setEmailSent(true);
    }
    setSendingEmail(false);
  }

  // Estado: a carregar
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-500">{t("auth.invite.loading")}</p>
      </div>
    );
  }

  // Estado: convite invalido
  if (!invite?.valid) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="bg-white rounded-xl border border-slate-200 p-8 max-w-md w-full text-center">
          <h2 className="text-xl font-bold text-red-600 mb-2">
            {t("auth.invite.invalid_title")}
          </h2>
          <p className="text-sm text-slate-600 mb-6">
            {invite?.error || t("auth.invite.invalid_message")}
          </p>
          <Link
            href="/login"
            className="text-teal-700 font-medium hover:underline text-sm"
          >
            {t("auth.invite.back_to_login")}
          </Link>
        </div>
      </div>
    );
  }

  // Estado: email enviado (magic link)
  if (emailSent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="bg-white rounded-xl border border-slate-200 p-8 max-w-md w-full text-center">
          <h2 className="text-xl font-bold text-teal-700 mb-2">
            {t("auth.login.success_title")}
          </h2>
          <p className="text-sm text-slate-600">
            {t("auth.login.success_message")}
          </p>
        </div>
      </div>
    );
  }

  // Estado: convite valido — mostrar opcoes de login
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white rounded-xl border border-slate-200 p-8 max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-teal-700">{t("app.name")}</h1>
          <p className="text-sm text-slate-500 mt-1">{t("app.tagline")}</p>
        </div>

        <h2 className="text-lg font-semibold text-slate-900 mb-1">
          {t("auth.invite.title")}
        </h2>
        <p className="text-sm text-slate-500 mb-2">
          {t("auth.invite.subtitle")}
        </p>
        <p className="text-base font-medium text-teal-700 mb-4">
          {invite.organization_name}
        </p>

        <p className="text-sm text-slate-500 mb-6">
          {t("auth.invite.role")}:{" "}
          <span className="font-medium text-slate-700">{invite.role}</span>
        </p>

        <button
          type="button"
          onClick={handleGoogleLogin}
          className="w-full py-2.5 border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors flex items-center justify-center gap-2"
        >
          <GoogleIcon />
          {t("auth.invite.accept_google")}
        </button>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="bg-white px-2 text-slate-400">
              {t("auth.login.or")}
            </span>
          </div>
        </div>

        <form onSubmit={handleMagicLink} className="space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("auth.login.email_placeholder")}
            required
            className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={sendingEmail}
            className="w-full py-2.5 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
          >
            {sendingEmail
              ? t("auth.login.sending")
              : t("auth.invite.accept_magic")}
          </button>
        </form>
      </div>
    </div>
  );
}
