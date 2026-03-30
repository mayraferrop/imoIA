"""Cliente para a API do SIR (Sistema de Informação Residencial).

Confidencial Imobiliário — preços reais de transação imobiliária em Portugal.
Autenticação via CAS SSO (users.confidencialimobiliario.com → sir.confidencialimobiliario.com).

Dados disponíveis (Fev/2026):
- Preço de Venda/m2 (média, percentis)
- Preço de Venda/Fogo
- Volume de fogos vendidos
- Área (ABP)
- Tempo de absorção
- Taxa de desconto
- Gap de mercado

Granularidade: concelho, freguesia, região.
Periodicidade: mensal, trimestral, semestral, anual.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.config import get_settings

# Cache de sessão (httpx.Client persistente)
_session_client: Optional[httpx.Client] = None
_session_ts: float = 0
_SESSION_TTL = 3600  # 1 hora

# Cache de dados
_data_cache: Dict[str, Any] = {}
_DATA_CACHE_TTL = 24 * 3600  # 24 horas

# Mapa de concelhos estratégicos (id SIR)
CONCELHO_MAP: Dict[str, int] = {
    "lisboa": 110600, "porto": 131200, "cascais": 110400,
    "oeiras": 111100, "sintra": 111500, "almada": 150300,
    "loures": 110700, "amadora": 111600, "odivelas": 111700,
    "vila franca de xira": 111400, "mafra": 110800, "seixal": 151300,
    "setubal": 151400, "barreiro": 150400, "montijo": 151000,
    "sesimbra": 151500, "palmela": 151100,
    "vila nova de gaia": 131700, "matosinhos": 130800,
    "maia": 130700, "gondomar": 130500, "valongo": 131600,
    "faro": 80500, "loule": 80800, "albufeira": 80100,
    "lagos": 80700, "portimao": 81100, "tavira": 81500,
    "braga": 30300, "coimbra": 60300, "aveiro": 10100,
    "funchal": 310300, "leiria": 100800, "viseu": 181800,
    "guimaraes": 30800, "viana do castelo": 160900,
    "evora": 70500,
}

# Variáveis disponíveis
VAR_FOGOS_VENDIDOS = 1
VAR_PRECO_M2 = 5
VAR_PRECO_FOGO = 6
VAR_AREA = 11
VAR_TEMPO_ABSORCAO = 14
VAR_TAXA_DESCONTO = 15
VAR_TAXA_DESC_REVISAO = 16
VAR_GAP_MERCADO = 17


class SIRClient:
    """Cliente para preços de transação via SIR / Confidencial Imobiliário."""

    _BASE_URL = "https://sir.confidencialimobiliario.com/api/v3"
    _USERS_URL = "https://users.confidencialimobiliario.com"

    def __init__(self) -> None:
        settings = get_settings()
        self._email = settings.sir_username
        self._password = settings.sir_password

    @property
    def is_configured(self) -> bool:
        return bool(self._email and self._password)

    # ------------------------------------------------------------------
    # Autenticação CAS
    # ------------------------------------------------------------------

    def _get_session(self) -> Optional[httpx.Client]:
        """Retorna httpx.Client autenticado via CAS SSO (reutiliza sessão)."""
        global _session_client, _session_ts

        if not self.is_configured:
            logger.warning("SIR: credenciais não configuradas")
            return None

        # Reutilizar sessão se ainda válida
        if _session_client and (time.time() - _session_ts) < _SESSION_TTL:
            return _session_client

        # Fechar sessão anterior se existir
        if _session_client:
            try:
                _session_client.close()
            except Exception:
                pass

        # Login CAS completo
        client = httpx.Client(timeout=20, follow_redirects=False)
        try:
            result = self._cas_login(client)
            if result:
                _session_client = result
                _session_ts = time.time()
            return result
        except Exception as e:
            logger.error(f"SIR: login CAS falhou: {e}")
            client.close()
            return None

    def _cas_login(self, client: httpx.Client) -> Optional[httpx.Client]:
        """Fluxo CAS: SIR → users portal → email → password → redirect back."""
        global _session_cookies, _session_ts

        # 1. SIR login → redirect para CAS
        r1 = client.get(f"https://sir.confidencialimobiliario.com/accounts/login/")
        cas_url = r1.headers.get("location", "")
        if not cas_url:
            logger.error("SIR: sem redirect CAS")
            return None

        # 2. CAS login page (segue redirects até ao form)
        r2 = client.get(cas_url, follow_redirects=True)

        # 3. POST email (step 1)
        csrf = self._extract_csrf(r2.text)
        r3 = client.post(
            str(r2.url),
            data={"csrfmiddlewaretoken": csrf, "email": self._email},
            headers={"Referer": str(r2.url)},
            follow_redirects=True,
        )

        # 4. POST password (step 2)
        csrf2 = self._extract_csrf(r3.text)
        r4 = client.post(
            str(r3.url),
            data={
                "csrfmiddlewaretoken": csrf2,
                "email": self._email,
                "password": self._password,
            },
            headers={"Referer": str(r3.url)},
            follow_redirects=False,
        )

        # 5. Seguir redirects CAS (ticket → SIR valida)
        loc = r4.headers.get("location", "")
        for _ in range(10):
            if not loc:
                break
            full_url = loc if loc.startswith("http") else f"{self._USERS_URL}{loc}"
            r4 = client.get(full_url, follow_redirects=False)
            loc = r4.headers.get("location", "")

        # Verificar autenticação
        r_check = client.get(f"{self._BASE_URL}/web/config", follow_redirects=True)
        if r_check.status_code == 200 and r_check.json().get("authenticated"):
            logger.info("SIR: login CAS bem sucedido")
            return client

        logger.error("SIR: login CAS completou mas não autenticou")
        return None

    @staticmethod
    def _extract_csrf(html: str) -> str:
        m = re.search(r'csrfmiddlewaretoken.*?value=["\']([^"\']+)', html)
        return m.group(1) if m else ""

    # ------------------------------------------------------------------
    # API: Dados de mercado
    # ------------------------------------------------------------------

    # Mapa de subjects por operação
    _SUBJECT_MAP = {
        "sale": "sir_venda",
        "rent": "siral_venda",
    }

    def get_transaction_prices(
        self,
        concelho_id: int,
        operation: str = "sale",
        variables: Optional[List[int]] = None,
        aggregation: int = 12,  # 12=anual, 3=trimestral, 6=semestral
    ) -> Optional[Dict[str, Any]]:
        """Obtém preços de transação/arrendamento para um concelho.

        Args:
            concelho_id: ID do concelho no SIR (ex: 110600 = Lisboa).
            operation: 'sale' (venda) ou 'rent' (arrendamento).
            variables: Lista de IDs de variáveis (default: preço/m2 + volume).
            aggregation: Agregação temporal (12=anual, 3=trimestral).

        Returns:
            Dict com price_m2, volume, period, operation, source.
        """
        if variables is None:
            variables = [VAR_PRECO_M2, VAR_FOGOS_VENDIDOS]

        subject = self._SUBJECT_MAP.get(operation, "sir_venda")

        # Cache
        cache_key = f"{concelho_id}:{operation}:{aggregation}:{','.join(map(str, variables))}"
        cached = _data_cache.get(cache_key)
        if cached and (time.time() - cached["ts"]) < _DATA_CACHE_TTL:
            return cached["data"]

        client = self._get_session()
        if not client:
            return None

        try:
            csrf = client.cookies.get("csrftoken", domain="sir.confidencialimobiliario.com")
            r = client.post(
                f"{self._BASE_URL}/subject/{subject}/data/",
                json={
                    "concelho": [concelho_id],
                    "var": variables,
                    "agregacao": [aggregation],
                },
                headers={
                    "Referer": "https://sir.confidencialimobiliario.com/",
                    "X-CSRFToken": csrf or "",
                },
            )

            if r.status_code != 200:
                logger.warning(f"SIR: HTTP {r.status_code} para concelho {concelho_id} ({operation})")
                return None

            data = r.json()
            result = self._parse_venda_response(data, concelho_id)

            if result:
                result["operation"] = operation
                label = "Renda contratada" if operation == "rent" else "Preço de venda"
                result["price_label"] = label
                _data_cache[cache_key] = {"data": result, "ts": time.time()}

            return result

        except Exception as e:
            logger.error(f"SIR: erro ao buscar dados ({operation}): {e}")
            return None

    def get_price_m2(
        self, municipality: str, operation: str = "sale"
    ) -> Optional[Dict[str, Any]]:
        """Obtém preço médio por m2 para um concelho (venda ou arrendamento).

        Args:
            municipality: Nome do concelho (ex: 'Lisboa', 'Porto').
            operation: 'sale' ou 'rent'.

        Returns:
            Dict com price_m2, volume, period, operation, source ou None.
        """
        key = self._normalize(municipality)
        concelho_id = CONCELHO_MAP.get(key)

        if not concelho_id:
            logger.info(f"SIR: concelho '{municipality}' não mapeado")
            return None

        return self.get_transaction_prices(concelho_id, operation=operation)

    def get_multiple_prices(
        self, municipalities: List[str], operation: str = "sale"
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Obtém preços para múltiplos concelhos."""
        results: Dict[str, Optional[Dict[str, Any]]] = {}
        for name in municipalities:
            results[name] = self.get_price_m2(name, operation=operation)
            time.sleep(0.2)
        return results

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_venda_response(
        data: Dict[str, Any], concelho_id: int
    ) -> Optional[Dict[str, Any]]:
        """Parseia resposta do endpoint sir_venda/data/."""
        results = data.get("results", [])
        if not results:
            return None

        price_m2 = None
        volume = None
        period = None

        for res in results:
            period = res.get("data", "")[:7]  # '2026-02'
            var_id = res.get("var")
            valores = res.get("valores", {})

            if var_id == VAR_PRECO_M2:
                price_m2 = valores.get("media")
            elif var_id == VAR_FOGOS_VENDIDOS:
                volume = valores.get("n")

        if price_m2 is None:
            return None

        return {
            "price_m2": price_m2,
            "volume": volume,
            "period": period,
            "concelho_id": concelho_id,
            "source": "SIR/Confidencial Imobiliário",
        }

    @staticmethod
    def _normalize(text: str) -> str:
        """Normaliza texto para lookup no mapa de concelhos."""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text.strip().lower())
        return "".join(c for c in nfkd if not unicodedata.combining(c))


def clear_cache() -> None:
    """Limpa caches do SIR."""
    global _session_client, _session_ts, _data_cache
    if _session_client:
        try:
            _session_client.close()
        except Exception:
            pass
    _session_client = None
    _session_ts = 0
    _data_cache.clear()
    logger.debug("Caches SIR limpos")
