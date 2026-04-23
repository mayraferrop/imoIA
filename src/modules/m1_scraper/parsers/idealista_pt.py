"""Parser de listagens Idealista PT (idealista.pt/comprar-casas/...).

Estratégia: extrai dados estruturados do HTML (cards `article.item`).
Se o Idealista alterar o markup, o parser degrada para devolver o que
conseguir (campo a campo, tolerante a falhas).

URLs esperados:
- https://www.idealista.pt/comprar-casas/lisboa/
- https://www.idealista.pt/comprar-casas/porto/
- https://www.idealista.pt/comprar-casas/<municipio>/?pagina=N

Output: list[ScrapedListing] — não classifica nem persiste.
"""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger

from src.modules.m1_scraper.base import RespectfulScraper, ScrapedListing


SOURCE = "idealista_pt"
BASE_URL = "https://www.idealista.pt"


def scrape_search_page(
    scraper: RespectfulScraper, url: str
) -> List[ScrapedListing]:
    """Scrapes uma página de resultados Idealista.

    Args:
        scraper: cliente HTTP respeitoso.
        url: URL da listagem (ex: 'https://www.idealista.pt/comprar-casas/lisboa/').

    Returns:
        Lista de ScrapedListing. Lista vazia se falhar.
    """
    html = scraper.get(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("article.item")
    if not cards:
        logger.warning(
            f"Idealista: sem cards em {url} — markup pode ter mudado"
        )
        return []

    results: List[ScrapedListing] = []
    for card in cards:
        listing = _parse_card(card)
        if listing:
            results.append(listing)

    logger.info(f"Idealista: {len(results)} listings extraídos de {url}")
    return results


def build_search_url(municipality_slug: str, page: int = 1) -> str:
    """Constrói URL de busca.

    Ex: build_search_url('lisboa') -> https://www.idealista.pt/comprar-casas/lisboa/
        build_search_url('porto', 2) -> https://www.idealista.pt/comprar-casas/porto/pagina-2/
    """
    base = f"{BASE_URL}/comprar-casas/{municipality_slug}/"
    if page > 1:
        base += f"pagina-{page}.htm"
    return base


def _parse_card(card) -> Optional[ScrapedListing]:
    """Extrai ScrapedListing de um card HTML. Tolerante a campos em falta."""
    try:
        external_id = _extract_id(card)
        if not external_id:
            return None

        link = card.select_one("a.item-link")
        if not link:
            return None
        url = urljoin(BASE_URL, link.get("href", ""))
        title = link.get("title") or link.get_text(strip=True) or None

        price = _extract_price(card)
        area_m2, bedrooms, typology = _extract_specs(card)
        description = _extract_description(card)
        photos = _extract_photos(card)

        municipality, parish = _extract_location(title)

        return ScrapedListing(
            source=SOURCE,
            external_id=external_id,
            url=url,
            title=title,
            price=price,
            area_m2=area_m2,
            bedrooms=bedrooms,
            typology=typology,
            property_type=_infer_property_type(title),
            municipality=municipality,
            parish=parish,
            district=None,
            description=description,
            photos=photos,
        )

    except Exception as e:
        logger.debug(f"Idealista: falha a parsear card — {e}")
        return None


def _extract_id(card) -> Optional[str]:
    for attr in ("data-element-id", "data-adid", "data-id"):
        val = card.get(attr)
        if val:
            return str(val)
    link = card.select_one("a.item-link")
    if link:
        href = link.get("href", "")
        match = re.search(r"/imovel/(\d+)/", href)
        if match:
            return match.group(1)
    return None


def _extract_price(card) -> Optional[float]:
    el = card.select_one(".item-price, .price-row .item-price")
    if not el:
        return None
    text = el.get_text(" ", strip=True)
    cleaned = re.sub(r"[^\d]", "", text)
    return float(cleaned) if cleaned else None


def _extract_specs(card):
    area_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    typology: Optional[str] = None
    details = card.select(".item-detail-char .item-detail, .item-details .item-detail")
    for d in details:
        text = d.get_text(" ", strip=True)
        if "m²" in text or "m2" in text:
            num = re.sub(r"[^\d]", "", text.split("m")[0])
            if num:
                area_m2 = float(num)
        elif re.match(r"^T\d$", text):
            typology = text
            bedrooms = int(text[1:]) if text[1].isdigit() else None
    return area_m2, bedrooms, typology


def _extract_description(card) -> Optional[str]:
    el = card.select_one(".item-description, .description")
    if not el:
        return None
    return el.get_text(" ", strip=True)[:1000]


def _extract_photos(card) -> List[str]:
    urls: List[str] = []
    for img in card.select("img"):
        src = img.get("data-src") or img.get("src")
        if src and src.startswith("http"):
            urls.append(src)
    return urls[:5]


def _extract_location(title: Optional[str]):
    if not title:
        return None, None
    # Pattern comum: "... em <parish>, <municipality>"
    m = re.search(r"\bem\s+([^,]+),\s*([^,]+)", title)
    if m:
        return m.group(2).strip(), m.group(1).strip()
    return None, None


def _infer_property_type(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    t = title.lower()
    for kw, ptype in [
        ("apartamento", "apartamento"),
        ("moradia", "moradia"),
        ("terreno", "terreno"),
        ("prédio", "predio"),
        ("predio", "predio"),
        ("loja", "loja"),
        ("escritório", "escritorio"),
        ("escritorio", "escritorio"),
        ("armazém", "armazem"),
        ("armazem", "armazem"),
        ("quinta", "quinta"),
    ]:
        if kw in t:
            return ptype
    return None
