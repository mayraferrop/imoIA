"""Cliente para a API do Casafari.

Busca comparaveis e estatisticas de mercado por localizacao e caracteristicas.

API: https://api.casafari.com/v1/
Auth: Token via header Authorization: Token <API_TOKEN>

Para obter o API Token:
  - Login em app.casafari.com > Settings > API > Generate Token
  - Guardar em .env como CASAFARI_API_TOKEN
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.config import get_settings

# Cache em memoria
_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 24 * 3600  # 24 horas


class CasafariClient:
    """Cliente para a API do Casafari (comparaveis e estatisticas de mercado).

    Usa a API REST em api.casafari.com/v1 com autenticacao por Token.
    """

    _BASE_URL = "https://api.casafari.com"

    # Mapeamento de tipos de imovel PT -> Casafari API
    _PROPERTY_TYPE_MAP = {
        "apartamento": "apartment",
        "moradia": "house",
        "terreno": "land",
        "loja": "retail",
        "escritorio": "office",
        "armazem": "warehouse",
        "predio": "building",
        "quinta": "farm",
    }

    def __init__(self) -> None:
        """Inicializa o cliente Casafari."""
        self._settings = get_settings()
        self._api_token = self._settings.casafari_api_token

    @property
    def is_configured(self) -> bool:
        """Verifica se o Casafari esta configurado."""
        return bool(self._api_token)

    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers com autenticacao."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Token {self._api_token}",
        }

    def search_comparables(
        self,
        municipality: str,
        property_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
        area_m2: Optional[float] = None,
        max_results: int = 20,
    ) -> Optional[Dict[str, Any]]:
        """Busca comparaveis no Casafari por localizacao e caracteristicas.

        Args:
            municipality: Municipio (ex: 'Lisboa', 'Cascais').
            property_type: Tipo de imovel ('apartamento', 'moradia', etc.).
            bedrooms: Numero de quartos.
            area_m2: Area em m2.
            max_results: Numero maximo de resultados.

        Returns:
            Dict com comparaveis, preco medio/m2, ou None.
        """
        if not self.is_configured:
            return None

        cache_key = f"casafari:comp:{municipality}:{property_type}:{bedrooms}:{area_m2}"
        cached = _cache.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < _CACHE_TTL:
            return cached["data"]

        # Construir filtros de pesquisa
        filters: Dict[str, Any] = {
            "country": "PT",
            "location": municipality,
            "transaction_type": "sale",
            "limit": max_results,
        }
        if property_type:
            mapped = self._PROPERTY_TYPE_MAP.get(
                property_type.lower(), property_type
            )
            filters["property_type"] = mapped
        if bedrooms is not None:
            filters["bedrooms"] = bedrooms
        if area_m2:
            filters["area_min"] = max(int(area_m2 * 0.7), 20)
            filters["area_max"] = int(area_m2 * 1.3)

        # Tentar endpoints conhecidos
        for endpoint in ["/v1/properties/search", "/v1/properties", "/v1/search"]:
            data = self._request("POST", endpoint, json_body=filters)
            if data is None:
                data = self._request("GET", endpoint, params=filters)
            if data and self._has_data(data):
                result = self._parse_comparables(data, municipality)
                if result and result.get("comparables_count", 0) > 0:
                    _cache[cache_key] = {"data": result, "timestamp": time.time()}
                    return result

        logger.info(f"Casafari: sem comparaveis para '{municipality}'")
        return None

    def get_market_stats(
        self,
        municipality: str,
        property_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Obtem estatisticas de mercado para uma localizacao."""
        if not self.is_configured:
            return None

        cache_key = f"casafari:stats:{municipality}:{property_type}"
        cached = _cache.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < _CACHE_TTL:
            return cached["data"]

        params: Dict[str, Any] = {
            "country": "PT",
            "location": municipality,
        }
        if property_type:
            mapped = self._PROPERTY_TYPE_MAP.get(
                property_type.lower(), property_type
            )
            params["property_type"] = mapped

        for endpoint in ["/v1/statistics", "/v1/market/stats"]:
            data = self._request("GET", endpoint, params=params)
            if data:
                result = self._parse_stats(data, municipality)
                if result:
                    _cache[cache_key] = {"data": result, "timestamp": time.time()}
                    return result

        logger.info(f"Casafari: sem estatisticas para '{municipality}'")
        return None

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Faz um pedido HTTP a API do Casafari."""
        url = f"{self._BASE_URL}{endpoint}"
        headers = self._get_headers()

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )
                if response.status_code == 401:
                    logger.warning("Casafari: token invalido ou expirado")
                    return None
                if response.status_code == 403:
                    logger.warning("Casafari: acesso negado (verificar permissoes do token)")
                    return None
                response.raise_for_status()
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    return response.json()
                return None
        except httpx.HTTPStatusError:
            return None
        except Exception as e:
            logger.debug(f"Casafari request falhou: {e}")
            return None

    def _has_data(self, data: Any) -> bool:
        """Verifica se a resposta contem dados."""
        if isinstance(data, dict):
            keys = {"results", "properties", "data", "items", "listings", "elements"}
            return bool(keys & set(data.keys()))
        return isinstance(data, list) and len(data) > 0

    def _parse_comparables(
        self, data: Any, municipality: str
    ) -> Dict[str, Any]:
        """Parseia a resposta de comparaveis."""
        properties: List[Any] = []
        if isinstance(data, dict):
            properties = (
                data.get("results")
                or data.get("properties")
                or data.get("data")
                or data.get("elements")
                or data.get("items")
                or []
            )
        elif isinstance(data, list):
            properties = data

        prices_m2: List[float] = []
        comparables: List[Dict[str, Any]] = []

        for prop in properties:
            if not isinstance(prop, dict):
                continue
            price = (
                prop.get("price")
                or prop.get("asking_price")
                or prop.get("valor")
            )
            area = (
                prop.get("area")
                or prop.get("useful_area")
                or prop.get("total_area")
                or prop.get("area_m2")
            )
            if price and area:
                try:
                    pf, af = float(price), float(area)
                    if af > 0:
                        pm2 = pf / af
                        prices_m2.append(pm2)
                        comparables.append({
                            "price": pf,
                            "area": af,
                            "price_m2": round(pm2, 2),
                            "bedrooms": prop.get("bedrooms"),
                            "property_type": prop.get("property_type") or prop.get("type"),
                            "location": prop.get("location") or prop.get("address", ""),
                        })
                except (ValueError, TypeError):
                    continue

        avg_m2 = round(sum(prices_m2) / len(prices_m2), 2) if prices_m2 else None
        sorted_prices = sorted(prices_m2)
        median_m2 = round(
            sorted_prices[len(sorted_prices) // 2], 2
        ) if sorted_prices else None

        return {
            "source": "casafari",
            "municipality": municipality,
            "comparables_count": len(comparables),
            "avg_price_m2": avg_m2,
            "median_price_m2": median_m2,
            "min_price_m2": round(min(prices_m2), 2) if prices_m2 else None,
            "max_price_m2": round(max(prices_m2), 2) if prices_m2 else None,
            "comparables": comparables[:10],
        }

    def _parse_stats(
        self, data: Dict[str, Any], municipality: str
    ) -> Optional[Dict[str, Any]]:
        """Parseia estatisticas de mercado."""
        if not data:
            return None
        avg = data.get("avg_price_m2") or data.get("average_price_per_sqm")
        median = data.get("median_price_m2") or data.get("median_price_per_sqm")
        if not avg and not median:
            return None
        return {
            "source": "casafari",
            "municipality": municipality,
            "avg_price_m2": float(avg) if avg else None,
            "median_price_m2": float(median) if median else None,
            "total_listings": data.get("total") or data.get("count"),
        }
