"""Helpers para migracao SQLite → PostgreSQL.

Funcoes utilitarias usadas pelo script scripts/migrate_to_postgres.py.
NAO altera a BD actual — apenas le dados para migrar.
"""

from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from src.database.db import get_session
from src.database.models import Group, MarketData, Message, Opportunity


def export_all_data() -> Dict[str, List[Dict[str, Any]]]:
    """Exporta todos os dados da BD SQLite actual.

    Returns:
        Dict com chaves 'groups', 'messages', 'opportunities', 'market_data'.
        Cada valor e uma lista de dicts com os dados da tabela.
    """
    data: Dict[str, List[Dict[str, Any]]] = {
        "groups": [],
        "messages": [],
        "opportunities": [],
        "market_data": [],
    }

    with get_session() as session:
        # Groups
        for g in session.execute(select(Group)).scalars().all():
            data["groups"].append({
                "id": g.id,
                "whatsapp_group_id": g.whatsapp_group_id,
                "name": g.name,
                "is_active": g.is_active,
                "last_processed_at": g.last_processed_at,
                "message_count": g.message_count,
                "opportunity_count": g.opportunity_count,
                "created_at": g.created_at,
            })

        # Messages
        for m in session.execute(select(Message)).scalars().all():
            data["messages"].append({
                "id": m.id,
                "whatsapp_message_id": m.whatsapp_message_id,
                "group_id": m.group_id,
                "group_name": m.group_name,
                "sender_id": m.sender_id,
                "sender_name": m.sender_name,
                "content": m.content,
                "message_type": m.message_type,
                "media_url": m.media_url,
                "timestamp": m.timestamp,
                "processed": m.processed,
                "created_at": m.created_at,
            })

        # Opportunities
        for o in session.execute(select(Opportunity)).scalars().all():
            data["opportunities"].append({
                "id": o.id,
                "message_id": o.message_id,
                "is_opportunity": o.is_opportunity,
                "confidence": o.confidence,
                "opportunity_type": o.opportunity_type,
                "property_type": o.property_type,
                "location_extracted": o.location_extracted,
                "parish": o.parish,
                "municipality": o.municipality,
                "district": o.district,
                "price_mentioned": o.price_mentioned,
                "area_m2": o.area_m2,
                "bedrooms": o.bedrooms,
                "ai_reasoning": o.ai_reasoning,
                "original_message": o.original_message,
                "status": o.status,
                "deal_score": o.deal_score,
                "deal_grade": o.deal_grade,
                "notes": o.notes,
                "created_at": o.created_at,
            })

        # MarketData
        for md in session.execute(select(MarketData)).scalars().all():
            data["market_data"].append({
                "id": md.id,
                "opportunity_id": md.opportunity_id,
                "ine_median_price_m2": md.ine_median_price_m2,
                "ine_quarter": md.ine_quarter,
                "estimated_market_value": md.estimated_market_value,
                "gross_yield_pct": md.gross_yield_pct,
                "net_yield_pct": md.net_yield_pct,
                "price_vs_market_pct": md.price_vs_market_pct,
                "imt_estimate": md.imt_estimate,
                "total_acquisition_cost": md.total_acquisition_cost,
                "created_at": md.created_at,
            })

    logger.info(
        f"Dados exportados: {len(data['groups'])} grupos, "
        f"{len(data['messages'])} mensagens, "
        f"{len(data['opportunities'])} oportunidades, "
        f"{len(data['market_data'])} market_data"
    )
    return data


def validate_migration(
    sqlite_counts: Dict[str, int],
    pg_counts: Dict[str, int],
) -> bool:
    """Valida que a migracao foi completa comparando contagens.

    Args:
        sqlite_counts: Contagens por tabela no SQLite.
        pg_counts: Contagens por tabela no PostgreSQL.

    Returns:
        True se as contagens coincidem.
    """
    ok = True
    for table, sqlite_count in sqlite_counts.items():
        pg_count = pg_counts.get(table, 0)
        if sqlite_count != pg_count:
            logger.error(
                f"Migracao incompleta: {table} — "
                f"SQLite={sqlite_count}, PostgreSQL={pg_count}"
            )
            ok = False
        else:
            logger.info(f"OK: {table} — {sqlite_count} registos")
    return ok
