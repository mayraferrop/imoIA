import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Cria cliente Supabase para server (middleware, server components, route handlers).
 * Le e escreve cookies para manter a sessao auth.
 * DEVE ser chamado com await (cookies() e async no Next.js 15).
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options?: Record<string, unknown> }[]) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // setAll chamado de Server Component — ignorar.
            // O middleware trata do refresh da sessao.
          }
        },
      },
    }
  );
}
