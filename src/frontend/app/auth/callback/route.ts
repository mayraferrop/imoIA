import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * Callback para magic links, signup e Google OAuth.
 * Supabase redireciona para ca com ?code=... apos autenticacao.
 * Troca o code por sessao (PKCE / OAuth flow).
 *
 * Fluxos:
 *  - Com ?next=/invite/{token}/accept → redirect para accept page (invite flow)
 *  - Sem next → verifica se user tem org → / ou /no-access
 */
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "";

  // Validar next param — prevenir open redirect
  const safeNext =
    next.startsWith("/") && !next.startsWith("//") ? next : "";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      // Invite flow: redirect directo para a pagina de accept
      if (safeNext) {
        return NextResponse.redirect(`${origin}${safeNext}`);
      }

      // Login normal: verificar se user tem organizacao
      const { data: memberships } = await supabase
        .from("organization_members")
        .select("id")
        .limit(1);

      if (memberships && memberships.length > 0) {
        return NextResponse.redirect(`${origin}/`);
      }

      // Sem organizacao → pagina de no-access
      return NextResponse.redirect(`${origin}/no-access`);
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth_callback_failed`);
}
