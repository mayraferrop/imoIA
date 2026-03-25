const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

const headers = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
  "Content-Type": "application/json",
};

export async function supabaseGet<T = any>(
  table: string,
  query: string = ""
): Promise<T[]> {
  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/${table}?${query}`,
      { headers, next: { revalidate: 30 } }
    );
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function supabaseCount(table: string, query: string = ""): Promise<number> {
  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/${table}?${query}&select=*`,
      {
        headers: { ...headers, Prefer: "count=exact" },
        next: { revalidate: 30 },
      }
    );
    const count = res.headers.get("content-range");
    if (count) {
      const total = count.split("/")[1];
      return parseInt(total) || 0;
    }
    return 0;
  } catch {
    return 0;
  }
}
