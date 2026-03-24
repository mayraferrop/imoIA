"""Schemas Pydantic para o modulo M5 — Due Diligence."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DDItemUpdateSchema(BaseModel):
    """Schema para actualizar um item de due diligence."""

    status: Optional[str] = Field(
        None, pattern="^(pendente|em_curso|obtido|problema|na)$"
    )
    document_url: Optional[str] = None
    document_date: Optional[datetime] = None
    verified_by: Optional[str] = None
    verification_notes: Optional[str] = None
    cost_paid: Optional[bool] = None
    notes: Optional[str] = None


class DDCustomItemSchema(BaseModel):
    """Schema para adicionar item personalizado ao checklist."""

    category: str
    item_name: str
    description: Optional[str] = None
    is_required: bool = False
    cost: Optional[float] = None
    sort_order: int = 99


class DDRedFlagSchema(BaseModel):
    """Schema para adicionar red flag."""

    severity: str = Field(pattern="^(low|medium|high|critical)$")
    description: str


class DDResolveFlagSchema(BaseModel):
    """Schema para resolver red flag."""

    resolution: str


class CMAComparable(BaseModel):
    """Um comparavel para CMA."""

    price: float = Field(gt=0)
    area_m2: float = Field(gt=0)
    address: Optional[str] = None
