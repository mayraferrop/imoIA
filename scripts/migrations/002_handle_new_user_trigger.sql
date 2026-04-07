-- =============================================================================
-- MIGRATION 002: Trigger handle_new_user (signup automatico)
-- =============================================================================
-- Contexto: Quando um utilizador faz signup via Supabase Auth, este trigger
-- cria automaticamente uma organizacao pessoal e associa o utilizador como owner.
--
-- Depende de: 001_organizations.sql (tabelas organizations, organization_members)
--
-- NOTA: A remocao de utilizadores de auth.users NAO apaga automaticamente
-- organization_members nem organizations orfas. Para remover utilizadores
-- correctamente, usar script manual que limpa ambas as tabelas.
-- TODO: criar trigger BEFORE DELETE em iteracao futura.
--
-- ESTE FICHEIRO E PARA REVISAO. NAO EXECUTAR SEM APROVACAO EXPLICITA.
-- =============================================================================

BEGIN;

-- =====================================================================
-- PARTE 1: Extensao unaccent + funcao slugify
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS unaccent;

-- Converte texto em slug URL-safe: remove acentos, lowercase,
-- espacos -> hifens, remove caracteres especiais.
-- Ex: "Imoveis Acores" -> "imoveis-acores"

CREATE OR REPLACE FUNCTION public.slugify(text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT
AS $$
    SELECT regexp_replace(
        regexp_replace(
            regexp_replace(
                lower(unaccent($1)),
                '[^a-z0-9\s-]', '', 'g'   -- remove caracteres especiais
            ),
            '[\s]+', '-', 'g'              -- espacos -> hifens
        ),
        '^-+|-+$', '', 'g'                -- trim hifens nas pontas
    );
$$;


-- =====================================================================
-- PARTE 2: Funcao handle_new_user
-- =====================================================================
-- SECURITY DEFINER: corre como owner da funcao (postgres), bypass RLS.
-- Isto e necessario porque organizations e organization_members tem RLS
-- activo, e o trigger corre no contexto do signup (sem sessao autenticada).
--
-- ATOMICIDADE: Se este trigger falhar (por qualquer razao), o INSERT em
-- auth.users e revertido. O utilizador NAO fica criado. Isto garante que
-- nunca ha um user sem organizacao. Em caso de erro, verificar logs do
-- Postgres no Supabase Dashboard -> Logs -> Postgres.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    _org_name text;
    _slug text;
    _org_id uuid;
BEGIN
    -- Ler org_name dos metadados do signup (passado via options.data)
    _org_name := COALESCE(
        NULLIF(TRIM(NEW.raw_user_meta_data->>'org_name'), ''),
        'Personal'
    );

    -- Gerar slug unico: slugify(nome) + user_id completo
    -- Ex: "habta-a1b2c3d4-5e6f-7890-abcd-ef1234567890"
    -- Feio mas garantidamente unico (uuid e unico por definicao)
    _slug := public.slugify(_org_name) || '-' || NEW.id::text;

    -- Criar organizacao
    INSERT INTO public.organizations (name, slug, created_by)
    VALUES (_org_name, _slug, NEW.id)
    RETURNING id INTO _org_id;

    -- Associar utilizador como owner
    INSERT INTO public.organization_members (organization_id, user_id, role)
    VALUES (_org_id, NEW.id, 'owner');

    RETURN NEW;
END;
$$;


-- =====================================================================
-- PARTE 3: Trigger AFTER INSERT em auth.users
-- =====================================================================
-- AFTER INSERT porque o utilizador ja deve existir em auth.users antes
-- de criarmos a organizacao. Se o trigger falhar, o INSERT em auth.users
-- e revertido (transaccao atomica do PostgreSQL).

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();


COMMIT;
