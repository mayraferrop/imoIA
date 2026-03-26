"""Cliente para a CASAFARI API v1.

Base URL: https://api.casafari.com/v1
Autenticacao: Token API (preferido) ou JWT Bearer via POST /login.

Endpoints principais:
- POST /v1/references/locations — resolver nomes para location_id
- POST /v1/listing-alerts/search — pesquisa ad-hoc de listagens
- POST /v1/listing-alerts/feeds — criar/gerir feeds de alertas
- GET  /v1/properties/search/{property_id} — detalhe completo
- POST /v1/valuation/comparables-prices — AVM nativo CASAFARI
- POST /v1/comparables/search — comparaveis dedicados
- GET  /v1/references/types, conditions, features — referencias
- GET  /v1/references/agents, agencies, sources — referencias
- POST /v1/references/zipcode-boundary — boundaries de codigo postal
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

from src.config import get_settings

# Cache de localizacoes: nome_lower -> location_id
_location_cache: Dict[str, int] = {}
_LOCATION_CACHE_TTL = 7 * 24 * 3600  # 7 dias
_location_cache_ts: float = 0

# Cache do JWT token
_jwt_token: Optional[str] = None
_jwt_expires_at: float = 0


class CasafariClient:
    """Cliente Python para a CASAFARI API v1.

    Usa autenticacao JWT (username/password) ou API Token.
    Suporta pesquisa de listagens, detalhe de propriedades,
    gestao de feeds de alertas e resolucao de localizacoes.
    """

    _BASE_URL = "https://api.casafari.com"

    # Mapeamento tipos PT -> CASAFARI
    PROPERTY_TYPE_MAP: Dict[str, List[str]] = {
        "apartamento": ["apartment", "studio", "duplex", "penthouse"],
        "moradia": ["house", "villa", "townhouse", "chalet", "bungalow"],
        "terreno": ["plot", "urban_plot", "rural_plot"],
        "predio": ["apartment_building", "mix_use_building"],
        "loja": ["retail", "restaurant"],
        "escritorio": ["office"],
        "armazem": ["warehouse", "industrial"],
        "quinta": ["country_house", "country_estate"],
        "hotel": ["hotel"],
        "garagem": ["garage", "parking"],
    }

    # Mapeamento condicao PT -> CASAFARI
    CONDITION_MAP: Dict[str, str] = {
        "novo": "new",
        "renovado": "very-good",
        "usado": "used",
        "para_renovar": "used",
        "ruina": "ruin",
    }

    def __init__(self) -> None:
        """Inicializa o cliente CASAFARI."""
        self._settings = get_settings()
        self._username = self._settings.casafari_username
        self._password = self._settings.casafari_password
        self._api_token = self._settings.casafari_api_token
        self._base_url = self._settings.casafari_base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        """Verifica se as credenciais CASAFARI estao configuradas."""
        return bool(self._api_token) or bool(self._username and self._password)

    # ------------------------------------------------------------------
    # Autenticacao
    # ------------------------------------------------------------------

    def check_search_access(self) -> bool:
        """Verifica se a conta tem acesso ao endpoint de pesquisa.

        Faz uma pesquisa minima (limit=1) para verificar se retorna 402.
        """
        if not self.is_configured:
            return False

        data = self._request(
            "POST",
            "/v1/listing-alerts/search",
            params={"limit": 1},
            json_body={"operation": "sale", "location_ids": [1600]},  # Lisboa
        )
        return data is not None

    def _get_auth_headers(self) -> Dict[str, str]:
        """Retorna headers com autenticacao (JWT ou API Token)."""
        headers = {"Content-Type": "application/json"}

        # Preferir API Token (mais simples)
        if self._api_token:
            headers["Authorization"] = f"Token {self._api_token}"
            return headers

        # Fallback: JWT via login
        token = self._get_jwt_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _get_jwt_token(self) -> Optional[str]:
        """Obtem JWT token, com refresh automatico."""
        global _jwt_token, _jwt_expires_at

        # Token ainda valido (com margem de 5 min)
        if _jwt_token and time.time() < (_jwt_expires_at - 300):
            return _jwt_token

        # Tentar refresh primeiro
        if _jwt_token:
            refreshed = self._refresh_token()
            if refreshed:
                return _jwt_token

        # Login completo
        return self._login()

    def _login(self) -> Optional[str]:
        """Autentica via POST /login e obtem JWT."""
        global _jwt_token, _jwt_expires_at

        if not self._username or not self._password:
            return None

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{self._base_url}/login",
                    json={
                        "email": self._username,
                        "password": self._password,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                _jwt_token = data.get("access_token") or data.get("access") or data.get("token")
                # Assumir validade de 1 hora se nao especificado
                _jwt_expires_at = time.time() + 3600
                logger.info("CASAFARI: login JWT bem sucedido")
                return _jwt_token

        except Exception as e:
            logger.error(f"CASAFARI login falhou: {e}")
            _jwt_token = None
            return None

    def _refresh_token(self) -> bool:
        """Renova o JWT via GET /refresh-token."""
        global _jwt_token, _jwt_expires_at

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{self._base_url}/refresh-token",
                    headers={"Authorization": f"Bearer {_jwt_token}"},
                )
                resp.raise_for_status()
                data = resp.json()

                _jwt_token = data.get("access_token") or data.get("access") or data.get("token") or _jwt_token
                _jwt_expires_at = time.time() + 3600
                logger.debug("CASAFARI: token refreshed")
                return True

        except Exception as e:
            logger.debug(f"CASAFARI refresh falhou: {e}")
            return False

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        """Faz pedido HTTP autenticado a API CASAFARI."""
        url = f"{self._base_url}{path}"
        headers = self._get_auth_headers()

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )

                if resp.status_code == 401:
                    logger.warning("CASAFARI: 401 — credenciais invalidas ou expiradas")
                    # Tentar re-login e retry uma vez
                    global _jwt_token
                    _jwt_token = None
                    token = self._get_jwt_token()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        resp = client.request(
                            method=method,
                            url=url,
                            headers=headers,
                            params=params,
                            json=json_body,
                        )

                if resp.status_code == 402:
                    logger.warning(
                        "CASAFARI: 402 — plano sem acesso a este endpoint. "
                        "Verifique a subscrição em app.casafari.com."
                    )
                    return None
                if resp.status_code == 403:
                    logger.warning("CASAFARI: 403 — sem permissao")
                    return None
                if resp.status_code == 404:
                    return None

                resp.raise_for_status()

                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    return resp.json()
                return None

        except httpx.HTTPStatusError as e:
            logger.warning(f"CASAFARI HTTP {e.response.status_code}: {path}")
            return None
        except Exception as e:
            logger.debug(f"CASAFARI request falhou ({path}): {e}")
            return None

    # ------------------------------------------------------------------
    # References: Localizacoes
    # ------------------------------------------------------------------

    def resolve_location(self, name: str) -> Optional[int]:
        """Resolve nome de localizacao para location_id CASAFARI.

        Args:
            name: Nome da localizacao (ex: 'Lisboa', 'Cascais', 'Almada').

        Returns:
            location_id ou None.
        """
        global _location_cache, _location_cache_ts

        key = name.strip().lower()

        # Cache hit
        if key in _location_cache and (time.time() - _location_cache_ts) < _LOCATION_CACHE_TTL:
            return _location_cache[key]

        data = self._request("POST", "/v1/references/locations", json_body={"name": name})
        if not data:
            return None

        locations = data.get("locations", [])
        if isinstance(data, list):
            locations = data

        if not locations:
            logger.info(f"CASAFARI: localizacao '{name}' nao encontrada")
            return None

        # Procurar melhor match: preferir Concelho, depois Freguesia
        best: Optional[Dict[str, Any]] = None
        for loc in locations:
            level = (loc.get("administrative_level") or "").lower()
            if "concelho" in level:
                best = loc
                break
            if "freguesia" in level and best is None:
                best = loc
            if best is None:
                best = loc

        if best:
            loc_id = best.get("location_id")
            if loc_id:
                _location_cache[key] = loc_id
                _location_cache_ts = time.time()
                logger.debug(
                    f"CASAFARI: '{name}' → location_id={loc_id} "
                    f"({best.get('name')}, {best.get('administrative_level')})"
                )
                return loc_id

        return None

    def resolve_location_by_coordinates(
        self, latitude: float, longitude: float
    ) -> Optional[Dict[str, Any]]:
        """Resolve coordenadas para localizacao CASAFARI.

        Returns:
            Dict com location_id, name, administrative_level, locations_structure.
        """
        data = self._request(
            "GET",
            "/v1/references/locations/by-coordinates",
            params={"latitude": latitude, "longitude": longitude},
        )
        return data

    # ------------------------------------------------------------------
    # References: Tipos, condicoes, features
    # ------------------------------------------------------------------

    def get_property_types(self) -> Optional[List[Dict[str, Any]]]:
        """Retorna lista de tipos de imovel CASAFARI."""
        return self._request("GET", "/v1/references/types")

    def get_conditions(self) -> Optional[List[str]]:
        """Retorna lista de condicoes possiveis."""
        data = self._request("GET", "/v1/references/conditions")
        if data and "conditions" in data:
            return data["conditions"]
        return data

    def get_features(self) -> Optional[List[Dict[str, Any]]]:
        """Retorna lista de features possiveis."""
        return self._request("GET", "/v1/references/features")

    def get_sources(self, location_id: int) -> Optional[Dict[str, Any]]:
        """Retorna fontes/dominios disponiveis para uma localizacao.

        Args:
            location_id: ID da localizacao CASAFARI.

        Returns:
            Dict com lista de sources.
        """
        return self._request(
            "GET", "/v1/references/sources", params={"locationId": location_id}
        )

    def search_agencies(self, name: str) -> Optional[Dict[str, Any]]:
        """Pesquisa agencias imobiliarias por nome.

        Args:
            name: Nome da agencia (ex: 'RE/MAX', 'Century 21').

        Returns:
            Dict com lista de agencias encontradas.
        """
        return self._request(
            "GET", "/v1/references/agencies", params={"name": name}
        )

    def search_agents(self, name: str) -> Optional[Dict[str, Any]]:
        """Pesquisa agentes imobiliarios por nome.

        Args:
            name: Nome do agente.

        Returns:
            Dict com lista de agentes encontrados.
        """
        return self._request(
            "GET", "/v1/references/agents", params={"name": name}
        )

    def get_zipcode_boundary(
        self, zip_code: str
    ) -> Optional[Dict[str, Any]]:
        """Obtem boundary (poligono) de um codigo postal.

        Args:
            zip_code: Codigo postal (ex: '1000-001').

        Returns:
            Dict com geometria do boundary.
        """
        return self._request(
            "POST",
            "/v1/references/zipcode-boundary",
            json_body={"zip_code": zip_code},
        )

    # ------------------------------------------------------------------
    # Listing Alerts: Pesquisa ad-hoc
    # ------------------------------------------------------------------

    def search_listings(
        self,
        location_ids: Optional[List[int]] = None,
        custom_locations: Optional[List[List[Dict[str, float]]]] = None,
        property_types: Optional[List[str]] = None,
        operation: str = "sale",
        price_from: Optional[float] = None,
        price_to: Optional[float] = None,
        price_per_sqm_from: Optional[int] = None,
        price_per_sqm_to: Optional[int] = None,
        bedrooms_from: Optional[int] = None,
        bedrooms_to: Optional[int] = None,
        bathrooms_from: Optional[int] = None,
        bathrooms_to: Optional[int] = None,
        total_area_from: Optional[float] = None,
        total_area_to: Optional[float] = None,
        plot_area_from: Optional[int] = None,
        plot_area_to: Optional[int] = None,
        construction_year_from: Optional[int] = None,
        construction_year_to: Optional[int] = None,
        conditions: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        alert_subtypes: Optional[List[str]] = None,
        alert_date_from: Optional[str] = None,
        alert_date_to: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        floors: Optional[List[str]] = None,
        views: Optional[List[str]] = None,
        directions: Optional[List[str]] = None,
        characteristics: Optional[List[str]] = None,
        private: Optional[bool] = None,
        auction: Optional[bool] = None,
        bank: Optional[bool] = None,
        new_development: Optional[bool] = None,
        with_agencies: Optional[List[str]] = None,
        without_agencies: Optional[List[str]] = None,
        listing_agents: Optional[List[str]] = None,
        exclusive: Optional[bool] = None,
        ref_numbers: Optional[List[str]] = None,
        has_phone: Optional[bool] = None,
        has_email: Optional[bool] = None,
        has_agency_name: Optional[bool] = None,
        property_ids: Optional[List[int]] = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str = "-alert_date",
    ) -> Optional[Dict[str, Any]]:
        """Pesquisa ad-hoc de listagens via POST /v1/listing-alerts/search.

        Este e o endpoint principal para buscar comparaveis e alertas.
        Suporta todos os filtros da API CASAFARI v1.

        Args:
            location_ids: IDs de localizacao (max 100).
            custom_locations: Poligonos de coordenadas (max 4).
            property_types: Tipos CASAFARI (apartment, house, etc.).
            operation: 'sale' ou 'rent'.
            price_from/price_to: Intervalo de preco.
            price_per_sqm_from/to: Intervalo de preco/m2.
            bedrooms_from/to: Intervalo de quartos.
            bathrooms_from/to: Intervalo de casas de banho.
            total_area_from/to: Intervalo de area total.
            plot_area_from/to: Intervalo de area de terreno.
            construction_year_from/to: Intervalo de ano de construcao.
            conditions: Condicoes (used, new, very-good, ruin, other).
            statuses: Estados (active, reserved, hold, sold, rented).
            alert_subtypes: Tipos (new, price_up, price_down, reserved, delisted, sold).
            alert_date_from/to: Intervalo de data do alerta (YYYY-MM-DD).
            created_at_from/to: Intervalo de data de criacao (YYYY-MM-DDTHH:mm:ss).
            floors: Andares (no_floor, ground, middle, top).
            views: Vistas (water, landscape, city, golf, park).
            directions: Orientacao (north, south, east, west).
            characteristics: Caracteristicas (balcony, elevator, garage, etc.).
            private/auction/bank/new_development: Filtros booleanos.
            with_agencies/without_agencies: Filtrar por agencias.
            listing_agents: Filtrar por agentes.
            exclusive: Apenas exclusivos.
            ref_numbers: Filtrar por referencia.
            has_phone/has_email/has_agency_name: Filtros de contacto.
            property_ids: IDs de propriedades especificas (max 100).
            limit: Resultados por pagina (max 100).
            offset: Offset para paginacao.
            order_by: Ordenacao (-alert_date, alert_date, -created_at, etc.).

        Returns:
            Dict com 'count', 'next', 'results' (lista de alertas/listagens).
        """
        body: Dict[str, Any] = {"operation": operation}

        # Apenas incluir campos com valores nao-nulos e listas nao-vazias.
        # A API CASAFARI rejeita (400) campos com listas vazias ou None.
        if location_ids:
            body["location_ids"] = location_ids
        if custom_locations:
            body["custom_locations"] = custom_locations
        if property_types:
            body["types"] = property_types
        if price_from is not None:
            body["price_from"] = int(price_from)
        if price_to is not None:
            body["price_to"] = int(price_to)
        if price_per_sqm_from is not None:
            body["price_per_sqm_from"] = price_per_sqm_from
        if price_per_sqm_to is not None:
            body["price_per_sqm_to"] = price_per_sqm_to
        if bedrooms_from is not None:
            body["bedrooms_from"] = bedrooms_from
        if bedrooms_to is not None:
            body["bedrooms_to"] = bedrooms_to
        if bathrooms_from is not None:
            body["bathrooms_from"] = bathrooms_from
        if bathrooms_to is not None:
            body["bathrooms_to"] = bathrooms_to
        if total_area_from is not None:
            body["total_area_from"] = int(total_area_from)
        if total_area_to is not None:
            body["total_area_to"] = int(total_area_to)
        if plot_area_from is not None:
            body["plot_area_from"] = plot_area_from
        if plot_area_to is not None:
            body["plot_area_to"] = plot_area_to
        if construction_year_from is not None:
            body["construction_year_from"] = construction_year_from
        if construction_year_to is not None:
            body["construction_year_to"] = construction_year_to
        if conditions:
            body["conditions"] = conditions
        if statuses:
            body["statuses"] = statuses
        if alert_subtypes:
            body["alert_subtypes"] = alert_subtypes
        if alert_date_from:
            body["alert_date_from"] = alert_date_from
        if alert_date_to:
            body["alert_date_to"] = alert_date_to
        if created_at_from:
            body["created_at_from"] = created_at_from
        if created_at_to:
            body["created_at_to"] = created_at_to
        if floors:
            body["floors"] = floors
        if views:
            body["views"] = views
        if directions:
            body["directions"] = directions
        if characteristics:
            body["characteristics"] = characteristics
        if private is not None:
            body["private"] = private
        if auction is not None:
            body["auction"] = auction
        if bank is not None:
            body["bank"] = bank
        if new_development is not None:
            body["new_development"] = new_development
        if with_agencies:
            body["with_agencies"] = with_agencies
        if without_agencies:
            body["without_agencies"] = without_agencies
        if listing_agents:
            body["listing_agents"] = listing_agents
        if exclusive is not None:
            body["exclusive"] = exclusive
        if ref_numbers:
            body["ref_numbers"] = ref_numbers
        if has_phone is not None:
            body["has_phone"] = has_phone
        if has_email is not None:
            body["has_email"] = has_email
        if has_agency_name is not None:
            body["has_agency_name"] = has_agency_name
        if property_ids:
            body["property_ids"] = property_ids

        params: Dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": offset,
            "order_by": order_by,
        }

        data = self._request(
            "POST",
            "/v1/listing-alerts/search",
            params=params,
            json_body=body,
        )
        return data

    # ------------------------------------------------------------------
    # Listing Alerts: Feeds (monitorizacao continua)
    # ------------------------------------------------------------------

    def list_feeds(self) -> Optional[List[Dict[str, Any]]]:
        """Lista todos os feeds de alertas do utilizador."""
        return self._request("GET", "/v1/listing-alerts/feeds")

    def create_feed(
        self,
        name: str,
        filter_config: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Cria um feed de alertas.

        Args:
            name: Nome do feed (ex: 'Apartamentos Lisboa').
            filter_config: Filtros (operation, types, location_ids, price_from, etc.).

        Returns:
            Dict com id, name, filter do feed criado.
        """
        body = {"name": name, "filter": filter_config}
        return self._request("POST", "/v1/listing-alerts/feeds", json_body=body)

    def get_feed_alerts(
        self,
        feed_id: int,
        limit: int = 50,
        offset: int = 0,
        alert_date_from: Optional[str] = None,
        alert_date_to: Optional[str] = None,
        created_at_from: Optional[str] = None,
        order_by: str = "-alert_date",
    ) -> Optional[Dict[str, Any]]:
        """Obtem alertas de um feed.

        Args:
            feed_id: ID do feed.
            limit: Resultados por pagina.
            offset: Offset para paginacao.
            alert_date_from/to: Filtro por data do alerta.
            created_at_from: Filtro por data de criacao (para sync incremental).
            order_by: Ordenacao.

        Returns:
            Dict com 'count', 'next', 'results'.
        """
        params: Dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": offset,
            "order_by": order_by,
        }
        if alert_date_from:
            params["alert_date_from"] = alert_date_from
        if alert_date_to:
            params["alert_date_to"] = alert_date_to
        if created_at_from:
            params["created_at_from"] = created_at_from

        return self._request("GET", f"/v1/listing-alerts/feeds/{feed_id}", params=params)

    def update_feed(
        self,
        feed_id: int,
        name: Optional[str] = None,
        filter_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Atualiza um feed de alertas existente.

        Args:
            feed_id: ID do feed.
            name: Novo nome (opcional).
            filter_config: Novos filtros (opcional).

        Returns:
            Dict com feed atualizado ou None.
        """
        body: Dict[str, Any] = {}
        if name:
            body["name"] = name
        if filter_config:
            body["filter"] = filter_config
        return self._request(
            "PUT", f"/v1/listing-alerts/feeds/{feed_id}/update", json_body=body
        )

    def delete_feed(self, feed_id: int) -> bool:
        """Remove um feed de alertas."""
        data = self._request("DELETE", f"/v1/listing-alerts/feeds/{feed_id}")
        if data and data.get("success"):
            return True
        return data is not None

    # ------------------------------------------------------------------
    # Properties: Detalhe completo e matching
    # ------------------------------------------------------------------

    def match_properties_by_listings(
        self, listing_ids: List[int]
    ) -> Optional[Dict[str, Any]]:
        """Mapeia listing IDs para property IDs.

        Args:
            listing_ids: Lista de listing_id.

        Returns:
            Dict com mapeamento listing_id → property_id.
        """
        return self._request(
            "POST",
            "/v1/properties/match-by-listings",
            json_body={"listing_ids": listing_ids},
        )

    def get_property_detail(self, property_id: int) -> Optional[Dict[str, Any]]:
        """Obtem detalhe completo de uma propriedade CASAFARI.

        Inclui:
        - Dados base (tipo, area, quartos, coordenadas)
        - Todas as listagens de todas as fontes
        - Historico de precos (sale_price_history, rent_price_history)
        - Historico de estado (sale_status_history, rent_status_history)
        - Tempo no mercado (sale_time_on_market)
        - Fotos e descricao
        - gross_yield (se disponivel)

        Args:
            property_id: CASAFARI property_id (inteiro).

        Returns:
            Dict completo da propriedade ou None.
        """
        return self._request("GET", f"/v1/properties/search/{property_id}")

    # ------------------------------------------------------------------
    # Valuation: AVM nativo CASAFARI
    # ------------------------------------------------------------------

    def get_comparables_prices(
        self,
        operation: str = "sale",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        address: Optional[str] = None,
        distance_km: float = 5.0,
        comparables_count: int = 20,
        comparables_types: Optional[List[str]] = None,
        condition: Optional[str] = None,
        bedrooms: Optional[int] = None,
        bathrooms: Optional[int] = None,
        total_area: Optional[int] = None,
        plot_area: Optional[int] = None,
        construction_year: Optional[int] = None,
        floors: Optional[List[str]] = None,
        views: Optional[List[str]] = None,
        directions: Optional[List[str]] = None,
        characteristics: Optional[Dict[str, List[str]]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        sold_or_rented_after: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """AVM nativo CASAFARI via POST /v1/valuation/comparables-prices.

        Estima preco com base em comparaveis vendidos/arrendados na zona.

        Args:
            operation: 'sale' ou 'rent'.
            latitude/longitude: Coordenadas do imovel alvo.
            address: Morada do imovel alvo.
            distance_km: Raio de pesquisa (0.05-50 km, default 5).
            comparables_count: Numero de comparaveis (1-50).
            comparables_types: Tipos de imovel para comparar.
            condition: Condicao (used, new, very-good, ruin, other).
            bedrooms/bathrooms: Filtros.
            total_area/plot_area: Area em m2.
            construction_year: Ano de construcao.
            floors/views/directions: Filtros de caracteristicas.
            characteristics: Dict com must_have, nice_to_have, exclude.
            min_price/max_price: Intervalo de preco.
            sold_or_rented_after: Data minima (YYYY-MM-DD), default 9 meses.

        Returns:
            Dict com estimativa de preco e comparaveis usados.
        """
        body: Dict[str, Any] = {
            "operation": operation,
            "comparables_count": min(comparables_count, 50),
        }

        # Localização via circle boundary
        if latitude is not None and longitude is not None:
            body["location_boundary"] = {
                "circle": {
                    "target_point": {
                        "coordinates": {
                            "latitude": latitude,
                            "longitude": longitude,
                        },
                    },
                    "distance": distance_km,
                },
            }
            if address:
                body["location_boundary"]["circle"]["target_point"]["address"] = address

        if comparables_types:
            body["comparables_types"] = comparables_types
        if condition:
            body["condition"] = condition
        if bedrooms is not None:
            body["bedrooms"] = bedrooms
        if bathrooms is not None:
            body["bathrooms"] = bathrooms
        if total_area is not None:
            body["total_area"] = total_area
        if plot_area is not None:
            body["plot_area"] = plot_area
        if construction_year is not None:
            body["construction_year"] = construction_year
        if floors:
            body["floors"] = floors
        if views:
            body["views"] = views
        if directions:
            body["directions"] = directions
        if characteristics:
            body["characteristics"] = characteristics
        if min_price is not None:
            body["min_price"] = min_price
        if max_price is not None:
            body["max_price"] = max_price
        if sold_or_rented_after:
            body["sold_or_rented_after"] = sold_or_rented_after

        return self._request(
            "POST",
            "/v1/valuation/comparables-prices",
            json_body=body,
            timeout=60.0,
        )

    # ------------------------------------------------------------------
    # Comparables: Pesquisa dedicada
    # ------------------------------------------------------------------

    def search_comparables(
        self,
        operation: str = "sale",
        location_ids: Optional[List[int]] = None,
        property_types: Optional[List[str]] = None,
        conditions: Optional[List[str]] = None,
        price_from: Optional[int] = None,
        price_to: Optional[int] = None,
        bedrooms_from: Optional[int] = None,
        bedrooms_to: Optional[int] = None,
        total_area_from: Optional[int] = None,
        total_area_to: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Pesquisa de comparaveis via POST /v1/comparables/search.

        Endpoint dedicado para comparaveis (separado de listing-alerts).

        Args:
            operation: 'sale' ou 'rent'.
            location_ids: IDs de localizacao CASAFARI.
            property_types: Tipos de imovel.
            conditions: Condicoes.
            price_from/price_to: Intervalo de preco.
            bedrooms_from/bedrooms_to: Intervalo de quartos.
            total_area_from/total_area_to: Intervalo de area.
            limit/offset: Paginacao.

        Returns:
            Dict com resultados de comparaveis.
        """
        body: Dict[str, Any] = {"operation": operation}

        if location_ids:
            body["location_ids"] = location_ids
        if property_types:
            body["types"] = property_types
        if conditions:
            body["conditions"] = conditions
        if price_from is not None:
            body["price_from"] = price_from
        if price_to is not None:
            body["price_to"] = price_to
        if bedrooms_from is not None:
            body["bedrooms_from"] = bedrooms_from
        if bedrooms_to is not None:
            body["bedrooms_to"] = bedrooms_to
        if total_area_from is not None:
            body["total_area_from"] = total_area_from
        if total_area_to is not None:
            body["total_area_to"] = total_area_to

        return self._request(
            "POST",
            "/v1/comparables/search",
            params={"limit": min(limit, 100), "offset": offset},
            json_body=body,
        )

    # ------------------------------------------------------------------
    # Helpers de mapeamento
    # ------------------------------------------------------------------

    @classmethod
    def map_property_type(cls, internal_type: Optional[str]) -> List[str]:
        """Mapeia tipo interno PT para tipos CASAFARI.

        Args:
            internal_type: Tipo interno (apartamento, moradia, etc.).

        Returns:
            Lista de tipos CASAFARI correspondentes.
        """
        if not internal_type:
            return []
        key = cls._normalize(internal_type)
        return cls.PROPERTY_TYPE_MAP.get(key, [key])

    @classmethod
    def map_condition(cls, internal_condition: Optional[str]) -> Optional[str]:
        """Mapeia condicao interna para CASAFARI."""
        if not internal_condition:
            return None
        return cls.CONDITION_MAP.get(cls._normalize(internal_condition))

    @staticmethod
    def _normalize(text: str) -> str:
        """Remove acentos e normaliza texto para mapeamento."""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text.strip().lower())
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    @classmethod
    def parse_alert_to_comparable(cls, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Converte um alerta CASAFARI para dados de comparavel.

        Args:
            alert: Dict de um alerta da resposta da API.

        Returns:
            Dict normalizado com campos do MarketComparable.
        """
        # Extrair localizacao da locations_structure
        district = None
        municipality = None
        parish = None
        for loc in alert.get("locations_structure", []):
            level = (loc.get("administrative_level") or "").lower()
            if "distrito" in level:
                district = loc.get("name")
            elif "concelho" in level:
                municipality = loc.get("name")
            elif "freguesia" in level:
                parish = loc.get("name")

        coords = alert.get("coordinates") or {}

        # Determinar comparison_type a partir do alert_subtype/sale_status
        sale_status = (alert.get("sale_status") or "").lower()
        alert_subtype = (alert.get("alert_subtype") or "").lower()

        if alert_subtype == "sold" or sale_status == "sold":
            comparison_type = "listing_sold"
        elif sale_status in ("active", "reserved"):
            comparison_type = "listing_active"
        else:
            comparison_type = "listing_historical"

        return {
            "source": "casafari",
            "source_id": str(alert.get("property_id") or alert.get("listing_id", "")),
            "source_url": alert.get("property_url") or alert.get("listing_url"),
            "property_type": alert.get("type"),
            "bedrooms": alert.get("bedrooms"),
            "bathrooms": alert.get("bathrooms"),
            "district": district,
            "municipality": municipality,
            "parish": parish,
            "address": alert.get("address"),
            "postal_code": alert.get("zip_code"),
            "latitude": coords.get("latitude"),
            "longitude": coords.get("longitude"),
            "listing_price": alert.get("sale_price"),
            "price_per_m2": alert.get("sale_price_per_sqm"),
            "currency": alert.get("sale_currency", "EUR"),
            "gross_area_m2": alert.get("total_area"),
            "useful_area_m2": alert.get("living_area"),
            "condition": alert.get("condition"),
            "construction_year": alert.get("construction_year"),
            "energy_certificate": alert.get("energy_certificate"),
            "listing_date": alert.get("alert_date"),
            "days_on_market": None,  # Preenchido via property detail
            "comparison_type": comparison_type,
            "alert_type": alert.get("alert_type"),
            "alert_subtype": alert_subtype,
            "features": alert.get("features"),
            "thumbnails": alert.get("thumbnails", []),
            "pictures": alert.get("pictures", []),
            "description": alert.get("description"),
            "agency": alert.get("agency"),
            "contacts_info": alert.get("contacts_info"),
            "raw_data": alert,
        }

    @classmethod
    def parse_property_detail(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parseia detalhe completo de propriedade para formato interno.

        Extrai historico de precos, DOM, listings por fonte, etc.
        """
        # Historico de preco de venda
        price_history = []
        for entry in data.get("sale_price_history", []):
            price_history.append({
                "date_start": entry.get("date_start"),
                "date_end": entry.get("date_end"),
                "price_old": entry.get("sale_price_old"),
                "price_new": entry.get("sale_price_new"),
            })

        # Tempo no mercado
        tom = data.get("sale_time_on_market") or {}
        days_on_market = tom.get("days_on_market")

        # Listings por fonte
        listings = []
        for listing in data.get("listings", []):
            listings.append({
                "listing_id": listing.get("listing_id"),
                "source_name": listing.get("source_name"),
                "sale_price": listing.get("sale_price"),
                "rent_price": listing.get("rent_price"),
                "agency": listing.get("agency"),
                "contacts_info": listing.get("contacts_info"),
                "created_at": listing.get("created_at"),
            })

        return {
            "property_id": data.get("property_id"),
            "property_url": data.get("property_url"),
            "sale_price": data.get("sale_price"),
            "sale_price_per_sqm": data.get("sale_price_per_sqm"),
            "rent_price": data.get("rent_price"),
            "gross_yield": data.get("gross_yield"),
            "total_area": data.get("total_area"),
            "days_on_market": days_on_market,
            "price_history": price_history,
            "listings_by_source": listings,
            "listings_count": len(listings),
            "raw_data": data,
        }


def clear_caches() -> None:
    """Limpa todos os caches do cliente CASAFARI."""
    global _location_cache, _location_cache_ts, _jwt_token, _jwt_expires_at
    _location_cache.clear()
    _location_cache_ts = 0
    _jwt_token = None
    _jwt_expires_at = 0
    logger.debug("Caches CASAFARI limpos")
