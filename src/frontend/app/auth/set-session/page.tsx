"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";

const COOKIE_NAME = "sb-jurzdyncaxkgvcatyfdu-auth-token";
const ORG_KEY = "imoia_active_org_id";
const HABTA_ORG_ID = "a0a450ff-2897-4431-be2f-440e7762629c";

function SetSessionInner() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState("A configurar sessao...");

  useEffect(() => {
    const access_token = searchParams.get("access_token");
    const refresh_token = searchParams.get("refresh_token");

    if (!access_token || !refresh_token) {
      setStatus("Erro: tokens em falta.");
      return;
    }

    // Limpar cookies e storage antigos
    document.cookie.split(";").forEach((c) => {
      const name = c.trim().split("=")[0];
      if (name.startsWith("sb-")) {
        document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
      }
    });

    // Construir cookie no formato @supabase/ssr
    const session = {
      access_token,
      token_type: "bearer",
      expires_in: 3600,
      expires_at: Math.floor(Date.now() / 1000) + 3600,
      refresh_token,
    };
    const encoded = btoa(JSON.stringify(session));
    document.cookie = `${COOKIE_NAME}=base64-${encoded}; path=/; max-age=3600; SameSite=Lax`;

    // Definir org activa
    localStorage.setItem(ORG_KEY, HABTA_ORG_ID);

    setStatus("Sessao configurada. A redirecionar...");
    setTimeout(() => {
      window.location.href = "/";
    }, 500);
  }, [searchParams]);

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50">
      <p className="text-slate-500 text-sm">{status}</p>
    </div>
  );
}

export default function SetSessionPage() {
  return (
    <Suspense>
      <SetSessionInner />
    </Suspense>
  );
}
