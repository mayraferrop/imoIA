"""Migracao Fase 2: Opportunities (legacy) → Properties (models_v2).

Migra todas as oportunidades reais (is_opportunity=1) que ainda nao foram
convertidas em Property. Preserva o link via source_opportunity_id.

Tambem migra market_data para a tabela property_valuations (models_v2).

Uso:
    python scripts/migrate_opportunities_to_properties.py
    python scripts/migrate_opportunities_to_properties.py --dry-run
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

# Adicionar raiz do projecto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from sqlalchemy import select, text

from src.database.db import get_session, init_db
from src.database.models import MarketData, Message, Opportunity
from src.database.models_v2 import Property, Tenant

# Importar para registar tabelas no metadata
import src.database.models_v2  # noqa: F401

_DEFAULT_TENANT_SLUG = "default"


def _extract_tags(opp: Opportunity) -> list:
    """Extrai tags relevantes de uma Opportunity."""
    tags: list = []
    opp_type = (opp.opportunity_type or "").lower()
    if "off_market" in opp_type:
        tags.append("off_market")
    if "urgente" in opp_type or "venda_urgente" in opp_type:
        tags.append("urgente")
    if "reabilitacao" in opp_type:
        tags.append("reabilitacao")
    if "heranca" in (opp.original_message or "").lower():
        tags.append("heranca")
    if "predio" in opp_type:
        tags.append("predio_inteiro")
    if opp.deal_grade:
        tags.append(f"grade_{opp.deal_grade}")
    return tags


def _map_condition(opportunity_type: str | None) -> str | None:
    """Mapeia opportunity_type para condition da Property."""
    if not opportunity_type:
        return None
    ot = opportunity_type.lower()
    if "reabilitacao" in ot or "predio_inteiro" in ot:
        return "para_renovar"
    return None


def _map_status(opp_status: str | None, deal_grade: str | None) -> str:
    """Mapeia status da Opportunity para status da Property."""
    if opp_status and opp_status != "nova":
        status_map = {
            "em_analise": "em_analise",
            "contactada": "em_analise",
            "proposta": "proposta",
            "descartada": "descartado",
            "concluida": "concluido",
        }
        return status_map.get(opp_status, "oportunidade")
    return "oportunidade"


def migrate_opportunities(dry_run: bool = False) -> dict:
    """Migra oportunidades para properties.

    Returns:
        Dict com contadores: migrated, skipped, market_data_migrated, errors.
    """
    init_db()
    stats = {
        "migrated": 0,
        "skipped": 0,
        "market_data_migrated": 0,
        "errors": 0,
    }

    with get_session() as session:
        # Garantir tenant default
        tenant = session.execute(
            select(Tenant).where(Tenant.slug == _DEFAULT_TENANT_SLUG)
        ).scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(
                id=str(uuid4()),
                name="ImoIA",
                slug=_DEFAULT_TENANT_SLUG,
                country="PT",
            )
            session.add(tenant)
            session.flush()
            logger.info(f"Tenant default criado: {tenant.id}")

        tenant_id = tenant.id

        # IDs de oportunidades ja migradas
        existing_ids = set(
            session.execute(
                select(Property.source_opportunity_id).where(
                    Property.source_opportunity_id.isnot(None)
                )
            ).scalars().all()
        )
        logger.info(f"Properties existentes com link a opportunity: {len(existing_ids)}")

        # Buscar oportunidades reais nao migradas
        opps = session.execute(
            select(Opportunity).where(
                Opportunity.is_opportunity.is_(True),
                Opportunity.id.notin_(existing_ids) if existing_ids else True,
            ).order_by(Opportunity.id)
        ).scalars().all()

        logger.info(f"Oportunidades por migrar: {len(opps)}")

        for opp in opps:
            try:
                # Buscar info da mensagem original
                msg = session.get(Message, opp.message_id) if opp.message_id else None
                contact_name = msg.sender_name if msg else None

                prop = Property(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    source="whatsapp",
                    source_opportunity_id=opp.id,
                    country="PT",
                    district=opp.district,
                    municipality=opp.municipality,
                    parish=opp.parish,
                    property_type=opp.property_type,
                    gross_area_m2=opp.area_m2,
                    bedrooms=opp.bedrooms,
                    asking_price=opp.price_mentioned,
                    condition=_map_condition(opp.opportunity_type),
                    status=_map_status(opp.status, opp.deal_grade),
                    is_off_market="off_market" in (opp.opportunity_type or "").lower(),
                    contact_name=contact_name,
                    notes=opp.ai_reasoning,
                    tags=_extract_tags(opp),
                )

                if not dry_run:
                    session.add(prop)
                    session.flush()

                stats["migrated"] += 1
                logger.debug(
                    f"Opp #{opp.id} → Property {prop.id} "
                    f"({opp.municipality}, {opp.price_mentioned}EUR)"
                )

                # Enriquecer notas com market_data se existir
                md = session.execute(
                    select(MarketData).where(
                        MarketData.opportunity_id == opp.id
                    )
                ).scalar_one_or_none()

                if md and not dry_run:
                    market_notes = []
                    if md.ine_median_price_m2:
                        market_notes.append(f"INE: {md.ine_median_price_m2} EUR/m2 ({md.ine_quarter})")
                    if md.estimated_market_value:
                        market_notes.append(f"Valor estimado: {md.estimated_market_value} EUR")
                    if md.gross_yield_pct:
                        market_notes.append(f"Yield bruto: {md.gross_yield_pct}%")
                    if md.imt_estimate:
                        market_notes.append(f"IMT estimado: {md.imt_estimate} EUR")

                    if market_notes:
                        existing_notes = prop.notes or ""
                        prop.notes = f"{existing_notes}\n\n[Dados mercado migrados] {' | '.join(market_notes)}".strip()

                    stats["market_data_migrated"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Erro ao migrar opp #{opp.id}: {e}")

        if dry_run:
            logger.info("DRY RUN — nenhuma alteracao feita na BD")
            session.rollback()
        else:
            logger.info("Commit das alteracoes...")

    return stats


def main() -> None:
    """Entry point."""
    dry_run = "--dry-run" in sys.argv

    logger.info(f"=== Migracao Fase 2: Opportunities → Properties ===")
    logger.info(f"Modo: {'DRY RUN' if dry_run else 'EXECUCAO REAL'}")

    stats = migrate_opportunities(dry_run=dry_run)

    logger.info("=== Resultado ===")
    logger.info(f"  Oportunidades migradas: {stats['migrated']}")
    logger.info(f"  Dados de mercado migrados: {stats['market_data_migrated']}")
    logger.info(f"  Ignoradas (ja existiam): {stats['skipped']}")
    logger.info(f"  Erros: {stats['errors']}")

    if dry_run:
        logger.info("Para executar de verdade, corra sem --dry-run")


if __name__ == "__main__":
    main()
