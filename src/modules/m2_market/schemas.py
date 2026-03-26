"""Schemas Pydantic para o modulo M2 — Pesquisa de Mercado."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Comparaveis
# ---------------------------------------------------------------------------


class ComparableSearchRequest(BaseModel):
    """Filtros para pesquisa de comparaveis."""

    district: Optional[str] = None
    municipality: Optional[str] = None
    parish: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: float = Field(default=1.0, ge=0.1, le=10.0)
    property_type: Optional[str] = None
    typology: Optional[str] = None
    bedrooms: Optional[int] = None
    area_m2: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    conditions: Optional[List[str]] = None
    months_back: int = Field(default=12, ge=1, le=36)
    max_results: int = Field(default=20, ge=1, le=100)
    include_sold: bool = True
    include_active: bool = True


class ComparableResponse(BaseModel):
    """Resposta de um comparavel."""

    id: str
    source: str
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    district: Optional[str] = None
    municipality: Optional[str] = None
    parish: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = None
    listing_price: Optional[float] = None
    sale_price: Optional[float] = None
    price_per_m2: Optional[float] = None
    gross_area_m2: Optional[float] = None
    useful_area_m2: Optional[float] = None
    condition: Optional[str] = None
    construction_year: Optional[int] = None
    energy_certificate: Optional[str] = None
    listing_date: Optional[str] = None
    days_on_market: Optional[int] = None
    comparison_type: Optional[str] = None
    fetched_at: Optional[str] = None


class ComparableSearchResponse(BaseModel):
    """Resposta de pesquisa de comparaveis com estatisticas."""

    comparables: List[ComparableResponse]
    total: int
    stats: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Avaliacao
# ---------------------------------------------------------------------------


class ValuationRequest(BaseModel):
    """Dados para avaliacao de imovel."""

    property_type: Optional[str] = None
    typology: Optional[str] = None
    gross_area_m2: Optional[float] = None
    useful_area_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    district: Optional[str] = None
    municipality: Optional[str] = None
    parish: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    condition: Optional[str] = None
    method: str = Field(default="hybrid")


class ValuationResponse(BaseModel):
    """Resultado de avaliacao."""

    id: str
    estimated_value: Optional[float] = None
    estimated_value_low: Optional[float] = None
    estimated_value_high: Optional[float] = None
    estimated_price_per_m2: Optional[float] = None
    confidence_score: Optional[float] = None
    avg_price_per_m2_zone: Optional[float] = None
    median_price_per_m2_zone: Optional[float] = None
    active_listings_zone: Optional[int] = None
    price_trend_6m: Optional[float] = None
    price_trend_12m: Optional[float] = None
    comparables_count: Optional[int] = None
    comparables_avg_price_m2: Optional[float] = None
    source: Optional[str] = None
    method: Optional[str] = None
    valuated_at: Optional[str] = None


class ARVEstimateResponse(BaseModel):
    """Estimativa de ARV (After Repair Value)."""

    current_value: Optional[float] = None
    arv_estimated: Optional[float] = None
    value_uplift: Optional[float] = None
    value_uplift_pct: Optional[float] = None
    arv_per_m2: Optional[float] = None
    comparables_used: int = 0
    confidence: Optional[float] = None
    method: str = "comparables"


# ---------------------------------------------------------------------------
# Zona / Estatisticas
# ---------------------------------------------------------------------------


class ZoneStatsRequest(BaseModel):
    """Filtros para estatisticas de zona."""

    district: str
    municipality: Optional[str] = None
    parish: Optional[str] = None
    property_type: str = "apartamento"


class ZoneStatsResponse(BaseModel):
    """Estatisticas de mercado de uma zona."""

    id: str
    district: str
    municipality: Optional[str] = None
    parish: Optional[str] = None
    period: Optional[str] = None
    avg_price_per_m2: Optional[float] = None
    median_price_per_m2: Optional[float] = None
    min_price_per_m2: Optional[float] = None
    max_price_per_m2: Optional[float] = None
    total_listings: Optional[int] = None
    avg_days_on_market: Optional[int] = None
    price_variation_yoy: Optional[float] = None
    property_type: Optional[str] = None
    source: Optional[str] = None
    fetched_at: Optional[str] = None


class PriceTrendPoint(BaseModel):
    """Ponto de serie temporal de preco."""

    period: str
    avg_price_m2: Optional[float] = None
    median_price_m2: Optional[float] = None
    volume: Optional[int] = None
    variation_pct: Optional[float] = None


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------


class AlertCreateRequest(BaseModel):
    """Dados para criar alerta de mercado."""

    alert_name: str
    alert_type: str = Field(
        description="new_listing, price_drop, below_market, comparable_sold"
    )
    districts: List[str] = Field(default_factory=list)
    municipalities: List[str] = Field(default_factory=list)
    property_types: List[str] = Field(default_factory=list)
    typologies: List[str] = Field(default_factory=list)
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    price_per_m2_max: Optional[float] = None
    max_price_vs_market_pct: Optional[float] = None
    notify_whatsapp: bool = True
    notify_email: bool = False


class AlertResponse(BaseModel):
    """Resposta de alerta."""

    id: str
    alert_name: str
    alert_type: str
    districts: List[str] = Field(default_factory=list)
    municipalities: List[str] = Field(default_factory=list)
    property_types: List[str] = Field(default_factory=list)
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    is_active: bool = True
    casafari_feed_id: Optional[int] = None
    last_triggered_at: Optional[str] = None
    total_triggers: int = 0
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Enriquecimento M1
# ---------------------------------------------------------------------------


class EnrichmentResponse(BaseModel):
    """Resultado de enriquecimento de uma oportunidade M1."""

    opportunity_id: int
    zone_avg_price_m2: Optional[float] = None
    zone_median_price_m2: Optional[float] = None
    asking_price_m2: Optional[float] = None
    discount_vs_market_pct: Optional[float] = None
    arv_estimated: Optional[float] = None
    comparables_found: int = 0
    source: str = "casafari"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class MarketOverviewResponse(BaseModel):
    """Overview de mercado para dashboard."""

    zones_monitored: int = 0
    alerts_active: int = 0
    valuations_total: int = 0
    comparables_cached: int = 0
    casafari_configured: bool = False
    casafari_search_access: bool = False
    ine_available: bool = True


# ---------------------------------------------------------------------------
# Casafari AVM Nativo
# ---------------------------------------------------------------------------


class CasafariValuationRequest(BaseModel):
    """Dados para avaliacao nativa CASAFARI (comparables-prices)."""

    operation: str = "sale"
    latitude: float
    longitude: float
    address: Optional[str] = None
    distance_km: float = Field(default=5.0, ge=0.05, le=50.0)
    comparables_count: int = Field(default=20, ge=1, le=50)
    property_types: Optional[List[str]] = None
    condition: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    total_area: Optional[int] = None
    plot_area: Optional[int] = None
    construction_year: Optional[int] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None


class CasafariValuationResponse(BaseModel):
    """Resultado do AVM nativo CASAFARI."""

    estimated_price: Optional[float] = None
    estimated_price_per_sqm: Optional[float] = None
    comparables_count: int = 0
    comparables: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = "casafari_native"


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------


class AgencySearchResponse(BaseModel):
    """Resultado de pesquisa de agencias."""

    agencies: List[Dict[str, Any]] = Field(default_factory=list)


class AgentSearchResponse(BaseModel):
    """Resultado de pesquisa de agentes."""

    agents: List[Dict[str, Any]] = Field(default_factory=list)


class LocationSearchRequest(BaseModel):
    """Dados para pesquisa de localizacao CASAFARI."""

    name: Optional[str] = None
    zip_codes: Optional[List[str]] = None


class LocationSearchResponse(BaseModel):
    """Resultado de pesquisa de localizacao."""

    locations: List[Dict[str, Any]] = Field(default_factory=list)
