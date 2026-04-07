import { createBrowserClient } from "@supabase/ssr";

/**
 * Cria cliente Supabase para browser (client components).
 * Singleton — chamadas repetidas retornam a mesma instancia.
 * Usado para auth (login, signup, session) e queries autenticadas.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
