"""Cliente para a API do INE (Instituto Nacional de Estatistica).

Migrado de src/market/ine.py para o modulo M2.
Obtem precos medianos de habitacao por municipio em Portugal.
Indicadores:
- 0009490: Valor mediano vendas alojamentos familiares (EUR/m2) — todos
- 0009486: Valor mediano vendas apartamentos (EUR/m2)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.config import get_settings

# Cache em memoria: {municipality_lower: {"data": dict, "timestamp": float}}
_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 30 * 24 * 3600  # 30 dias

# Cache dos dados completos do INE (evitar chamadas repetidas)
_ine_data_cache: Optional[Dict[str, Dict[str, Any]]] = None
_ine_data_timestamp: float = 0


class INEClient:
    """Cliente para consulta de precos medianos de habitacao via INE."""

    # Indicador para valor mediano vendas (todos os tipos)
    INDICATOR_ALL = "0009490"
    # Indicador para valor mediano vendas (apartamentos)
    INDICATOR_APT = "0009486"

    BASE_URL = "https://www.ine.pt/ine/json_indicador/pindica.jsp"

    def __init__(self, http_client: Optional[httpx.Client] = None) -> None:
        """Inicializa o cliente INE."""
        self._http = http_client or httpx.Client(timeout=30.0)

    def get_median_price(self, municipality: str) -> Optional[Dict[str, Any]]:
        """Obtem o preco mediano por m2 para um municipio.

        Args:
            municipality: Nome do municipio (ex: 'Lisboa', 'Porto').

        Returns:
            Dict com 'price_m2', 'quarter', 'source' ou None se nao encontrado.
        """
        key = municipality.strip().lower()

        # Verificar cache
        cached = _cache.get(key)
        if cached and (time.time() - cached["timestamp"]) < _CACHE_TTL:
            logger.debug(f"Cache hit para municipio '{municipality}'")
            return cached["data"]

        try:
            # Carregar dados (com cache global)
            locations = self._load_all_data()

            if not locations:
                return None

            result = self._find_municipality(locations, municipality)

            if result is None:
                logger.info(f"Municipio '{municipality}' nao encontrado nos dados do INE")
                return None

            # Guardar em cache
            _cache[key] = {"data": result, "timestamp": time.time()}
            logger.info(
                f"Preco mediano INE para '{municipality}': {result['price_m2']} EUR/m2 ({result['quarter']})"
            )
            return result

        except Exception as e:
            logger.error(f"Erro ao consultar INE para '{municipality}': {e}")
            return None

    def _load_all_data(self) -> Dict[str, Dict[str, Any]]:
        """Carrega todos os dados do INE (com cache global)."""
        global _ine_data_cache, _ine_data_timestamp

        if _ine_data_cache and (time.time() - _ine_data_timestamp) < _CACHE_TTL:
            return _ine_data_cache

        # Tentar apartamentos primeiro (mais recente tipicamente)
        locations = self._fetch_indicator(self.INDICATOR_APT)
        if not locations:
            locations = self._fetch_indicator(self.INDICATOR_ALL)

        if locations:
            _ine_data_cache = locations
            _ine_data_timestamp = time.time()
            logger.info(f"INE: {len(locations)} municipios carregados")

        return locations or {}

    def _fetch_indicator(self, indicator_code: str) -> Optional[Dict[str, Dict[str, Any]]]:
        """Busca dados de um indicador do INE."""
        try:
            response = self._http.get(
                self.BASE_URL,
                params={"op": "2", "varcd": indicator_code, "lang": "PT"},
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                data = data[0] if data else {}

            # Verificar sucesso
            success = data.get("Sucesso", {})
            if isinstance(success, dict) and "Falso" in success:
                logger.warning(f"INE indicador {indicator_code}: erro na resposta")
                return None

            return self._parse_indicator_data(data)

        except Exception as e:
            logger.error(f"Erro ao buscar INE indicador {indicator_code}: {e}")
            return None

    def _parse_indicator_data(
        self, data: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Parseia dados do indicador do INE.

        A estrutura e: Dados -> {periodo} -> [{geocod, geodsg, valor}, ...]

        Returns:
            Dict mapeando nome de municipio para dados de preco.
        """
        locations: Dict[str, Dict[str, Any]] = {}

        dados = data.get("Dados", {})
        if not dados:
            return locations

        # Usar o periodo mais recente
        periods = sorted(dados.keys(), reverse=True)
        if not periods:
            return locations

        latest_period = periods[0]
        entries = dados[latest_period]

        for entry in entries:
            name = entry.get("geodsg", "")
            valor = entry.get("valor")

            if not name or valor is None:
                continue

            try:
                price = float(valor)
            except (ValueError, TypeError):
                continue

            if price <= 0:
                continue

            locations[name] = {
                "price_m2": price,
                "quarter": latest_period,
            }

        return locations

    def _find_municipality(
        self,
        locations: Dict[str, Dict[str, Any]],
        municipality: str,
    ) -> Optional[Dict[str, Any]]:
        """Procura dados de um municipio.

        Tenta correspondencia exata, depois parcial (sem acentos).
        """
        target = municipality.strip().lower()

        # Correspondencia exata
        for loc_name, values in locations.items():
            if loc_name.lower() == target:
                return self._format_result(loc_name, values)

        # Correspondencia parcial
        for loc_name, values in locations.items():
            if target in loc_name.lower() or loc_name.lower() in target:
                return self._format_result(loc_name, values)

        # Tentar sem acentos
        target_clean = self._remove_accents(target)
        for loc_name, values in locations.items():
            if self._remove_accents(loc_name.lower()) == target_clean:
                return self._format_result(loc_name, values)

        return None

    @staticmethod
    def _format_result(name: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """Formata o resultado."""
        return {
            "price_m2": values["price_m2"],
            "quarter": values.get("quarter", "desconhecido"),
            "municipality": name,
            "source": "INE",
        }

    @staticmethod
    def _remove_accents(text: str) -> str:
        """Remove acentos de texto para comparacao."""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))


def clear_cache() -> None:
    """Limpa o cache de dados do INE."""
    global _ine_data_cache, _ine_data_timestamp
    _cache.clear()
    _ine_data_cache = None
    _ine_data_timestamp = 0
    logger.debug("Cache do INE limpo")
