"""Schemas Pydantic para o modulo M3 — Motor Financeiro."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class FinancialModelCreateRequest(BaseModel):
    """Request para criar um modelo financeiro."""

    purchase_price: float = Field(gt=0, description="Preco de compra")
    country: str = Field(default="PT", pattern="^(PT|BR)$")
    scenario_name: str = Field(default="base")

    # Estrutura da operacao
    entity_structure: str = Field(
        default="pf_jp", pattern="^(pf_jp|pf_only|jp_only)$"
    )
    imt_resale_regime: str = Field(
        default="none", pattern="^(none|reembolso|isencao)$"
    )

    # Obra
    renovation_budget: float = Field(default=0, ge=0)
    renovation_contingency_pct: float = Field(default=15, ge=0, le=50)
    renovation_duration_months: int = Field(default=6, ge=0, le=36)

    # Financiamento
    financing_type: str = Field(
        default="cash", pattern="^(cash|mortgage|mixed)$"
    )
    loan_amount: float = Field(default=0, ge=0)
    interest_rate_pct: float = Field(default=0, ge=0, le=20)
    spread_pct: float = Field(default=0, ge=0, le=5)
    loan_term_months: int = Field(default=240, ge=0, le=480)

    # Venda
    estimated_sale_price: float = Field(
        default=0, ge=0, description="ARV — After Repair Value"
    )
    comissao_venda_pct: float = Field(default=6.15, ge=0, le=15)

    # Holding
    additional_holding_months: int = Field(default=3, ge=0, le=24)
    monthly_condominio: float = Field(default=50, ge=0)
    annual_insurance: float = Field(default=300, ge=0)

    # Comissao compra
    comissao_compra_pct: float = Field(default=0, ge=0, le=10)

    # Fiscal
    is_resident: bool = Field(default=True)
    estimated_annual_income: float = Field(default=0, ge=0)
    renovation_with_invoice_pct: float = Field(default=100, ge=0, le=100)

    # Go/no-go
    roi_target_pct: float = Field(default=15, ge=0)

    # Brasil
    itbi_pct: float = Field(default=3.0, ge=0, le=10)


class MAORequest(BaseModel):
    """Request para calculo de MAO (Maximum Allowable Offer)."""

    arv: float = Field(gt=0, description="After Repair Value")
    renovation_total: float = Field(
        ge=0, description="Custo total de obra (com contingencia)"
    )


class FloorPriceRequest(BaseModel):
    """Request para calculo de preco minimo de venda."""

    total_investment: float = Field(gt=0)
    roi_target_pct: float = Field(default=15, ge=0)
    comissao_venda_pct: float = Field(default=6.15, ge=0, le=15)


class QuickIMTRequest(BaseModel):
    """Calculo rapido de IMT sem modelo completo."""

    value: float = Field(gt=0, description="Valor do imovel")
    country: str = Field(default="PT", pattern="^(PT|BR)$")
    is_hpp: bool = Field(
        default=False, description="Habitacao propria permanente?"
    )
