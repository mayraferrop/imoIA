"""Cron job: corre run_pipeline() para todas as organizações com WhatsApp activo.

Invocado pelo Render Cron Job em schedule. Conecta directamente à BD + bridge Baileys.
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
    """Devolve IDs de organizações que têm pelo menos 1 grupo WhatsApp activo."""
    from src.database.db import get_session
    from src.database.models import Group
    from sqlalchemy import select, distinct

    with get_session() as s:
        rows = s.execute(
            select(distinct(Group.organization_id)).where(Group.is_active == True)
        ).all()
        return [r[0] for r in rows if r[0]]


def main() -> int:
    from src.database.supabase_rest import current_org_id
    from src.modules.m1_ingestor.service import run_pipeline

    override = os.getenv("IMOIA_CRON_ORG_IDS", "").strip()
    if override:
        org_ids = [x.strip() for x in override.split(",") if x.strip()]
    else:
        org_ids = _discover_orgs()

    if not org_ids:
        logger.warning("[cron] nenhuma organização com grupos activos — a sair")
        return 0

    logger.info(f"[cron] a processar {len(org_ids)} organização(ões): {org_ids}")
    total_errors = 0

    for oid in org_ids:
        current_org_id.set(oid)
        t0 = time.time()
        try:
            result = run_pipeline(trigger_source="cron")
            elapsed = time.time() - t0
            logger.info(
                f"[cron] org={oid} done in {elapsed:.1f}s | "
                f"msgs={result.messages_fetched} opps={result.opportunities_found} "
                f"groups={result.groups_processed} errors={len(result.errors)}"
            )
            total_errors += len(result.errors)
        except Exception as e:
            total_errors += 1
            logger.exception(f"[cron] org={oid} FALHOU: {type(e).__name__}: {e}")

    logger.info(f"[cron] finalizado às {datetime.now(tz=timezone.utc).isoformat()} | erros totais: {total_errors}")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
