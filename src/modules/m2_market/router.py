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

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from src.api.dependencies.auth import get_current_organization
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
    LocalAVMRequest,
    LocalAVMResponse,
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
async def search_comparables(
    data: ComparableSearchRequest,
    organization_id: str = Depends(get_current_organization),
) -> Dict[str, Any]:
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
        organization_id=organization_id,
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
async def valuate_property(
    data: ValuationRequest,
    organization_id: str = Depends(get_current_organization),
) -> Dict[str, Any]:
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
        organization_id=organization_id,
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
    organization_id: str = Depends(get_current_organization),
) -> Dict[str, Any]:
    """Estatisticas de mercado para uma zona geografica."""
    svc = _get_service()
    return svc.get_zone_stats(
        district=district,
        municipality=municipality,
        parish=parish,
        property_type=property_type,
        organization_id=organization_id,
    )


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------


@router.post(
    "/alerts",
    summary="Criar alerta de mercado",
)
async def create_alert(
    data: AlertCreateRequest,
    organization_id: str = Depends(get_current_organization),
) -> Dict[str, Any]:
    """Cria alerta para novas listagens ou mudancas de preco."""
    svc = _get_service()
    return svc.create_alert(data.model_dump(), organization_id=organization_id)


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
# SIR (Confidencial Imobiliário — preços reais de transação)
# ---------------------------------------------------------------------------


@router.get(
    "/sir/search",
    summary="Pesquisa SIR por morada ou CEP",
)
async def sir_search_by_address(
    q: str = Query(..., description="Morada, CEP ou concelho (ex: '1050-001', 'Rua Augusta Lisboa', 'Porto')"),
    operation: str = Query("sale", description="'sale' (venda) ou 'rent' (arrendamento)"),
) -> Dict[str, Any]:
    """Resolve morada/CEP para concelho e retorna preço SIR (venda ou arrendamento).

    Usa Nominatim (OpenStreetMap) para geocoding gratuito.
    """
    import httpx as _httpx

    if operation not in ("sale", "rent"):
        raise HTTPException(status_code=400, detail="operation deve ser 'sale' ou 'rent'")

    try:
        from src.modules.m2_market.sir_client import SIRClient, CONCELHO_MAP

        # 1. Tentar como concelho directo
        client = SIRClient()
        direct = client.get_price_m2(q, operation=operation)
        if direct:
            return {**direct, "query": q, "resolved_via": "direct"}

        # 2. Geocoding via Nominatim
        async_query = f"{q} Portugal" if "portugal" not in q.lower() else q
        geo_resp = _httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": async_query, "format": "json", "addressdetails": 1, "limit": 1},
            headers={"User-Agent": "imoIA/1.0 (imoia.vercel.app)"},
            timeout=10,
        )
        if geo_resp.status_code != 200 or not geo_resp.json():
            raise HTTPException(status_code=404, detail=f"Morada não encontrada: '{q}'")

        geo = geo_resp.json()[0]
        addr = geo.get("address", {})
        municipality = (
            addr.get("city")
            or addr.get("town")
            or addr.get("municipality")
            or addr.get("county")
            or ""
        )
        freguesia = addr.get("suburb") or addr.get("quarter") or addr.get("neighbourhood")
        district = addr.get("state") or addr.get("state_district")

        if not municipality:
            raise HTTPException(status_code=404, detail=f"Não foi possível resolver concelho para: '{q}'")

        # 3. Buscar preço SIR (venda ou arrendamento)
        sir_data = client.get_price_m2(municipality, operation=operation)
        result: Dict[str, Any] = {
            "query": q,
            "resolved_via": "geocoding",
            "municipality": municipality,
            "freguesia": freguesia,
            "district": district,
            "latitude": float(geo.get("lat", 0)),
            "longitude": float(geo.get("lon", 0)),
            "display_name": geo.get("display_name", ""),
        }
        if sir_data:
            result.update(sir_data)
        else:
            result["price_m2"] = None
            result["operation"] = operation
            result["note"] = f"Concelho '{municipality}' sem dados SIR para {operation}"

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"SIR search erro: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sir/prices",
    summary="Preços de transação SIR",
)
async def get_sir_prices(
    municipality: str = Query(..., description="Município"),
) -> Dict[str, Any]:
    """Preço médio de transação por m2 (SIR / Confidencial Imobiliário)."""
    try:
        from src.modules.m2_market.sir_client import SIRClient
        client = SIRClient()
        if not client.is_configured:
            raise HTTPException(status_code=503, detail="SIR não configurado")
        result = client.get_price_m2(municipality)
        if result:
            return result
        raise HTTPException(
            status_code=404,
            detail=f"Dados SIR não encontrados para '{municipality}'",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"SIR erro: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/sir/prices/bulk",
    summary="Preços SIR para múltiplos concelhos",
)
async def get_sir_prices_bulk(
    municipalities: List[str],
) -> Dict[str, Any]:
    """Preços de transação para vários concelhos de uma vez."""
    try:
        from src.modules.m2_market.sir_client import SIRClient
        client = SIRClient()
        if not client.is_configured:
            raise HTTPException(status_code=503, detail="SIR não configurado")
        results = client.get_multiple_prices(municipalities)
        return {"results": {k: v for k, v in results.items() if v is not None}}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"SIR bulk erro: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# BPstat (Banco de Portugal — índices de preços habitação)
# ---------------------------------------------------------------------------


@router.get(
    "/bpstat/index",
    summary="Índice de preços habitação (BPstat)",
)
async def get_bpstat_index() -> Dict[str, Any]:
    """Índice de preços de habitação nacional (base 2015=100)."""
    try:
        from src.modules.m2_market.bpstat_client import BPstatClient
        client = BPstatClient()
        data = client.get_price_index(obs_last_n=20)
        if data:
            latest = client.get_latest_index()
            return {"series": data, "latest": latest}
        raise HTTPException(status_code=503, detail="BPstat sem dados")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"BPstat erro: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/bpstat/estimate",
    summary="Estimativa de preço actual (INE + BPstat)",
)
async def get_bpstat_estimate(
    municipality: str = Query(..., description="Município"),
) -> Dict[str, Any]:
    """Estima preço actual: preço base INE × variação índice BPstat."""
    try:
        from src.modules.m2_market.ine_client import INEClient
        from src.modules.m2_market.bpstat_client import BPstatClient
        ine = INEClient()
        bpstat = BPstatClient()
        ine_data = ine.get_median_price(municipality)
        if not ine_data:
            raise HTTPException(
                status_code=404,
                detail=f"Sem dados INE para '{municipality}'",
            )
        estimate = bpstat.estimate_current_price(
            ine_data["price_m2"], ine_data["quarter"], "existing"
        )
        return {
            "ine": ine_data,
            "estimate": estimate,
            "municipality": municipality,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"BPstat estimate erro: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
# AVM Local (imoIA)
# ---------------------------------------------------------------------------


@router.post(
    "/valuate/local",
    summary="AVM local imoIA (ponderado por comparaveis)",
    response_model=LocalAVMResponse,
)
async def valuate_local(data: LocalAVMRequest) -> Dict[str, Any]:
    """Avaliacao automatica usando comparaveis CASAFARI com ponderacao local.

    Calcula preco estimado com media ponderada por distancia, area,
    quartos e condicao. Nao depende do endpoint pago de valuation.
    """
    svc = _get_service()
    result = svc.local_avm(
        latitude=data.latitude,
        longitude=data.longitude,
        address=data.address,
        district=data.district,
        municipality=data.municipality,
        property_type=data.property_type,
        bedrooms=data.bedrooms,
        bathrooms=data.bathrooms,
        total_area=data.total_area,
        condition=data.condition,
        operation=data.operation,
        distance_km=data.distance_km,
        max_comparables=data.max_comparables,
    )

    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])

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
            "POST", "/api/v1/references/locations", json_body={"name": data.name}
        )
        return result or {"locations": []}
    elif data.zip_codes:
        result = client._request(
            "POST",
            "/api/v1/references/locations",
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
