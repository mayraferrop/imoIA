"""Schemas Pydantic para o modulo M9 — Fecho + P&L."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Closing Process
# ---------------------------------------------------------------------------

CLOSING_TYPES = {"compra", "venda"}

CLOSING_STATUSES = [
    "pending",
    "imt_paid",
    "deed_scheduled",
    "deed_done",
    "registered",
    "completed",
    "cancelled",
]

CLOSING_TRANSITIONS: Dict[str, List[str]] = {
    "pending": ["imt_paid", "cancelled"],
    "imt_paid": ["deed_scheduled", "cancelled"],
    "deed_scheduled": ["deed_done", "cancelled"],
    "deed_done": ["registered", "completed", "cancelled"],  # completed se Casa Pronta
    "registered": ["completed", "cancelled"],
    "completed": [],
    "cancelled": ["pending"],  # reabrir
}


class ClosingProcessCreate(BaseModel):
    """Criar processo de fecho."""

    deal_id: str
    property_id: str
    closing_type: str = Field(..., description="compra ou venda")
    transaction_price: Optional[float] = None
    deposit_amount: Optional[float] = None
    cpcv_date: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("closing_type")
    @classmethod
    def validate_closing_type(cls, v: str) -> str:
        if v not in CLOSING_TYPES:
            raise ValueError(f"closing_type deve ser: {CLOSING_TYPES}")
        return v


class ClosingProcessUpdate(BaseModel):
    """Actualizar processo de fecho."""

    transaction_price: Optional[float] = None
    deposit_amount: Optional[float] = None
    cpcv_date: Optional[datetime] = None
    deed_scheduled_date: Optional[datetime] = None
    deed_cost: Optional[float] = None
    registration_cost: Optional[float] = None
    lawyer_cost: Optional[float] = None
    commission_cost: Optional[float] = None
    other_costs: Optional[float] = None
    notes: Optional[str] = None


class ClosingStatusUpdate(BaseModel):
    """Avancar status do closing."""

    target_status: str
    notes: Optional[str] = None

    @field_validator("target_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in CLOSING_STATUSES:
            raise ValueError(f"Status invalido: {v}. Validos: {CLOSING_STATUSES}")
        return v


class TaxGuideCreate(BaseModel):
    """Emitir guia fiscal (IMT ou IS)."""

    guide_type: str = Field(..., description="imt ou is")
    amount: float = Field(..., gt=0)

    @field_validator("guide_type")
    @classmethod
    def validate_guide_type(cls, v: str) -> str:
        if v not in {"imt", "is"}:
            raise ValueError("guide_type deve ser 'imt' ou 'is'")
        return v


class PreferenceRightCreate(BaseModel):
    """Notificar direito de preferencia."""

    entities: List[str] = Field(
        ..., min_length=1, description="Entidades a notificar (ex: camara, inquilino)"
    )
    notification_date: Optional[datetime] = None


class ClosingProcessResponse(BaseModel):
    """Resposta completa de um processo de fecho."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    deal_id: str
    property_id: str
    closing_type: str
    status: str
    cpcv_date: Optional[datetime] = None
    deed_scheduled_date: Optional[datetime] = None
    deed_actual_date: Optional[datetime] = None
    registration_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    transaction_price: Optional[float] = None
    deposit_amount: Optional[float] = None
    imt_amount: Optional[float] = None
    imt_guide_issued_at: Optional[datetime] = None
    imt_guide_expires_at: Optional[datetime] = None
    imt_paid: bool = False
    is_amount: Optional[float] = None
    is_guide_issued_at: Optional[datetime] = None
    is_guide_expires_at: Optional[datetime] = None
    is_paid: bool = False
    preference_right_notified: bool = False
    preference_right_date: Optional[datetime] = None
    preference_right_expires: Optional[datetime] = None
    preference_right_entities: Optional[List[Any]] = None
    deed_cost: Optional[float] = None
    registration_cost: Optional[float] = None
    lawyer_cost: Optional[float] = None
    commission_cost: Optional[float] = None
    other_costs: Optional[float] = None
    checklist: Optional[Dict[str, Any]] = None
    calendar_alerts: Optional[List[Any]] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# P&L
# ---------------------------------------------------------------------------


class DealPnLResponse(BaseModel):
    """Resposta completa de P&L com metricas e comparacao M3."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    deal_id: str
    property_id: str
    status: str

    # Compra
    purchase_price: float = 0
    imt_cost: float = 0
    is_cost: float = 0
    notary_cost: float = 0
    lawyer_cost: float = 0
    purchase_commission: float = 0
    total_acquisition: float = 0

    # Financiamento
    loan_amount: float = 0
    interest_rate_pct: float = 0
    loan_setup_costs: float = 0
    total_interest_paid: float = 0
    financing_months: int = 0

    # Obra
    renovation_budget: float = 0
    renovation_actual: float = 0
    renovation_variance: float = 0
    renovation_variance_pct: float = 0
    renovation_deductible: float = 0

    # Holding
    holding_months: int = 0
    holding_costs: float = 0

    # Venda
    sale_price: float = 0
    sale_commission: float = 0
    sale_costs: float = 0
    net_proceeds: float = 0

    # P&L
    total_invested: float = 0
    gross_profit: float = 0
    capital_gain_taxable: float = 0
    capital_gain_tax: float = 0
    net_profit: float = 0

    # Metricas
    roi_simple_pct: float = 0
    roi_annualized_pct: float = 0
    moic: float = 0
    profit_margin_pct: float = 0

    # Comparacao M3
    estimated_roi_pct: float = 0
    estimated_profit: float = 0
    roi_variance_pct: float = 0
    profit_variance: float = 0

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DealPnLUpdate(BaseModel):
    """Actualizar P&L manualmente."""

    purchase_price: Optional[float] = None
    sale_price: Optional[float] = None
    sale_commission: Optional[float] = None
    sale_costs: Optional[float] = None
    holding_months: Optional[int] = None
    holding_costs: Optional[float] = None
    loan_amount: Optional[float] = None
    interest_rate_pct: Optional[float] = None
    loan_setup_costs: Optional[float] = None
    total_interest_paid: Optional[float] = None
    financing_months: Optional[int] = None
    notes: Optional[str] = None


class PortfolioSummary(BaseModel):
    """Resumo agregado do portfolio."""

    total_deals: int = 0
    total_invested: float = 0
    total_profit: float = 0
    total_revenue: float = 0
    avg_roi_pct: float = 0
    avg_holding_months: float = 0
    best_deal: Optional[Dict[str, Any]] = None
    worst_deal: Optional[Dict[str, Any]] = None
    deals: List[Dict[str, Any]] = Field(default_factory=list)


class FiscalReportResponse(BaseModel):
    """Relatorio fiscal anual."""

    year: int
    total_capital_gains: float = 0
    total_deductible_expenses: float = 0
    taxable_amount: float = 0
    estimated_tax: float = 0
    deals: List[Dict[str, Any]] = Field(default_factory=list)
