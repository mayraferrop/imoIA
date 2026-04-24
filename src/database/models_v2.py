"""Modelos SQLAlchemy expandidos para o ImoIA.

Coexistem com os modelos existentes em models.py (que NAO sao alterados).
Usam a mesma Base para partilhar o metadata.

Tabela central: Property — todos os modulos futuros referenciam esta tabela.
Liga aos dados legacy via Property.source_opportunity_id → opportunities.id.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base


# ---------------------------------------------------------------------------
# Core: Tenant + User (prepara multi-tenant / SaaS futuro)
# ---------------------------------------------------------------------------


class Tenant(Base):
    """Tenant para suporte multi-tenant futuro (SaaS)."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="PT")
    settings: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    users: Mapped[List["User"]] = relationship("User", back_populates="tenant")
    properties: Mapped[List["Property"]] = relationship(
        "Property", back_populates="tenant"
    )


class User(Base):
    """Utilizador da plataforma."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="investor")
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")


# ---------------------------------------------------------------------------
# Tabela central: Property
# ---------------------------------------------------------------------------


class Property(Base):
    """Propriedade — tabela central do ImoIA.

    Todos os modulos futuros (M2-M9) referenciam esta tabela.
    Pode ser criada a partir de uma Opportunity legacy
    ou inserida manualmente.
    """

    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Origem
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_opportunity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("opportunities.id"), nullable=True
    )
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_external_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    source_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Localizacao
    country: Mapped[str] = mapped_column(String(2), default="PT")
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    municipality: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    parish: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Caracteristicas
    property_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    typology: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    gross_area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    land_area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_elevator: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    has_parking: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    construction_year: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    energy_certificate: Mapped[Optional[str]] = mapped_column(
        String(5), nullable=True
    )
    condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Registo PT
    conservatoria: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    descricao_predial: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    artigo_matricial: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    vpt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Registo BR
    matricula: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cartorio: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Pipeline
    status: Mapped[str] = mapped_column(String(50), default="lead")

    # Preco
    asking_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Fotos (migrada de Listing em 005_property_photos.sql) — array JSON
    # com {document_id, url, filename, order, is_cover}. cover_photo_url é
    # espelho da foto com is_cover=true para render rápido.
    photos: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    cover_photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Meta
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    is_off_market: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    contact_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="properties")


class PropertyPriceHistory(Base):
    """M1: Histórico de alterações de preço de propriedades.

    Popula-se quando o scraper detecta alteração de preço entre runs
    (para properties com source != NULL). Para listings M7 nossos,
    existe a tabela paralela listing_price_history.
    """

    __tablename__ = "property_price_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    old_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_price: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# M3 — Motor financeiro
# ---------------------------------------------------------------------------


class FinancialModel(Base):
    """M3: Modelo financeiro para analise de investimento fix and flip.

    Cada registo e um cenario (base, optimista, pessimista, custom) para uma Property.
    Suporta Portugal e Brasil com parametros fiscais distintos.
    """

    __tablename__ = "financial_models"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id"), nullable=False, index=True
    )

    # Cenario
    scenario_name: Mapped[str] = mapped_column(String(100), default="base")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    country: Mapped[str] = mapped_column(String(2), default="PT")

    # Estrutura da operacao
    entity_structure: Mapped[str] = mapped_column(String(20), default="pf_jp")
    imt_resale_regime: Mapped[str] = mapped_column(String(20), default="none")

    # === AQUISICAO ===
    purchase_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Custos aquisicao — Portugal (1a escritura)
    imt: Mapped[float] = mapped_column(Float, default=0)
    imposto_selo: Mapped[float] = mapped_column(Float, default=0)
    notario_registo: Mapped[float] = mapped_column(Float, default=0)
    comissao_compra: Mapped[float] = mapped_column(Float, default=0)
    comissao_compra_pct: Mapped[float] = mapped_column(Float, default=0)

    # 2a escritura (PF → JP, so quando entity_structure = pf_jp)
    imt_2: Mapped[float] = mapped_column(Float, default=0)
    imt_2_original: Mapped[float] = mapped_column(Float, default=0)
    is_2: Mapped[float] = mapped_column(Float, default=0)
    escritura_2: Mapped[float] = mapped_column(Float, default=0)
    total_acquisition_cost_2: Mapped[float] = mapped_column(Float, default=0)

    # Custos aquisicao — Brasil
    itbi: Mapped[float] = mapped_column(Float, default=0)
    itbi_pct: Mapped[float] = mapped_column(Float, default=3.0)
    escritura_registro_br: Mapped[float] = mapped_column(Float, default=0)

    total_acquisition_cost: Mapped[float] = mapped_column(Float, default=0)

    # === OBRA / RENOVACAO ===
    renovation_budget: Mapped[float] = mapped_column(Float, default=0)
    renovation_contingency_pct: Mapped[float] = mapped_column(Float, default=15)
    renovation_total: Mapped[float] = mapped_column(Float, default=0)
    renovation_duration_months: Mapped[int] = mapped_column(Integer, default=6)

    # === FINANCIAMENTO ===
    financing_type: Mapped[str] = mapped_column(String(20), default="cash")
    loan_amount: Mapped[float] = mapped_column(Float, default=0)
    ltv_pct: Mapped[float] = mapped_column(Float, default=0)
    interest_rate_pct: Mapped[float] = mapped_column(Float, default=0)
    spread_pct: Mapped[float] = mapped_column(Float, default=0)
    euribor_pct: Mapped[float] = mapped_column(Float, default=0)
    loan_term_months: Mapped[int] = mapped_column(Integer, default=0)
    monthly_payment: Mapped[float] = mapped_column(Float, default=0)
    total_interest: Mapped[float] = mapped_column(Float, default=0)
    bank_fees: Mapped[float] = mapped_column(Float, default=0)
    bank_fees_detail: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # === HOLDING COSTS ===
    holding_months: Mapped[int] = mapped_column(Integer, default=0)
    monthly_condominio: Mapped[float] = mapped_column(Float, default=0)
    monthly_insurance: Mapped[float] = mapped_column(Float, default=0)
    monthly_consumos: Mapped[float] = mapped_column(Float, default=0)
    monthly_imi_proportional: Mapped[float] = mapped_column(Float, default=0)
    other_monthly_costs: Mapped[float] = mapped_column(Float, default=0)
    total_holding_cost: Mapped[float] = mapped_column(Float, default=0)

    # === VENDA ===
    estimated_sale_price: Mapped[float] = mapped_column(Float, default=0)
    comissao_venda_pct: Mapped[float] = mapped_column(Float, default=6.15)
    comissao_venda: Mapped[float] = mapped_column(Float, default=0)
    other_sale_costs: Mapped[float] = mapped_column(Float, default=0)
    total_sale_costs: Mapped[float] = mapped_column(Float, default=0)

    # === FISCALIDADE (Mais-Valias) ===
    devaluation_coefficient: Mapped[float] = mapped_column(Float, default=1.0)
    deductible_expenses: Mapped[float] = mapped_column(Float, default=0)
    taxable_gain_50pct: Mapped[float] = mapped_column(Float, default=0)
    estimated_irs_rate_pct: Mapped[float] = mapped_column(Float, default=0)
    capital_gains_tax_pt: Mapped[float] = mapped_column(Float, default=0)
    capital_gain_br: Mapped[float] = mapped_column(Float, default=0)
    capital_gains_tax_br: Mapped[float] = mapped_column(Float, default=0)
    capital_gains_tax_rate_br: Mapped[float] = mapped_column(Float, default=15.0)
    capital_gains_tax: Mapped[float] = mapped_column(Float, default=0)

    # === FISCALIDADE (IRC — pf_jp/jp_only) ===
    irc_taxable_income: Mapped[float] = mapped_column(Float, default=0)
    irc_rate_pct: Mapped[float] = mapped_column(Float, default=21.0)
    irc_estimated: Mapped[float] = mapped_column(Float, default=0)
    derrama_estimated: Mapped[float] = mapped_column(Float, default=0)
    total_corporate_tax: Mapped[float] = mapped_column(Float, default=0)

    # === RESULTADOS ===
    total_investment: Mapped[float] = mapped_column(Float, default=0)
    total_costs: Mapped[float] = mapped_column(Float, default=0)
    gross_profit: Mapped[float] = mapped_column(Float, default=0)
    net_profit: Mapped[float] = mapped_column(Float, default=0)
    roi_pct: Mapped[float] = mapped_column(Float, default=0)
    roi_simple_pct: Mapped[float] = mapped_column(Float, default=0)
    roi_annualized_pct: Mapped[float] = mapped_column(Float, default=0)
    tir_anual_pct: Mapped[float] = mapped_column(Float, default=0)
    cash_on_cash_return_pct: Mapped[float] = mapped_column(Float, default=0)
    moic: Mapped[float] = mapped_column(Float, default=0)
    payoff_at_sale: Mapped[float] = mapped_column(Float, default=0)
    caixa_closing: Mapped[float] = mapped_column(Float, default=0)

    # === GO / NO-GO ===
    mao: Mapped[float] = mapped_column(Float, default=0)
    floor_price: Mapped[float] = mapped_column(Float, default=0)
    margin_of_safety_pct: Mapped[float] = mapped_column(Float, default=0)
    roi_target_pct: Mapped[float] = mapped_column(Float, default=15.0)
    meets_criteria: Mapped[bool] = mapped_column(Boolean, default=False)
    go_nogo: Mapped[str] = mapped_column(String(20), default="pending")

    # === META ===
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_calculations: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# M3 — Condicoes de pagamento + Projecao financeira
# ---------------------------------------------------------------------------


class PaymentCondition(Base):
    """Condicoes de pagamento vinculadas a um modelo financeiro.

    Guarda datas do CPCV e escritura + tranches de pagamento (sinal, intermédias, escritura).
    """

    __tablename__ = "payment_conditions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tenants.id"), index=True, nullable=True
    )
    financial_model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("financial_models.id"), nullable=False, index=True
    )

    cpcv_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    escritura_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Tranches como JSON: [{descricao, tipo, pct, valor, data, dias_apos_cpcv}]
    tranches: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CashflowProjection(Base):
    """Projecao financeira mensal — projetado vs real.

    Cada linha corresponde a um periodo (mes) do fluxo de caixa.
    Valores projetados sao gerados no save do cenario.
    Valores reais sao preenchidos por M6/M9 a medida que o deal avanca.
    """

    __tablename__ = "cashflow_projections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tenants.id"), index=True, nullable=True
    )
    financial_model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("financial_models.id"), nullable=False, index=True
    )

    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    data_referencia: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    periodo_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    categoria: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Projetado
    saidas_projetado: Mapped[float] = mapped_column(Float, default=0)
    pmt_projetado: Mapped[float] = mapped_column(Float, default=0)
    manutencao_projetado: Mapped[float] = mapped_column(Float, default=0)
    payoff_projetado: Mapped[float] = mapped_column(Float, default=0)
    fluxo_projetado: Mapped[float] = mapped_column(Float, default=0)
    acumulado_projetado: Mapped[float] = mapped_column(Float, default=0)

    # Real (preenchido por M6/M9)
    saidas_real: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pmt_real: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    manutencao_real: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fluxo_real: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    acumulado_real: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# M4 — Deal pipeline
# ---------------------------------------------------------------------------


class Deal(Base):
    """M4: Deal — negocio imobiliario com ciclo de vida completo.

    Tabela central do M4. Liga a Property via property_id.
    Cada deal tem uma investment_strategy que determina a rota de estados.
    """

    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id"), nullable=False, index=True
    )

    # Estrategia e estado
    investment_strategy: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="lead", nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Precos
    purchase_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_sale_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_sale_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_rent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    renovation_budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_renovation_cost: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    # Contacto principal do negocio
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Datas
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    cpcv_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    escritura_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    obra_start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    obra_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sale_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Flags
    is_financed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_off_market: Mapped[bool] = mapped_column(Boolean, default=False)
    discard_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pause_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Origem M1
    source_opportunity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("opportunities.id"), nullable=True
    )

    # === MEDIACAO ===
    role: Mapped[str] = mapped_column(String(20), default="investidor")

    # Proprietario (quando mediador representa o vendedor)
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    owner_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Contrato de mediacao (CMI)
    mediation_contract_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    mediation_contract_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    mediation_contract_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    mediation_contract_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # Comissao
    commission_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    commission_vat_included: Mapped[bool] = mapped_column(Boolean, default=False)
    commission_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    commission_split_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    commission_split_agent: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    commission_split_agency: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # CMA (Comparative Market Analysis)
    cma_estimated_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cma_min_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cma_max_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cma_recommended_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    cma_report_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cma_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Meta
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    property: Mapped["Property"] = relationship("Property", foreign_keys=[property_id])
    proposals: Mapped[List["Proposal"]] = relationship(
        "Proposal", back_populates="deal", order_by="Proposal.created_at.desc()"
    )
    history: Mapped[List["DealStateHistory"]] = relationship(
        "DealStateHistory",
        back_populates="deal",
        order_by="DealStateHistory.created_at.desc()",
    )
    tasks: Mapped[List["DealTask"]] = relationship(
        "DealTask", back_populates="deal", order_by="DealTask.due_date"
    )
    rentals: Mapped[List["DealRental"]] = relationship(
        "DealRental", back_populates="deal"
    )
    visits: Mapped[List["DealVisit"]] = relationship(
        "DealVisit", back_populates="deal", order_by="DealVisit.visit_date.desc()"
    )
    commissions: Mapped[List["DealCommission"]] = relationship(
        "DealCommission", back_populates="deal"
    )


class Proposal(Base):
    """M4: Proposta de compra ou contraproposta."""

    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, index=True
    )

    proposal_type: Mapped[str] = mapped_column(
        String(20), default="offer"
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    deposit_pct: Mapped[float] = mapped_column(Float, default=10.0)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    validity_days: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(50), default="draft")

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    response_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    response_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="proposals")


class DealStateHistory(Base):
    """M4: Audit trail de transicoes de estado."""

    __tablename__ = "deal_state_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, index=True
    )

    from_status: Mapped[str] = mapped_column(String(50), nullable=False)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="history")


class DealTask(Base):
    """M4: Tarefa/milestone associada a um deal."""

    __tablename__ = "deal_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(50), default="manual")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="tasks")


class DealApproval(Base):
    """M4: Aprovacao/decisao sobre um deal."""

    __tablename__ = "deal_approvals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, index=True
    )

    approval_type: Mapped[str] = mapped_column(String(50), nullable=False)
    approver_name: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class DealRental(Base):
    """M4: Dados de arrendamento (buy_and_hold, brrrr, AL)."""

    __tablename__ = "deal_rentals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, index=True
    )

    # Tipo de arrendamento
    rental_type: Mapped[str] = mapped_column(
        String(50), default="longa_duracao"
    )

    # Valores
    monthly_rent: Mapped[float] = mapped_column(Float, nullable=False)
    deposit_months: Mapped[int] = mapped_column(Integer, default=2)

    # Inquilino
    tenant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tenant_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tenant_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Contrato
    lease_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    lease_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    lease_duration_months: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # AL (Alojamento Local)
    al_license_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    platform: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    average_daily_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    occupancy_rate_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Custos mensais
    condominio_monthly: Mapped[float] = mapped_column(Float, default=0)
    imi_annual: Mapped[float] = mapped_column(Float, default=0)
    insurance_annual: Mapped[float] = mapped_column(Float, default=0)
    management_fee_pct: Mapped[float] = mapped_column(Float, default=0)

    status: Mapped[str] = mapped_column(String(20), default="activo")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="rentals")


class DealVisit(Base):
    """M4: Registo de visitas ao imovel (mediacao)."""

    __tablename__ = "deal_visits"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, index=True
    )

    # Quem visitou
    visitor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    visitor_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    visitor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Detalhes
    visit_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    visit_type: Mapped[str] = mapped_column(String(50), default="presencial")
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Feedback
    interest_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objections: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wants_second_visit: Mapped[bool] = mapped_column(Boolean, default=False)
    made_proposal: Mapped[bool] = mapped_column(Boolean, default=False)
    proposal_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Quem acompanhou
    accompanied_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="visits")


class DealCommission(Base):
    """M4: Tracking de comissoes (mediacao)."""

    __tablename__ = "deal_commissions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, index=True
    )

    # Valores
    sale_price: Mapped[float] = mapped_column(Float, nullable=False)
    commission_pct: Mapped[float] = mapped_column(Float, nullable=False)
    commission_gross: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vat_pct: Mapped[float] = mapped_column(Float, default=23.0)
    commission_with_vat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Partilha
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    share_pct: Mapped[float] = mapped_column(Float, default=100.0)
    my_commission: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    other_agent_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    other_agent_agency: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    other_agent_commission: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    # Pagamento
    payment_status: Mapped[str] = mapped_column(String(50), default="pendente")
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invoice_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    paid_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="commissions")


# ---------------------------------------------------------------------------
# M5 — Due diligence
# ---------------------------------------------------------------------------


class DueDiligenceItem(Base):
    """M5: Item de due diligence — documento ou verificacao a fazer."""

    __tablename__ = "due_diligence_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, index=True
    )

    # Identificacao
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    item_key: Mapped[str] = mapped_column(String(100), nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Estado
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(50), default="pendente")

    # Documento
    document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    document_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    expiry_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Verificacao
    verified_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Red flags
    red_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    red_flag_severity: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    red_flag_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Custos
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_paid: Mapped[bool] = mapped_column(Boolean, default=False)

    # Ordem e contexto
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    country: Mapped[str] = mapped_column(String(2), default="PT")
    property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# M6 — Gestao de obra
# ---------------------------------------------------------------------------


class Renovation(Base):
    """M6: Obra/renovacao associada a um deal."""

    __tablename__ = "renovations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, unique=True, index=True
    )

    # Orcamento
    initial_budget: Mapped[float] = mapped_column(Float, nullable=False)
    current_budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_spent: Mapped[float] = mapped_column(Float, default=0)
    total_committed: Mapped[float] = mapped_column(Float, default=0)
    budget_variance_pct: Mapped[float] = mapped_column(Float, default=0)
    contingency_pct: Mapped[float] = mapped_column(Float, default=15)
    contingency_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Cronograma
    planned_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    planned_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    estimated_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    planned_duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    delay_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Empreiteiro principal
    contractor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contractor_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contractor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contractor_nif: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Licenciamento
    license_type: Mapped[str] = mapped_column(String(50), default="isento")
    license_status: Mapped[str] = mapped_column(String(50), default="na")
    license_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ARU
    is_aru: Mapped[bool] = mapped_column(Boolean, default=False)

    # Estado e progresso
    status: Mapped[str] = mapped_column(String(50), default="planeamento")
    progress_pct: Mapped[float] = mapped_column(Float, default=0)

    # Descricao
    scope_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sincronizacao Cash Flow Pro
    cashflow_project_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )
    cashflow_project_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class RenovationMilestone(Base):
    """M6: Fase/milestone da obra."""

    __tablename__ = "renovation_milestones"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    renovation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("renovations.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Orcamento do milestone
    budget: Mapped[float] = mapped_column(Float, default=0)
    spent: Mapped[float] = mapped_column(Float, default=0)
    variance_pct: Mapped[float] = mapped_column(Float, default=0)

    # Cronograma
    planned_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    planned_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Estado
    status: Mapped[str] = mapped_column(String(50), default="pendente")
    completion_pct: Mapped[int] = mapped_column(Integer, default=0)

    # Dependencia
    depends_on_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("renovation_milestones.id"), nullable=True
    )

    # Fornecedor especifico
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    supplier_nif: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class RenovationExpense(Base):
    """M6: Despesa individual da obra."""

    __tablename__ = "renovation_expenses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    renovation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("renovations.id"), nullable=False, index=True
    )
    milestone_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("renovation_milestones.id"), nullable=True
    )

    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Factura
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_nif: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    invoice_document_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )

    # Dedutibilidade fiscal
    has_valid_invoice: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_tax_deductible: Mapped[bool] = mapped_column(Boolean, default=False)

    # Pagamento
    payment_status: Mapped[str] = mapped_column(String(50), default="pendente")
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    paid_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    expense_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Sincronizacao externa (Cash Flow Pro)
    external_id: Mapped[Optional[str]] = mapped_column(
        String(36), unique=True, nullable=True
    )
    external_source: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class RenovationPhoto(Base):
    """M6: Foto de progresso da obra."""

    __tablename__ = "renovation_photos"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    renovation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("renovations.id"), nullable=False, index=True
    )
    milestone_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("renovation_milestones.id"), nullable=True
    )
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    photo_type: Mapped[str] = mapped_column(String(50), default="progresso")
    caption: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    taken_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    taken_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    room_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# M7 — Marketing
# ---------------------------------------------------------------------------


class BrandKit(Base):
    """M7: Kit de marca do tenant (cores, tipografia, voz, contactos, redes sociais).

    Cada tenant tem um BrandKit unico que define a identidade visual e
    de comunicacao usada na geracao automatica de conteudos de marketing.
    """

    __tablename__ = "brand_kits"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, unique=True
    )

    # Identidade da marca
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tagline: Mapped[Optional[str]] = mapped_column(String(500))
    website_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Logos (URLs locais via DocumentStorage)
    logo_primary_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    logo_white_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    logo_icon_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Cores
    color_primary: Mapped[str] = mapped_column(String(7), default="#1E3A5F")
    color_secondary: Mapped[str] = mapped_column(String(7), default="#F4A261")
    color_accent: Mapped[str] = mapped_column(String(7), default="#E76F51")

    # Tipografia
    font_heading: Mapped[str] = mapped_column(String(100), default="Montserrat")
    font_body: Mapped[str] = mapped_column(String(100), default="Inter")

    # Voz e tom
    voice_tone: Mapped[str] = mapped_column(String(50), default="profissional")
    voice_description: Mapped[Optional[str]] = mapped_column(Text)
    voice_forbidden_words: Mapped[Optional[list]] = mapped_column(
        JSON, default=list
    )
    voice_preferred_words: Mapped[Optional[list]] = mapped_column(
        JSON, default=list
    )

    # Contactos
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_whatsapp: Mapped[Optional[str]] = mapped_column(String(50))

    # Redes sociais
    social_instagram: Mapped[Optional[str]] = mapped_column(String(255))
    social_facebook: Mapped[Optional[str]] = mapped_column(String(255))
    social_linkedin: Mapped[Optional[str]] = mapped_column(String(255))

    # Configuracoes de conteudo
    active_languages: Mapped[Optional[list]] = mapped_column(
        JSON, default=lambda: ["pt-PT"]
    )
    template_style: Mapped[str] = mapped_column(String(50), default="modern")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Listing(Base):
    """M7: Anuncio de venda/arrendamento.

    Contem conteudo multilingue, metricas de desempenho, integracao com
    o portal Habta e distribuicao por WhatsApp e redes sociais.
    """

    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    deal_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("deals.id"), index=True, nullable=True
    )

    # Tipo e preco
    listing_type: Mapped[str] = mapped_column(String(50), nullable=False)
    listing_price: Mapped[float] = mapped_column(Float, nullable=False)
    floor_price: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    price_negotiable: Mapped[bool] = mapped_column(Boolean, default=True)
    price_on_request: Mapped[bool] = mapped_column(Boolean, default=False)

    # Conteudo — Portugues (PT-PT)
    title_pt: Mapped[Optional[str]] = mapped_column(String(500))
    description_pt: Mapped[Optional[str]] = mapped_column(Text)
    short_description_pt: Mapped[Optional[str]] = mapped_column(String(500))

    # Conteudo — Ingles
    title_en: Mapped[Optional[str]] = mapped_column(String(500))
    description_en: Mapped[Optional[str]] = mapped_column(Text)
    short_description_en: Mapped[Optional[str]] = mapped_column(String(500))

    # Conteudo — Portugues do Brasil
    title_pt_br: Mapped[Optional[str]] = mapped_column(String(500))
    description_pt_br: Mapped[Optional[str]] = mapped_column(Text)

    # Conteudo — Frances
    title_fr: Mapped[Optional[str]] = mapped_column(String(500))
    description_fr: Mapped[Optional[str]] = mapped_column(Text)

    # Conteudo — Chines
    title_zh: Mapped[Optional[str]] = mapped_column(String(500))
    description_zh: Mapped[Optional[str]] = mapped_column(Text)

    # SEO e destaques
    highlights: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    meta_title: Mapped[Optional[str]] = mapped_column(String(60))
    meta_description: Mapped[Optional[str]] = mapped_column(String(160))
    keywords: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    slug: Mapped[Optional[str]] = mapped_column(String(255))

    # Media
    photos: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    cover_photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    video_url: Mapped[Optional[str]] = mapped_column(String(500))
    virtual_tour_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Conteudo por canal
    content_whatsapp: Mapped[Optional[str]] = mapped_column(Text)
    content_instagram_post: Mapped[Optional[str]] = mapped_column(Text)
    content_facebook_post: Mapped[Optional[str]] = mapped_column(Text)
    content_linkedin: Mapped[Optional[str]] = mapped_column(Text)
    content_portal: Mapped[Optional[str]] = mapped_column(Text)
    content_email_subject: Mapped[Optional[str]] = mapped_column(String(255))
    content_email_body: Mapped[Optional[str]] = mapped_column(Text)

    # Estado
    status: Mapped[str] = mapped_column(String(50), default="draft")

    # Integracao Habta
    habta_published: Mapped[bool] = mapped_column(Boolean, default=False)
    habta_project_id: Mapped[Optional[str]] = mapped_column(String(36))
    habta_url: Mapped[Optional[str]] = mapped_column(String(500))
    habta_published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    habta_last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Distribuicao WhatsApp
    whatsapp_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    whatsapp_groups_sent: Mapped[Optional[list]] = mapped_column(
        JSON, default=list
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Metricas
    days_on_market: Mapped[int] = mapped_column(Integer, default=0)
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    total_contacts: Mapped[int] = mapped_column(Integer, default=0)
    total_proposals: Mapped[int] = mapped_column(Integer, default=0)

    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ListingPriceHistory(Base):
    """M7: Historico de alteracoes de preco de um anuncio."""

    __tablename__ = "listing_price_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=False, index=True
    )
    old_price: Mapped[Optional[float]] = mapped_column(Float)
    new_price: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    changed_by: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class ListingContent(Base):
    """M7: Versoes de conteudo gerado por IA para um anuncio.

    Permite rastrear multiplas versoes de conteudo por idioma e canal,
    com aprovacao humana antes de publicacao.
    """

    __tablename__ = "listing_contents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Metadados de geracao IA
    model_used: Mapped[Optional[str]] = mapped_column(String(50))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Aprovacao
    approved_by: Mapped[Optional[str]] = mapped_column(String(255))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class ListingCreative(Base):
    """M7b: Peca visual/criativa gerada para uma listagem."""

    __tablename__ = "listing_creatives"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=False, index=True
    )
    creative_type: Mapped[str] = mapped_column(String(50), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="pt-PT")
    document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title_used: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photos_used: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    template_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    template_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="generated")
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class EmailCampaign(Base):
    """M7h: Campanha de email."""

    __tablename__ = "email_campaigns"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=True, index=True
    )
    campaign_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="pt-PT")
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)
    recipient_filter: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered: Mapped[int] = mapped_column(Integer, default=0)
    opened: Mapped[int] = mapped_column(Integer, default=0)
    clicked: Mapped[int] = mapped_column(Integer, default=0)
    open_rate: Mapped[float] = mapped_column(Float, default=0)
    click_rate: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class VideoProject(Base):
    """M7c: Projecto de video gerado para uma listagem."""

    __tablename__ = "video_projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=False, index=True
    )
    video_type: Mapped[str] = mapped_column(String(50), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    fps: Mapped[int] = mapped_column(Integer, default=30)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    orientation: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="pt-PT")
    template_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    template_props: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    title_overlay: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    photos_used: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    music_track: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    music_mood: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    brand_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    color_primary: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    color_accent: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    format: Mapped[str] = mapped_column(String(10), default="mp4")
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    render_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    render_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    render_duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SocialMediaPost(Base):
    """M7e: Post de rede social agendado ou publicado."""

    __tablename__ = "social_media_posts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    listing_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=True, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hashtags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    media_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    media_urls: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    creative_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    video_project_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )
    language: Mapped[str] = mapped_column(String(5), default="pt-PT")
    status: Mapped[str] = mapped_column(String(50), default="draft")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    external_post_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    external_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SocialMediaAccount(Base):
    """M7e: Conta de rede social configurada para publicacao."""

    __tablename__ = "social_media_accounts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# M8 — CRM de leads (compradores)
# ---------------------------------------------------------------------------


class Lead(Base):
    """M8: Lead (potencial comprador/inquilino).

    Gestao completa do pipeline de compradores: captacao, qualificacao,
    scoring, matching com listings, nurturing automatico, e fecho.
    """

    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Dados pessoais
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Orcamento
    budget_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Preferencias
    preferred_typology: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    preferred_locations: Mapped[Optional[list]] = mapped_column(
        JSON, default=list
    )
    preferred_features: Mapped[Optional[list]] = mapped_column(
        JSON, default=list
    )

    # Perfil do comprador
    timeline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    financing: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    buyer_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )

    # Pipeline
    stage: Mapped[str] = mapped_column(String(50), default="new", index=True)
    stage_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Scoring
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    grade: Mapped[str] = mapped_column(String(5), default="D")

    # Fonte / Origem
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_listing_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=True
    )
    source_campaign: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    utm_source: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    utm_medium: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    utm_campaign: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # Integracao Habta
    habta_contact_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )

    # Associacao a deal
    deal_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=True, index=True
    )

    # Gestao
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    interactions: Mapped[List["LeadInteraction"]] = relationship(
        "LeadInteraction", back_populates="lead", cascade="all, delete-orphan"
    )


class LeadInteraction(Base):
    """M8: Interaccao com lead.

    Regista todas as interaccoes: chamadas, visitas, emails, mensagens,
    propostas enviadas, e qualquer outro contacto.
    """

    __tablename__ = "lead_interactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=False, index=True
    )

    # Tipo e canal
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )

    # Conteudo
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Referencia a listing
    listing_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )

    # Metadados extra
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, default=dict
    )

    # Quem realizou
    performed_by: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", back_populates="interactions")


class LeadListingMatch(Base):
    """M8: Match entre lead e listing.

    Resultado do matching automatico entre preferencias do lead
    e listings disponiveis. Inclui score e razoes do match.
    """

    __tablename__ = "lead_listing_matches"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=False, index=True
    )
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=False, index=True
    )

    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    match_reasons: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="suggested")

    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    response_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class NurtureSequence(Base):
    """M8: Sequencia de nurturing automatico para um lead.

    Gere o envio automatico de conteudo ao lead, com passos
    configuráveis e controlo de execucao.
    """

    __tablename__ = "nurture_sequences"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )

    sequence_type: Mapped[str] = mapped_column(
        String(50), default="standard"
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")
    next_action_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    steps_executed: Mapped[Optional[list]] = mapped_column(
        JSON, default=list
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# M9 — Fecho + P&L
# ---------------------------------------------------------------------------


class ClosingProcess(Base):
    """M9: Processo de fecho (compra ou venda).

    Gere o workflow administrativo: CPCV → escritura → registo.
    Inclui guias fiscais, direito de preferencia e checklist.
    """

    __tablename__ = "closing_processes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, index=True
    )
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id"), nullable=False, index=True
    )

    # Tipo e estado
    closing_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # compra | venda
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )  # pending → imt_paid → deed_scheduled → deed_done → registered → completed | cancelled

    # Datas-chave
    cpcv_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deed_scheduled_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    deed_actual_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    registration_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    completed_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Valor da transaccao
    transaction_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    deposit_amount: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Sinal CPCV

    # Guias fiscais
    imt_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    imt_guide_issued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    imt_guide_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    imt_paid: Mapped[bool] = mapped_column(Boolean, default=False)

    is_amount: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Imposto de Selo
    is_guide_issued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    is_guide_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)

    # Direito de preferencia
    preference_right_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    preference_right_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    preference_right_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    preference_right_entities: Mapped[Optional[dict]] = mapped_column(
        JSON, default=list
    )

    # Custos reais
    deed_cost: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Escritura (Casa Pronta)
    registration_cost: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Registo predial
    lawyer_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    commission_cost: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Comissao imobiliaria
    other_costs: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Checklist e alertas
    checklist: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    calendar_alerts: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Transaction(Base):
    """M9: Transaccao (compra ou venda).

    Registo de cada transaccao financeira associada a um fecho.
    """

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id"), nullable=False
    )
    closing_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("closing_processes.id"), nullable=True
    )

    # Tipo e estado
    transaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # purchase | sale | deposit | tax | fee
    status: Mapped[str] = mapped_column(String(50), default="pending")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Datas
    transaction_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Partes
    payer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payee: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class DealPnL(Base):
    """M9: Profit & Loss de um deal.

    Calculo real vs estimado apos venda. Um por deal (unique on deal_id).
    """

    __tablename__ = "deal_pnl"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=False, unique=True
    )
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )  # draft | in_progress | final

    # Compra
    purchase_price: Mapped[float] = mapped_column(Float, default=0)
    imt_cost: Mapped[float] = mapped_column(Float, default=0)
    is_cost: Mapped[float] = mapped_column(Float, default=0)  # Imposto de Selo
    notary_cost: Mapped[float] = mapped_column(Float, default=0)
    lawyer_cost: Mapped[float] = mapped_column(Float, default=0)
    purchase_commission: Mapped[float] = mapped_column(Float, default=0)
    total_acquisition: Mapped[float] = mapped_column(Float, default=0)

    # Financiamento
    loan_amount: Mapped[float] = mapped_column(Float, default=0)
    interest_rate_pct: Mapped[float] = mapped_column(Float, default=0)
    loan_setup_costs: Mapped[float] = mapped_column(Float, default=0)
    total_interest_paid: Mapped[float] = mapped_column(Float, default=0)
    financing_months: Mapped[int] = mapped_column(Integer, default=0)

    # Obra
    renovation_budget: Mapped[float] = mapped_column(Float, default=0)
    renovation_actual: Mapped[float] = mapped_column(Float, default=0)
    renovation_variance: Mapped[float] = mapped_column(Float, default=0)
    renovation_variance_pct: Mapped[float] = mapped_column(Float, default=0)
    renovation_deductible: Mapped[float] = mapped_column(Float, default=0)

    # Holding
    holding_months: Mapped[int] = mapped_column(Integer, default=0)
    holding_costs: Mapped[float] = mapped_column(Float, default=0)

    # Venda
    sale_price: Mapped[float] = mapped_column(Float, default=0)
    sale_commission: Mapped[float] = mapped_column(Float, default=0)
    sale_costs: Mapped[float] = mapped_column(Float, default=0)
    net_proceeds: Mapped[float] = mapped_column(Float, default=0)

    # P&L
    total_invested: Mapped[float] = mapped_column(Float, default=0)
    gross_profit: Mapped[float] = mapped_column(Float, default=0)
    capital_gain_taxable: Mapped[float] = mapped_column(Float, default=0)
    capital_gain_tax: Mapped[float] = mapped_column(Float, default=0)
    net_profit: Mapped[float] = mapped_column(Float, default=0)

    # Metricas
    roi_simple_pct: Mapped[float] = mapped_column(Float, default=0)
    roi_annualized_pct: Mapped[float] = mapped_column(Float, default=0)  # CAGR
    moic: Mapped[float] = mapped_column(Float, default=0)
    profit_margin_pct: Mapped[float] = mapped_column(Float, default=0)

    # Comparacao M3
    estimated_roi_pct: Mapped[float] = mapped_column(Float, default=0)
    estimated_profit: Mapped[float] = mapped_column(Float, default=0)
    roi_variance_pct: Mapped[float] = mapped_column(Float, default=0)
    profit_variance: Mapped[float] = mapped_column(Float, default=0)

    data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Transversais (usados por varios modulos)
# ---------------------------------------------------------------------------


class CalendarEvent(Base):
    """Evento de calendario (visitas, reunioes, prazos).

    TODO: Completar campos — titulo, descricao, data/hora,
    duracao, participantes, lembretes, recorrencia.
    """

    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    property_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("properties.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Document(Base):
    """Servico partilhado: documento/ficheiro guardado no storage."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )

    # Associacao flexivel
    deal_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=True, index=True
    )
    dd_item_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("due_diligence_items.id"), nullable=True, index=True
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Metadados do ficheiro
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_extension: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Categorizacao
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Controlo
    uploaded_by: Mapped[Optional[str]] = mapped_column(
        String(255), default="system"
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Notification(Base):
    """Notificacao do sistema.

    TODO: Completar campos — tipo, titulo, mensagem, destinatario,
    lida, canal (email, push, whatsapp), prioridade.
    """

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    property_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("properties.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="unread")
    data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# M2 — Analista de mercado
# ---------------------------------------------------------------------------


class MarketComparable(Base):
    """M2: Imovel comparavel encontrado via CASAFARI ou outras fontes."""

    __tablename__ = "market_comparables"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )

    # Referencia ao deal/oportunidade que originou a pesquisa
    deal_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=True, index=True
    )
    opportunity_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # Fonte
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Dados do imovel comparavel
    property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    typology: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Localizacao
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    municipality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parish: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Preco
    listing_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sale_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_per_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Area
    gross_area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    useful_area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Estado e caracteristicas
    condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    construction_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_elevator: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    has_parking: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    has_terrace: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    energy_certificate: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Datas
    listing_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sale_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    days_on_market: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Tipo de comparacao
    comparison_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Dados brutos da API
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Cache
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class PropertyValuation(Base):
    """M2: Avaliacao de mercado — AVM (Automated Valuation Model)."""

    __tablename__ = "property_valuations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    deal_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("deals.id"), nullable=True, index=True
    )

    # Imovel avaliado
    property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    typology: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    gross_area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    useful_area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    municipality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parish: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Resultado da avaliacao
    estimated_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_value_low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_value_high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_price_per_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Contexto de mercado
    avg_price_per_m2_zone: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    median_price_per_m2_zone: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_days_on_market_zone: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active_listings_zone: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recent_sales_zone: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_trend_6m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_trend_12m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Comparaveis usados
    comparables_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comparables_avg_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    comparables_avg_price_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Fonte e metodo
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Dados brutos
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Metadados
    valuated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    requested_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class MarketZoneStats(Base):
    """M2: Estatisticas de mercado por zona — cache de dados macro."""

    __tablename__ = "market_zone_stats"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )

    # Zona
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    municipality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parish: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zone_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Periodo
    period: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    period_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Precos
    avg_price_per_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    median_price_per_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_price_per_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_price_per_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Volume
    total_transactions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_listings: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_days_on_market: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Tendencia
    price_variation_vs_previous: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_variation_yoy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    supply_demand_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Tipologia
    property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Fonte
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Dados brutos
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class MarketAlert(Base):
    """M2: Alerta de mercado — novas oportunidades ou mudancas de preco."""

    __tablename__ = "market_alerts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )

    # Criterios do alerta
    alert_name: Mapped[str] = mapped_column(String(255), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Filtros
    districts: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    municipalities: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    property_types: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    typologies: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    price_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_per_m2_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_price_vs_market_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # CASAFARI feed ID (se criado via API)
    casafari_feed_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_sync_cursor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Estado
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_triggers: Mapped[int] = mapped_column(Integer, default=0)

    # Notificacao
    notify_whatsapp: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Estratégias de investimento configuráveis (SaaS)
# ---------------------------------------------------------------------------


class InvestmentStrategy(Base):
    """Estratégia de investimento do utilizador.

    Define os critérios personalizados para classificação de oportunidades.
    Cada utilizador pode ter várias estratégias, mas apenas uma ativa.
    """

    __tablename__ = "investment_strategies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    signals: Mapped[List["ClassificationSignal"]] = relationship(
        "ClassificationSignal",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="ClassificationSignal.priority",
    )


class ClassificationSignal(Base):
    """Sinal individual de classificação dentro de uma estratégia.

    Pode ser positivo (procurar este sinal) ou negativo (ignorar).
    """

    __tablename__ = "classification_signals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    strategy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("investment_strategies.id"), nullable=False, index=True
    )
    signal_text: Mapped[str] = mapped_column(Text, nullable=False)
    signal_category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="outro"
    )
    is_positive: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    is_ai_suggested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    strategy: Mapped["InvestmentStrategy"] = relationship(
        "InvestmentStrategy", back_populates="signals"
    )
