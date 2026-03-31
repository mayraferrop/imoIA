"use client";

import { useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

// Acorda o Render em background quando o utilizador abre o site
// Sem isto, o primeiro clique em "Rodar pipeline" demora 60s+ (cold start)
export function RenderWake() {
  useEffect(() => {
    const wake = async () => {
      try {
        await fetch(`${API_BASE}/health`, {
          mode: "no-cors",
          signal: AbortSignal.timeout(30000),
        });
      } catch {
        // ignorar — é só para acordar
      }
    };
    wake();
  }, []);

  return null;
}
