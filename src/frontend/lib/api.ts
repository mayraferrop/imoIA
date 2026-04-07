import { createClient } from "@/lib/supabase/client";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";
const ACTIVE_ORG_KEY = "imoia_active_org_id";

/**
 * Constroi headers de auth para chamadas ao FastAPI backend.
 * Inclui JWT do Supabase Auth e X-Organization-Id activo.
 */
async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (typeof window === "undefined") return headers;

  try {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      headers["Authorization"] = `Bearer ${session.access_token}`;
    }
  } catch {
    // Sem sessao — headers sem auth
  }

  const orgId = localStorage.getItem(ACTIVE_ORG_KEY);
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

// SWR fetcher com auth
export const fetcher = async (path: string) => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}${path}`, { headers });
  return res.ok ? res.json() : null;
};
