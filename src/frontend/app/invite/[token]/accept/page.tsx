"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { API_BASE } from "@/lib/api";
import { t } from "@/lib/i18n";

export default function AcceptInvitePage() {
  const params = useParams();
  const token = params.token as string;
  const router = useRouter();
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading"
  );
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    async function accept() {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session) {
        // Sem sessao — redirecionar para a pagina do convite
        router.replace(`/invite/${token}`);
        return;
      }

      try {
        const resp = await fetch(
          `${API_BASE}/api/v1/invites/${token}/accept`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${session.access_token}`,
              "Content-Type": "application/json",
            },
          }
        );

        if (resp.ok) {
          setStatus("success");
          setTimeout(() => router.push("/"), 2000);
        } else {
          const data = await resp
            .json()
            .catch(() => ({ detail: t("auth.invite.accept_error") }));
          setErrorMessage(data.detail || t("auth.invite.accept_error"));
          setStatus("error");
        }
      } catch {
        setErrorMessage(t("auth.invite.accept_error"));
        setStatus("error");
      }
    }

    accept();
  }, [token, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white rounded-xl border border-slate-200 p-8 max-w-md w-full text-center">
        {status === "loading" && (
          <p className="text-sm text-slate-500">
            {t("auth.invite.accepting")}
          </p>
        )}

        {status === "success" && (
          <>
            <h2 className="text-xl font-bold text-teal-700 mb-2">
              {t("auth.invite.accept_success")}
            </h2>
            <p className="text-sm text-slate-500">{t("common.loading")}</p>
          </>
        )}

        {status === "error" && (
          <>
            <h2 className="text-xl font-bold text-red-600 mb-2">
              {t("common.error")}
            </h2>
            <p className="text-sm text-slate-600 mb-6">{errorMessage}</p>
            <Link
              href="/login"
              className="text-teal-700 font-medium hover:underline text-sm"
            >
              {t("auth.invite.back_to_login")}
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
