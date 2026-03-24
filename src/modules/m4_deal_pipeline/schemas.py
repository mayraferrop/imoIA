"""Schemas Pydantic para o modulo M4 — Deal Pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.modules.m4_deal_pipeline.state_machine import (
    DEAL_STATUSES,
    INVESTMENT_STRATEGIES,
)


# ---------------------------------------------------------------------------
# Deal
# ---------------------------------------------------------------------------


class DealCreateSchema(BaseModel):
    """Schema para criacao de um deal."""

    property_id: str
    investment_strategy: str
    title: str
    purchase_price: Optional[float] = None
    target_sale_price: Optional[float] = None
    monthly_rent: Optional[float] = None
    renovation_budget: Optional[float] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_role: Optional[str] = None
    is_financed: bool = False
    is_off_market: bool = False
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class DealFromOpportunitySchema(BaseModel):
    """Schema para criar deal a partir de oportunidade M1."""

    investment_strategy: str
    title: Optional[str] = None
    purchase_price: Optional[float] = None
    target_sale_price: Optional[float] = None
    monthly_rent: Optional[float] = None
    renovation_budget: Optional[float] = None
    notes: Optional[str] = None


class DealUpdateSchema(BaseModel):
    """Schema para actualizacao de deal."""

    title: Optional[str] = None
    investment_strategy: Optional[str] = None
    purchase_price: Optional[float] = None
    target_sale_price: Optional[float] = None
    actual_sale_price: Optional[float] = None
    monthly_rent: Optional[float] = None
    renovation_budget: Optional[float] = None
    actual_renovation_cost: Optional[float] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_role: Optional[str] = None
    is_financed: Optional[bool] = None
    is_off_market: Optional[bool] = None
    cpcv_date: Optional[datetime] = None
    escritura_date: Optional[datetime] = None
    obra_start_date: Optional[datetime] = None
    obra_end_date: Optional[datetime] = None
    sale_date: Optional[datetime] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class AdvanceDealSchema(BaseModel):
    """Schema para avancar o estado de um deal."""

    target_status: str
    reason: Optional[str] = None
    changed_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Proposal
# ---------------------------------------------------------------------------


class ProposalCreateSchema(BaseModel):
    """Schema para criacao de proposta."""

    proposal_type: str = Field(default="offer", pattern="^(offer|counter)$")
    amount: float = Field(gt=0)
    deposit_pct: float = Field(default=10.0, ge=0, le=100)
    conditions: Optional[str] = None
    validity_days: int = Field(default=5, ge=1, le=90)


class ProposalResponseSchema(BaseModel):
    """Schema para responder a uma proposta."""

    status: str = Field(pattern="^(accepted|rejected|counter)$")
    response_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


class TaskCreateSchema(BaseModel):
    """Schema para criacao de tarefa."""

    title: str
    description: Optional[str] = None
    task_type: str = Field(default="manual")
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None


# ---------------------------------------------------------------------------
# Rental
# ---------------------------------------------------------------------------


class RentalCreateSchema(BaseModel):
    """Schema para adicionar dados de arrendamento."""

    rental_type: str = Field(
        default="longa_duracao",
        pattern="^(longa_duracao|al_inteiro|al_quarto|estudantes|corporativo)$",
    )
    monthly_rent: float = Field(gt=0)
    deposit_months: int = Field(default=2, ge=0, le=12)
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None
    lease_start: Optional[datetime] = None
    lease_end: Optional[datetime] = None
    lease_duration_months: Optional[int] = None
    al_license_number: Optional[str] = None
    platform: Optional[str] = None
    average_daily_rate: Optional[float] = None
    occupancy_rate_pct: Optional[float] = None
    condominio_monthly: float = 0
    imi_annual: float = 0
    insurance_annual: float = 0
    management_fee_pct: float = 0


class RentalUpdateSchema(BaseModel):
    """Schema para actualizar dados de arrendamento."""

    rental_type: Optional[str] = None
    monthly_rent: Optional[float] = None
    deposit_months: Optional[int] = None
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None
    lease_start: Optional[datetime] = None
    lease_end: Optional[datetime] = None
    lease_duration_months: Optional[int] = None
    al_license_number: Optional[str] = None
    platform: Optional[str] = None
    average_daily_rate: Optional[float] = None
    occupancy_rate_pct: Optional[float] = None
    condominio_monthly: Optional[float] = None
    imi_annual: Optional[float] = None
    insurance_annual: Optional[float] = None
    management_fee_pct: Optional[float] = None
    status: Optional[str] = None


# ---------------------------------------------------------------------------
# Mediacao
# ---------------------------------------------------------------------------


class MediationDealCreateSchema(BaseModel):
    """Schema para criacao de deal de mediacao imobiliaria."""

    # Campos obrigatorios
    property_id: str
    investment_strategy: str
    title: str
    commission_pct: float = Field(gt=0, le=100)

    # Dados do proprietario
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None

    # Contrato de mediacao
    mediation_contract_type: Optional[str] = Field(
        default=None,
        pattern="^(exclusivo|aberto|partilha)$",
    )

    # Comissao
    commission_vat_included: bool = False
    commission_split_pct: Optional[float] = Field(default=None, ge=0, le=100)
    commission_split_agent: Optional[str] = None
    commission_split_agency: Optional[str] = None

    # Campos herdados do DealCreateSchema
    purchase_price: Optional[float] = None
    target_sale_price: Optional[float] = None
    monthly_rent: Optional[float] = None
    renovation_budget: Optional[float] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_role: Optional[str] = None
    is_financed: bool = False
    is_off_market: bool = False
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CMA — Analise Comparativa de Mercado
# ---------------------------------------------------------------------------


class CMAInputSchema(BaseModel):
    """Schema para analise comparativa de mercado (CMA)."""

    comparables: List[dict] = Field(
        default_factory=list,
        description=(
            "Lista de comparaveis com {price: float, area_m2: float,"
            " address: Optional[str]}"
        ),
    )
    recommended_price: Optional[float] = None


# ---------------------------------------------------------------------------
# Visita
# ---------------------------------------------------------------------------


class VisitCreateSchema(BaseModel):
    """Schema para agendamento de visita."""

    visitor_name: str
    visitor_phone: Optional[str] = None
    visitor_email: Optional[str] = None
    visit_date: datetime
    visit_type: str = Field(
        default="presencial",
        pattern="^(presencial|virtual|open_house)$",
    )
    duration_minutes: Optional[int] = None
    accompanied_by: Optional[str] = None


class VisitUpdateSchema(BaseModel):
    """Schema para registo de feedback apos visita."""

    interest_level: Optional[str] = Field(
        default=None,
        pattern="^(baixo|medio|alto|muito_alto)$",
    )
    feedback: Optional[str] = None
    objections: Optional[str] = None
    wants_second_visit: Optional[bool] = None
    made_proposal: Optional[bool] = None
    proposal_amount: Optional[float] = None


# ---------------------------------------------------------------------------
# Fatura de Comissao
# ---------------------------------------------------------------------------


class CommissionInvoiceSchema(BaseModel):
    """Schema para registo de fatura de comissao."""

    invoice_number: str
    invoice_url: Optional[str] = None
    paid_amount: Optional[float] = None
    paid_date: Optional[datetime] = None
