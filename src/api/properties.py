"""Router para gestao de Properties — tabela central do ImoIA.

Uma Property pode ser criada manualmente via este endpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from src.database.db import get_session
from src.database.models_v2 import Property, Tenant

router = APIRouter()

_DEFAULT_TENANT_SLUG = "default"


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
# Helpers
# ---------------------------------------------------------------------------


def _ensure_default_tenant(session: Any) -> str:
    """Garante que o tenant default existe e retorna o id."""
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
        logger.info("Tenant default criado")

    return tenant.id


def _prop_to_dict(prop: Property) -> Dict[str, Any]:
    """Serializa Property para dict."""
    return {
        "id": prop.id,
        "tenant_id": prop.tenant_id,
        "source": prop.source,
        "source_opportunity_id": prop.source_opportunity_id,
        "country": prop.country,
        "district": prop.district,
        "municipality": prop.municipality,
        "parish": prop.parish,
        "address": prop.address,
        "postal_code": prop.postal_code,
        "latitude": prop.latitude,
        "longitude": prop.longitude,
        "property_type": prop.property_type,
        "typology": prop.typology,
        "gross_area_m2": prop.gross_area_m2,
        "net_area_m2": prop.net_area_m2,
        "land_area_m2": prop.land_area_m2,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "condition": prop.condition,
        "status": prop.status,
        "asking_price": prop.asking_price,
        "currency": prop.currency,
        "is_off_market": prop.is_off_market,
        "contact_name": prop.contact_name,
        "contact_phone": prop.contact_phone,
        "contact_email": prop.contact_email,
        "notes": prop.notes,
        "tags": prop.tags or [],
        "created_at": prop.created_at.isoformat() if prop.created_at else None,
        "updated_at": prop.updated_at.isoformat() if prop.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", summary="Listar propriedades")
async def list_properties(
    status: Optional[str] = None,
    municipality: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lista propriedades com filtros opcionais."""
    with get_session() as session:
        stmt = select(Property)

        if status:
            stmt = stmt.where(Property.status == status)
        if municipality:
            stmt = stmt.where(Property.municipality == municipality)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = session.execute(count_stmt).scalar() or 0

        stmt = stmt.order_by(Property.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        results = session.execute(stmt).scalars().all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [_prop_to_dict(p) for p in results],
        }


@router.post("/", summary="Criar propriedade manualmente")
async def create_property(data: PropertyCreateSchema) -> Dict[str, Any]:
    """Cria uma nova propriedade manualmente."""
    with get_session() as session:
        tenant_id = _ensure_default_tenant(session)

        prop = Property(
            id=str(uuid4()),
            tenant_id=tenant_id,
            source="manual",
            country="PT",
            district=data.district,
            municipality=data.municipality,
            parish=data.parish,
            address=data.address,
            postal_code=data.postal_code,
            property_type=data.property_type,
            typology=data.typology,
            gross_area_m2=data.gross_area_m2,
            net_area_m2=data.net_area_m2,
            bedrooms=data.bedrooms,
            bathrooms=data.bathrooms,
            asking_price=data.asking_price,
            condition=data.condition,
            is_off_market=data.is_off_market,
            contact_name=data.contact_name,
            contact_phone=data.contact_phone,
            notes=data.notes,
            tags=data.tags,
            status="lead",
        )
        session.add(prop)
        session.flush()

        logger.info(f"Property criada manualmente: {prop.id}")
        return _prop_to_dict(prop)


@router.get("/{property_id}", summary="Detalhe de uma propriedade")
async def get_property(property_id: str) -> Dict[str, Any]:
    """Retorna detalhe completo de uma propriedade."""
    with get_session() as session:
        prop = session.get(Property, property_id)
        if not prop:
            raise HTTPException(
                status_code=404, detail="Propriedade nao encontrada"
            )
        return _prop_to_dict(prop)


@router.patch("/{property_id}", summary="Actualizar propriedade")
async def update_property(
    property_id: str, data: PropertyUpdateSchema
) -> Dict[str, Any]:
    """Actualiza campos de uma propriedade."""
    with get_session() as session:
        prop = session.get(Property, property_id)
        if not prop:
            raise HTTPException(
                status_code=404, detail="Propriedade nao encontrada"
            )

        update_data = data.model_dump(exclude_unset=True)
        for field_name, value in update_data.items():
            setattr(prop, field_name, value)

        session.flush()
        logger.info(f"Property {property_id} actualizada: {list(update_data.keys())}")
        return _prop_to_dict(prop)


