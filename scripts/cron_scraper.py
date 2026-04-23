"""Cron job: corre o scraper M1 (portais PT) para organizações com estratégia activa.

Invocado pelo Render Cron Job em schedule diário. Requer:
- DATABASE_URL / SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY no env
- Pelo menos 1 estratégia activa em investment_strategies (senão classifier não filtra)

O scraper só persiste listings classificados como `is_opportunity=true` pela
estratégia activa do tenant. Listings fora da estratégia são descartados.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from loguru import logger


def _discover_orgs() -> list[str]:
    """Devolve IDs de organizações-alvo.

    Estratégia: qualquer org que tenha grupos WhatsApp activos OU
    propriedades. O filtro por estratégia é aplicado depois.
    """
    from src.database import supabase_rest as db

    ids: set[str] = set()
    with db.admin_client():
        groups = db.list_rows("groups", filters="is_active=eq.true", select="organization_id", limit=1000)
        for g in groups:
            oid = g.get("organization_id")
            if oid:
                ids.add(oid)

        props = db.list_rows("properties", select="organization_id", limit=1000)
        for p in props:
            oid = p.get("organization_id")
            if oid:
                ids.add(oid)

    return sorted(ids)


def _active_strategy_exists(tenant_id: str) -> bool:
    from src.database import supabase_rest as db
    with db.admin_client():
        rows = db.list_rows(
            "investment_strategies",
            filters=f"tenant_id=eq.{tenant_id}&is_active=eq.true",
            limit=1,
        )
    return bool(rows)


def main() -> int:
    from src.database import supabase_rest as db
    from src.database.supabase_rest import current_org_id
    from src.modules.m1_scraper.service import run_scraper_pipeline

    override = os.getenv("IMOIA_CRON_ORG_IDS", "").strip()
    if override:
        org_ids = [x.strip() for x in override.split(",") if x.strip()]
    else:
        org_ids = _discover_orgs()

    if not org_ids:
        logger.warning("[cron-scraper] nenhuma organização candidata — a sair")
        return 0

    tenant_id = db.ensure_tenant()
    if not _active_strategy_exists(tenant_id):
        logger.warning(
            f"[cron-scraper] tenant={tenant_id} sem estratégia activa — a sair "
            "(configure uma em /settings/strategy)"
        )
        return 0

    logger.info(f"[cron-scraper] a processar {len(org_ids)} organização(ões): {org_ids}")
    total_errors = 0
    max_listings = int(os.getenv("IMOIA_SCRAPER_MAX_LISTINGS", "200"))

    for oid in org_ids:
        current_org_id.set(oid)
        t0 = time.time()
        try:
            result = run_scraper_pipeline(
                organization_id=oid,
                tenant_id=tenant_id,
                max_listings=max_listings,
            )
            elapsed = time.time() - t0
            logger.info(
                f"[cron-scraper] org={oid} done in {elapsed:.1f}s | "
                f"fetched={result.listings_fetched} "
                f"classified={result.listings_classified} "
                f"opps={result.opportunities_found} "
                f"created={result.properties_created} "
                f"updated={result.properties_updated} "
                f"price_changes={result.price_changes} "
                f"errors={len(result.errors)}"
            )
            total_errors += len(result.errors)
        except Exception as e:
            total_errors += 1
            logger.exception(f"[cron-scraper] org={oid} FALHOU: {type(e).__name__}: {e}")

    logger.info(
        f"[cron-scraper] finalizado às {datetime.now(tz=timezone.utc).isoformat()} "
        f"| erros totais: {total_errors}"
    )
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
