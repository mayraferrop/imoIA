"""Router FastAPI de retrocompatibilidade para o ingestor (M1).

Le dados historicos das tabelas legacy (groups, messages, opportunities, market_data)
que continuam a existir na BD como read-only.
O pipeline de ingestao WhatsApp foi descontinuado.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from loguru import logger
from sqlalchemy import func, select

from src.database.db import get_session
from src.database.models import Group, MarketData, Message, Opportunity

router = APIRouter()

_LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


def _opp_to_dict(opp: Opportunity) -> Dict[str, Any]:
    """Serializa uma Opportunity para dict."""
    return {
        "id": opp.id,
        "is_opportunity": opp.is_opportunity,
        "confidence": opp.confidence,
        "opportunity_type": opp.opportunity_type,
        "property_type": opp.property_type,
        "location": opp.location_extracted,
        "parish": opp.parish,
        "municipality": opp.municipality,
        "district": opp.district,
        "price": opp.price_mentioned,
        "area_m2": opp.area_m2,
        "bedrooms": opp.bedrooms,
        "deal_score": opp.deal_score,
        "deal_grade": opp.deal_grade,
        "status": opp.status,
        "ai_reasoning": opp.ai_reasoning,
        "original_message": opp.original_message,
        "notes": opp.notes,
        "created_at": opp.created_at.isoformat() if opp.created_at else None,
    }


def _market_to_dict(md: MarketData) -> Dict[str, Any]:
    """Serializa MarketData para dict."""
    return {
        "ine_median_price_m2": md.ine_median_price_m2,
        "ine_quarter": md.ine_quarter,
        "casafari_avg_price_m2": md.casafari_avg_price_m2,
        "casafari_median_price_m2": md.casafari_median_price_m2,
        "sir_median_price_m2": md.sir_median_price_m2,
        "sir_market_position": md.sir_market_position,
        "sir_price_vs_market_pct": md.sir_price_vs_market_pct,
        "idealista_avg_price_m2": md.idealista_avg_price_m2,
        "idealista_listings_count": md.idealista_listings_count,
        "estimated_market_value": md.estimated_market_value,
        "estimated_monthly_rent": md.estimated_monthly_rent,
        "gross_yield_pct": md.gross_yield_pct,
        "net_yield_pct": md.net_yield_pct,
        "price_vs_market_pct": md.price_vs_market_pct,
        "imt_estimate": md.imt_estimate,
        "stamp_duty_estimate": md.stamp_duty_estimate,
        "total_acquisition_cost": md.total_acquisition_cost,
    }


@router.post("/trigger", summary="Disparar pipeline de ingestao")
async def trigger_pipeline(background_tasks: BackgroundTasks) -> Dict[str, str]:
    """Dispara o pipeline M1 (WhatsApp → IA → oportunidades) em background."""
    from src.modules.m1_ingestor.service import run_pipeline

    background_tasks.add_task(run_pipeline)
    logger.info("Pipeline M1 disparado via API")
    return {
        "status": "pipeline_iniciado",
        "mensagem": "Pipeline a correr em background",
    }


@router.get("/status", summary="Estado da ultima execucao")
async def get_pipeline_status() -> Dict[str, Any]:
    """Retorna estado do sistema (retrocompatibilidade)."""
    status_file = _LOGS_DIR / "pipeline_status.json"
    if status_file.exists():
        try:
            return json.loads(status_file.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {"state": "descontinuado", "mensagem": "Pipeline migrado para API REST"}


@router.get("/groups", summary="Listar grupos monitorizados")
async def list_groups() -> List[Dict[str, Any]]:
    """Lista todos os grupos com estatisticas (dados historicos)."""
    with get_session() as session:
        groups = session.execute(
            select(Group).order_by(Group.name)
        ).scalars().all()
        return [
            {
                "id": g.id,
                "whatsapp_group_id": g.whatsapp_group_id,
                "name": g.name,
                "is_active": g.is_active,
                "last_processed_at": (
                    g.last_processed_at.isoformat()
                    if g.last_processed_at
                    else None
                ),
                "messages": g.message_count,
                "opportunities": g.opportunity_count,
            }
            for g in groups
        ]


@router.get("/opportunities", summary="Listar oportunidades")
async def list_opportunities(
    min_confidence: float = Query(0.6, ge=0.0, le=1.0),
    grade: Optional[str] = Query(None, pattern="^[A-F]$"),
    district: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lista oportunidades com filtros (dados historicos read-only)."""
    with get_session() as session:
        stmt = select(Opportunity).where(Opportunity.is_opportunity.is_(True))

        if min_confidence > 0.0:
            stmt = stmt.where(Opportunity.confidence >= min_confidence)
        if grade:
            stmt = stmt.where(Opportunity.deal_grade == grade)
        if district:
            stmt = stmt.where(Opportunity.district == district)
        if status:
            stmt = stmt.where(Opportunity.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = session.execute(count_stmt).scalar() or 0

        stmt = stmt.order_by(
            Opportunity.deal_score.desc().nullslast(),
            Opportunity.created_at.desc(),
        )
        stmt = stmt.offset(offset).limit(limit)

        results = session.execute(stmt).scalars().all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [_opp_to_dict(opp) for opp in results],
        }


@router.get("/opportunities/{opp_id}", summary="Detalhe de uma oportunidade")
async def get_opportunity(opp_id: int) -> Dict[str, Any]:
    """Retorna detalhe completo de uma oportunidade + market data."""
    with get_session() as session:
        opp = session.get(Opportunity, opp_id)
        if not opp:
            raise HTTPException(
                status_code=404, detail="Oportunidade nao encontrada"
            )

        market = session.execute(
            select(MarketData).where(MarketData.opportunity_id == opp_id)
        ).scalar_one_or_none()

        result = _opp_to_dict(opp)
        result["market_data"] = _market_to_dict(market) if market else None

        # Buscar info do grupo
        msg = session.get(Message, opp.message_id)
        if msg:
            result["group_name"] = msg.group_name
            result["sender_name"] = msg.sender_name
            result["message_timestamp"] = (
                msg.timestamp.isoformat() if msg.timestamp else None
            )

        return result


@router.get("/stats", summary="Estatisticas gerais")
async def get_stats() -> Dict[str, Any]:
    """Resumo: totais, top grupos, distribuicao geografica e por tipo."""
    with get_session() as session:
        total_groups = session.execute(
            select(func.count(Group.id))
        ).scalar() or 0
        active_groups = session.execute(
            select(func.count(Group.id)).where(Group.is_active.is_(True))
        ).scalar() or 0
        total_messages = session.execute(
            select(func.count(Message.id))
        ).scalar() or 0
        total_opps = session.execute(
            select(func.count(Opportunity.id)).where(
                Opportunity.is_opportunity.is_(True)
            )
        ).scalar() or 0

        # Distribuicao por grade
        grade_counts: Dict[str, int] = {}
        for g in ["A", "B", "C", "D", "F"]:
            cnt = session.execute(
                select(func.count(Opportunity.id)).where(
                    Opportunity.is_opportunity.is_(True),
                    Opportunity.deal_grade == g,
                )
            ).scalar() or 0
            grade_counts[g] = cnt

        # Top distritos
        top_districts = session.execute(
            select(
                Opportunity.district, func.count(Opportunity.id).label("total")
            )
            .where(
                Opportunity.is_opportunity.is_(True),
                Opportunity.district.isnot(None),
            )
            .group_by(Opportunity.district)
            .order_by(func.count(Opportunity.id).desc())
            .limit(10)
        ).all()

        return {
            "groups": {"total": total_groups, "active": active_groups},
            "messages": total_messages,
            "opportunities": total_opps,
            "grade_distribution": grade_counts,
            "top_districts": [
                {"district": d, "count": c} for d, c in top_districts
            ],
        }
