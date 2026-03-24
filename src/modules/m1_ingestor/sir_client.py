"""Cliente para a API do SIR (Confidencial Imobiliario).

Valida precos de imoveis contra dados de transacoes reais em Portugal.
Determina se um preco esta dentro, acima ou abaixo de mercado.

API: https://sir.confidencialimobiliario.com/api/v3/
Auth: JWT via POST /token/auth/ com {email, password}
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

import httpx
from loguru import logger

from src.config import get_settings

# Cache em memoria
_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 24 * 3600  # 24 horas

# JWT tokens (guardados apos login)
_access_token: Optional[str] = None
_refresh_token: Optional[str] = None
_session_cookies: Optional[Dict[str, str]] = None


class SIRClient:
    """Cliente para a API do SIR / Confidencial Imobiliario.

    Usa dados de transacoes reais (desde 2007) para validar precos.
    Auth: JWT via /token/auth/ ou CAS SSO como fallback.
    """

    _BASE_URL = "https://sir.confidencialimobiliario.com/api/v3"

    def __init__(self) -> None:
        """Inicializa o cliente SIR."""
        self._settings = get_settings()
        self._email = self._settings.sir_username
        self._password = self._settings.sir_password
        self._access_token: Optional[str] = _access_token
        self._refresh_token: Optional[str] = _refresh_token
        self._session_cookies: Optional[Dict[str, str]] = _session_cookies

    @property
    def is_configured(self) -> bool:
        """Verifica se o SIR esta configurado."""
        return bool(self._email and self._password)

    def _authenticate(self) -> bool:
        """Autentica no SIR via JWT ou CAS SSO."""
        if self._access_token:
            return True
        if self._session_cookies:
            return True
        if not self.is_configured:
            return False

        # Metodo 1: JWT directo
        if self._authenticate_jwt():
            return True

        # Metodo 2: CAS SSO (login no portal + redirect para SIR)
        if self._authenticate_cas():
            return True

        logger.warning("SIR: autenticacao falhou (JWT e CAS)")
        return False

    def _authenticate_jwt(self) -> bool:
        """Autentica via JWT em /token/auth/."""
        global _access_token, _refresh_token
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    f"{self._BASE_URL}/token/auth/",
                    json={"email": self._email, "password": self._password},
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("access") or data.get("token")
                    if token:
                        self._access_token = token
                        _access_token = token
                        self._refresh_token = data.get("refresh")
                        _refresh_token = self._refresh_token
                        logger.info("SIR autenticado via JWT")
                        return True
        except Exception as e:
            logger.debug(f"SIR JWT auth falhou: {e}")
        return False

    def _authenticate_cas(self) -> bool:
        """Autentica via CAS SSO (users.confidencialimobiliario.com)."""
        global _session_cookies
        try:
            import requests

            session = requests.Session()

            # Step 1: GET login page
            r = session.get(
                "https://users.confidencialimobiliario.com/accounts/login/",
                timeout=15,
            )
            csrf_match = re.search(
                r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text
            )
            if not csrf_match:
                return False

            # Step 2: POST credentials
            r2 = session.post(
                "https://users.confidencialimobiliario.com/accounts/login/",
                data={
                    "csrfmiddlewaretoken": csrf_match.group(1),
                    "email": self._email,
                    "password": self._password,
                },
                headers={"Referer": r.url},
            )

            # Step 3: Try CAS flow to SIR
            r3 = session.get(
                "https://sir.confidencialimobiliario.com/accounts/login/?next=/",
                timeout=15,
            )

            # Check if we landed on SIR (not back on login)
            sir_cookies = {
                c.name: c.value
                for c in session.cookies
                if "sir.confidencial" in (c.domain or "")
            }
            if sir_cookies:
                self._session_cookies = sir_cookies
                _session_cookies = sir_cookies
                logger.info("SIR autenticado via CAS SSO")
                return True

            # Verify by testing /web/config
            r4 = session.get(
                f"{self._BASE_URL}/web/config", timeout=10
            )
            if r4.status_code == 200:
                data = r4.json()
                if data.get("authenticated"):
                    self._session_cookies = {
                        c.name: c.value for c in session.cookies
                    }
                    _session_cookies = self._session_cookies
                    logger.info("SIR autenticado via CAS SSO (verified)")
                    return True

        except Exception as e:
            logger.debug(f"SIR CAS auth falhou: {e}")
        return False

    def _refresh_jwt(self) -> bool:
        """Renova o JWT access token."""
        global _access_token
        if not self._refresh_token:
            return False
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    f"{self._BASE_URL}/token/refresh/",
                    json={"refresh": self._refresh_token},
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("access") or data.get("token")
                    if token:
                        self._access_token = token
                        _access_token = token
                        logger.debug("SIR JWT token renovado")
                        return True
        except Exception:
            pass
        return False

    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers com autenticacao."""
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _get_cookies(self) -> Optional[Dict[str, str]]:
        """Retorna cookies de sessao se autenticado via CAS."""
        return self._session_cookies

    def get_transaction_prices(
        self,
        municipality: str,
        property_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Obtem precos de transacao reais para uma localizacao.

        Args:
            municipality: Municipio (ex: 'Lisboa', 'Porto').
            property_type: 'apartamento' ou 'moradia'.
            bedrooms: Numero de quartos (0-5+).

        Returns:
            Dict com preco mediano/m2 de transacoes reais ou None.
        """
        if not self.is_configured:
            return None

        cache_key = f"sir:{municipality}:{property_type}:{bedrooms}"
        cached = _cache.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < _CACHE_TTL:
            return cached["data"]

        if not self._authenticate():
            return None

        # Parametros (termos portugueses — API portuguesa)
        params: Dict[str, Any] = {"concelho": municipality}
        if property_type:
            params["tipo"] = property_type
        if bedrooms is not None:
            params["tipologia"] = f"T{bedrooms}"

        # Tentar endpoints conhecidos
        for endpoint in ["/data/transactions/", "/data/prices/", "/transactions/", "/prices/"]:
            data = self._request("GET", endpoint, params=params)
            if data and self._has_price_data(data):
                result = self._parse_transaction_data(data, municipality)
                if result:
                    _cache[cache_key] = {"data": result, "timestamp": time.time()}
                    return result

        logger.info(f"SIR: sem dados de transacao para '{municipality}'")
        return None

    def evaluate_price(
        self,
        price: float,
        municipality: str,
        area_m2: Optional[float] = None,
        property_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Avalia se um preco esta dentro, acima ou abaixo de mercado.

        Args:
            price: Preco do imovel em EUR.
            municipality: Municipio.
            area_m2: Area em m2.
            property_type: Tipo de imovel.
            bedrooms: Numero de quartos.

        Returns:
            Dict com avaliacao (dentro/acima/abaixo de mercado) ou None.
        """
        transaction_data = self.get_transaction_prices(
            municipality, property_type, bedrooms
        )

        if not transaction_data or not transaction_data.get("median_price_m2"):
            return None

        median_m2 = transaction_data["median_price_m2"]

        if area_m2 and area_m2 > 0:
            price_m2 = price / area_m2
        else:
            estimated_area = self._estimate_area(property_type, bedrooms)
            price_m2 = price / estimated_area

        ratio = price_m2 / median_m2
        if ratio <= 0.80:
            position = "muito_abaixo"
            label = "Muito abaixo do mercado"
        elif ratio <= 0.95:
            position = "abaixo"
            label = "Abaixo do mercado"
        elif ratio <= 1.05:
            position = "dentro"
            label = "Dentro do mercado"
        elif ratio <= 1.20:
            position = "acima"
            label = "Acima do mercado"
        else:
            position = "muito_acima"
            label = "Muito acima do mercado"

        return {
            "source": "sir",
            "price_m2": round(price_m2, 2),
            "market_median_m2": median_m2,
            "price_vs_market_pct": round(ratio * 100, 1),
            "position": position,
            "position_label": label,
            "municipality": municipality,
            "is_opportunity": ratio <= 0.90,
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Faz um pedido HTTP a API do SIR."""
        url = f"{self._BASE_URL}{endpoint}"
        headers = self._get_headers()
        cookies = self._get_cookies()

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    cookies=cookies,
                )
                if response.status_code == 401:
                    # Token expirado — tentar refresh
                    if self._refresh_jwt():
                        headers = self._get_headers()
                        response = client.request(
                            method=method,
                            url=url,
                            headers=headers,
                            params=params,
                            json=json_body,
                            cookies=cookies,
                        )
                    else:
                        self._access_token = None
                        return None
                response.raise_for_status()
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    return response.json()
                return None
        except httpx.HTTPStatusError:
            return None
        except Exception:
            return None

    def _has_price_data(self, data: Any) -> bool:
        """Verifica se a resposta contem dados de preco."""
        if isinstance(data, dict):
            price_keys = {"price", "price_m2", "median", "valor", "preco", "results", "data"}
            return bool(price_keys & set(data.keys()))
        if isinstance(data, list) and data:
            return True
        return False

    def _parse_transaction_data(
        self, data: Any, municipality: str
    ) -> Optional[Dict[str, Any]]:
        """Parseia dados de transacao do SIR."""
        if isinstance(data, dict):
            median = (
                data.get("median_price_m2")
                or data.get("median")
                or data.get("valor_mediano")
                or data.get("price_m2")
            )
            if median:
                return {
                    "source": "sir",
                    "municipality": municipality,
                    "median_price_m2": float(median),
                    "transactions_count": data.get("count") or data.get("total"),
                    "period": data.get("period") or data.get("periodo"),
                }

            results = data.get("results", data.get("data", []))
            if results and isinstance(results, list):
                return self._aggregate_results(results, municipality)

        if isinstance(data, list) and data:
            return self._aggregate_results(data, municipality)

        return None

    def _aggregate_results(
        self, results: list, municipality: str
    ) -> Optional[Dict[str, Any]]:
        """Agrega resultados de transacoes individuais."""
        prices_m2: list = []

        for r in results:
            pm2 = r.get("price_m2") or r.get("valor_m2") or r.get("preco_m2")
            if pm2:
                prices_m2.append(float(pm2))
            else:
                price = r.get("price") or r.get("valor") or r.get("preco")
                area = r.get("area") or r.get("area_m2")
                if price and area and float(area) > 0:
                    prices_m2.append(float(price) / float(area))

        if not prices_m2:
            return None

        sorted_prices = sorted(prices_m2)
        median_idx = len(sorted_prices) // 2

        return {
            "source": "sir",
            "municipality": municipality,
            "median_price_m2": round(sorted_prices[median_idx], 2),
            "avg_price_m2": round(sum(prices_m2) / len(prices_m2), 2),
            "min_price_m2": round(sorted_prices[0], 2),
            "max_price_m2": round(sorted_prices[-1], 2),
            "transactions_count": len(prices_m2),
        }

    @staticmethod
    def _estimate_area(
        property_type: Optional[str], bedrooms: Optional[int]
    ) -> float:
        """Estima a area com base no tipo e quartos (fallback)."""
        base = {0: 35, 1: 55, 2: 80, 3: 110, 4: 140, 5: 180}
        area = base.get(bedrooms or 2, 80)
        if property_type and "moradia" in property_type.lower():
            area = int(area * 1.3)
        return float(area)
