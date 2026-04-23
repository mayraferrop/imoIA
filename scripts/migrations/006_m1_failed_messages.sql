-- ============================================================
-- Migração 006 — Dead-letter queue do pipeline M1 (Fase 5)
-- ============================================================
-- Captura mensagens que não foram classificadas (excederam o limite
-- MAX_CLASSIFY=500 por corrida) para serem re-tentadas em runs futuras,
-- evitando perda silenciosa de leads em grupos muito activos.
--
-- Idempotente: IF NOT EXISTS em tudo. Mesmo padrão das migrations
-- anteriores (004_pipeline_runs).
-- ============================================================

CREATE TABLE IF NOT EXISTS public.m1_failed_messages (
    id                      bigserial PRIMARY KEY,
    organization_id         uuid NOT NULL,
    group_id                text NOT NULL,
    group_name              text,
    whatsapp_message_id     text NOT NULL,
    content                 text NOT NULL,
    sender_id               text,
    sender_name             text,
    message_timestamp       timestamptz,
    reason                  text NOT NULL,
    retry_count             integer NOT NULL DEFAULT 0,
    next_retry_at           timestamptz NOT NULL DEFAULT now(),
    last_error              text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, whatsapp_message_id)
);

CREATE INDEX IF NOT EXISTS idx_m1_failed_retry
    ON public.m1_failed_messages(organization_id, next_retry_at)
    WHERE retry_count < 5;
CREATE INDEX IF NOT EXISTS idx_m1_failed_org
    ON public.m1_failed_messages(organization_id);

ALTER TABLE public.m1_failed_messages ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.m1_failed_messages TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.m1_failed_messages TO authenticated;
GRANT SELECT ON public.m1_failed_messages TO anon;
GRANT USAGE, SELECT ON SEQUENCE public.m1_failed_messages_id_seq TO service_role, authenticated, imoia_app;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'm1_failed_messages' AND policyname = 'imoia_app_all'
    ) THEN
        CREATE POLICY imoia_app_all ON public.m1_failed_messages
            FOR ALL TO imoia_app USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'm1_failed_messages' AND policyname = 'org_all'
    ) THEN
        CREATE POLICY org_all ON public.m1_failed_messages
            FOR ALL TO authenticated
            USING (organization_id IN (SELECT user_organization_ids()))
            WITH CHECK (organization_id IN (SELECT user_organization_ids()));
    END IF;
END $$;
