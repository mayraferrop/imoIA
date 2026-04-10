-- ============================================================
-- Migração 003 — Fase 2B Dia 2
-- ============================================================
-- Tabela de convites para organizações.
-- Idempotente: IF NOT EXISTS em todos os objectos.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.organization_invites (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    email           text NOT NULL,
    role            text NOT NULL DEFAULT 'member'
                    CHECK (role IN ('admin', 'member')),
    token           text NOT NULL UNIQUE,
    invited_by      uuid NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL DEFAULT (now() + interval '7 days'),
    accepted_at     timestamptz,
    revoked_at      timestamptz,
    UNIQUE (organization_id, email)
);

CREATE INDEX IF NOT EXISTS idx_invites_token ON public.organization_invites(token);
CREATE INDEX IF NOT EXISTS idx_invites_org ON public.organization_invites(organization_id);
CREATE INDEX IF NOT EXISTS idx_invites_email ON public.organization_invites(email);

ALTER TABLE public.organization_invites ENABLE ROW LEVEL SECURITY;

-- Permissoes: mesmo padrao das tabelas organizations e organization_members
GRANT ALL ON public.organization_invites TO service_role;
GRANT ALL ON public.organization_invites TO authenticated;
GRANT SELECT ON public.organization_invites TO anon;

-- Backend (imoia_app) acesso total via RLS policy
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'organization_invites'
          AND policyname = 'imoia_app_all'
    ) THEN
        CREATE POLICY imoia_app_all ON public.organization_invites
            TO imoia_app USING (true) WITH CHECK (true);
    END IF;
END $$;

-- Policy RLS para utilizadores autenticados (membros da org)
-- NOTA: Requer execucao via Supabase Dashboard (superuser) porque
-- referencia auth.uid() que imoia_app nao consegue aceder.
-- DO $$
-- BEGIN
--     IF NOT EXISTS (
--         SELECT 1 FROM pg_policies
--         WHERE tablename = 'organization_invites'
--           AND policyname = 'invites_select_own_org'
--     ) THEN
--         CREATE POLICY invites_select_own_org ON public.organization_invites
--           FOR SELECT USING (
--             organization_id IN (
--               SELECT organization_id FROM public.organization_members
--               WHERE user_id = auth.uid()
--             )
--           );
--     END IF;
-- END $$;

-- ============================================================
-- Migração 003 aplicada: tabela organization_invites com RLS.
-- NOTA: Policy invites_select_own_org (auth.uid) requer execucao
-- manual via Supabase Dashboard SQL Editor.
-- ============================================================
