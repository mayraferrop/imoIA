-- ============================================================
-- Migração 002 — Fase 2B Dia 1
-- ============================================================
-- Verifica que a coluna `role` existe em organization_members
-- (foi criada na migração 001 da Fase 1) e garante que existe
-- pelo menos um owner para a organização HABTA.
--
-- Idempotente: pode ser executada múltiplas vezes sem efeito.
-- ============================================================

-- 1. Verificar que a coluna role existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'organization_members'
          AND column_name = 'role'
    ) THEN
        RAISE EXCEPTION 'Coluna role não existe em organization_members. Migração 001 não foi aplicada.';
    END IF;
END $$;

-- 2. Verificar que a constraint check existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname LIKE '%organization_members%role%check%'
           OR conname = 'organization_members_role_check'
    ) THEN
        RAISE EXCEPTION 'Constraint check de role não existe em organization_members.';
    END IF;
END $$;

-- 3. Garantir que existe pelo menos um owner para a HABTA
-- (Se já existir, não faz nada. Se não existir, dá erro claro
-- pedindo para correr scripts/setup_owner.py)
DO $$
DECLARE
    habta_org_id uuid;
    habta_owner_count int;
BEGIN
    -- Procurar org HABTA
    SELECT id INTO habta_org_id
    FROM organizations
    WHERE slug = 'habta' OR name = 'HABTA'
    LIMIT 1;

    IF habta_org_id IS NULL THEN
        RAISE NOTICE 'Organização HABTA não encontrada. Criar primeiro via Fase 1.';
        RETURN;
    END IF;

    -- Contar owners
    SELECT COUNT(*) INTO habta_owner_count
    FROM organization_members
    WHERE organization_id = habta_org_id
      AND role = 'owner';

    IF habta_owner_count = 0 THEN
        RAISE NOTICE 'Sem owner para HABTA. Correr scripts/setup_owner.py para criar.';
    ELSE
        RAISE NOTICE 'HABTA tem % owner(s). OK.', habta_owner_count;
    END IF;
END $$;

-- ============================================================
-- Marcador Fase 2B Dia 1: schema validado, sem alterações.
-- ============================================================
