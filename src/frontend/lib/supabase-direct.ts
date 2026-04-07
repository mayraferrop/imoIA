/**
 * DEPRECATED — acesso directo ao Supabase REST com anon key.
 * Apos activacao de auth (Fase 2A), estas funcoes deixam de funcionar
 * porque as policies anon_select foram removidas.
 * Migrar para chamadas via FastAPI com JWT (lib/api.ts).
 */

const SUPABASE_URL =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  "https://jurzdyncaxkgvcatyfdu.supabase.co";
const SUPABASE_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp1cnpkeW5jYXhrZ3ZjYXR5ZmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNzM2MDcsImV4cCI6MjA4OTk0OTYwN30.2DCCWcrhdwBLMxJ9hUbYkhOBQIgE_aD2jGNaZlAhO5k";

const HEADERS = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
};

export async function supabaseGet<T = any>(
  table: string,
  query?: string
): Promise<T[]> {
  const url = `${SUPABASE_URL}/rest/v1/${table}${query ? `?${query}` : ""}`;
  const res = await fetch(url, { headers: HEADERS });
  if (!res.ok) return [];
  return res.json();
}

export async function supabaseCount(
  table: string,
  query?: string
): Promise<number> {
  const url = `${SUPABASE_URL}/rest/v1/${table}${query ? `?${query}` : ""}`;
  const res = await fetch(url, {
    headers: { ...HEADERS, Prefer: "count=exact", Range: "0-0" },
  });
  const cr = res.headers.get("content-range") || "";
  return cr.includes("/") ? parseInt(cr.split("/")[1], 10) : 0;
}
