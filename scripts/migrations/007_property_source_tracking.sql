-- ============================================================
-- Migração 007 — Property source tracking (M1 scraping portais PT)
-- ============================================================
-- Prepara a tabela properties para receber imóveis capturados por
-- scrapers de portais (Idealista, Imovirtual, ZAP, VivaReal, etc.)
-- e cria tabela dedicada para histórico de preço.
--
-- Decisões:
-- - source_url + source_external_id: permitem dedup e reabrir a página
-- - source_confidence + source_reasoning: vem do OpportunityClassifier
--   (reaproveitamos a pipeline de classificação por estratégia que
--   já corre em cima de mensagens WhatsApp)
-- - UNIQUE (source, source_external_id) WHERE source IS NOT NULL:
--   dedup. NULLs não batem no UNIQUE (imóveis manuais continuam livres)
-- - property_price_history: espelha listing_price_history, mas para
--   Property. Popula-se quando o scraper detecta alteração entre runs.
--
-- Idempotente: IF NOT EXISTS em tudo.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- PARTE 1: Extensão do Property para rastreio de origem scraping
-- ------------------------------------------------------------

ALTER TABLE public.properties
    ADD COLUMN IF NOT EXISTS source_url          text,
    ADD COLUMN IF NOT EXISTS source_external_id  varchar(255),
    ADD COLUMN IF NOT EXISTS source_confidence   real,
    ADD COLUMN IF NOT EXISTS source_reasoning    text,
    ADD COLUMN IF NOT EXISTS source_last_seen_at timestamptz;

-- Dedup por (source, source_external_id). UNIQUE parcial para não
-- afectar imóveis manuais (source IS NULL).
CREATE UNIQUE INDEX IF NOT EXISTS properties_source_external_uidx
    ON public.properties (source, source_external_id)
    WHERE source IS NOT NULL AND source_external_id IS NOT NULL;

-- Index para queries de listings recentes ("scraped nas últimas 24h")
CREATE INDEX IF NOT EXISTS properties_source_last_seen_idx
    ON public.properties (organization_id, source, source_last_seen_at DESC)
    WHERE source IS NOT NULL;

COMMENT ON COLUMN public.properties.source_url IS
    'URL original do anúncio no portal (idealista.pt/..., imovirtual.com/...)';
COMMENT ON COLUMN public.properties.source_external_id IS
    'ID do listing no portal (para dedup entre runs do scraper)';
COMMENT ON COLUMN public.properties.source_confidence IS
    'Confiança 0-1 do OpportunityClassifier sobre ser oportunidade face à estratégia activa';
COMMENT ON COLUMN public.properties.source_reasoning IS
    'Razão que a IA deu para classificar como oportunidade';
COMMENT ON COLUMN public.properties.source_last_seen_at IS
    'Última vez que o scraper viu este listing online (para despejar off-market)';

-- ------------------------------------------------------------
-- PARTE 2: property_price_history (histórico de alterações)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.property_price_history (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id       uuid NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
    organization_id   uuid NOT NULL REFERENCES public.organizations(id),
    old_price         numeric,
    new_price         numeric NOT NULL,
    source            varchar(50),
    detected_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pph_property
    ON public.property_price_history(property_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_pph_org
    ON public.property_price_history(organization_id, detected_at DESC);

-- ------------------------------------------------------------
-- PARTE 3: RLS + grants (mesmo padrão das outras tabelas)
-- ------------------------------------------------------------

ALTER TABLE public.property_price_history ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.property_price_history TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.property_price_history TO authenticated;
GRANT SELECT ON public.property_price_history TO anon;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'property_price_history' AND policyname = 'imoia_app_all'
    ) THEN
        CREATE POLICY imoia_app_all ON public.property_price_history
            FOR ALL TO imoia_app USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'property_price_history' AND policyname = 'org_all'
    ) THEN
        CREATE POLICY org_all ON public.property_price_history
            FOR ALL TO authenticated
            USING (organization_id IN (SELECT public.user_organization_ids()))
            WITH CHECK (organization_id IN (SELECT public.user_organization_ids()));
    END IF;
END $$;

COMMIT;
