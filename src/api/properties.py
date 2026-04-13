"""Router para gestao de Properties — via Supabase REST API.

Todos os endpoints leem e escrevem directamente no Supabase PostgreSQL
via REST API (sem SQLAlchemy/SQLite).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

# FIXME(jwt-refactor): migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'
from src.database import supabase_rest as supa

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------


class PropertyCreateSchema(BaseModel):
    """Schema para criacao manual de propriedade."""

    district: Optional[str] = None
    municipality: Optional[str] = None
    parish: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    property_type: Optional[str] = None
    typology: Optional[str] = None
    gross_area_m2: Optional[float] = None
    net_area_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    asking_price: Optional[float] = None
    condition: Optional[str] = None
    is_off_market: bool = False
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PropertyUpdateSchema(BaseModel):
    """Schema para actualizacao de propriedade."""

    district: Optional[str] = None
    municipality: Optional[str] = None
    parish: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    property_type: Optional[str] = None
    typology: Optional[str] = None
    gross_area_m2: Optional[float] = None
    net_area_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    asking_price: Optional[float] = None
    condition: Optional[str] = None
    status: Optional[str] = None
    is_off_market: Optional[bool] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Endpoints — Supabase REST
# ---------------------------------------------------------------------------


@router.get("/", summary="Listar propriedades")
async def list_properties(
    status: Optional[str] = None,
    municipality: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lista propriedades via Supabase REST."""
    params = "select=*&order=created_at.desc"
    if status:
        params += f"&status=eq.{status}"
    else:
        params += "&status=neq.descartado"
    if municipality:
        params += f"&municipality=eq.{municipality}"
    params += f"&limit={limit}&offset={offset}"

    items = supa._get("properties", params)

    # Contar total (query separada)
    count_params = "select=id"
    if status:
        count_params += f"&status=eq.{status}"
    else:
        count_params += "&status=neq.descartado"
    if municipality:
        count_params += f"&municipality=eq.{municipality}"
    supa._ensure_config()
    try:
        resp = httpx.get(
            f"{supa._SUPA_URL}/rest/v1/properties?{count_params}",
            headers={**supa._headers(), "Prefer": "count=exact", "Range": "0-0"},
            timeout=10,
        )
        # Extrair count do header Content-Range: 0-0/155
        cr = resp.headers.get("content-range", "")
        total = int(cr.split("/")[1]) if "/" in cr else len(items)
    except Exception:
        total = len(items)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.post("/", summary="Criar propriedade manualmente")
async def create_property(data: PropertyCreateSchema) -> Dict[str, Any]:
    """Cria uma nova propriedade no Supabase."""
    tenant_id = supa.ensure_tenant()
    row = {
        "id": str(uuid4()),
        "tenant_id": tenant_id,
        "source": "manual",
        "country": "PT",
        "status": "lead",
    }
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            row[k] = v

    result = supa._post("properties", row)
    logger.info(f"Property criada: {row['id']}")
    return result[0] if result else row


@router.get("/{property_id}", summary="Detalhe de uma propriedade")
async def get_property(property_id: str) -> Dict[str, Any]:
    """Retorna detalhe completo de uma propriedade."""
    rows = supa._get("properties", f"id=eq.{property_id}&select=*&limit=1")
    if not rows:
        raise HTTPException(status_code=404, detail="Propriedade nao encontrada")
    return rows[0]


@router.patch("/{property_id}", summary="Actualizar propriedade")
async def update_property(
    property_id: str, data: PropertyUpdateSchema
) -> Dict[str, Any]:
    """Actualiza campos de uma propriedade no Supabase."""
    supa._ensure_config()
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para actualizar")

    resp = httpx.patch(
        f"{supa._SUPA_URL}/rest/v1/properties?id=eq.{property_id}",
        headers=supa._headers(),
        json=update_data,
        timeout=10,
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    result = resp.json()
    if not result:
        raise HTTPException(status_code=404, detail="Propriedade nao encontrada")

    logger.info(f"Property {property_id} actualizada: {list(update_data.keys())}")
    return result[0]
