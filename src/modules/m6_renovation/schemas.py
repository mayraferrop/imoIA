"""Schemas Pydantic para o modulo M6 — Gestao de Obra."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RenovationCreateSchema(BaseModel):
    """Schema para criacao de obra."""

    initial_budget: float = Field(gt=0)
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    contractor_name: Optional[str] = None
    contractor_phone: Optional[str] = None
    contractor_nif: Optional[str] = None
    scope_description: Optional[str] = None
    license_type: str = Field(default="isento")
    is_aru: bool = False
    contingency_pct: float = Field(default=15, ge=0, le=50)
    auto_milestones: bool = True


class RenovationUpdateSchema(BaseModel):
    """Schema para actualizacao de obra."""

    current_budget: Optional[float] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    contractor_name: Optional[str] = None
    contractor_phone: Optional[str] = None
    contractor_email: Optional[str] = None
    contractor_nif: Optional[str] = None
    scope_description: Optional[str] = None
    license_type: Optional[str] = None
    license_status: Optional[str] = None
    license_number: Optional[str] = None
    is_aru: Optional[bool] = None
    contingency_pct: Optional[float] = None
    delay_reason: Optional[str] = None
    notes: Optional[str] = None


class MilestoneCreateSchema(BaseModel):
    """Schema para criacao de milestone."""

    name: str
    category: str
    description: Optional[str] = None
    budget: float = Field(default=0, ge=0)
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    depends_on_id: Optional[str] = None
    supplier_name: Optional[str] = None
    sort_order: int = 99


class MilestoneUpdateSchema(BaseModel):
    """Schema para actualizacao de milestone."""

    name: Optional[str] = None
    budget: Optional[float] = None
    completion_pct: Optional[int] = Field(None, ge=0, le=100)
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    supplier_name: Optional[str] = None
    supplier_phone: Optional[str] = None
    supplier_nif: Optional[str] = None
    notes: Optional[str] = None


class ExpenseCreateSchema(BaseModel):
    """Schema para criacao de despesa."""

    description: str
    amount: float = Field(gt=0)
    expense_date: datetime
    milestone_id: Optional[str] = None
    category: str = "outro"
    supplier_name: Optional[str] = None
    supplier_nif: Optional[str] = None
    invoice_number: Optional[str] = None
    payment_method: Optional[str] = None
    has_valid_invoice: bool = False
    notes: Optional[str] = None


class ExpenseUpdateSchema(BaseModel):
    """Schema para actualizacao de despesa."""

    description: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_nif: Optional[str] = None
    invoice_number: Optional[str] = None
    payment_method: Optional[str] = None
    has_valid_invoice: Optional[bool] = None
    notes: Optional[str] = None
