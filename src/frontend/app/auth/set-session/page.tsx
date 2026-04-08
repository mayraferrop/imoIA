"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Suspense } from "react";

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

    const supabase = createClient();
    supabase.auth
      .setSession({ access_token, refresh_token })
      .then(({ error }) => {
        if (error) {
          setStatus("Erro: " + error.message);
        } else {
          setStatus("Sessao configurada. A redirecionar...");
          window.location.href = "/";
        }
      });
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
