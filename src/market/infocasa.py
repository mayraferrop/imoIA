"""Cliente para o Infocasa.

Autentica com username/password (mesmo login do site) e busca
comparaveis e estatisticas de mercado por localizacao e caracteristicas.
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

# Sessao (guardada apos login)
_auth_token: Optional[str] = None
_auth_cookies: Optional[Dict[str, str]] = None


class InfocasaClient:
    """Cliente para o Infocasa (comparaveis e analise de mercado).

    Autentica com username/password, tentando varios endpoints de login.
    """

    _LOGIN_ENDPOINTS = [
        "/api/auth/login",
        "/api/v1/auth/login",
        "/auth/login",
        "/api/login",
        "/login",
        "/api/auth/signin",
        "/rest-auth/login/",
        "/api-token-auth/",
        "/api/v1/login",
    ]

    _DATA_ENDPOINTS_SEARCH = [
        "/api/properties/search",
        "/api/v1/properties/search",
        "/api/v1/properties",
        "/api/properties",
        "/api/search",
        "/api/v1/search",
    ]

    _DATA_ENDPOINTS_STATS = [
        "/api/statistics",
        "/api/v1/statistics",
        "/api/market/stats",
        "/api/v1/market/stats",
    ]

    def __init__(self) -> None:
        """Inicializa o cliente Infocasa."""
        self._settings = get_settings()
        self._username = self._settings.infocasa_username
        self._password = self._settings.infocasa_password
        self._base_url = self._settings.infocasa_base_url.rstrip("/")
        self._token: Optional[str] = _auth_token
        self._cookies: Optional[Dict[str, str]] = _auth_cookies

    @property
    def is_configured(self) -> bool:
        """Verifica se o Infocasa esta configurado."""
        return bool(self._username and self._password)

    def _authenticate(self) -> bool:
        """Autentica no Infocasa com username/password."""
        global _auth_token, _auth_cookies

        if self._token:
            return True

        if not self.is_configured:
            return False

        for endpoint in self._LOGIN_ENDPOINTS:
            try:
                url = f"{self._base_url}{endpoint}"
                with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                    response = client.post(
                        url,
                        json={
                            "username": self._username,
                            "password": self._password,
                            "email": self._username,
                        },
                        headers={"Content-Type": "application/json"},
                    )
                    if response.status_code in (200, 201):
                        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                        token = (
                            data.get("token")
                            or data.get("access_token")
                            or data.get("key")
                            or data.get("session_id")
                            or data.get("auth_token")
                        )
                        if token:
                            self._token = token
                            _auth_token = token
                            logger.info(f"Infocasa autenticado via {endpoint}")
                            return True

                        if response.cookies:
                            self._cookies = dict(response.cookies)
                            _auth_cookies = self._cookies
                            logger.info(f"Infocasa autenticado via cookies em {endpoint}")
                            return True
            except Exception:
                continue

        # Fallback: Basic Auth em cada pedido
        logger.warning("Infocasa: login nao funcionou, a usar Basic Auth")
        return False

    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers com autenticacao."""
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Token {self._token}"
        elif self._username and self._password:
            import base64
            creds = base64.b64encode(
                f"{self._username}:{self._password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {creds}"
        return headers

    def search_comparables(
        self,
        municipality: str,
        property_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
        area_m2: Optional[float] = None,
        max_results: int = 20,
    ) -> Optional[Dict[str, Any]]:
        """Busca comparaveis no Infocasa por localizacao e caracteristicas.

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

        cache_key = f"infocasa:comp:{municipality}:{property_type}:{bedrooms}:{area_m2}"
        cached = _cache.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < _CACHE_TTL:
            return cached["data"]

        self._authenticate()

        filters: Dict[str, Any] = {
            "location": municipality,
            "concelho": municipality,
            "transaction_type": "sale",
            "limit": max_results,
        }
        if property_type:
            pt_map = {
                "apartamento": "apartment",
                "moradia": "house",
                "terreno": "land",
                "loja": "retail",
                "escritorio": "office",
            }
            filters["property_type"] = pt_map.get(property_type, property_type)
            filters["tipo"] = property_type
        if bedrooms is not None:
            filters["bedrooms"] = bedrooms
            filters["tipologia"] = f"T{bedrooms}"
        if area_m2:
            filters["area_min"] = max(area_m2 * 0.7, 20)
            filters["area_max"] = area_m2 * 1.3

        for endpoint in self._DATA_ENDPOINTS_SEARCH:
            try:
                data = self._request("POST", endpoint, json_body=filters)
                if data is None:
                    data = self._request("GET", endpoint, params=filters)
                if data and self._has_data(data):
                    result = self._parse_comparables(data, municipality)
                    if result and result.get("comparables_count", 0) > 0:
                        _cache[cache_key] = {"data": result, "timestamp": time.time()}
                        return result
            except Exception as e:
                logger.debug(f"Infocasa endpoint {endpoint} falhou: {e}")
                continue

        logger.info(f"Infocasa: sem comparaveis para '{municipality}'")
        return None

    def get_market_stats(
        self,
        municipality: str,
        property_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Obtem estatisticas de mercado para uma localizacao."""
        if not self.is_configured:
            return None

        cache_key = f"infocasa:stats:{municipality}:{property_type}"
        cached = _cache.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < _CACHE_TTL:
            return cached["data"]

        self._authenticate()

        params: Dict[str, Any] = {
            "location": municipality,
            "concelho": municipality,
        }
        if property_type:
            params["property_type"] = property_type

        for endpoint in self._DATA_ENDPOINTS_STATS:
            try:
                data = self._request("GET", endpoint, params=params)
                if data:
                    result = self._parse_stats(data, municipality)
                    if result:
                        _cache[cache_key] = {"data": result, "timestamp": time.time()}
                        return result
            except Exception as e:
                logger.debug(f"Infocasa stats {endpoint} falhou: {e}")
                continue

        logger.info(f"Infocasa: sem estatisticas para '{municipality}'")
        return None

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Faz um pedido HTTP ao Infocasa."""
        url = f"{self._base_url}{endpoint}"
        headers = self._get_headers()

        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    cookies=self._cookies,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self._token = None
                global _auth_token
                _auth_token = None
            return None
        except Exception:
            return None

    def _has_data(self, data: Any) -> bool:
        """Verifica se a resposta contem dados."""
        if isinstance(data, dict):
            keys = {"results", "properties", "data", "items", "listings"}
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
                or prop.get("preco")
                or prop.get("valor")
            )
            area = (
                prop.get("area")
                or prop.get("useful_area")
                or prop.get("area_m2")
                or prop.get("area_util")
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
                            "bedrooms": prop.get("bedrooms") or prop.get("tipologia"),
                            "property_type": prop.get("property_type") or prop.get("tipo"),
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
            "source": "infocasa",
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
        avg = (
            data.get("avg_price_m2")
            or data.get("average_price_per_sqm")
            or data.get("preco_medio_m2")
        )
        median = (
            data.get("median_price_m2")
            or data.get("median_price_per_sqm")
            or data.get("preco_mediano_m2")
        )
        if not avg and not median:
            return None
        return {
            "source": "infocasa",
            "municipality": municipality,
            "avg_price_m2": float(avg) if avg else None,
            "median_price_m2": float(median) if median else None,
            "total_listings": data.get("total") or data.get("count"),
        }


def clear_cache() -> None:
    """Limpa o cache de dados do Infocasa."""
    global _auth_token, _auth_cookies
    _cache.clear()
    _auth_token = None
    _auth_cookies = None
    logger.debug("Cache do Infocasa limpo")
