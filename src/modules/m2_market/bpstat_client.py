"""Cliente para a API do BPstat (Banco de Portugal).

Obtem indices de precos de habitacao atualizados (trimestrais, base 2015=100).
Gratuito, sem autenticacao.

Datasets do dominio 39 (Precos de Habitacao):
- da133c091337a417b8b242c65e477ca0: IPHab (3 series, mais recente)
  - 12559645: Total
  - 12559646: Alojamentos novos
  - 12559647: Alojamentos existentes

Combinado com dados INE (preco/m2 por concelho de Q3/2021), permite
estimar precos atuais aplicando a variacao do indice nacional.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

# Cache em memoria
_bpstat_cache: Optional[Dict[str, Any]] = None
_bpstat_cache_ts: float = 0
_CACHE_TTL = 7 * 24 * 3600  # 7 dias

# Indice do INE no trimestre Q3/2021 (periodo base dos dados INE por concelho)
# Extraido do dataset BPstat: Q3 2021 = indice ~155.8 (total)
_INE_BASE_QUARTER = "Q3 2021"


class BPstatClient:
    """Cliente para indices de precos de habitacao via BPstat API."""

    _BASE_URL = "https://bpstat.bportugal.pt/data/v1"
    _DOMAIN_ID = 39  # Precos de habitacao
    _DATASET_ID = "da133c091337a417b8b242c65e477ca0"

    def __init__(self, http_client: Optional[httpx.Client] = None) -> None:
        self._http = http_client or httpx.Client(timeout=30.0)

    def get_price_index(self, obs_last_n: int = 20) -> Optional[Dict[str, Any]]:
        """Obtem indices de precos de habitacao recentes.

        Returns:
            Dict com 'total', 'new', 'existing' — cada um com lista de
            {quarter, index_value} ordenados do mais antigo ao mais recente.
        """
        global _bpstat_cache, _bpstat_cache_ts

        if _bpstat_cache and (time.time() - _bpstat_cache_ts) < _CACHE_TTL:
            return _bpstat_cache

        try:
            resp = self._http.get(
                f"{self._BASE_URL}/domains/{self._DOMAIN_ID}"
                f"/datasets/{self._DATASET_ID}/",
                params={"lang": "PT", "obs_last_n": obs_last_n},
            )
            resp.raise_for_status()
            data = resp.json()

            result = self._parse_dataset(data)
            if result:
                _bpstat_cache = result
                _bpstat_cache_ts = time.time()
                latest = result["total"][-1] if result["total"] else {}
                logger.info(
                    f"BPstat: indice habitacao carregado — "
                    f"ultimo: {latest.get('quarter')} = {latest.get('index_value')}"
                )
            return result

        except Exception as e:
            logger.error(f"Erro ao consultar BPstat: {e}")
            return None

    def get_latest_index(self) -> Optional[Dict[str, float]]:
        """Retorna o ultimo indice disponivel para cada categoria.

        Returns:
            Dict com 'total', 'new', 'existing' (valores float do indice).
        """
        data = self.get_price_index(obs_last_n=4)
        if not data:
            return None

        result: Dict[str, float] = {}
        for key in ("total", "new", "existing"):
            series = data.get(key, [])
            if series:
                result[key] = series[-1]["index_value"]

        return result if result else None

    def estimate_current_price(
        self,
        base_price_m2: float,
        base_quarter: str = _INE_BASE_QUARTER,
        property_type: str = "total",
    ) -> Optional[Dict[str, Any]]:
        """Estima preco atual aplicando variacao do indice BPstat.

        Pega no preco base (ex: INE Q3/2021) e ajusta pela variacao
        percentual do indice de precos de habitacao ate ao trimestre
        mais recente.

        Args:
            base_price_m2: Preco/m2 no periodo base.
            base_quarter: Trimestre do preco base (ex: 'Q3 2021').
            property_type: 'total', 'new' ou 'existing'.

        Returns:
            Dict com estimated_price_m2, variation_pct, base_quarter,
            current_quarter, index_base, index_current, source.
        """
        data = self.get_price_index(obs_last_n=20)
        if not data:
            return None

        series_key = property_type if property_type in data else "total"
        series = data.get(series_key, [])
        if not series:
            return None

        # Encontrar indice do trimestre base
        base_index = self._find_index_for_quarter(series, base_quarter)
        if base_index is None:
            logger.warning(
                f"BPstat: trimestre base '{base_quarter}' nao encontrado"
            )
            return None

        # Indice mais recente
        current = series[-1]
        current_index = current["index_value"]
        current_quarter = current["quarter"]

        # Calcular variacao e preco estimado
        variation = (current_index - base_index) / base_index
        estimated_price = base_price_m2 * (1 + variation)

        return {
            "estimated_price_m2": round(estimated_price, 2),
            "variation_pct": round(variation * 100, 1),
            "base_price_m2": base_price_m2,
            "base_quarter": base_quarter,
            "current_quarter": current_quarter,
            "index_base": base_index,
            "index_current": current_index,
            "source": "INE+BPstat",
        }

    def _find_index_for_quarter(
        self, series: List[Dict[str, Any]], quarter: str
    ) -> Optional[float]:
        """Encontra valor do indice para um trimestre especifico.

        Aceita formatos: 'Q3 2021', '3T2021', '2021-Q3', '2021T3'.
        """
        q_norm = self._normalize_quarter(quarter)
        for entry in series:
            if self._normalize_quarter(entry["quarter"]) == q_norm:
                return entry["index_value"]
        return None

    @staticmethod
    def _normalize_quarter(q: str) -> str:
        """Normaliza formato de trimestre para comparacao.

        Aceita: 'Q3 2021', '3.º Trimestre de 2021', '3T2021', '2021-Q3'.
        Retorna sempre: '2021Q3'.
        """
        import re
        q = q.strip()
        # 'Q3 2021' ou 'Q3-2021'
        m = re.match(r"Q(\d)\s*[-/]?\s*(\d{4})", q, re.I)
        if m:
            return f"{m.group(2)}Q{m.group(1)}"
        # '3.º Trimestre de 2021' ou '3º Trimestre de 2021'
        m = re.search(r"(\d)[.ºª]*\s*[Tt]rimestre\s+de\s+(\d{4})", q)
        if m:
            return f"{m.group(2)}Q{m.group(1)}"
        # '3T2021' ou '3.ºT2021'
        m = re.match(r"(\d)[.ºª]*\s*T\s*(\d{4})", q, re.I)
        if m:
            return f"{m.group(2)}Q{m.group(1)}"
        # '2021-Q3' ou '2021Q3' ou '2021T3'
        m = re.match(r"(\d{4})[-]?[QT](\d)", q, re.I)
        if m:
            return f"{m.group(1)}Q{m.group(2)}"
        return q

    def _parse_dataset(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parseia resposta do dataset BPstat.

        Estrutura: dimension.reference_date.category.index = lista de datas ISO
        Values: array plano [serie0_d0, serie0_d1, ..., serie1_d0, ...]
        """
        values = data.get("value", [])
        if not values:
            return None

        # Extrair datas: category.index e uma lista de datas ISO (ex: '2024-03-31')
        dims = data.get("dimension", {})
        ref_date = dims.get("reference_date", {})
        date_list = ref_date.get("category", {}).get("index", [])

        # Converter datas ISO para labels de trimestre
        date_labels: List[str] = []
        for d in date_list:
            date_labels.append(self._iso_to_quarter(d))

        sizes = data.get("size", [])
        n_dates = sizes[-1] if sizes else len(date_labels)
        n_series = len(data.get("extension", {}).get("series", []))

        if n_dates == 0 or n_series == 0:
            return None

        # Mapear series: 0=total, 1=novos, 2=existentes
        series_map = {0: "total", 1: "new", 2: "existing"}
        result: Dict[str, List[Dict[str, Any]]] = {
            "total": [], "new": [], "existing": [],
        }

        for s_idx in range(min(n_series, 3)):
            key = series_map.get(s_idx, f"series_{s_idx}")
            if key not in result:
                result[key] = []
            for d_idx in range(n_dates):
                val_idx = s_idx * n_dates + d_idx
                if val_idx < len(values) and values[val_idx] is not None:
                    quarter = date_labels[d_idx] if d_idx < len(date_labels) else f"period_{d_idx}"
                    result[key].append({
                        "quarter": quarter,
                        "index_value": float(values[val_idx]),
                    })

        return result

    @staticmethod
    def _iso_to_quarter(iso_date: str) -> str:
        """Converte data ISO (ex: '2024-03-31') para label de trimestre ('Q1 2024')."""
        try:
            parts = iso_date.split("-")
            year = parts[0]
            month = int(parts[1])
            q = (month - 1) // 3 + 1
            return f"Q{q} {year}"
        except (IndexError, ValueError):
            return iso_date


def clear_cache() -> None:
    """Limpa o cache do BPstat."""
    global _bpstat_cache, _bpstat_cache_ts
    _bpstat_cache = None
    _bpstat_cache_ts = 0
    logger.debug("Cache BPstat limpo")
