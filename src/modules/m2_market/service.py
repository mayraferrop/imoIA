"""Servico M2 — orquestra pesquisa de mercado, comparaveis e avaliacoes.

Combina CASAFARI API + INE para fornecer dados de mercado a todos os modulos.
Funciona sem CASAFARI (so INE) quando a API key nao esta configurada.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.database.db import get_session
from src.database.models_v2 import (
    Deal,
    MarketAlert,
    MarketComparable,
    MarketZoneStats,
    Property,
    PropertyValuation,
    Tenant,
)
from src.modules.m2_market.casafari_client import CasafariClient

# Cache TTLs lidos de config.py (fallback hardcoded se config falhar)
_settings = get_settings()
_CACHE_COMPARABLES_DAYS = _settings.market_cache_days_comparables
_CACHE_ZONE_STATS_DAYS = _settings.market_cache_days_zone_stats
_CACHE_VALUATION_DAYS = _settings.market_cache_days_valuation

_DEFAULT_TENANT_SLUG = "default"


def _ensure_tenant(session: Session) -> str:
    """Garante que o tenant default existe e retorna o id."""
    tenant = session.execute(
        select(Tenant).where(Tenant.slug == _DEFAULT_TENANT_SLUG)
    ).scalar_one_or_none()

    if tenant is None:
        tenant = Tenant(
            id=str(uuid4()),
            name="ImoIA",
            slug=_DEFAULT_TENANT_SLUG,
            country="PT",
        )
        session.add(tenant)
        session.flush()

    return tenant.id


def _get_ine_client():
    """Retorna INEClient (importacao lazy para evitar dependencias circulares)."""
    try:
        from src.modules.m2_market.ine_client import INEClient
        return INEClient()
    except ImportError:
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distancia em km entre duas coordenadas."""
    R = 6371.0
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class MarketService:
    """Servico de pesquisa de mercado — M2.

    Combina CASAFARI (listagens, comparaveis, detalhe) + INE (benchmarks macro).
    """

    def __init__(self) -> None:
        self._casafari = CasafariClient()
        self._ine = _get_ine_client()
        self._settings = get_settings()

    @property
    def casafari_available(self) -> bool:
        """Verifica se CASAFARI esta disponivel."""
        return self._casafari.is_configured

    # ------------------------------------------------------------------
    # Comparaveis
    # ------------------------------------------------------------------

    def find_comparables(
        self,
        municipality: Optional[str] = None,
        district: Optional[str] = None,
        parish: Optional[str] = None,
        property_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
        area_m2: Optional[float] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        conditions: Optional[List[str]] = None,
        months_back: int = 12,
        max_results: int = 20,
        include_sold: bool = True,
        include_active: bool = True,
        deal_id: Optional[str] = None,
        opportunity_id: Optional[int] = None,
        tenant_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Encontra comparaveis para um imovel.

        Fluxo:
        1. Verifica cache (comparaveis < 7 dias para o mesmo deal/localizacao)
        2. Resolve localizacao para location_id CASAFARI
        3. Pesquisa via POST /listing-alerts/search
        4. Parseia e guarda resultados como MarketComparable
        5. Calcula estatisticas (mediana, media, etc.)

        Returns:
            Dict com 'comparables', 'total', 'stats'.
        """
        with get_session() as session:
            if tenant_id is None:
                tenant_id = _ensure_tenant(session)

            # Verificar cache se temos deal_id
            if deal_id:
                cached = self._get_cached_comparables(session, deal_id)
                if cached:
                    logger.debug(f"M2: cache hit — {len(cached)} comparaveis para deal {deal_id}")
                    return self._build_comparable_response(cached)

            if not self.casafari_available:
                logger.info("M2: CASAFARI nao configurada — sem comparaveis")
                return {"comparables": [], "total": 0, "stats": {}}

            # Resolver localizacao
            location_name = municipality or parish or district
            if not location_name:
                return {"comparables": [], "total": 0, "stats": {}}

            location_id = self._casafari.resolve_location(location_name)
            if not location_id:
                logger.info(f"M2: localizacao '{location_name}' nao encontrada no CASAFARI")
                return {"comparables": [], "total": 0, "stats": {}}

            # Preparar filtros
            casafari_types = CasafariClient.map_property_type(property_type)
            casafari_conditions = None
            if conditions:
                casafari_conditions = [
                    CasafariClient.map_condition(c) for c in conditions
                    if CasafariClient.map_condition(c)
                ]

            statuses = []
            if include_active:
                statuses.extend(["active", "reserved"])
            if include_sold:
                statuses.append("sold")

            # Calcular data minima
            alert_date_from = (
                datetime.now(tz=timezone.utc) - timedelta(days=months_back * 30)
            ).strftime("%Y-%m-%d")

            # Area: intervalo ±30%
            area_from = int(area_m2 * 0.7) if area_m2 else None
            area_to = int(area_m2 * 1.3) if area_m2 else None

            # Pesquisar
            data = self._casafari.search_listings(
                location_ids=[location_id],
                property_types=casafari_types or None,
                operation="sale",
                price_from=price_min,
                price_to=price_max,
                bedrooms_from=bedrooms,
                bedrooms_to=bedrooms,
                total_area_from=area_from,
                total_area_to=area_to,
                conditions=casafari_conditions,
                statuses=statuses or None,
                alert_date_from=alert_date_from,
                limit=min(max_results, 100),
            )

            if not data:
                logger.info(f"M2: sem resultados CASAFARI para '{location_name}'")
                return {"comparables": [], "total": 0, "stats": {}}

            results = data.get("results", [])
            if isinstance(data, list):
                results = data

            if not results:
                return {"comparables": [], "total": 0, "stats": {}}

            # Parsear e guardar
            saved = []
            for alert in results[:max_results]:
                parsed = CasafariClient.parse_alert_to_comparable(alert)
                comp = MarketComparable(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    organization_id=organization_id,
                    deal_id=deal_id,
                    opportunity_id=opportunity_id,
                    source=parsed["source"],
                    source_id=parsed["source_id"],
                    source_url=parsed["source_url"],
                    property_type=parsed["property_type"],
                    bedrooms=parsed["bedrooms"],
                    bathrooms=parsed["bathrooms"],
                    district=parsed["district"],
                    municipality=parsed["municipality"],
                    parish=parsed["parish"],
                    address=parsed["address"],
                    postal_code=parsed["postal_code"],
                    latitude=parsed["latitude"],
                    longitude=parsed["longitude"],
                    listing_price=parsed["listing_price"],
                    price_per_m2=parsed["price_per_m2"],
                    currency=parsed["currency"],
                    gross_area_m2=parsed["gross_area_m2"],
                    useful_area_m2=parsed["useful_area_m2"],
                    condition=parsed["condition"],
                    construction_year=parsed["construction_year"],
                    energy_certificate=parsed["energy_certificate"],
                    comparison_type=parsed["comparison_type"],
                    days_on_market=parsed["days_on_market"],
                    raw_data=parsed["raw_data"],
                    expires_at=datetime.now(tz=timezone.utc) + timedelta(days=_CACHE_COMPARABLES_DAYS),
                )

                # Calcular price_per_m2 se nao veio da API
                if not comp.price_per_m2 and comp.listing_price and comp.gross_area_m2:
                    if comp.gross_area_m2 > 0:
                        comp.price_per_m2 = round(comp.listing_price / comp.gross_area_m2, 2)

                session.add(comp)
                saved.append(comp)

            session.flush()
            logger.info(
                f"M2: {len(saved)} comparaveis encontrados e guardados para "
                f"'{location_name}' (deal={deal_id})"
            )

            return self._build_comparable_response(saved)

    def find_comparables_for_deal(
        self, deal_id: str, radius_km: float = 1.0
    ) -> Dict[str, Any]:
        """Encontra comparaveis para um deal existente."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal {deal_id} nao encontrado")

            prop = session.get(Property, deal.property_id)
            if not prop:
                raise ValueError(f"Property do deal {deal_id} nao encontrada")

            return self.find_comparables(
                municipality=prop.municipality,
                district=prop.district,
                parish=prop.parish,
                property_type=prop.property_type,
                bedrooms=prop.bedrooms,
                area_m2=prop.gross_area_m2,
                deal_id=deal_id,
                tenant_id=deal.tenant_id,
            )

    def _get_cached_comparables(
        self, session: Session, deal_id: str
    ) -> Optional[List[MarketComparable]]:
        """Retorna comparaveis em cache (< CACHE_DAYS dias) para um deal."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_CACHE_COMPARABLES_DAYS)
        results = session.execute(
            select(MarketComparable)
            .where(
                MarketComparable.deal_id == deal_id,
                MarketComparable.fetched_at >= cutoff,
            )
            .order_by(MarketComparable.listing_price.desc())
        ).scalars().all()

        return results if results else None

    def _build_comparable_response(
        self, comparables: List[MarketComparable]
    ) -> Dict[str, Any]:
        """Constroi resposta com comparaveis e estatisticas."""
        prices_m2 = [
            c.price_per_m2 for c in comparables
            if c.price_per_m2 and c.price_per_m2 > 0
        ]

        stats: Dict[str, Any] = {}
        if prices_m2:
            sorted_p = sorted(prices_m2)
            n = len(sorted_p)
            # Mediana correcta para arrays pares e ímpares
            if n % 2 == 1:
                median = sorted_p[n // 2]
            else:
                median = (sorted_p[n // 2 - 1] + sorted_p[n // 2]) / 2
            stats = {
                "avg_price_m2": round(sum(sorted_p) / n, 2),
                "median_price_m2": round(median, 2),
                "min_price_m2": round(sorted_p[0], 2),
                "max_price_m2": round(sorted_p[-1], 2),
                "count": n,
            }

        items = []
        for c in comparables:
            items.append({
                "id": c.id,
                "source": c.source,
                "source_id": c.source_id,
                "source_url": c.source_url,
                "property_type": c.property_type,
                "bedrooms": c.bedrooms,
                "bathrooms": c.bathrooms,
                "district": c.district,
                "municipality": c.municipality,
                "parish": c.parish,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "distance_km": c.distance_km,
                "listing_price": c.listing_price,
                "sale_price": c.sale_price,
                "price_per_m2": c.price_per_m2,
                "gross_area_m2": c.gross_area_m2,
                "useful_area_m2": c.useful_area_m2,
                "condition": c.condition,
                "construction_year": c.construction_year,
                "energy_certificate": c.energy_certificate,
                "listing_date": c.listing_date.isoformat() if c.listing_date else None,
                "days_on_market": c.days_on_market,
                "comparison_type": c.comparison_type,
                "fetched_at": c.fetched_at.isoformat() if c.fetched_at else None,
            })

        return {
            "comparables": items,
            "total": len(items),
            "stats": stats,
        }

    # ------------------------------------------------------------------
    # Avaliacao (AVM)
    # ------------------------------------------------------------------

    def _try_casafari_native_valuation(
        self,
        property_type: Optional[str],
        latitude: Optional[float],
        longitude: Optional[float],
        address: Optional[str],
        condition: Optional[str],
        bedrooms: Optional[int],
        bathrooms: Optional[int],
        gross_area_m2: Optional[float],
    ) -> Optional[Dict[str, Any]]:
        """Tenta AVM nativo da CASAFARI (POST /v1/valuation/comparables-prices).

        Requer coordenadas. Retorna None se nao disponivel.
        """
        if not self.casafari_available:
            return None
        if latitude is None or longitude is None:
            return None

        casafari_types = CasafariClient.map_property_type(property_type)
        casafari_condition = CasafariClient.map_condition(condition) if condition else None

        data = self._casafari.get_comparables_prices(
            operation="sale",
            latitude=latitude,
            longitude=longitude,
            address=address,
            distance_km=5.0,
            comparables_count=30,
            comparables_types=casafari_types or None,
            condition=casafari_condition,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            total_area=int(gross_area_m2) if gross_area_m2 else None,
        )

        if data:
            logger.info(
                f"M2: AVM nativo CASAFARI retornou dados "
                f"(lat={latitude}, lon={longitude})"
            )
        return data

    def valuate_property(
        self,
        municipality: Optional[str] = None,
        district: Optional[str] = None,
        parish: Optional[str] = None,
        property_type: Optional[str] = None,
        typology: Optional[str] = None,
        gross_area_m2: Optional[float] = None,
        useful_area_m2: Optional[float] = None,
        bedrooms: Optional[int] = None,
        bathrooms: Optional[int] = None,
        condition: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        address: Optional[str] = None,
        method: str = "hybrid",
        deal_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Avalia um imovel combinando AVM local + INE.

        Metodo 'hybrid' (prioridade):
        1. AVM local ponderado (se tem coordenadas + CASAFARI)
        2. Fallback: comparaveis simples via listing-alerts
        3. Complementa com INE para benchmarks

        Metodo 'local_avm': usa apenas AVM local ponderado.
        Metodo 'comparables': usa apenas comparaveis simples.

        Returns:
            Dict com resultado da avaliacao.
        """
        with get_session() as session:
            if tenant_id is None:
                tenant_id = _ensure_tenant(session)

            area = gross_area_m2 or useful_area_m2 or 80.0

            estimated_value = None
            estimated_price_m2 = None
            confidence = 0.0
            comp_count = 0
            stats: Dict[str, Any] = {}
            used_method = method

            # --- 1. Tentar AVM local ponderado (metodo principal) ---
            if method in ("hybrid", "local_avm") and latitude and longitude:
                avm_result = self.local_avm(
                    latitude=latitude,
                    longitude=longitude,
                    property_type=property_type or "apartment",
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    total_area=area,
                    condition=condition,
                    address=address,
                    municipality=municipality,
                    district=district,
                )

                if "error" not in avm_result:
                    estimated_value = avm_result["fair_market_price"]
                    estimated_price_m2 = avm_result["estimated_price_per_m2"]
                    confidence = avm_result["confidence_score"]
                    comp_count = avm_result["comparables_used"]
                    ms = avm_result.get("market_stats") or {}
                    stats = {
                        "avg_price_m2": ms.get("avg_price_per_m2"),
                        "median_price_m2": ms.get("median_price_per_m2"),
                        "count": comp_count,
                    }
                    used_method = "local_avm"

            # --- 2. Fallback: comparaveis simples via listing-alerts ---
            if estimated_value is None and method in ("hybrid", "comparables"):
                comp_result = self.find_comparables(
                    municipality=municipality,
                    district=district,
                    parish=parish,
                    property_type=property_type,
                    bedrooms=bedrooms,
                    area_m2=area,
                    deal_id=deal_id,
                    tenant_id=tenant_id,
                )

                stats = comp_result.get("stats", {})
                comp_count = stats.get("count", 0)

                if stats.get("median_price_m2"):
                    estimated_price_m2 = stats["median_price_m2"]
                    estimated_value = round(estimated_price_m2 * area, 2)

                    if comp_count >= 15:
                        confidence = 85.0
                    elif comp_count >= 10:
                        confidence = 75.0
                    elif comp_count >= 5:
                        confidence = 60.0
                    elif comp_count >= 3:
                        confidence = 45.0
                    else:
                        confidence = 25.0
                    used_method = "comparables"

            # --- 3. Complementar com INE ---
            ine_price_m2 = None
            if self._ine and municipality:
                ine_data = self._ine.get_median_price(municipality)
                if ine_data:
                    ine_price_m2 = ine_data.get("price_m2")

            # Se nao temos nada, usar INE como ultimo fallback
            if estimated_value is None and ine_price_m2:
                estimated_price_m2 = ine_price_m2
                estimated_value = round(ine_price_m2 * area, 2)
                confidence = 20.0
                used_method = "ine"

            # Intervalo (±7% local_avm, ±15% comparaveis, ±25% INE)
            if used_method == "local_avm":
                margin = 0.07
            elif confidence >= 60:
                margin = 0.15
            else:
                margin = 0.25
            value_low = round(estimated_value * (1 - margin), 2) if estimated_value else None
            value_high = round(estimated_value * (1 + margin), 2) if estimated_value else None

            # Persistir
            valuation = PropertyValuation(
                id=str(uuid4()),
                tenant_id=tenant_id,
                deal_id=deal_id,
                property_type=property_type,
                typology=typology,
                gross_area_m2=gross_area_m2,
                useful_area_m2=useful_area_m2,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                district=district,
                municipality=municipality,
                parish=parish,
                address=address,
                latitude=latitude,
                longitude=longitude,
                condition=condition,
                estimated_value=estimated_value,
                estimated_value_low=value_low,
                estimated_value_high=value_high,
                estimated_price_per_m2=estimated_price_m2,
                confidence_score=confidence,
                avg_price_per_m2_zone=stats.get("avg_price_m2"),
                median_price_per_m2_zone=stats.get("median_price_m2") or ine_price_m2,
                comparables_count=comp_count,
                comparables_avg_price_m2=stats.get("avg_price_m2"),
                source="casafari" if used_method != "ine" else "ine",
                method=used_method,
                model_version="m2_v3",
                expires_at=datetime.now(tz=timezone.utc) + timedelta(days=_CACHE_VALUATION_DAYS),
            )
            session.add(valuation)
            session.flush()

            logger.info(
                f"M2: avaliacao {valuation.id} — valor={estimated_value}, "
                f"preco_m2={estimated_price_m2}, confianca={confidence}%, "
                f"metodo={used_method}, comparaveis={comp_count}"
            )

            return self._valuation_to_dict(valuation)

    def local_avm(
        self,
        latitude: float,
        longitude: float,
        property_type: str = "apartment",
        bedrooms: Optional[int] = None,
        bathrooms: Optional[int] = None,
        total_area: Optional[float] = None,
        condition: Optional[str] = None,
        operation: str = "sale",
        distance_km: float = 5.0,
        max_comparables: int = 30,
        address: Optional[str] = None,
        municipality: Optional[str] = None,
        district: Optional[str] = None,
    ) -> Dict[str, Any]:
        """AVM local completo — substitui o valuation pago da CASAFARI.

        Busca comparaveis via /comparables/search e calcula:
        - Preco estimado com media ponderada (distancia, area, quartos, condicao)
        - fast_sell / fair_market / out_of_market (equivalente CASAFARI)
        - Estatisticas de mercado (DOM, volume, breakdowns)
        - Percentis e intervalo de confianca

        Returns:
            Dict completo com estimativa, mercado e comparaveis.
        """
        if not self.casafari_available:
            return {"error": "CASAFARI nao configurada"}

        casafari_types = CasafariClient.map_property_type(property_type)
        casafari_condition = (
            CasafariClient.map_condition(condition) if condition else None
        )

        # Buscar comparaveis via endpoint dedicado
        data = self._casafari.search_comparables(
            operation=operation,
            latitude=latitude,
            longitude=longitude,
            address=address,
            distance_km=distance_km,
            comparables_count=min(max_comparables, 50),
            comparables_types=casafari_types or ["apartment"],
            condition=casafari_condition,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            total_area=int(total_area) if total_area else None,
        )

        if not data:
            return {"error": "CASAFARI nao retornou comparaveis"}

        results = data.get("results", [])
        if isinstance(data, list):
            results = data
        if not results:
            return {"error": "0 comparaveis encontrados"}

        # Parsear comparaveis com todos os campos
        parsed = []
        for item in results:
            comp = CasafariClient.parse_alert_to_comparable(item)
            price_m2 = comp.get("price_per_m2")
            price = comp.get("listing_price")
            gross = comp.get("gross_area_m2")
            useful = comp.get("useful_area_m2")
            area = gross or useful
            if not price_m2 and price and area and area > 0:
                price_m2 = round(price / area, 2)
            if not price_m2 or price_m2 <= 0:
                continue

            clat = comp.get("latitude")
            clon = comp.get("longitude")
            dist = None
            if clat and clon:
                dist = self._haversine(latitude, longitude, clat, clon)

            # Extrair dados do raw para DOM e listings
            raw = comp.get("raw_data") or {}
            dom = raw.get("days_on_market") or comp.get("days_on_market")
            listings_count = len(raw.get("listings", []))
            alert_date = comp.get("listing_date") or raw.get("alert_date")
            alert_type = raw.get("alert_type", "")
            alert_subtype = comp.get("alert_subtype") or raw.get("alert_subtype", "")

            # Determinar tipo de comparavel (activo, vendido, etc.)
            comparison = comp.get("comparison_type", "listing_active")
            if "sold" in str(alert_subtype).lower() or "sold" in str(alert_type).lower():
                comparison = "sold"

            parsed.append({
                "source_id": comp.get("source_id"),
                "source_url": comp.get("source_url"),
                "parish": comp.get("parish"),
                "latitude": clat,
                "longitude": clon,
                "distance_km": round(dist, 2) if dist else None,
                "listing_price": price,
                "price_per_m2": price_m2,
                "gross_area_m2": gross,
                "useful_area_m2": useful,
                "bedrooms": comp.get("bedrooms"),
                "bathrooms": comp.get("bathrooms"),
                "condition": comp.get("condition"),
                "construction_year": comp.get("construction_year"),
                "energy_certificate": comp.get("energy_certificate"),
                "listing_date": alert_date,
                "days_on_market": dom,
                "comparison_type": comparison,
                "listings_count": listings_count if listings_count > 0 else None,
            })

        if not parsed:
            return {"error": "0 comparaveis com preco/m2 valido"}

        # Calcular pesos
        area_ref = total_area or 80.0
        weighted_comps = []
        for c in parsed:
            w = 1.0

            # Peso distancia: mais perto = mais peso (decay gaussiano)
            d = c.get("distance_km")
            if d is not None:
                w *= math.exp(-(d ** 2) / (2 * (distance_km / 2) ** 2))
            else:
                w *= 0.3

            # Peso area: area similar = mais peso
            c_area = c.get("gross_area_m2") or c.get("useful_area_m2")
            if c_area and c_area > 0:
                area_ratio = min(c_area, area_ref) / max(c_area, area_ref)
                w *= area_ratio
            else:
                w *= 0.5

            # Peso quartos: mesmo numero = bonus
            c_bed = c.get("bedrooms")
            if bedrooms is not None and c_bed is not None:
                if c_bed == bedrooms:
                    w *= 1.2
                elif abs(c_bed - bedrooms) == 1:
                    w *= 0.8
                else:
                    w *= 0.5

            # Peso condicao: mesma condicao = bonus
            c_cond = c.get("condition")
            if condition and c_cond:
                if c_cond == condition:
                    w *= 1.2
                elif c_cond in ("new", "very-good") and condition in ("new", "very-good"):
                    w *= 1.0
                else:
                    w *= 0.7

            c["weight"] = round(w, 4)
            weighted_comps.append(c)

        # Ordenar por peso (maior primeiro)
        weighted_comps.sort(key=lambda x: x["weight"], reverse=True)

        # Media ponderada do preco/m2
        total_w = sum(c["weight"] for c in weighted_comps)
        if total_w <= 0:
            return {"error": "pesos zerados — sem comparaveis validos"}

        weighted_price_m2 = sum(
            c["price_per_m2"] * c["weight"] for c in weighted_comps
        ) / total_w

        # Estatisticas de preco
        all_prices_m2 = sorted(c["price_per_m2"] for c in weighted_comps)
        all_prices = sorted(c["listing_price"] for c in weighted_comps if c.get("listing_price"))
        n = len(all_prices_m2)

        # Mediana
        if n % 2 == 1:
            median_price_m2 = all_prices_m2[n // 2]
        else:
            median_price_m2 = (all_prices_m2[n // 2 - 1] + all_prices_m2[n // 2]) / 2

        # Percentis 25 e 75 (para IQR)
        p25_idx = max(0, int(n * 0.25))
        p75_idx = min(n - 1, int(n * 0.75))
        p25 = all_prices_m2[p25_idx]
        p75 = all_prices_m2[p75_idx]

        # Desvio padrao e CV
        mean_p = sum(all_prices_m2) / n
        variance = sum((p - mean_p) ** 2 for p in all_prices_m2) / n
        std_dev = math.sqrt(variance)
        cv = std_dev / mean_p if mean_p > 0 else 1.0

        # Confianca baseada em CV + numero de comparaveis
        if n >= 15 and cv < 0.25:
            confidence = 90.0
        elif n >= 10 and cv < 0.35:
            confidence = 80.0
        elif n >= 5 and cv < 0.40:
            confidence = 65.0
        elif n >= 3:
            confidence = 45.0
        else:
            confidence = 25.0

        # Precos estimados (equivalente CASAFARI: fast_sell/fair_market/out_of_market)
        area_for_calc = total_area or 80.0
        fair_market = round(weighted_price_m2 * area_for_calc, 2)
        # fast_sell = ~7% abaixo do fair_market (CASAFARI usa ~7%)
        fast_sell = round(fair_market * 0.93, 2)
        # out_of_market = ~7% acima
        out_of_market = round(fair_market * 1.07, 2)

        # --- Estatisticas de mercado ---

        # Media de area
        areas = [c.get("gross_area_m2") or c.get("useful_area_m2") for c in weighted_comps]
        areas = [a for a in areas if a and a > 0]
        avg_area = round(sum(areas) / len(areas), 1) if areas else None

        # Media de ano de construcao
        years = [c.get("construction_year") for c in weighted_comps]
        years = [y for y in years if y and y > 1800]
        avg_year = round(sum(years) / len(years)) if years else None

        # Tempo medio no mercado (DOM)
        doms = [c.get("days_on_market") for c in weighted_comps]
        doms = [d for d in doms if d and d > 0]
        avg_dom = round(sum(doms) / len(doms)) if doms else None

        # Media de listings por propriedade
        lcounts = [c.get("listings_count") for c in weighted_comps]
        lcounts = [lc for lc in lcounts if lc and lc > 0]
        avg_listings = round(sum(lcounts) / len(lcounts), 1) if lcounts else None

        # Contagem de vendidos nos ultimos 6 meses
        now = datetime.now(tz=timezone.utc)
        six_months_ago = now - timedelta(days=180)
        sold_6m = 0
        active_count = 0
        for c in weighted_comps:
            ct = c.get("comparison_type", "")
            if "sold" in ct:
                sold_6m += 1
            else:
                active_count += 1

        # Breakdown por condicao
        cond_breakdown: Dict[str, int] = {}
        for c in weighted_comps:
            cond = c.get("condition") or "unknown"
            cond_breakdown[cond] = cond_breakdown.get(cond, 0) + 1

        # Breakdown por freguesia
        parish_breakdown: Dict[str, int] = {}
        for c in weighted_comps:
            p = c.get("parish") or "unknown"
            parish_breakdown[p] = parish_breakdown.get(p, 0) + 1

        # Breakdown por certificado energetico
        energy_breakdown: Dict[str, int] = {}
        for c in weighted_comps:
            e = c.get("energy_certificate") or "unknown"
            energy_breakdown[e] = energy_breakdown.get(e, 0) + 1

        # Media de preco absoluto
        avg_price = round(sum(all_prices) / len(all_prices), 2) if all_prices else None

        market_stats = {
            "avg_price": avg_price,
            "avg_price_per_m2": round(mean_p, 2),
            "median_price_per_m2": round(median_price_m2, 2),
            "min_price_per_m2": round(all_prices_m2[0], 2),
            "max_price_per_m2": round(all_prices_m2[-1], 2),
            "std_dev_price_m2": round(std_dev, 2),
            "coefficient_of_variation": round(cv, 4),
            "avg_area_m2": avg_area,
            "avg_construction_year": avg_year,
            "avg_time_on_market_days": avg_dom,
            "avg_listings_per_property": avg_listings,
            "sold_or_rented_last_6m": sold_6m if sold_6m > 0 else None,
            "total_active_listings": active_count,
            "condition_breakdown": cond_breakdown,
            "parish_breakdown": parish_breakdown,
            "energy_breakdown": energy_breakdown,
        }

        logger.info(
            f"M2-AVM-LOCAL: {n} comparaveis, "
            f"fair_market={fair_market:.0f}€, "
            f"preco_m2={weighted_price_m2:.0f}, "
            f"CV={cv:.2f}, confianca={confidence}%"
        )

        # Limpar campo listings_count dos comparaveis (so para calculo interno)
        for c in weighted_comps:
            c.pop("listings_count", None)

        return {
            "estimated_price": fair_market,
            "fast_sell_price": fast_sell,
            "fair_market_price": fair_market,
            "out_of_market_price": out_of_market,
            "estimated_price_per_m2": round(weighted_price_m2, 2),
            "confidence_score": confidence,
            "comparables_used": n,
            "comparables_total": len(results),
            "weighted_avg_price_m2": round(weighted_price_m2, 2),
            "simple_median_price_m2": round(median_price_m2, 2),
            "percentile_25_price_m2": round(p25, 2),
            "percentile_75_price_m2": round(p75, 2),
            "market_stats": market_stats,
            "method": "weighted_comparables",
            "source": "imoia_local",
            "comparables": weighted_comps[:20],
        }

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distancia em km entre dois pontos (formula de Haversine)."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def valuate_deal(self, deal_id: str) -> Dict[str, Any]:
        """Avalia um deal existente."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal {deal_id} nao encontrado")

            prop = session.get(Property, deal.property_id)
            if not prop:
                raise ValueError(f"Property do deal {deal_id} nao encontrada")

            return self.valuate_property(
                municipality=prop.municipality,
                district=prop.district,
                parish=prop.parish,
                property_type=prop.property_type,
                typology=prop.typology,
                gross_area_m2=prop.gross_area_m2,
                useful_area_m2=prop.net_area_m2,
                bedrooms=prop.bedrooms,
                bathrooms=prop.bathrooms,
                condition=prop.condition,
                latitude=prop.latitude,
                longitude=prop.longitude,
                address=prop.address,
                deal_id=deal_id,
                tenant_id=deal.tenant_id,
            )

    def estimate_arv(self, deal_id: str) -> Dict[str, Any]:
        """Estima ARV (After Repair Value) para um deal fix and flip.

        1. Avalia no estado actual (condition do deal)
        2. Avalia no estado pos-obra (condition='renovado')
        3. Delta = potencial de valorizacao

        Returns:
            Dict com current_value, arv_estimated, value_uplift, etc.
        """
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal {deal_id} nao encontrado")

            prop = session.get(Property, deal.property_id)
            if not prop:
                raise ValueError(f"Property do deal {deal_id} nao encontrada")

        # Avaliacao actual
        current = self.valuate_property(
            municipality=prop.municipality,
            district=prop.district,
            parish=prop.parish,
            property_type=prop.property_type,
            gross_area_m2=prop.gross_area_m2,
            bedrooms=prop.bedrooms,
            condition=prop.condition or "usado",
            deal_id=deal_id,
        )

        # Avaliacao pos-obra (comparaveis em bom estado)
        arv_result = self.find_comparables(
            municipality=prop.municipality,
            district=prop.district,
            property_type=prop.property_type,
            bedrooms=prop.bedrooms,
            area_m2=prop.gross_area_m2,
            conditions=["renovado", "novo"],
        )

        arv_stats = arv_result.get("stats", {})
        area = prop.gross_area_m2 or 80.0

        arv_price_m2 = arv_stats.get("median_price_m2")
        arv_estimated = round(arv_price_m2 * area, 2) if arv_price_m2 else None

        current_value = current.get("estimated_value")

        value_uplift = None
        value_uplift_pct = None
        if arv_estimated and current_value and current_value > 0:
            value_uplift = round(arv_estimated - current_value, 2)
            value_uplift_pct = round((value_uplift / current_value) * 100, 1)

        return {
            "current_value": current_value,
            "arv_estimated": arv_estimated,
            "value_uplift": value_uplift,
            "value_uplift_pct": value_uplift_pct,
            "arv_per_m2": arv_price_m2,
            "comparables_used": arv_stats.get("count", 0),
            "confidence": current.get("confidence_score", 0),
            "method": "comparables",
        }

    # ------------------------------------------------------------------
    # Estatisticas de zona
    # ------------------------------------------------------------------

    def get_zone_stats(
        self,
        district: str,
        municipality: Optional[str] = None,
        parish: Optional[str] = None,
        property_type: str = "apartamento",
    ) -> Dict[str, Any]:
        """Estatisticas de mercado para uma zona.

        Combina CASAFARI (listagens, precos) + INE (transaccoes, macro).
        Cache: 30 dias.
        """
        with get_session() as session:
            tenant_id = _ensure_tenant(session)

            # Verificar cache
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_CACHE_ZONE_STATS_DAYS)
            cached = session.execute(
                select(MarketZoneStats).where(
                    MarketZoneStats.district == district,
                    MarketZoneStats.municipality == municipality,
                    MarketZoneStats.property_type == property_type,
                    MarketZoneStats.fetched_at >= cutoff,
                )
            ).scalar_one_or_none()

            if cached:
                return self._zone_stats_to_dict(cached)

            # Buscar dados frescos
            comp_result = self.find_comparables(
                municipality=municipality or district,
                district=district,
                parish=parish,
                property_type=property_type,
                months_back=6,
                max_results=100,
            )

            stats = comp_result.get("stats", {})

            # Complementar com INE
            ine_price_m2 = None
            if self._ine and (municipality or district):
                ine_data = self._ine.get_median_price(municipality or district)
                if ine_data:
                    ine_price_m2 = ine_data.get("price_m2")

            # Determinar nivel
            zone_level = "district"
            if parish:
                zone_level = "parish"
            elif municipality:
                zone_level = "municipality"

            zone = MarketZoneStats(
                id=str(uuid4()),
                tenant_id=tenant_id,
                district=district,
                municipality=municipality,
                parish=parish,
                zone_level=zone_level,
                period=f"{datetime.now(tz=timezone.utc).year}-Q{(datetime.now().month - 1) // 3 + 1}",
                period_type="quarterly",
                avg_price_per_m2=stats.get("avg_price_m2"),
                median_price_per_m2=stats.get("median_price_m2") or ine_price_m2,
                min_price_per_m2=stats.get("min_price_m2"),
                max_price_per_m2=stats.get("max_price_m2"),
                total_listings=stats.get("count"),
                property_type=property_type,
                source="casafari" if self.casafari_available else "ine",
                expires_at=datetime.now(tz=timezone.utc) + timedelta(days=_CACHE_ZONE_STATS_DAYS),
            )
            session.add(zone)
            session.flush()

            return self._zone_stats_to_dict(zone)

    # ------------------------------------------------------------------
    # Alertas
    # ------------------------------------------------------------------

    def create_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria alerta de mercado.

        Se CASAFARI disponivel: cria feed na API para monitorizacao continua.
        """
        with get_session() as session:
            tenant_id = _ensure_tenant(session)

            alert = MarketAlert(
                id=str(uuid4()),
                tenant_id=tenant_id,
                alert_name=alert_data["alert_name"],
                alert_type=alert_data["alert_type"],
                districts=alert_data.get("districts", []),
                municipalities=alert_data.get("municipalities", []),
                property_types=alert_data.get("property_types", []),
                typologies=alert_data.get("typologies", []),
                price_min=alert_data.get("price_min"),
                price_max=alert_data.get("price_max"),
                area_min=alert_data.get("area_min"),
                area_max=alert_data.get("area_max"),
                price_per_m2_max=alert_data.get("price_per_m2_max"),
                max_price_vs_market_pct=alert_data.get("max_price_vs_market_pct"),
                notify_whatsapp=alert_data.get("notify_whatsapp", True),
                notify_email=alert_data.get("notify_email", False),
            )

            # Tentar criar feed CASAFARI
            if self.casafari_available:
                feed = self._create_casafari_feed(alert)
                if feed:
                    alert.casafari_feed_id = feed.get("id")

            session.add(alert)
            session.flush()

            logger.info(
                f"M2: alerta '{alert.alert_name}' criado (id={alert.id}, "
                f"casafari_feed={alert.casafari_feed_id})"
            )
            return self._alert_to_dict(alert)

    def _create_casafari_feed(self, alert: MarketAlert) -> Optional[Dict[str, Any]]:
        """Cria feed CASAFARI a partir de um MarketAlert."""
        # Resolver location_ids
        location_ids = []
        for name in (alert.municipalities or []) + (alert.districts or []):
            loc_id = self._casafari.resolve_location(name)
            if loc_id:
                location_ids.append(loc_id)

        if not location_ids:
            return None

        # Mapear tipos
        types = []
        for pt in alert.property_types or []:
            types.extend(CasafariClient.map_property_type(pt))

        filter_config: Dict[str, Any] = {
            "operation": "sale",
            "location_ids": location_ids,
            "statuses": ["active", "reserved"],
        }
        if types:
            filter_config["types"] = types
        if alert.price_min:
            filter_config["price_from"] = int(alert.price_min)
        if alert.price_max:
            filter_config["price_to"] = int(alert.price_max)
        if alert.area_min:
            filter_config["total_area_from"] = int(alert.area_min)
        if alert.area_max:
            filter_config["total_area_to"] = int(alert.area_max)

        return self._casafari.create_feed(
            name=alert.alert_name,
            filter_config=filter_config,
        )

    def check_alerts(self) -> List[Dict[str, Any]]:
        """Verifica alertas activos e retorna novos resultados.

        Para alertas com casafari_feed_id: GET /feeds/{id} com created_at_from.
        Para alertas sem feed: pesquisa ad-hoc.
        """
        new_results: List[Dict[str, Any]] = []

        with get_session() as session:
            alerts = session.execute(
                select(MarketAlert).where(MarketAlert.is_active.is_(True))
            ).scalars().all()

            for alert in alerts:
                try:
                    results = self._check_single_alert(session, alert)
                    if results:
                        alert.last_triggered_at = datetime.now(tz=timezone.utc)
                        alert.total_triggers += len(results)
                        new_results.extend(results)
                except Exception as e:
                    logger.error(f"M2: erro ao verificar alerta '{alert.alert_name}': {e}")

        logger.info(f"M2: {len(new_results)} novos resultados de {len(alerts)} alertas")
        return new_results

    def _check_single_alert(
        self, session: Session, alert: MarketAlert
    ) -> List[Dict[str, Any]]:
        """Verifica um unico alerta."""
        if not self.casafari_available:
            return []

        # Cursor: usar ultima verificacao ou ultimas 24h
        since = alert.last_triggered_at or (
            datetime.now(tz=timezone.utc) - timedelta(hours=24)
        )
        since_str = since.strftime("%Y-%m-%dT%H:%M:%S")

        if alert.casafari_feed_id:
            data = self._casafari.get_feed_alerts(
                feed_id=alert.casafari_feed_id,
                created_at_from=since_str,
                limit=50,
            )
        else:
            # Pesquisa ad-hoc
            location_ids = []
            for name in (alert.municipalities or []) + (alert.districts or []):
                loc_id = self._casafari.resolve_location(name)
                if loc_id:
                    location_ids.append(loc_id)

            if not location_ids:
                return []

            types = []
            for pt in alert.property_types or []:
                types.extend(CasafariClient.map_property_type(pt))

            data = self._casafari.search_listings(
                location_ids=location_ids,
                property_types=types or None,
                price_from=alert.price_min,
                price_to=alert.price_max,
                alert_date_from=since.strftime("%Y-%m-%d"),
                limit=50,
            )

        if not data:
            return []

        results = data.get("results", [])
        return [CasafariClient.parse_alert_to_comparable(r) for r in results]

    def list_alerts(self, is_active: Optional[bool] = True) -> List[Dict[str, Any]]:
        """Lista alertas."""
        with get_session() as session:
            stmt = select(MarketAlert)
            if is_active is not None:
                stmt = stmt.where(MarketAlert.is_active == is_active)
            stmt = stmt.order_by(MarketAlert.created_at.desc())

            alerts = session.execute(stmt).scalars().all()
            return [self._alert_to_dict(a) for a in alerts]

    def delete_alert(self, alert_id: str) -> bool:
        """Remove um alerta (e feed CASAFARI se existir)."""
        with get_session() as session:
            alert = session.get(MarketAlert, alert_id)
            if not alert:
                return False

            # Remover feed CASAFARI
            if alert.casafari_feed_id and self.casafari_available:
                self._casafari.delete_feed(alert.casafari_feed_id)

            session.delete(alert)
            logger.info(f"M2: alerta '{alert.alert_name}' removido")
            return True

    # ------------------------------------------------------------------
    # Enriquecimento M1 (oportunidades)
    # ------------------------------------------------------------------

    def enrich_opportunity(self, opportunity_id: int) -> Dict[str, Any]:
        """Enriquece uma oportunidade do M1 com dados de mercado.

        Returns:
            Dict com zone_avg_price_m2, discount_vs_market_pct, arv_estimated, etc.
        """
        from src.database.models import MarketData, Opportunity

        with get_session() as session:
            opp = session.get(Opportunity, opportunity_id)
            if not opp or not opp.is_opportunity:
                raise ValueError(f"Oportunidade {opportunity_id} nao encontrada")

            municipality = opp.municipality
            area_m2 = opp.area_m2 or 80.0
            price = opp.price_mentioned

            result: Dict[str, Any] = {
                "opportunity_id": opportunity_id,
                "zone_avg_price_m2": None,
                "zone_median_price_m2": None,
                "asking_price_m2": None,
                "discount_vs_market_pct": None,
                "arv_estimated": None,
                "comparables_found": 0,
                "source": "casafari" if self.casafari_available else "ine",
            }

            # Buscar comparaveis
            comp_result = self.find_comparables(
                municipality=municipality,
                district=opp.district,
                property_type=opp.property_type,
                bedrooms=opp.bedrooms,
                area_m2=area_m2,
                opportunity_id=opportunity_id,
            )

            stats = comp_result.get("stats", {})
            result["comparables_found"] = stats.get("count", 0)
            result["zone_avg_price_m2"] = stats.get("avg_price_m2")
            result["zone_median_price_m2"] = stats.get("median_price_m2")

            # Fallback INE
            if not result["zone_median_price_m2"] and self._ine and municipality:
                ine_data = self._ine.get_median_price(municipality)
                if ine_data:
                    result["zone_median_price_m2"] = ine_data.get("price_m2")
                    result["source"] = "ine"

            # Calcular preco/m2 e desconto
            if price and area_m2 > 0:
                result["asking_price_m2"] = round(price / area_m2, 2)

            median = result["zone_median_price_m2"]
            if result["asking_price_m2"] and median and median > 0:
                result["discount_vs_market_pct"] = round(
                    ((result["asking_price_m2"] - median) / median) * 100, 1
                )

            # ARV estimado (comparaveis renovados)
            if self.casafari_available and municipality:
                arv_result = self.find_comparables(
                    municipality=municipality,
                    property_type=opp.property_type,
                    bedrooms=opp.bedrooms,
                    area_m2=area_m2,
                    conditions=["renovado", "novo"],
                    max_results=10,
                )
                arv_stats = arv_result.get("stats", {})
                if arv_stats.get("median_price_m2"):
                    result["arv_estimated"] = round(
                        arv_stats["median_price_m2"] * area_m2, 2
                    )

            # Actualizar MarketData existente
            market_data = session.execute(
                select(MarketData).where(MarketData.opportunity_id == opportunity_id)
            ).scalar_one_or_none()

            if market_data:
                market_data.casafari_avg_price_m2 = result["zone_avg_price_m2"]
                market_data.casafari_median_price_m2 = result["zone_median_price_m2"]
                market_data.casafari_comparables_count = result["comparables_found"]
                if result["arv_estimated"]:
                    market_data.estimated_market_value = result["arv_estimated"]

            logger.info(
                f"M2: oportunidade {opportunity_id} enriquecida — "
                f"desconto={result['discount_vs_market_pct']}%, "
                f"comparaveis={result['comparables_found']}"
            )

            return result

    # ------------------------------------------------------------------
    # Integracao M3 (financeiro)
    # ------------------------------------------------------------------

    def get_arv_for_financial_model(self, deal_id: str) -> Optional[float]:
        """Retorna ARV estimado para o M3 usar nas projeccoes financeiras.

        Se nao existe avaliacao recente: faz uma nova.
        """
        with get_session() as session:
            # Verificar avaliacao recente
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_CACHE_VALUATION_DAYS)
            valuation = session.execute(
                select(PropertyValuation).where(
                    PropertyValuation.deal_id == deal_id,
                    PropertyValuation.valuated_at >= cutoff,
                )
            ).scalar_one_or_none()

            if valuation and valuation.estimated_value:
                return valuation.estimated_value

        # Criar nova avaliacao
        try:
            result = self.valuate_deal(deal_id)
            return result.get("estimated_value")
        except Exception as e:
            logger.error(f"M2: erro ao avaliar deal {deal_id} para M3: {e}")
            return None

    def get_comparables_for_pricing(self, deal_id: str) -> Dict[str, Any]:
        """Retorna dados de comparaveis formatados para M3/M7.

        Returns:
            Dict com avg_price_m2, median_price_m2, suggested_listing_price,
            price_range (low, mid, high).
        """
        comp_result = self.find_comparables_for_deal(deal_id)
        stats = comp_result.get("stats", {})

        with get_session() as session:
            deal = session.get(Deal, deal_id)
            prop = session.get(Property, deal.property_id) if deal else None
            area = (prop.gross_area_m2 or 80.0) if prop else 80.0

        median = stats.get("median_price_m2")
        suggested = round(median * area, 2) if median else None

        return {
            "avg_price_m2": stats.get("avg_price_m2"),
            "median_price_m2": median,
            "min_price_m2": stats.get("min_price_m2"),
            "max_price_m2": stats.get("max_price_m2"),
            "comparables_count": stats.get("count", 0),
            "suggested_listing_price": suggested,
            "price_range": {
                "low": round(stats["min_price_m2"] * area, 2) if stats.get("min_price_m2") else None,
                "mid": suggested,
                "high": round(stats["max_price_m2"] * area, 2) if stats.get("max_price_m2") else None,
            },
        }

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_market_overview(self) -> Dict[str, Any]:
        """Overview completo para dashboard."""
        with get_session() as session:
            zones = session.execute(
                select(func.count()).select_from(MarketZoneStats)
            ).scalar() or 0

            alerts = session.execute(
                select(func.count()).select_from(
                    select(MarketAlert).where(MarketAlert.is_active.is_(True)).subquery()
                )
            ).scalar() or 0

            valuations = session.execute(
                select(func.count()).select_from(PropertyValuation)
            ).scalar() or 0

            comparables = session.execute(
                select(func.count()).select_from(MarketComparable)
            ).scalar() or 0

            # Ultima avaliacao e media de confianca
            last_val = session.execute(
                select(PropertyValuation)
                .order_by(PropertyValuation.valuated_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            last_val_at = last_val.valuated_at.isoformat() if last_val and last_val.valuated_at else None

            avg_conf = session.execute(
                select(func.avg(PropertyValuation.confidence_score))
            ).scalar()

            # Verificar acesso real a pesquisa CASAFARI
            casafari_search_ok = False
            if self.casafari_available:
                casafari_search_ok = self._casafari.check_search_access()

            # Fontes de dados activas
            sources = []
            if self.casafari_available:
                sources.append("casafari")
            if self._ine:
                sources.append("ine")
            sources.append("bpstat")  # sempre disponivel (API publica)
            if hasattr(self, "_sir") and self._sir and self._sir.is_configured:
                sources.append("sir")

            sir_ok = hasattr(self, "_sir") and self._sir and self._sir.is_configured

            return {
                "zones_monitored": zones,
                "alerts_active": alerts,
                "valuations_total": valuations,
                "comparables_cached": comparables,
                "casafari_configured": self.casafari_available,
                "casafari_search_access": casafari_search_ok,
                "ine_available": self._ine is not None,
                "bpstat_available": True,
                "sir_available": sir_ok,
                "avm_method": "local_avm",
                "last_valuation_at": last_val_at,
                "avg_confidence_score": round(avg_conf, 1) if avg_conf else None,
                "data_sources": sources,
            }

    # ------------------------------------------------------------------
    # Serializers
    # ------------------------------------------------------------------

    @staticmethod
    def _valuation_to_dict(v: PropertyValuation) -> Dict[str, Any]:
        """Serializa PropertyValuation."""
        return {
            "id": v.id,
            "deal_id": v.deal_id,
            "estimated_value": v.estimated_value,
            "estimated_value_low": v.estimated_value_low,
            "estimated_value_high": v.estimated_value_high,
            "estimated_price_per_m2": v.estimated_price_per_m2,
            "confidence_score": v.confidence_score,
            "avg_price_per_m2_zone": v.avg_price_per_m2_zone,
            "median_price_per_m2_zone": v.median_price_per_m2_zone,
            "active_listings_zone": v.active_listings_zone,
            "price_trend_6m": v.price_trend_6m,
            "price_trend_12m": v.price_trend_12m,
            "comparables_count": v.comparables_count,
            "comparables_avg_price_m2": v.comparables_avg_price_m2,
            "source": v.source,
            "method": v.method,
            "valuated_at": v.valuated_at.isoformat() if v.valuated_at else None,
        }

    @staticmethod
    def _zone_stats_to_dict(z: MarketZoneStats) -> Dict[str, Any]:
        """Serializa MarketZoneStats."""
        return {
            "id": z.id,
            "district": z.district,
            "municipality": z.municipality,
            "parish": z.parish,
            "period": z.period,
            "avg_price_per_m2": z.avg_price_per_m2,
            "median_price_per_m2": z.median_price_per_m2,
            "min_price_per_m2": z.min_price_per_m2,
            "max_price_per_m2": z.max_price_per_m2,
            "total_listings": z.total_listings,
            "avg_days_on_market": z.avg_days_on_market,
            "price_variation_yoy": z.price_variation_yoy,
            "property_type": z.property_type,
            "source": z.source,
            "fetched_at": z.fetched_at.isoformat() if z.fetched_at else None,
        }

    @staticmethod
    def _alert_to_dict(a: MarketAlert) -> Dict[str, Any]:
        """Serializa MarketAlert."""
        return {
            "id": a.id,
            "alert_name": a.alert_name,
            "alert_type": a.alert_type,
            "districts": a.districts or [],
            "municipalities": a.municipalities or [],
            "property_types": a.property_types or [],
            "typologies": a.typologies or [],
            "price_min": a.price_min,
            "price_max": a.price_max,
            "area_min": a.area_min,
            "area_max": a.area_max,
            "is_active": a.is_active,
            "casafari_feed_id": a.casafari_feed_id,
            "last_triggered_at": a.last_triggered_at.isoformat() if a.last_triggered_at else None,
            "total_triggers": a.total_triggers,
            "notify_whatsapp": a.notify_whatsapp,
            "notify_email": a.notify_email,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
