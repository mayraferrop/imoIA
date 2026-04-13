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

-- Policies RLS para utilizadores autenticados
-- Usa current_setting em vez de auth.uid() para evitar dependencia do schema auth
-- (imoia_app nao tem USAGE no schema auth).

DO $$
BEGIN
    -- SELECT: membros da org podem ver convites
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'organization_invites'
          AND policyname = 'invites_select_own_org'
    ) THEN
        CREATE POLICY invites_select_own_org ON public.organization_invites
          FOR SELECT TO authenticated USING (
            organization_id IN (
              SELECT organization_id FROM public.organization_members
              WHERE user_id = (current_setting('request.jwt.claims', true)::json->>'sub')::uuid
            )
          );
    END IF;

    -- INSERT: apenas admin/owner podem criar convites
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'organization_invites'
          AND policyname = 'invites_insert_admin'
    ) THEN
        CREATE POLICY invites_insert_admin ON public.organization_invites
          FOR INSERT TO authenticated WITH CHECK (
            organization_id IN (
              SELECT organization_id FROM public.organization_members
              WHERE user_id = (current_setting('request.jwt.claims', true)::json->>'sub')::uuid
                AND role IN ('owner', 'admin')
            )
          );
    END IF;

    -- UPDATE: admin/owner podem marcar como aceite/revogado
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'organization_invites'
          AND policyname = 'invites_update_admin'
    ) THEN
        CREATE POLICY invites_update_admin ON public.organization_invites
          FOR UPDATE TO authenticated USING (
            organization_id IN (
              SELECT organization_id FROM public.organization_members
              WHERE user_id = (current_setting('request.jwt.claims', true)::json->>'sub')::uuid
                AND role IN ('owner', 'admin')
            )
          );
    END IF;

    -- DELETE: admin/owner podem eliminar convites
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'organization_invites'
          AND policyname = 'invites_delete_admin'
    ) THEN
        CREATE POLICY invites_delete_admin ON public.organization_invites
          FOR DELETE TO authenticated USING (
            organization_id IN (
              SELECT organization_id FROM public.organization_members
              WHERE user_id = (current_setting('request.jwt.claims', true)::json->>'sub')::uuid
                AND role IN ('owner', 'admin')
            )
          );
    END IF;
END $$;

-- ============================================================
-- Migração 003 aplicada: tabela organization_invites com RLS.
-- Policies aplicadas: imoia_app_all + 4 policies authenticated
-- (SELECT membros, INSERT/UPDATE/DELETE admin/owner).
-- NOTA: invites.py mantém SERVICE_ROLE_KEY porque accept_invite
-- é chamado por users que ainda não são membros da org.
-- ============================================================
