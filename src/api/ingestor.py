"""Router FastAPI para o ingestor (M1).

Gere o pipeline de ingestao WhatsApp (trigger + polling de estado)
e expoe dados historicos das tabelas legacy como read-only.

Migrado para Supabase REST (sem SQLAlchemy).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from src.database import supabase_rest as db

router = APIRouter()

_LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"

# -- Estado in-memory do pipeline --
_pipeline_lock = threading.Lock()
_pipeline_state: Dict[str, Any] = {
    "status": "idle",  # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "messages_fetched": 0,
    "opportunities_found": 0,
    "groups_processed": 0,
    "errors": [],
}


def _run_pipeline_background() -> None:
    """Executa o pipeline numa thread separada e atualiza o estado global."""
    global _pipeline_state
    from src.modules.m1_ingestor.service import run_pipeline

    try:
        result = run_pipeline()
        with _pipeline_lock:
            _pipeline_state = {
                "status": "done",
                "started_at": _pipeline_state["started_at"],
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "messages_fetched": result.messages_fetched,
                "opportunities_found": result.opportunities_found,
                "groups_processed": result.groups_processed,
                "errors": result.errors,
            }
        logger.info(
            f"Pipeline M1 concluido: {result.messages_fetched} msgs, "
            f"{result.opportunities_found} oportunidades"
        )
    except Exception as e:
        with _pipeline_lock:
            _pipeline_state = {
                "status": "error",
                "started_at": _pipeline_state["started_at"],
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "messages_fetched": 0,
                "opportunities_found": 0,
                "groups_processed": 0,
                "errors": [str(e)],
            }
        logger.error(f"Pipeline M1 falhou: {e}")


@router.post("/trigger", summary="Disparar pipeline de ingestao")
async def trigger_pipeline() -> Dict[str, Any]:
    """Dispara o pipeline M1 em background. Usar GET /status para acompanhar."""
    global _pipeline_state

    with _pipeline_lock:
        if _pipeline_state["status"] == "running":
            return {
                "status": "already_running",
                "started_at": _pipeline_state["started_at"],
            }

        _pipeline_state = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "messages_fetched": 0,
            "opportunities_found": 0,
            "groups_processed": 0,
            "errors": [],
        }

    thread = threading.Thread(target=_run_pipeline_background, daemon=True)
    thread.start()
    logger.info("Pipeline M1 disparado via API (background)")
    return {"status": "started", "started_at": _pipeline_state["started_at"]}


# Estado do reprocess (batch-based, sem background threads)
_reprocess_state: Dict[str, Any] = {
    "pending_groups": [],       # IDs dos grupos por processar
    "total_groups": 0,
    "groups_processed": 0,
    "messages_fetched": 0,
    "opportunities_found": 0,
    "errors": [],
    "days": 10,
    "active": False,
}


@router.post("/reprocess", summary="Iniciar reprocessamento dos ultimos N dias")
async def start_reprocess(days: int = Query(10, ge=1, le=30)) -> Dict[str, Any]:
    """Prepara a lista de grupos para reprocessar. Chamar /reprocess/batch para processar."""
    global _reprocess_state
    from src.modules.m1_ingestor.service import get_reprocess_groups

    try:
        group_ids = get_reprocess_groups(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    _reprocess_state = {
        "pending_groups": group_ids,
        "total_groups": len(group_ids),
        "groups_processed": 0,
        "messages_fetched": 0,
        "opportunities_found": 0,
        "errors": [],
        "days": days,
        "active": True,
    }

    logger.info(f"Reprocess preparado: {len(group_ids)} grupos, ultimos {days} dias")
    return {
        "status": "ready",
        "total_groups": len(group_ids),
        "days": days,
    }


@router.post("/reprocess/batch", summary="Processar proximo batch de grupos")
async def reprocess_batch(batch_size: int = Query(10, ge=1, le=20)) -> Dict[str, Any]:
    """Processa os proximos N grupos. Chamar repetidamente ate done=true."""
    global _reprocess_state
    from src.modules.m1_ingestor.service import reprocess_group_batch

    if not _reprocess_state["active"]:
        raise HTTPException(status_code=400, detail="Nenhum reprocess activo. Chamar POST /reprocess primeiro.")

    pending = _reprocess_state["pending_groups"]
    if not pending:
        _reprocess_state["active"] = False
        return {
            "done": True,
            "groups_processed": _reprocess_state["groups_processed"],
            "messages_fetched": _reprocess_state["messages_fetched"],
            "opportunities_found": _reprocess_state["opportunities_found"],
            "errors": _reprocess_state["errors"],
        }

    # Tirar os proximos N grupos
    batch = pending[:batch_size]
    _reprocess_state["pending_groups"] = pending[batch_size:]

    try:
        result = reprocess_group_batch(
            group_ids=batch,
            days=_reprocess_state["days"],
        )
        _reprocess_state["groups_processed"] += result["groups_processed"]
        _reprocess_state["messages_fetched"] += result["messages_fetched"]
        _reprocess_state["opportunities_found"] += result["opportunities_found"]
        _reprocess_state["errors"].extend(result.get("errors", []))
    except Exception as e:
        _reprocess_state["errors"].append(str(e))
        logger.error(f"Batch reprocess falhou: {e}")

    remaining = len(_reprocess_state["pending_groups"])
    done = remaining == 0
    if done:
        _reprocess_state["active"] = False

    return {
        "done": done,
        "remaining": remaining,
        "batch_processed": len(batch),
        "groups_processed": _reprocess_state["groups_processed"],
        "total_groups": _reprocess_state["total_groups"],
        "messages_fetched": _reprocess_state["messages_fetched"],
        "opportunities_found": _reprocess_state["opportunities_found"],
        "errors": _reprocess_state["errors"][-3:] if _reprocess_state["errors"] else [],
    }


@router.get("/status", summary="Estado do pipeline")
async def get_pipeline_status() -> Dict[str, Any]:
    """Retorna estado atual do pipeline (polling endpoint)."""
    with _pipeline_lock:
        return dict(_pipeline_state)


@router.get("/groups", summary="Listar grupos monitorizados")
async def list_groups() -> List[Dict[str, Any]]:
    """Lista todos os grupos com estatisticas (dados historicos)."""
    rows = db.list_rows("groups", order="name.asc", limit=200)
    return [
        {
            "id": g.get("id"),
            "whatsapp_group_id": g.get("whatsapp_group_id"),
            "name": g.get("name"),
            "is_active": g.get("is_active"),
            "last_processed_at": g.get("last_processed_at"),
            "messages": g.get("message_count", 0),
            "opportunities": g.get("opportunity_count", 0),
        }
        for g in rows
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
    # Montar filtros
    filters: list[str] = ["is_opportunity=eq.true"]
    if min_confidence > 0.0:
        filters.append(f"confidence=gte.{min_confidence}")
    if grade:
        filters.append(f"deal_grade=eq.{grade}")
    if district:
        filters.append(f"district=eq.{district}")
    if status:
        filters.append(f"status=eq.{status}")

    params = "&".join(filters)

    # Total count
    total = db._count("opportunities", params)

    # Buscar registos com paginacao
    rows = db.list_rows(
        "opportunities",
        select="id,is_opportunity,confidence,opportunity_type,property_type,"
               "location_extracted,parish,municipality,district,"
               "price_mentioned,area_m2,bedrooms,deal_score,deal_grade,"
               "status,ai_reasoning,original_message,notes,created_at",
        filters=params,
        order="deal_score.desc.nullslast,created_at.desc",
        limit=limit,
        offset=offset,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": rows,
    }


@router.get("/opportunities/{opp_id}", summary="Detalhe de uma oportunidade")
async def get_opportunity(opp_id: int) -> Dict[str, Any]:
    """Retorna detalhe completo de uma oportunidade + market data."""
    rows = db._get("opportunities", f"id=eq.{opp_id}&select=*&limit=1")
    if not rows:
        raise HTTPException(
            status_code=404, detail="Oportunidade nao encontrada"
        )
    opp = rows[0]

    # Market data
    market_rows = db._get(
        "market_data",
        f"opportunity_id=eq.{opp_id}&limit=1"
        "&select=ine_median_price_m2,ine_quarter,casafari_avg_price_m2,"
        "casafari_median_price_m2,sir_median_price_m2,sir_market_position,"
        "sir_price_vs_market_pct,idealista_avg_price_m2,idealista_listings_count,"
        "estimated_market_value,estimated_monthly_rent,gross_yield_pct,"
        "net_yield_pct,price_vs_market_pct,imt_estimate,stamp_duty_estimate,"
        "total_acquisition_cost"
    )
    opp["market_data"] = market_rows[0] if market_rows else None

    # Info do grupo via message
    message_id = opp.get("message_id")
    if message_id:
        msg_rows = db._get("messages", f"id=eq.{message_id}&select=group_name,sender_name,timestamp&limit=1")
        if msg_rows:
            msg = msg_rows[0]
            opp["group_name"] = msg.get("group_name")
            opp["sender_name"] = msg.get("sender_name")
            opp["message_timestamp"] = msg.get("timestamp")

    return opp


@router.get("/stats", summary="Estatisticas gerais")
async def get_stats() -> Dict[str, Any]:
    """Resumo: totais, top grupos, distribuicao geografica e por tipo."""
    total_groups = db._count("groups")
    active_groups = db._count("groups", "is_active=eq.true")
    total_messages = db._count("messages")
    total_opps = db._count("opportunities", "is_opportunity=eq.true")

    # Distribuicao por grade
    grade_counts: Dict[str, int] = {}
    for g in ["A", "B", "C", "D", "F"]:
        grade_counts[g] = db._count(
            "opportunities",
            f"is_opportunity=eq.true&deal_grade=eq.{g}",
        )

    # Top distritos — buscar oportunidades agrupadas manualmente
    # (Supabase REST nao suporta GROUP BY, fazemos client-side)
    opp_rows = db._get(
        "opportunities",
        "is_opportunity=eq.true&district=not.is.null"
        "&select=district&limit=1000",
    )
    district_map: Dict[str, int] = {}
    for r in opp_rows:
        d = r.get("district")
        if d:
            district_map[d] = district_map.get(d, 0) + 1
    top_districts = sorted(district_map.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "groups": {"total": total_groups, "active": active_groups},
        "messages": total_messages,
        "opportunities": total_opps,
        "grade_distribution": grade_counts,
        "top_districts": [
            {"district": d, "count": c} for d, c in top_districts
        ],
    }
