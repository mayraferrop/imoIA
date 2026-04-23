-- ============================================================
-- Migração 004 — Histórico de execuções do pipeline M1
-- ============================================================
-- Persiste cada corrida de run_pipeline() (cron, api, manual)
-- para consulta no painel admin /admin/runs.
--
-- Idempotente: IF NOT EXISTS em tudo. Segue o padrão das
-- migrations anteriores (organization_invites, organizations).
-- ============================================================

CREATE TABLE IF NOT EXISTS public.pipeline_runs (
    id                  serial PRIMARY KEY,
    organization_id     uuid NOT NULL,
    started_at          timestamptz NOT NULL,
    finished_at         timestamptz NOT NULL,
    duration_sec        double precision NOT NULL,
    messages_fetched    integer NOT NULL DEFAULT 0,
    messages_filtered   integer NOT NULL DEFAULT 0,
    opportunities_found integer NOT NULL DEFAULT 0,
    groups_processed    integer NOT NULL DEFAULT 0,
    groups_with_unread  integer NOT NULL DEFAULT 0,
    groups_archived     integer NOT NULL DEFAULT 0,
    groups_to_archive   integer NOT NULL DEFAULT 0,
    errors_count        integer NOT NULL DEFAULT 0,
    phases_duration     jsonb,
    errors              jsonb,
    group_logs          jsonb,
    trigger_source      varchar(30),
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_org ON public.pipeline_runs(organization_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON public.pipeline_runs(started_at DESC);

ALTER TABLE public.pipeline_runs ENABLE ROW LEVEL SECURITY;

-- Permissões Supabase (sem estas, PostgREST devolve 403 antes de avaliar RLS)
GRANT SELECT, INSERT, UPDATE, DELETE ON public.pipeline_runs TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.pipeline_runs TO authenticated;
GRANT SELECT ON public.pipeline_runs TO anon;
GRANT USAGE, SELECT ON SEQUENCE public.pipeline_runs_id_seq TO service_role, authenticated, imoia_app;

-- Backend (imoia_app) acesso total via policy bypass
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'pipeline_runs' AND policyname = 'imoia_app_all'
    ) THEN
        CREATE POLICY imoia_app_all ON public.pipeline_runs
            FOR ALL TO imoia_app USING (true) WITH CHECK (true);
    END IF;
END $$;

-- Isolamento multi-tenant: cada user só vê runs das suas orgs
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'pipeline_runs' AND policyname = 'org_all'
    ) THEN
        CREATE POLICY org_all ON public.pipeline_runs
            FOR ALL TO authenticated
            USING (organization_id IN (SELECT user_organization_ids()))
            WITH CHECK (organization_id IN (SELECT user_organization_ids()));
    END IF;
END $$;
