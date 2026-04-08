export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";
const ACTIVE_ORG_KEY = "imoia_active_org_id";
const COOKIE_PREFIX = "sb-";

/**
 * Le o access_token directamente do cookie Supabase.
 * Evita getSession() que pode pendurar com Web Locks.
 */
function getTokenFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const cookie = document.cookie.split(";").find((c) => c.trim().startsWith(COOKIE_PREFIX));
  if (!cookie) return null;
  const value = cookie.split("=").slice(1).join("=").trim();
  if (value.startsWith("base64-")) {
    try {
      const decoded = JSON.parse(atob(value.slice(7)));
      return decoded.access_token ?? null;
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * Constroi headers de auth para chamadas ao FastAPI backend.
 * Le token do cookie directamente (sem Supabase client = sem locks).
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (typeof window === "undefined") return headers;

  const token = getTokenFromCookie();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
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
