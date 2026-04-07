-- =============================================================================
-- PÓS-MIGRAÇÃO 001: FKs, NOT NULL, e RLS policies
-- =============================================================================
-- Executar APENAS depois de:
-- 1. 001_organizations.sql ter corrido com sucesso
-- 2. 001_migrate_org_data.py ter populado organization_id em todas as tabelas
-- 3. Verificação: SELECT count(*) FROM {table} WHERE organization_id IS NULL
--    deve retornar 0 para todas as tabelas com dados
--
-- ESTE FICHEIRO É PARA REVISÃO. NÃO EXECUTAR SEM APROVAÇÃO EXPLÍCITA.
-- =============================================================================

BEGIN;

-- =====================================================================
-- PARTE 7: Tornar organization_id NOT NULL e adicionar FKs
-- =====================================================================

-- Grupo A: tabelas com tenant_id
ALTER TABLE public.brand_kits            ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT brand_kits_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.calendar_events       ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT calendar_events_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.cashflow_projections  ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT cashflow_projections_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.closing_processes     ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT closing_processes_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.deal_approvals        ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT deal_approvals_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.deal_commissions      ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT deal_commissions_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.deal_pnl              ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT deal_pnl_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.deal_rentals          ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT deal_rentals_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.deal_state_history    ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT deal_state_history_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.deal_tasks            ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT deal_tasks_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.deal_visits           ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT deal_visits_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.deals                 ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT deals_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.documents             ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT documents_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.due_diligence_items   ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT due_diligence_items_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.email_campaigns       ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT email_campaigns_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.financial_models      ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT financial_models_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.investment_strategies ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT investment_strategies_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.lead_interactions     ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT lead_interactions_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.lead_listing_matches  ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT lead_listing_matches_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.leads                 ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT leads_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.listing_creatives     ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT listing_creatives_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.listings              ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT listings_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.market_alerts         ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT market_alerts_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.market_comparables    ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT market_comparables_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.market_zone_stats     ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT market_zone_stats_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.notifications         ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT notifications_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.nurture_sequences     ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT nurture_sequences_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.payment_conditions    ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT payment_conditions_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.properties            ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT properties_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.property_valuations   ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT property_valuations_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.proposals             ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT proposals_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.renovations           ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT renovations_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.social_media_accounts ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT social_media_accounts_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.social_media_posts    ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT social_media_posts_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.transactions          ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT transactions_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.video_projects        ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT video_projects_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);

-- Grupo B: tabelas sem tenant_id
ALTER TABLE public.groups                ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT groups_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.messages              ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT messages_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.opportunities         ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT opportunities_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.market_data           ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT market_data_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.classification_signals ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT classification_signals_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.renovation_milestones ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT renovation_milestones_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.renovation_expenses   ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT renovation_expenses_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.renovation_photos     ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT renovation_photos_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.listing_contents      ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT listing_contents_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);
ALTER TABLE public.listing_price_history ALTER COLUMN organization_id SET NOT NULL,
  ADD CONSTRAINT listing_price_history_org_fk FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


-- =====================================================================
-- PARTE 8: RLS — Novas policies baseadas em organizações
-- =====================================================================

-- 8a. Habilitar RLS nas novas tabelas
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;

-- 8b. Policies para organizations
-- Membros vêem as suas organizações
CREATE POLICY org_select ON public.organizations
    FOR SELECT TO authenticated
    USING (id IN (SELECT public.user_organization_ids()));

-- Só owners podem actualizar
CREATE POLICY org_update ON public.organizations
    FOR UPDATE TO authenticated
    USING (id IN (
        SELECT organization_id FROM public.organization_members
        WHERE user_id = auth.uid() AND role = 'owner'
    ));

-- Backend (imoia_app) mantém acesso total
CREATE POLICY imoia_app_all ON public.organizations
    TO imoia_app USING (true) WITH CHECK (true);

-- 8c. Policies para organization_members
-- Membros vêem outros membros das suas organizações
CREATE POLICY members_select ON public.organization_members
    FOR SELECT TO authenticated
    USING (organization_id IN (SELECT public.user_organization_ids()));

-- Só owners podem adicionar membros
CREATE POLICY members_insert ON public.organization_members
    FOR INSERT TO authenticated
    WITH CHECK (organization_id IN (
        SELECT organization_id FROM public.organization_members
        WHERE user_id = auth.uid() AND role = 'owner'
    ));

-- Só owners podem alterar roles
CREATE POLICY members_update ON public.organization_members
    FOR UPDATE TO authenticated
    USING (organization_id IN (
        SELECT organization_id FROM public.organization_members
        WHERE user_id = auth.uid() AND role = 'owner'
    ));

-- Só owners podem remover membros
CREATE POLICY members_delete ON public.organization_members
    FOR DELETE TO authenticated
    USING (organization_id IN (
        SELECT organization_id FROM public.organization_members
        WHERE user_id = auth.uid() AND role = 'owner'
    ));

-- Backend (imoia_app) mantém acesso total
CREATE POLICY imoia_app_all ON public.organization_members
    TO imoia_app USING (true) WITH CHECK (true);


-- 8d. Policies para TODAS as tabelas de domínio (46 tabelas)
-- Padrão: authenticated pode SELECT/INSERT/UPDATE/DELETE onde
-- organization_id pertence a uma organização do utilizador.
-- Policies anon_select (USING true) são REMOVIDAS.
-- Policies imoia_app_all são MANTIDAS (backend usa este role).

-- Uma policy "org_all" por tabela (FOR ALL = SELECT+INSERT+UPDATE+DELETE).
-- Mais simples de auditar. Se precisarmos de granularidade por operação,
-- refactorizamos depois.
DO $$
DECLARE
    t text;
    domain_tables text[] := ARRAY[
        -- Grupo A (36 tabelas com tenant_id)
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
        -- Grupo B (10 tabelas sem tenant_id)
        'groups', 'messages', 'opportunities', 'market_data',
        'classification_signals', 'renovation_milestones',
        'renovation_expenses', 'renovation_photos',
        'listing_contents', 'listing_price_history'
    ];
BEGIN
    FOREACH t IN ARRAY domain_tables LOOP
        -- Remover policies abertas
        EXECUTE format('DROP POLICY IF EXISTS anon_select ON public.%I', t);
        EXECUTE format('DROP POLICY IF EXISTS allow_all_signals ON public.%I', t);
        EXECUTE format('DROP POLICY IF EXISTS allow_all_strategies ON public.%I', t);

        -- Criar policy única para authenticated (FOR ALL)
        EXECUTE format(
            'CREATE POLICY org_all ON public.%I
                FOR ALL TO authenticated
                USING (organization_id IN (SELECT public.user_organization_ids()))
                WITH CHECK (organization_id IN (SELECT public.user_organization_ids()))',
            t
        );

        -- imoia_app_all JÁ EXISTE nestas tabelas — manter
    END LOOP;
END
$$;

-- 8e. Remover anon_select da tabela tenants (mantida temporariamente)
DROP POLICY IF EXISTS anon_select ON public.tenants;


COMMIT;
