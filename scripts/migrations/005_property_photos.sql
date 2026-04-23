-- ============================================================
-- Migração 005 — Fotos nas propriedades (M1)
-- ============================================================
-- Move o conceito de "fotos do imóvel" de Listing (M7) para
-- Property (M1). Permite registar fotos no acto de cadastro do
-- imóvel (M1) e depois propagá-las automaticamente para o
-- listing criado em M7 quando o deal transita para venda/
-- arrendamento.
--
-- Segue o mesmo padrão JSONB que já existe em listings.photos.
-- Idempotente: IF NOT EXISTS em tudo.
-- ============================================================

ALTER TABLE public.properties
    ADD COLUMN IF NOT EXISTS photos           jsonb       NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE public.properties
    ADD COLUMN IF NOT EXISTS cover_photo_url  text;

-- Index para queries por property_id em documents (usado para limpar fotos)
CREATE INDEX IF NOT EXISTS documents_entity_property_idx
    ON public.documents (entity_type, entity_id)
    WHERE entity_type = 'property';

COMMENT ON COLUMN public.properties.photos IS
    'Array JSON [{document_id,url,filename,order,is_cover}]. Cover espelhada em cover_photo_url.';
COMMENT ON COLUMN public.properties.cover_photo_url IS
    'URL da foto de capa. Herdada pelo listing quando deal transita para venda/arrendamento.';
