const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

export async function apiGet<T = any>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function apiPost<T = any>(path: string, body?: any): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function apiPatch<T = any>(path: string, body?: any): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function apiDelete<T = any>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
    if (!res.ok) return null;
    // Some DELETE endpoints return 204 with no body
    const text = await res.text();
    return text ? JSON.parse(text) : ({} as T);
  } catch {
    return null;
  }
}

// SWR fetcher for client components
export const fetcher = (path: string) =>
  fetch(`${API_BASE}${path}`).then((r) => (r.ok ? r.json() : null));
