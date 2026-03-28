"""Schemas Pydantic para o modulo M3 — Motor Financeiro."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class FinancialModelCreateRequest(BaseModel):
    """Request para criar um modelo financeiro."""

    purchase_price: float = Field(gt=0, description="Preco de compra")

    @model_validator(mode="before")
    @classmethod
    def _replace_none_with_defaults(cls, values: dict) -> dict:
        """Converte None para defaults — frontend pode enviar null."""
        defaults = {
            "renovation_budget": 0, "renovation_contingency_pct": 0,
            "renovation_duration_months": 6, "loan_amount": 0,
            "loan_pct_purchase": 0, "loan_pct_renovation": 0,
            "interest_rate_pct": 0, "spread_pct": 0, "loan_term_months": 240,
            "estimated_sale_price": 0, "comissao_venda_pct": 6.15,
            "additional_holding_months": 3, "monthly_condominio": 50,
            "annual_insurance": 300, "monthly_consumos": 80,
            "comissao_compra_pct": 0, "estimated_annual_income": 0,
            "renovation_with_invoice_pct": 100, "roi_target_pct": 15,
        }
        if isinstance(values, dict):
            for k, default in defaults.items():
                if values.get(k) is None:
                    values[k] = default
        return values
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
    renovation_contingency_pct: float = Field(default=0, ge=0, le=50)
    renovation_duration_months: int = Field(default=6, ge=0, le=36)

    # Financiamento
    financing_type: str = Field(
        default="cash", pattern="^(cash|mortgage)$"
    )
    loan_amount: float = Field(default=0, ge=0)
    loan_pct_purchase: float = Field(default=0, ge=0, le=90)
    loan_pct_renovation: float = Field(default=0, ge=0, le=100)
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
    monthly_consumos: float = Field(default=80, ge=0)

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


class TrancheSchema(BaseModel):
    """Uma tranche de pagamento."""

    descricao: str = "Sinal CPCV"
    tipo: str = "cpcv_sinal"  # cpcv_sinal, tranche_intermedia, escritura
    pct: float = Field(ge=0, le=100)
    valor: float = Field(ge=0)
    data: str = ""  # ISO date "2026-03-15"
    dias_apos_cpcv: int = Field(default=0, ge=0)


class ScenarioSaveRequest(FinancialModelCreateRequest):
    """Request para salvar cenario com condicoes de pagamento.

    Extende FinancialModelCreateRequest com campos de identificacao e pagamento.
    """

    # Identificacao
    property_id: Optional[str] = None
    # scenario_name ja existe no parent

    # Condicoes de pagamento
    cpcv_date: str = ""  # ISO date "2026-03-15"
    escritura_date: str = ""  # ISO date "2026-05-15"
    tranches: List[TrancheSchema] = Field(default_factory=list)


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
