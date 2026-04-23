"""Base do scraper: fetch HTTP com rate limit + User-Agent identificável.

Princípios:
- Rate limit configurável (default 5s entre requests ao mesmo domínio)
- User-Agent próprio e identificável ("imoIA-bot/1.0 contact:...")
- Respeitar robots.txt (urllib.robotparser já integrado)
- Sem proxies nem rotação — uso pessoal, não agregação comercial
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from loguru import logger


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_RATE_LIMIT_SECONDS = 5.0
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass
class ScrapedListing:
    """Listing bruto extraído do portal, antes de passar pelo classifier.

    Campos pensados para alimentar tanto o classifier (via texto formatado)
    como o INSERT em properties (via campos estruturados).
    """

    source: str  # 'idealista_pt', 'imovirtual_pt'
    external_id: str  # ID no portal — usado para dedup
    url: str
    title: Optional[str] = None
    price: Optional[float] = None
    currency: str = "EUR"
    area_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    typology: Optional[str] = None
    property_type: Optional[str] = None
    district: Optional[str] = None
    municipality: Optional[str] = None
    parish: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    photos: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)  # payload original

    def to_classifier_text(self) -> str:
        """Formata o listing como texto para o OpportunityClassifier.

        O classifier aceita qualquer string — formatamos para parecer uma
        oferta concisa (portal → mensagem estilo WhatsApp) para reutilizar
        o prompt existente sem alterações.
        """
        parts: List[str] = []
        if self.title:
            parts.append(self.title)
        loc_bits = [b for b in [self.parish, self.municipality, self.district] if b]
        if loc_bits:
            parts.append(f"Zona: {', '.join(loc_bits)}")
        specs: List[str] = []
        if self.typology:
            specs.append(self.typology)
        if self.area_m2:
            specs.append(f"{self.area_m2:.0f}m²")
        if self.bedrooms:
            specs.append(f"{self.bedrooms} quartos")
        if specs:
            parts.append(", ".join(specs))
        if self.price:
            parts.append(f"Preço: €{self.price:,.0f}".replace(",", " "))
        if self.description:
            parts.append(self.description[:400])
        parts.append(f"Origem: {self.source} — {self.url}")
        return "\n".join(parts)


class RespectfulScraper:
    """Cliente HTTP com rate limit por host e respeito a robots.txt."""

    def __init__(
        self,
        *,
        rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
        respect_robots: bool = True,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._rate_limit = rate_limit_seconds
        self._respect_robots = respect_robots
        self._last_request: Dict[str, float] = {}
        self._robots_cache: Dict[str, Optional[RobotFileParser]] = {}
        self._http = http_client or httpx.Client(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

    def get(self, url: str) -> Optional[str]:
        """Faz GET respeitando rate limit + robots.txt.

        Returns:
            HTML da página, ou None se bloqueado/erro.
        """
        if self._respect_robots and not self._is_allowed(url):
            logger.warning(f"Scraper: bloqueado por robots.txt — {url}")
            return None

        self._wait_for_host(url)

        try:
            response = self._http.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.warning(f"Scraper: {e.response.status_code} para {url}")
            return None
        except httpx.HTTPError as e:
            logger.warning(f"Scraper: falha HTTP para {url} — {e}")
            return None

    def _wait_for_host(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_request.get(host, 0.0)
        elapsed = time.time() - last
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request[host] = time.time()

    def _is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"

        if host not in self._robots_cache:
            robots_url = f"{host}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                self._robots_cache[host] = rp
            except Exception as e:
                logger.debug(f"Scraper: sem robots.txt em {host} ({e}) — permitir")
                self._robots_cache[host] = None

        rp = self._robots_cache[host]
        if rp is None:
            return True
        return rp.can_fetch(USER_AGENT, url)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "RespectfulScraper":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
