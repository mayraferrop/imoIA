#!/usr/bin/env python3
"""Backup local dos dados do Supabase via REST API.

Exporta todas as tabelas com dados para ficheiros JSON.
Pode ser executado manualmente ou via cron.

Uso:
    python scripts/backup_supabase.py
    python scripts/backup_supabase.py --output-dir /path/to/backups
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Garantir que o projecto esta no sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(Path(_PROJECT_ROOT) / ".env")

import httpx
from loguru import logger

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

TABLES = [
    "tenants", "users", "properties", "groups", "messages", "opportunities",
    "market_data", "financial_models", "payment_conditions", "cashflow_projections",
    "deals", "deal_state_history", "deal_tasks", "deal_approvals",
    "deal_rentals", "deal_visits", "deal_commissions", "deal_pnl",
    "due_diligence_items", "renovations", "renovation_expenses",
    "renovation_milestones", "renovation_photos", "brand_kits",
    "listings", "listing_contents", "listing_creatives", "listing_price_history",
    "leads", "lead_interactions", "nurture_sequences",
    "market_comparables", "property_valuations", "market_zone_stats",
    "investment_strategies", "classification_signals", "documents",
]


def backup_table(table: str, headers: dict, timeout: int = 30) -> list:
    """Exporta todos os registos de uma tabela."""
    all_rows: list = []
    offset = 0
    limit = 1000

    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select=*&order=created_at.asc&limit={limit}&offset={offset}"
        try:
            resp = httpx.get(url, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                logger.warning(f"{table}: HTTP {resp.status_code}")
                break
            rows = resp.json()
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < limit:
                break
            offset += limit
        except Exception as e:
            logger.error(f"{table}: {e}")
            break

    return all_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup Supabase para JSON")
    parser.add_argument("--output-dir", default="backups", help="Directório de destino")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL e SUPABASE_KEY não configurados")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

    logger.info(f"Backup iniciado → {output_dir}")

    manifest = {"timestamp": timestamp, "tables": {}}
    total_rows = 0

    for table in TABLES:
        rows = backup_table(table, headers)
        count = len(rows)

        if count > 0:
            filepath = output_dir / f"{table}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, default=str, indent=2)
            logger.info(f"  {table}: {count} registos")
        else:
            logger.debug(f"  {table}: vazio")

        manifest["tables"][table] = count
        total_rows += count

    # Guardar manifest
    manifest["total_rows"] = total_rows
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Backup concluído: {total_rows} registos em {len([t for t, c in manifest['tables'].items() if c > 0])} tabelas → {output_dir}")


if __name__ == "__main__":
    main()
