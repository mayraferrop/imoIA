"""Router FastAPI para o modulo M2 — Pesquisa de Mercado.

Endpoints:
- Comparaveis: pesquisa, por deal
- Avaliacao: AVM, ARV
- Zona: estatisticas, tendencias
- Alertas: CRUD + check manual
- Enriquecimento: M1 oportunidades
- Dashboard: overview
- INE: dados gratuitos
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from src.modules.m2_market.schemas import (
    AgencySearchResponse,
    AgentSearchResponse,
    AlertCreateRequest,
    AlertResponse,
    ARVEstimateResponse,
    CasafariValuationRequest,
    CasafariValuationResponse,
    ComparableSearchRequest,
    ComparableSearchResponse,
    EnrichmentResponse,
    LocationSearchRequest,
    LocationSearchResponse,
    MarketOverviewResponse,
    ValuationRequest,
    ValuationResponse,
    ZoneStatsRequest,
    ZoneStatsResponse,
)
from src.modules.m2_market.casafari_client import CasafariClient
from src.modules.m2_market.service import MarketService

router = APIRouter()


def _get_service() -> MarketService:
    return MarketService()


# ---------------------------------------------------------------------------
# Comparaveis
# ---------------------------------------------------------------------------


@router.post(
    "/comparables/search",
    summary="Pesquisar comparaveis",
    response_model=ComparableSearchResponse,
)
async def search_comparables(data: ComparableSearchRequest) -> Dict[str, Any]:
    """Pesquisa comparaveis por localizacao e caracteristicas.

    Usa CASAFARI API (se configurada) + cache local.
    """
    svc = _get_service()
    return svc.find_comparables(
        municipality=data.municipality,
        district=data.district,
        parish=data.parish,
        property_type=data.property_type,
        bedrooms=data.bedrooms,
        area_m2=data.area_m2,
        price_min=data.price_min,
        price_max=data.price_max,
        conditions=data.conditions,
        months_back=data.months_back,
        max_results=data.max_results,
        include_sold=data.include_sold,
        include_active=data.include_active,
    )


@router.get(
    "/deals/{deal_id}/comparables",
    summary="Comparaveis para um deal",
)
async def get_deal_comparables(
    deal_id: str,
    radius_km: float = Query(default=1.0, ge=0.1, le=10.0),
) -> Dict[str, Any]:
    """Encontra comparaveis para um deal existente."""
    svc = _get_service()
    try:
        return svc.find_comparables_for_deal(deal_id, radius_km=radius_km)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Avaliacao
# ---------------------------------------------------------------------------


@router.post(
    "/valuate",
    summary="Avaliar imovel",
)
async def valuate_property(data: ValuationRequest) -> Dict[str, Any]:
    """Avaliacao automatica (AVM) de um imovel."""
    svc = _get_service()
    return svc.valuate_property(
        municipality=data.municipality,
        district=data.district,
        parish=data.parish,
        property_type=data.property_type,
        typology=data.typology,
        gross_area_m2=data.gross_area_m2,
        useful_area_m2=data.useful_area_m2,
        bedrooms=data.bedrooms,
        bathrooms=data.bathrooms,
        condition=data.condition,
        latitude=data.latitude,
        longitude=data.longitude,
        address=data.address,
        method=data.method,
    )


@router.post(
    "/deals/{deal_id}/valuate",
    summary="Avaliar deal",
)
async def valuate_deal(deal_id: str) -> Dict[str, Any]:
    """Avaliacao automatica de um deal existente."""
    svc = _get_service()
    try:
        return svc.valuate_deal(deal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/deals/{deal_id}/arv",
    summary="Estimar ARV (After Repair Value)",
)
async def estimate_arv(deal_id: str) -> Dict[str, Any]:
    """Estima ARV para um deal fix and flip.

    Compara valor actual vs comparaveis renovados na mesma zona.
    """
    svc = _get_service()
    try:
        return svc.estimate_arv(deal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Zona / Estatisticas
# ---------------------------------------------------------------------------


@router.get(
    "/zones/stats",
    summary="Estatisticas de zona",
)
async def get_zone_stats(
    district: str = Query(..., description="Distrito"),
    municipality: Optional[str] = Query(None, description="Concelho"),
    parish: Optional[str] = Query(None, description="Freguesia"),
    property_type: str = Query("apartamento", description="Tipo de imovel"),
) -> Dict[str, Any]:
    """Estatisticas de mercado para uma zona geografica."""
    svc = _get_service()
    return svc.get_zone_stats(
        district=district,
        municipality=municipality,
        parish=parish,
        property_type=property_type,
    )


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------


@router.post(
    "/alerts",
    summary="Criar alerta de mercado",
)
async def create_alert(data: AlertCreateRequest) -> Dict[str, Any]:
    """Cria alerta para novas listagens ou mudancas de preco."""
    svc = _get_service()
    return svc.create_alert(data.model_dump())


@router.get(
    "/alerts",
    summary="Listar alertas",
)
async def list_alerts(
    is_active: Optional[bool] = Query(True),
) -> List[Dict[str, Any]]:
    """Lista alertas de mercado."""
    svc = _get_service()
    return svc.list_alerts(is_active=is_active)


@router.delete(
    "/alerts/{alert_id}",
    summary="Remover alerta",
)
async def delete_alert(alert_id: str) -> Dict[str, Any]:
    """Remove um alerta de mercado."""
    svc = _get_service()
    deleted = svc.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alerta nao encontrado")
    return {"deleted": True}


@router.post(
    "/alerts/check",
    summary="Verificar alertas (manual)",
)
async def check_alerts() -> Dict[str, Any]:
    """Verifica todos os alertas activos e retorna novos resultados."""
    svc = _get_service()
    results = svc.check_alerts()
    return {"new_results": len(results), "results": results[:20]}


# ---------------------------------------------------------------------------
# Enriquecimento M1
# ---------------------------------------------------------------------------


@router.post(
    "/opportunities/{opportunity_id}/enrich",
    summary="Enriquecer oportunidade M1",
)
async def enrich_opportunity(opportunity_id: int) -> Dict[str, Any]:
    """Enriquece uma oportunidade do M1 com dados de mercado.

    Busca comparaveis, calcula desconto vs mercado, estima ARV.
    """
    svc = _get_service()
    try:
        return svc.enrich_opportunity(opportunity_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# INE (dados gratuitos)
# ---------------------------------------------------------------------------


@router.get(
    "/ine/housing-prices",
    summary="Precos medianos INE",
)
async def get_ine_housing_prices(
    municipality: str = Query(..., description="Municipio"),
) -> Dict[str, Any]:
    """Precos medianos de habitacao do INE (gratuito, sem API key)."""
    try:
        from src.modules.m2_market.ine_client import INEClient
        client = INEClient()
        result = client.get_median_price(municipality)
        if result:
            return result
        raise HTTPException(
            status_code=404,
            detail=f"Dados INE nao encontrados para '{municipality}'",
        )
    except ImportError:
        raise HTTPException(status_code=503, detail="INEClient nao disponivel")


# ---------------------------------------------------------------------------
# Casafari AVM Nativo
# ---------------------------------------------------------------------------


@router.post(
    "/valuate/casafari",
    summary="Avaliacao nativa CASAFARI (comparables-prices)",
)
async def valuate_casafari_native(data: CasafariValuationRequest) -> Dict[str, Any]:
    """AVM nativo da CASAFARI usando comparaveis vendidos na zona.

    Requer coordenadas (latitude/longitude). Retorna estimativa de preco
    e lista de comparaveis usados no calculo.
    """
    client = CasafariClient()
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="CASAFARI nao configurada")

    casafari_types = None
    if data.property_types:
        casafari_types = []
        for pt in data.property_types:
            casafari_types.extend(CasafariClient.map_property_type(pt))

    casafari_condition = CasafariClient.map_condition(data.condition) if data.condition else None

    result = client.get_comparables_prices(
        operation=data.operation,
        latitude=data.latitude,
        longitude=data.longitude,
        address=data.address,
        distance_km=data.distance_km,
        comparables_count=data.comparables_count,
        comparables_types=casafari_types,
        condition=casafari_condition,
        bedrooms=data.bedrooms,
        bathrooms=data.bathrooms,
        total_area=data.total_area,
        plot_area=data.plot_area,
        construction_year=data.construction_year,
        min_price=data.min_price,
        max_price=data.max_price,
    )

    if result is None:
        raise HTTPException(
            status_code=502,
            detail="CASAFARI nao retornou dados — verifique limites da API",
        )
    return result


# ---------------------------------------------------------------------------
# References CASAFARI
# ---------------------------------------------------------------------------


@router.post(
    "/references/locations",
    summary="Pesquisar localizacoes CASAFARI",
)
async def search_locations(data: LocationSearchRequest) -> Dict[str, Any]:
    """Pesquisa localizacoes por nome ou codigo postal."""
    client = CasafariClient()
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="CASAFARI nao configurada")

    if data.name:
        loc_id = client.resolve_location(data.name)
        # Retornar resultado completo da API
        result = client._request(
            "POST", "/v1/references/locations", json_body={"name": data.name}
        )
        return result or {"locations": []}
    elif data.zip_codes:
        result = client._request(
            "POST",
            "/v1/references/locations",
            json_body={"zip_codes": data.zip_codes},
        )
        return result or {"locations": []}
    else:
        raise HTTPException(status_code=400, detail="Fornecer name ou zip_codes")


@router.get(
    "/references/agencies",
    summary="Pesquisar agencias imobiliarias",
)
async def search_agencies(
    name: str = Query(..., description="Nome da agencia"),
) -> Dict[str, Any]:
    """Pesquisa agencias imobiliarias por nome."""
    client = CasafariClient()
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="CASAFARI nao configurada")
    return client.search_agencies(name) or {"agencies": []}


@router.get(
    "/references/agents",
    summary="Pesquisar agentes imobiliarios",
)
async def search_agents(
    name: str = Query(..., description="Nome do agente"),
) -> Dict[str, Any]:
    """Pesquisa agentes imobiliarios por nome."""
    client = CasafariClient()
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="CASAFARI nao configurada")
    return client.search_agents(name) or {"agents": []}


@router.get(
    "/references/sources",
    summary="Fontes de listagens por localizacao",
)
async def get_sources(
    location_id: int = Query(..., description="ID da localizacao CASAFARI"),
) -> Dict[str, Any]:
    """Retorna fontes/dominios disponiveis para uma localizacao."""
    client = CasafariClient()
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="CASAFARI nao configurada")
    return client.get_sources(location_id) or {"sources": []}


@router.get(
    "/references/types",
    summary="Tipos de imoveis CASAFARI",
)
async def get_property_types() -> Dict[str, Any]:
    """Retorna todos os tipos de imoveis disponiveis na CASAFARI."""
    client = CasafariClient()
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="CASAFARI nao configurada")
    return client.get_property_types() or {"types": []}


@router.get(
    "/references/features",
    summary="Features de imoveis CASAFARI",
)
async def get_features() -> Dict[str, Any]:
    """Retorna todas as features disponiveis (floor, views, etc.)."""
    client = CasafariClient()
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="CASAFARI nao configurada")
    return client.get_features() or {"features": []}


@router.get(
    "/references/conditions",
    summary="Condicoes de imoveis CASAFARI",
)
async def get_conditions() -> Dict[str, Any]:
    """Retorna todas as condicoes disponiveis."""
    client = CasafariClient()
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="CASAFARI nao configurada")
    conditions = client.get_conditions()
    if isinstance(conditions, list):
        return {"conditions": conditions}
    return conditions or {"conditions": []}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/overview",
    summary="Overview de mercado",
)
async def market_overview() -> Dict[str, Any]:
    """Overview de mercado para dashboard."""
    svc = _get_service()
    return svc.get_market_overview()
