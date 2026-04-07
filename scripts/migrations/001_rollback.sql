-- =============================================================================
-- ROLLBACK 001: Reverter modelo de organizações (Etapa 1)
-- =============================================================================
-- Desfaz TUDO da migração 001 sem perder dados existentes.
-- Seguro porque: organization_id é coluna nova (DROP não afecta dados antigos),
-- e tenant_id foi mantido intacto.
--
-- Ordem: inversa da migração (policies → FKs → colunas → tabelas)
-- =============================================================================

BEGIN;

-- =====================================================================
-- 1. Remover RLS policies novas (org_select, org_insert, org_update, org_delete)
-- =====================================================================

DO $$
DECLARE
    t text;
    all_tables text[] := ARRAY[
        'brand_kits', 'calendar_events', 'cashflow_projections',
        'closing_processes', 'deal_approvals', 'deal_commissions',
        'deal_pnl', 'deal_rentals', 'deal_state_history', 'deal_tasks',
        'deal_visits', 'deals', 'documents', 'due_diligence_items',
        'email_campaigns', 'financial_models', 'investment_strategies',
        'lead_interactions', 'lead_listing_matches', 'leads',
        'listing_creatives', 'listings', 'market_alerts',
        'market_comparables', 'market_zone_stats', 'notifications',
        'nurture_sequences', 'payment_conditions', 'properties',
        'property_valuations', 'proposals', 'renovations',
        'social_media_accounts', 'social_media_posts', 'transactions',
        'video_projects',
        'groups', 'messages', 'opportunities', 'market_data',
        'classification_signals', 'renovation_milestones',
        'renovation_expenses', 'renovation_photos',
        'listing_contents', 'listing_price_history'
    ];
BEGIN
    FOREACH t IN ARRAY all_tables LOOP
        EXECUTE format('DROP POLICY IF EXISTS org_all ON public.%I', t);

        -- Restaurar anon_select (aberta, como estava antes)
        EXECUTE format('DROP POLICY IF EXISTS anon_select ON public.%I', t);
        EXECUTE format(
            'CREATE POLICY anon_select ON public.%I
                FOR SELECT TO anon USING (true)',
            t
        );
    END LOOP;
END
$$;

-- Restaurar policies de classification_signals e investment_strategies
DROP POLICY IF EXISTS allow_all_signals ON public.classification_signals;
CREATE POLICY allow_all_signals
    ON public.classification_signals USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS allow_all_strategies ON public.investment_strategies;
CREATE POLICY allow_all_strategies
    ON public.investment_strategies USING (true) WITH CHECK (true);

-- Restaurar anon_select em tenants
DROP POLICY IF EXISTS anon_select ON public.tenants;
CREATE POLICY anon_select ON public.tenants
    FOR SELECT TO anon USING (true);

-- Remover policies das tabelas novas
DROP POLICY IF EXISTS org_select ON public.organizations;
DROP POLICY IF EXISTS org_update ON public.organizations;
DROP POLICY IF EXISTS imoia_app_all ON public.organizations;
DROP POLICY IF EXISTS members_select ON public.organization_members;
DROP POLICY IF EXISTS members_insert ON public.organization_members;
DROP POLICY IF EXISTS members_update ON public.organization_members;
DROP POLICY IF EXISTS members_delete ON public.organization_members;
DROP POLICY IF EXISTS imoia_app_all ON public.organization_members;


-- =====================================================================
-- 2. Remover FKs de organization_id (se existirem, da post_migration)
-- =====================================================================

DO $$
DECLARE
    t text;
    all_tables text[] := ARRAY[
        'brand_kits', 'calendar_events', 'cashflow_projections',
        'closing_processes', 'deal_approvals', 'deal_commissions',
        'deal_pnl', 'deal_rentals', 'deal_state_history', 'deal_tasks',
        'deal_visits', 'deals', 'documents', 'due_diligence_items',
        'email_campaigns', 'financial_models', 'investment_strategies',
        'lead_interactions', 'lead_listing_matches', 'leads',
        'listing_creatives', 'listings', 'market_alerts',
        'market_comparables', 'market_zone_stats', 'notifications',
        'nurture_sequences', 'payment_conditions', 'properties',
        'property_valuations', 'proposals', 'renovations',
        'social_media_accounts', 'social_media_posts', 'transactions',
        'video_projects',
        'groups', 'messages', 'opportunities', 'market_data',
        'classification_signals', 'renovation_milestones',
        'renovation_expenses', 'renovation_photos',
        'listing_contents', 'listing_price_history'
    ];
BEGIN
    FOREACH t IN ARRAY all_tables LOOP
        EXECUTE format(
            'ALTER TABLE public.%I DROP CONSTRAINT IF EXISTS %I',
            t, t || '_org_fk'
        );
    END LOOP;
END
$$;


-- =====================================================================
-- 3. Remover coluna organization_id de todas as tabelas
-- =====================================================================

DO $$
DECLARE
    t text;
    all_tables text[] := ARRAY[
        'brand_kits', 'calendar_events', 'cashflow_projections',
        'closing_processes', 'deal_approvals', 'deal_commissions',
        'deal_pnl', 'deal_rentals', 'deal_state_history', 'deal_tasks',
        'deal_visits', 'deals', 'documents', 'due_diligence_items',
        'email_campaigns', 'financial_models', 'investment_strategies',
        'lead_interactions', 'lead_listing_matches', 'leads',
        'listing_creatives', 'listings', 'market_alerts',
        'market_comparables', 'market_zone_stats', 'notifications',
        'nurture_sequences', 'payment_conditions', 'properties',
        'property_valuations', 'proposals', 'renovations',
        'social_media_accounts', 'social_media_posts', 'transactions',
        'video_projects',
        'groups', 'messages', 'opportunities', 'market_data',
        'classification_signals', 'renovation_milestones',
        'renovation_expenses', 'renovation_photos',
        'listing_contents', 'listing_price_history'
    ];
BEGIN
    FOREACH t IN ARRAY all_tables LOOP
        EXECUTE format(
            'ALTER TABLE public.%I DROP COLUMN IF EXISTS organization_id',
            t
        );
    END LOOP;
END
$$;


-- =====================================================================
-- 4. Remover função auxiliar
-- =====================================================================

DROP FUNCTION IF EXISTS public.user_organization_ids();


-- =====================================================================
-- 5. Dropar tabelas novas
-- =====================================================================

DROP TABLE IF EXISTS public.organization_members;
DROP TABLE IF EXISTS public.organizations;


-- =====================================================================
-- 6. Restaurar public.users (se necessário)
-- =====================================================================
-- NOTA: Só necessário se algo depender de public.users após rollback.
-- A tabela estava vazia e sem uso, mas as FKs existiam.

CREATE TABLE IF NOT EXISTS public.users (
    id          character varying(36) NOT NULL PRIMARY KEY,
    tenant_id   character varying(36) NOT NULL REFERENCES public.tenants(id),
    email       character varying(255) NOT NULL,
    name        character varying(255) NOT NULL,
    role        character varying(50) NOT NULL,
    phone       character varying(50),
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamp without time zone DEFAULT now() NOT NULL,
    UNIQUE (tenant_id, email)
);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS anon_select ON public.users;
CREATE POLICY anon_select ON public.users
    FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS imoia_app_all ON public.users;
CREATE POLICY imoia_app_all ON public.users
    TO imoia_app USING (true) WITH CHECK (true);

-- Restaurar FKs de deals e properties para users
ALTER TABLE public.deals
    ADD CONSTRAINT deals_assigned_to_fkey
    FOREIGN KEY (assigned_to) REFERENCES public.users(id);

ALTER TABLE public.properties
    ADD CONSTRAINT properties_assigned_to_fkey
    FOREIGN KEY (assigned_to) REFERENCES public.users(id);


COMMIT;
