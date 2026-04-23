"""Router HTTP do scraper M1."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src.api.dependencies.auth import get_current_organization
from src.database import supabase_rest as db
from src.modules.m1_scraper.service import (
    DEFAULT_SEARCH_URLS,
    run_scraper_pipeline,
)

router = APIRouter()


class RunRequest(BaseModel):
    search_urls: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Lista de {portal, slug, pages, property_type?}. Se None, usa defaults.",
    )
    max_listings: int = Field(default=200, ge=10, le=1000)


class RunResponse(BaseModel):
    listings_fetched: int
    listings_classified: int
    opportunities_found: int
    properties_created: int
    properties_updated: int
    price_changes: int
    errors: List[str]


@router.post("/run", response_model=RunResponse)
async def run(
    req: RunRequest,
    organization_id: str = Depends(get_current_organization),
) -> Dict[str, Any]:
    """Corre o pipeline manualmente (síncrono — pode demorar 30-120s)."""
    tenant_id = db.ensure_tenant()
    result = run_scraper_pipeline(
        organization_id=organization_id,
        tenant_id=tenant_id,
        search_urls=req.search_urls,
        max_listings=req.max_listings,
    )
    return result.as_dict()


@router.get("/stats")
async def stats(
    days: int = 7,
    organization_id: str = Depends(get_current_organization),
) -> Dict[str, Any]:
    """Estatísticas de scraping dos últimos N dias."""
    from datetime import datetime, timezone, timedelta

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    created_rows = db.list_rows(
        "properties",
        select="id,source,created_at,asking_price,municipality",
        filters=(
            f"organization_id=eq.{organization_id}"
            f"&source=in.(idealista_pt,imovirtual_pt)"
            f"&created_at=gte.{since}"
        ),
        order="created_at.desc",
        limit=500,
    )

    price_changes = db.list_rows(
        "property_price_history",
        select="id,property_id,old_price,new_price,detected_at,source",
        filters=(
            f"organization_id=eq.{organization_id}"
            f"&detected_at=gte.{since}"
        ),
        order="detected_at.desc",
        limit=200,
    )

    by_source: Dict[str, int] = {}
    for r in created_rows:
        by_source[r.get("source") or "unknown"] = by_source.get(r.get("source") or "unknown", 0) + 1

    return {
        "since_days": days,
        "total_opportunities": len(created_rows),
        "by_source": by_source,
        "price_changes": len(price_changes),
        "recent_opportunities": created_rows[:20],
        "recent_price_changes": price_changes[:20],
    }


@router.get("/defaults")
async def defaults() -> Dict[str, Any]:
    """Expõe a lista de URLs default para o UI mostrar/editar."""
    return {"search_urls": DEFAULT_SEARCH_URLS}
