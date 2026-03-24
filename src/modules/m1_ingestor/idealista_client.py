"""Cliente para a API Idealista.

Pesquisa imóveis comparáveis para enriquecimento de oportunidades.
Requer credenciais OAuth2 (client_id + client_secret).
"""

from __future__ import annotations

import base64
import time
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.config import get_settings


class IdealistaClient:
    """Cliente para a API Idealista com autenticação OAuth2."""

    def __init__(self, http_client: Optional[httpx.Client] = None) -> None:
        """Inicializa o cliente Idealista.

        Args:
            http_client: Cliente HTTP opcional (útil para testes).
        """
        self._settings = get_settings()
        self._http = http_client or httpx.Client(timeout=30.0)
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def search_comparables(
        self,
        location: str,
        property_type: str,
        area_m2: float,
    ) -> Optional[Dict[str, Any]]:
        """Pesquisa imóveis comparáveis no Idealista.

        Args:
            location: Localização (ex: 'Lisboa', 'Porto').
            property_type: Tipo de imóvel (ex: 'apartamento', 'moradia').
            area_m2: Área em m2.

        Returns:
            Dict com 'avg_price_m2', 'listings_count', 'comparable_urls' ou None.
        """
        if not self._settings.idealista_client_id or not self._settings.idealista_client_secret:
            logger.debug("Credenciais Idealista não configuradas — a ignorar")
            return None

        try:
            token = self._get_token()
            if token is None:
                return None

            result = self._search(token, location, property_type, area_m2)
            return result

        except Exception as e:
            logger.error(f"Erro ao pesquisar Idealista: {e}")
            return None

    def _get_token(self) -> Optional[str]:
        """Obtém ou renova o bearer token OAuth2.

        Returns:
            Token de acesso ou None em caso de erro.
        """
        if self._token and time.time() < self._token_expires_at:
            return self._token

        try:
            credentials = base64.b64encode(
                f"{self._settings.idealista_client_id}:{self._settings.idealista_client_secret}".encode()
            ).decode()

            response = self._http.post(
                "https://api.idealista.com/oauth/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
            response.raise_for_status()

            token_data = response.json()
            self._token = token_data["access_token"]
            # Expirar 60s antes para margem de segurança
            self._token_expires_at = time.time() + token_data.get("expires_in", 3600) - 60

            logger.debug("Token Idealista obtido com sucesso")
            return self._token

        except httpx.HTTPError as e:
            logger.error(f"Erro ao obter token Idealista: {e}")
            return None

    def _search(
        self,
        token: str,
        location: str,
        property_type: str,
        area_m2: float,
    ) -> Optional[Dict[str, Any]]:
        """Executa a pesquisa na API Idealista.

        Args:
            token: Bearer token.
            location: Localização.
            property_type: Tipo de imóvel.
            area_m2: Área em m2.

        Returns:
            Dict com resultados formatados ou None.
        """
        pt_type_map = {
            "apartamento": "homes",
            "moradia": "homes",
            "terreno": "homes",
            "prédio": "homes",
            "loja": "premises",
            "escritório": "offices",
            "armazém": "garages",
        }
        api_type = pt_type_map.get(property_type.lower(), "homes")

        min_area = max(1, int(area_m2 * 0.8))
        max_area = int(area_m2 * 1.2)

        params: Dict[str, Any] = {
            "operation": "sale",
            "propertyType": api_type,
            "locationName": location,
            "minSize": min_area,
            "maxSize": max_area,
            "order": "priceDown",
            "maxItems": 20,
            "country": "pt",
            "locale": "pt",
        }

        try:
            response = self._http.post(
                f"{self._settings.idealista_base_url}pt/search",
                headers={"Authorization": f"Bearer {token}"},
                data=params,
            )
            response.raise_for_status()
            data = response.json()

            return self._format_results(data)

        except httpx.HTTPError as e:
            logger.error(f"Erro na pesquisa Idealista: {e}")
            return None

    @staticmethod
    def _format_results(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Formata os resultados da pesquisa.

        Args:
            data: Resposta da API Idealista.

        Returns:
            Dict formatado ou None se sem resultados.
        """
        listings: List[Dict[str, Any]] = data.get("elementList", [])

        if not listings:
            return None

        prices_m2 = [
            listing["priceByArea"]
            for listing in listings
            if "priceByArea" in listing
        ]

        if not prices_m2:
            return None

        avg_price_m2 = sum(prices_m2) / len(prices_m2)

        urls = [
            listing.get("url", "")
            for listing in listings[:5]
            if listing.get("url")
        ]

        return {
            "avg_price_m2": round(avg_price_m2, 2),
            "listings_count": len(listings),
            "comparable_urls": urls,
        }
