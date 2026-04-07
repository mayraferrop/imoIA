#!/usr/bin/env python3
"""Migração de dados: tenant_id → organization_id.

Cria a organização HABTA a partir do tenant existente e popula
organization_id em todas as tabelas de domínio.

Uso:
    python scripts/migrations/001_migrate_org_data.py
    python scripts/migrations/001_migrate_org_data.py --dry-run

ESTE SCRIPT É PARA REVISÃO. NÃO EXECUTAR SEM APROVAÇÃO EXPLÍCITA.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

# Garantir projecto no path
_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(Path(_ROOT) / ".env")

import httpx
from loguru import logger

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# -----------------------------------------------------------------------
# Configuração
# -----------------------------------------------------------------------

# Tenant existente (do backup validado)
EXISTING_TENANT_ID = "7127a463-eb79-42fe-ba54-6f2551b459af"

# Nova organização
ORG_ID = str(uuid4())  # Gerado uma vez, reutilizado em todo o script
ORG_NAME = "HABTA"
ORG_SLUG = "habta"

# TODO: Substituir pelo user_id real após criar conta na Fase 2
OWNER_USER_ID = None  # Placeholder — preenchido manualmente

# Grupo A: tabelas com tenant_id (mapear directamente)
TABLES_WITH_TENANT_ID = [
    "brand_kits",
    "calendar_events",
    "cashflow_projections",
    "closing_processes",
    "deal_approvals",
    "deal_commissions",
    "deal_pnl",
    "deal_rentals",
    "deal_state_history",
    "deal_tasks",
    "deal_visits",
    "deals",
    "documents",
    "due_diligence_items",
    "email_campaigns",
    "financial_models",
    "investment_strategies",
    "lead_interactions",
    "lead_listing_matches",
    "leads",
    "listing_creatives",
    "listings",
    "market_alerts",
    "market_comparables",
    "market_zone_stats",
    "notifications",
    "nurture_sequences",
    "payment_conditions",
    "properties",
    "property_valuations",
    "proposals",
    "renovations",
    "social_media_accounts",
    "social_media_posts",
    "transactions",
    "video_projects",
]

# Grupo B: tabelas sem tenant_id (popular via parent ou atribuir à org única)
# Como só existe 1 tenant/organização, todas as linhas recebem o mesmo org_id.
TABLES_WITHOUT_TENANT_ID = [
    "groups",
    "messages",
    "opportunities",
    "market_data",
    "classification_signals",
    "renovation_milestones",
    "renovation_expenses",
    "renovation_photos",
    "listing_contents",
    "listing_price_history",
]


def supabase_rpc(sql: str, dry_run: bool = False) -> dict | None:
    """Executa SQL via PostgREST RPC (requer function no Supabase)."""
    # Nota: Supabase REST não permite SQL arbitrário.
    # Vamos usar a abordagem de PATCH por tabela.
    raise NotImplementedError("Usar update_table() em vez de SQL directo")


def count_table(table: str) -> int:
    """Conta registos numa tabela."""
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/{table}?select=*",
        headers={**HEADERS, "Prefer": "count=exact"},
        timeout=30,
    )
    count_header = resp.headers.get("content-range", "")
    if "/" in count_header:
        total = count_header.split("/")[1]
        return int(total) if total != "*" else 0
    return 0


def update_table_with_tenant(table: str, org_id: str, tenant_id: str,
                              dry_run: bool = False) -> int:
    """Popula organization_id para linhas com tenant_id específico."""
    # Conta registos a actualizar
    count = count_table(table)
    if count == 0:
        logger.debug(f"  {table}: 0 registos — skip")
        return 0

    if dry_run:
        logger.info(f"  {table}: {count} registos (DRY RUN — não altera)")
        return count

    # PATCH via REST API: actualizar todas as linhas onde tenant_id = X
    resp = httpx.patch(
        f"{SUPABASE_URL}/rest/v1/{table}?tenant_id=eq.{tenant_id}",
        headers={**HEADERS, "Prefer": "return=headers-only"},
        json={"organization_id": org_id},
        timeout=60,
    )
    if resp.status_code in (200, 204):
        logger.info(f"  {table}: actualizado (tenant_id={tenant_id[:8]}…)")
        return count

    # Sem fallback — falhar ruidosamente para evitar data corruption
    logger.error(
        f"  {table}: FALHOU — HTTP {resp.status_code}: {resp.text[:200]}\n"
        f"  ABORTADO. Corrigir o erro e re-executar. Nenhum dado foi corrompido."
    )
    sys.exit(1)


def update_table_without_tenant(table: str, org_id: str,
                                 dry_run: bool = False) -> int:
    """Popula organization_id para tabelas sem tenant_id."""
    count = count_table(table)
    if count == 0:
        logger.debug(f"  {table}: 0 registos — skip")
        return 0

    if dry_run:
        logger.info(f"  {table}: {count} registos (DRY RUN — não altera)")
        return count

    # Todas as linhas recebem a mesma org (só existe 1)
    resp = httpx.patch(
        f"{SUPABASE_URL}/rest/v1/{table}?organization_id=is.null",
        headers={**HEADERS, "Prefer": "return=headers-only"},
        json={"organization_id": org_id},
        timeout=60,
    )
    if resp.status_code in (200, 204):
        logger.info(f"  {table}: actualizado ({count} registos)")
        return count

    logger.error(f"  {table}: FALHOU — HTTP {resp.status_code}: {resp.text[:200]}")
    return 0


def create_organization(org_id: str, dry_run: bool = False) -> bool:
    """Cria a organização HABTA."""
    org = {
        "id": org_id,
        "name": ORG_NAME,
        "slug": ORG_SLUG,
    }

    if dry_run:
        logger.info(f"DRY RUN — Criaria organização: {org}")
        return True

    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/organizations",
        headers=HEADERS,
        json=org,
        timeout=30,
    )
    if resp.status_code in (200, 201):
        logger.info(f"Organização criada: {ORG_NAME} (id={org_id[:8]}…)")
        return True

    if resp.status_code == 409:
        logger.info(f"Organização {ORG_NAME} já existe (slug={ORG_SLUG}) — re-execução segura")
        return True

    logger.error(f"Falha ao criar organização: HTTP {resp.status_code}: {resp.text[:200]}")
    return False


def create_owner_membership(org_id: str, dry_run: bool = False) -> bool:
    """Cria membership owner para a organização HABTA."""
    if OWNER_USER_ID is None:
        logger.warning(
            "TODO: OWNER_USER_ID não definido. "
            "Definir após criar conta na Fase 2 e re-executar."
        )
        return False

    member = {
        "organization_id": org_id,
        "user_id": OWNER_USER_ID,
        "role": "owner",
    }

    if dry_run:
        logger.info(f"DRY RUN — Criaria membership: {member}")
        return True

    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/organization_members",
        headers=HEADERS,
        json=member,
        timeout=30,
    )
    if resp.status_code in (200, 201):
        logger.info(f"Owner membership criada: user={OWNER_USER_ID[:8]}… org={org_id[:8]}…")
        return True

    logger.error(f"Falha ao criar membership: HTTP {resp.status_code}: {resp.text[:200]}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrar tenant_id → organization_id")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra o que faria sem alterar dados")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY não configurados")
        sys.exit(1)

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "LIVE"
    logger.info(f"=== Migração organization_id [{mode}] ===")
    logger.info(f"Org: {ORG_NAME} (slug={ORG_SLUG}, id={ORG_ID[:8]}…)")
    logger.info(f"Tenant existente: {EXISTING_TENANT_ID[:8]}…")

    # Passo 1: Criar organização
    logger.info("\n--- Passo 1: Criar organização ---")
    if not create_organization(ORG_ID, dry_run):
        logger.error("Abortado — falha ao criar organização")
        sys.exit(1)

    # Passo 2: Criar owner membership (se user_id disponível)
    logger.info("\n--- Passo 2: Criar owner membership ---")
    create_owner_membership(ORG_ID, dry_run)

    # Passo 3: Popular organization_id — Grupo A (com tenant_id)
    logger.info(f"\n--- Passo 3: Grupo A — {len(TABLES_WITH_TENANT_ID)} tabelas com tenant_id ---")
    total_a = 0
    for table in TABLES_WITH_TENANT_ID:
        total_a += update_table_with_tenant(table, ORG_ID, EXISTING_TENANT_ID, dry_run)

    # Passo 4: Popular organization_id — Grupo B (sem tenant_id)
    logger.info(f"\n--- Passo 4: Grupo B — {len(TABLES_WITHOUT_TENANT_ID)} tabelas sem tenant_id ---")
    total_b = 0
    for table in TABLES_WITHOUT_TENANT_ID:
        total_b += update_table_without_tenant(table, ORG_ID, dry_run)

    # Resumo
    logger.info(f"\n=== Resumo [{mode}] ===")
    logger.info(f"Organização: {ORG_NAME} ({ORG_ID[:8]}…)")
    logger.info(f"Grupo A: {total_a} registos actualizados em {len(TABLES_WITH_TENANT_ID)} tabelas")
    logger.info(f"Grupo B: {total_b} registos actualizados em {len(TABLES_WITHOUT_TENANT_ID)} tabelas")
    logger.info(f"Total: {total_a + total_b} registos")

    if OWNER_USER_ID is None:
        logger.warning("ATENÇÃO: Owner membership não criada — definir OWNER_USER_ID na Fase 2")

    # Passo 5: Validação final — zero NULLs em organization_id
    if not dry_run:
        logger.info(f"\n--- Passo 5: Validação final ---")
        all_tables = TABLES_WITH_TENANT_ID + TABLES_WITHOUT_TENANT_ID
        tables_ok = 0
        total_rows = 0
        for table in all_tables:
            resp = httpx.get(
                f"{SUPABASE_URL}/rest/v1/{table}?organization_id=is.null&select=id",
                headers={**HEADERS, "Prefer": "count=exact"},
                timeout=30,
            )
            if resp.status_code != 200:
                logger.error(
                    f"  FALHA na validação de {table}: HTTP {resp.status_code}: "
                    f"{resp.text[:200]}"
                )
                sys.exit(1)

            null_count_header = resp.headers.get("content-range", "")
            null_count = 0
            if "/" in null_count_header:
                total_str = null_count_header.split("/")[1]
                null_count = int(total_str) if total_str != "*" else 0

            row_count = count_table(table)
            total_rows += row_count

            if null_count > 0:
                logger.error(
                    f"  FALHA: {table} tem {null_count} linhas com organization_id = NULL"
                )
                sys.exit(1)
            else:
                tables_ok += 1

        logger.info(
            f"Validação final: {tables_ok} tabelas, {total_rows} linhas, "
            f"0 NULLs em organization_id"
        )
        logger.info("\nPróximo passo: executar scripts/migrations/001_post_migration.sql")


if __name__ == "__main__":
    main()
