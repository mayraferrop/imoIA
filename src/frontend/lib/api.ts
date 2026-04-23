import { createClient } from "@/lib/supabase/client";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

/**
 * Constroi headers de auth para chamadas ao FastAPI backend.
 * Usa supabase.auth.getSession() que gere refresh automatico do token.
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (typeof window === "undefined") return headers;

  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();

  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }

  const orgId = localStorage.getItem("imoia_active_org_id");
  if (orgId) {
    headers["X-Organization-Id"] = orgId;
  }

  return headers;
}

export async function apiGet<T = unknown>(path: string): Promise<T | null> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, { headers });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function apiPost<T = unknown>(
  path: string,
  body?: unknown
): Promise<T | null> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function apiPatch<T = unknown>(
  path: string,
  body?: unknown
): Promise<T | null> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
      method: "PATCH",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function apiUpload<T = unknown>(
  path: string,
  formData: FormData
): Promise<T | null> {
  try {
    const headers = await getAuthHeaders();
    // Remove Content-Type para o browser adicionar boundary multipart correcto
    delete headers["Content-Type"];
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function apiDelete<T = unknown>(path: string): Promise<T | null> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
      method: "DELETE",
      headers,
    });
    if (!res.ok) return null;
    const text = await res.text();
    return text ? JSON.parse(text) : ({} as T);
  } catch {
    return null;
  }
}

// SWR fetcher com auth — LANCA em erro para SWR poder fazer retry.
// Retornar null silenciosamente faz SWR cachear o null e nunca recuperar
// de race conditions (ex.: fetch antes da sessao auth estar hidratada).
export const fetcher = async (path: string) => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status} em ${path}`) as Error & {
      status?: number;
    };
    err.status = res.status;
    throw err;
  }
  return res.json();
};
