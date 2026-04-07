-- =============================================================================
-- MIGRAÇÃO 001: Modelo de Organizações (Etapa 1)
-- =============================================================================
-- Objectivo: Adicionar multi-tenancy real baseado em organizações + auth.users
-- Contexto: tenant_id coexiste temporariamente (removido na Etapa 2)
--
-- ESTE FICHEIRO É PARA REVISÃO. NÃO EXECUTAR SEM APROVAÇÃO EXPLÍCITA.
-- =============================================================================

BEGIN;

-- =====================================================================
-- PARTE 1: Remover public.users (scaffold não utilizado)
-- =====================================================================

-- 1a. Remover FKs que apontam para public.users
ALTER TABLE public.deals
  DROP CONSTRAINT IF EXISTS deals_assigned_to_fkey;

ALTER TABLE public.properties
  DROP CONSTRAINT IF EXISTS properties_assigned_to_fkey;

-- 1b. Remover policies de public.users
DROP POLICY IF EXISTS anon_select ON public.users;
DROP POLICY IF EXISTS imoia_app_all ON public.users;

-- 1c. Dropar a tabela
DROP TABLE IF EXISTS public.users;


-- =====================================================================
-- PARTE 2: Criar tabelas de organização
-- =====================================================================

-- 2a. organizations
CREATE TABLE public.organizations (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name          text NOT NULL,
    slug          text NOT NULL UNIQUE,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    created_by    uuid  -- FK para auth.users, placeholder até Fase 2
);

CREATE INDEX idx_organizations_slug ON public.organizations (slug);

-- 2b. organization_members
CREATE TABLE public.organization_members (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id          uuid NOT NULL,  -- FK para auth.users (sem REFERENCES porque auth.users é schema separado)
    role             text NOT NULL DEFAULT 'member'
                     CHECK (role IN ('owner', 'admin', 'member')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, user_id)
);

CREATE INDEX idx_org_members_user ON public.organization_members (user_id);
CREATE INDEX idx_org_members_org  ON public.organization_members (organization_id);


-- =====================================================================
-- PARTE 3: Função auxiliar para RLS
-- =====================================================================

-- Retorna os IDs de organizações a que o utilizador autenticado pertence.
-- SECURITY DEFINER para que RLS nas tabelas não bloqueie a consulta.
CREATE OR REPLACE FUNCTION public.user_organization_ids()
RETURNS SETOF uuid
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT organization_id
    FROM public.organization_members
    WHERE user_id = auth.uid()
$$;


-- =====================================================================
-- PARTE 4: Adicionar organization_id a TODAS as tabelas de domínio
-- =====================================================================

-- ---------------------------------------------------------------------
-- GRUPO A: Tabelas que JÁ TÊM tenant_id (36 tabelas)
-- organization_id adicionado como uuid nullable (será populado pelo
-- script de migração e depois tornado NOT NULL)
-- ---------------------------------------------------------------------

ALTER TABLE public.brand_kits            ADD COLUMN organization_id uuid;
ALTER TABLE public.calendar_events       ADD COLUMN organization_id uuid;
ALTER TABLE public.cashflow_projections  ADD COLUMN organization_id uuid;
ALTER TABLE public.closing_processes     ADD COLUMN organization_id uuid;
ALTER TABLE public.deal_approvals        ADD COLUMN organization_id uuid;
ALTER TABLE public.deal_commissions      ADD COLUMN organization_id uuid;
ALTER TABLE public.deal_pnl              ADD COLUMN organization_id uuid;
ALTER TABLE public.deal_rentals          ADD COLUMN organization_id uuid;
ALTER TABLE public.deal_state_history    ADD COLUMN organization_id uuid;
ALTER TABLE public.deal_tasks            ADD COLUMN organization_id uuid;
ALTER TABLE public.deal_visits           ADD COLUMN organization_id uuid;
ALTER TABLE public.deals                 ADD COLUMN organization_id uuid;
ALTER TABLE public.documents             ADD COLUMN organization_id uuid;
ALTER TABLE public.due_diligence_items   ADD COLUMN organization_id uuid;
ALTER TABLE public.email_campaigns       ADD COLUMN organization_id uuid;
ALTER TABLE public.financial_models      ADD COLUMN organization_id uuid;
ALTER TABLE public.investment_strategies ADD COLUMN organization_id uuid;
ALTER TABLE public.lead_interactions     ADD COLUMN organization_id uuid;
ALTER TABLE public.lead_listing_matches  ADD COLUMN organization_id uuid;
ALTER TABLE public.leads                 ADD COLUMN organization_id uuid;
ALTER TABLE public.listing_creatives     ADD COLUMN organization_id uuid;
ALTER TABLE public.listings              ADD COLUMN organization_id uuid;
ALTER TABLE public.market_alerts         ADD COLUMN organization_id uuid;
ALTER TABLE public.market_comparables    ADD COLUMN organization_id uuid;
ALTER TABLE public.market_zone_stats     ADD COLUMN organization_id uuid;
ALTER TABLE public.notifications         ADD COLUMN organization_id uuid;
ALTER TABLE public.nurture_sequences     ADD COLUMN organization_id uuid;
ALTER TABLE public.payment_conditions    ADD COLUMN organization_id uuid;
ALTER TABLE public.properties            ADD COLUMN organization_id uuid;
ALTER TABLE public.property_valuations   ADD COLUMN organization_id uuid;
ALTER TABLE public.proposals             ADD COLUMN organization_id uuid;
ALTER TABLE public.renovations           ADD COLUMN organization_id uuid;
ALTER TABLE public.social_media_accounts ADD COLUMN organization_id uuid;
ALTER TABLE public.social_media_posts    ADD COLUMN organization_id uuid;
ALTER TABLE public.transactions          ADD COLUMN organization_id uuid;
ALTER TABLE public.video_projects        ADD COLUMN organization_id uuid;

-- ---------------------------------------------------------------------
-- GRUPO B: Tabelas SEM tenant_id (10 tabelas)
-- Adicionamos organization_id directamente para isolamento defensivo.
-- Justificação por tabela:
--
-- groups:                 Raiz da cadeia WhatsApp. Sem org_id, impossível
--                         filtrar por organização sem JOINs.
-- messages:               Poderia herdar de groups via FK, mas JOIN em
--                         cada query é penalizante (3031 registos).
-- opportunities:          Idem — 3031 registos, performance justifica
--                         coluna directa.
-- market_data:            Poderia herdar de opportunities, mas com org_id
--                         directa evita JOIN duplo (market_data→opportunities→?).
-- classification_signals: Herda de investment_strategies, mas tabela
--                         pequena (12 registos) — org_id directa é simples.
-- renovation_milestones:  Herda de renovations (que tem tenant_id), mas
--                         org_id directa evita JOIN e torna RLS autónomo.
-- renovation_expenses:    Idem.
-- renovation_photos:      Idem.
-- listing_contents:       Herda de listings, mas org_id directa para
--                         queries independentes de conteúdo.
-- listing_price_history:  Idem.
-- ---------------------------------------------------------------------

ALTER TABLE public.groups                ADD COLUMN organization_id uuid;
ALTER TABLE public.messages              ADD COLUMN organization_id uuid;
ALTER TABLE public.opportunities         ADD COLUMN organization_id uuid;
ALTER TABLE public.market_data           ADD COLUMN organization_id uuid;
ALTER TABLE public.classification_signals ADD COLUMN organization_id uuid;
ALTER TABLE public.renovation_milestones ADD COLUMN organization_id uuid;
ALTER TABLE public.renovation_expenses   ADD COLUMN organization_id uuid;
ALTER TABLE public.renovation_photos     ADD COLUMN organization_id uuid;
ALTER TABLE public.listing_contents      ADD COLUMN organization_id uuid;
ALTER TABLE public.listing_price_history ADD COLUMN organization_id uuid;


-- =====================================================================
-- PARTE 5: Indexes para organization_id
-- =====================================================================
-- Criamos index em todas as tabelas com dados (>0 registos) e nas
-- tabelas que serão mais consultadas. Tabelas vazias podem esperar.

CREATE INDEX idx_brand_kits_org            ON public.brand_kits (organization_id);
CREATE INDEX idx_cashflow_projections_org  ON public.cashflow_projections (organization_id);
CREATE INDEX idx_classification_signals_org ON public.classification_signals (organization_id);
CREATE INDEX idx_deal_state_history_org    ON public.deal_state_history (organization_id);
CREATE INDEX idx_deal_tasks_org            ON public.deal_tasks (organization_id);
CREATE INDEX idx_deals_org                 ON public.deals (organization_id);
CREATE INDEX idx_due_diligence_items_org   ON public.due_diligence_items (organization_id);
CREATE INDEX idx_financial_models_org      ON public.financial_models (organization_id);
CREATE INDEX idx_groups_org                ON public.groups (organization_id);
CREATE INDEX idx_investment_strategies_org ON public.investment_strategies (organization_id);
CREATE INDEX idx_leads_org                 ON public.leads (organization_id);
CREATE INDEX idx_listings_org              ON public.listings (organization_id);
CREATE INDEX idx_market_comparables_org    ON public.market_comparables (organization_id);
CREATE INDEX idx_messages_org              ON public.messages (organization_id);
CREATE INDEX idx_opportunities_org         ON public.opportunities (organization_id);
CREATE INDEX idx_properties_org            ON public.properties (organization_id);
CREATE INDEX idx_renovations_org           ON public.renovations (organization_id);
CREATE INDEX idx_renovation_milestones_org ON public.renovation_milestones (organization_id);


COMMIT;
