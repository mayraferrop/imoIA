"""Parser de listagens Imovirtual (imovirtual.com/pt/resultados/...).

Imovirtual é um site Next.js — o estado do SSR fica em <script id="__NEXT_DATA__">
como JSON. É a fonte mais estável porque reflecte o state da app, não o markup.

Fallback: se __NEXT_DATA__ falhar, tentamos parse de cards article[data-cy='listing-item'].

URLs esperados:
- https://www.imovirtual.com/pt/resultados/comprar/apartamento/lisboa
- https://www.imovirtual.com/pt/resultados/comprar/apartamento/porto
- ...?page=N
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from loguru import logger

from src.modules.m1_scraper.base import RespectfulScraper, ScrapedListing


SOURCE = "imovirtual_pt"
BASE_URL = "https://www.imovirtual.com"


def scrape_search_page(
    scraper: RespectfulScraper, url: str
) -> List[ScrapedListing]:
    """Scrapes uma página de resultados Imovirtual."""
    html = scraper.get(url)
    if not html:
        return []

    listings = _parse_next_data(html)
    if listings:
        logger.info(f"Imovirtual: {len(listings)} listings (__NEXT_DATA__) de {url}")
        return listings

    listings = _parse_html_fallback(html)
    if listings:
        logger.info(f"Imovirtual: {len(listings)} listings (fallback HTML) de {url}")
    else:
        logger.warning(
            f"Imovirtual: sem listings em {url} — markup e NEXT_DATA podem ter mudado"
        )
    return listings


def build_search_url(
    property_type: str, municipality_slug: str, page: int = 1
) -> str:
    """Ex: build_search_url('apartamento', 'lisboa')
        -> https://www.imovirtual.com/pt/resultados/comprar/apartamento/lisboa
    """
    url = f"{BASE_URL}/pt/resultados/comprar/{property_type}/{municipality_slug}"
    if page > 1:
        url += f"?page={page}"
    return url


def _parse_next_data(html: str) -> List[ScrapedListing]:
    """Extrai listings do JSON em <script id='__NEXT_DATA__'>."""
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return []

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return []

    items = _find_listings_in_nextdata(data)
    results: List[ScrapedListing] = []
    for item in items:
        listing = _item_to_scraped(item)
        if listing:
            results.append(listing)
    return results


def _find_listings_in_nextdata(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Percorre a árvore __NEXT_DATA__ à procura do array de listings.

    Estrutura esperada em Imovirtual (pode mudar):
        props.pageProps.data.searchAds.items[]
    Fazemos busca defensiva por heurística.
    """
    try:
        page_props = data.get("props", {}).get("pageProps", {})
    except AttributeError:
        return []

    candidates = [
        ("data", "searchAds", "items"),
        ("data", "searchResult", "items"),
        ("searchAds", "items"),
        ("tracking", "listing", "items"),
    ]
    for path in candidates:
        node = page_props
        for key in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        if isinstance(node, list) and node:
            return node

    return _deep_find_list_of_items(page_props)


def _deep_find_list_of_items(obj: Any, depth: int = 0) -> List[Dict[str, Any]]:
    if depth > 8:
        return []
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        sample = obj[0]
        if any(k in sample for k in ("id", "title", "totalPrice", "price")):
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            found = _deep_find_list_of_items(v, depth + 1)
            if found:
                return found
    return []


def _item_to_scraped(item: Dict[str, Any]) -> Optional[ScrapedListing]:
    try:
        external_id = str(item.get("id") or item.get("adId") or "")
        if not external_id:
            return None

        url = item.get("url") or item.get("seoUrl") or ""
        if url and not url.startswith("http"):
            url = f"{BASE_URL}{url if url.startswith('/') else '/' + url}"

        title = item.get("title") or item.get("name")

        price = _extract_price_from_item(item)
        area_m2 = _safe_float(
            item.get("areaInSquareMeters")
            or item.get("area")
            or (item.get("characteristics", {}) or {}).get("m")
        )
        bedrooms = _safe_int(
            item.get("roomsNumber")
            or (item.get("characteristics", {}) or {}).get("rooms_num")
        )

        location = item.get("location", {}) or {}
        address = location.get("address", {}) or {}
        municipality = address.get("city", {}).get("name") if isinstance(address.get("city"), dict) else address.get("city")
        parish = address.get("street", {}).get("name") if isinstance(address.get("street"), dict) else None
        district = address.get("province", {}).get("name") if isinstance(address.get("province"), dict) else address.get("province")

        description = item.get("shortDescription") or item.get("description")
        if description and len(description) > 1000:
            description = description[:1000]

        photos = []
        for img in item.get("images", []) or []:
            if isinstance(img, dict):
                src = img.get("large") or img.get("medium") or img.get("url")
                if src:
                    photos.append(src)
            elif isinstance(img, str):
                photos.append(img)

        return ScrapedListing(
            source=SOURCE,
            external_id=external_id,
            url=url,
            title=title,
            price=price,
            area_m2=area_m2,
            bedrooms=bedrooms,
            typology=f"T{bedrooms}" if bedrooms else None,
            property_type=_infer_type(item, title),
            district=district,
            municipality=municipality,
            parish=parish,
            description=description,
            photos=photos[:5],
            raw=item if len(str(item)) < 5000 else {},
        )

    except Exception as e:
        logger.debug(f"Imovirtual: falha a converter item — {e}")
        return None


def _extract_price_from_item(item: Dict[str, Any]) -> Optional[float]:
    for key in ("totalPrice", "price"):
        v = item.get(key)
        if isinstance(v, dict):
            val = v.get("value") or v.get("amount")
            if val:
                return _safe_float(val)
        elif v:
            return _safe_float(v)
    return None


def _infer_type(item: Dict[str, Any], title: Optional[str]) -> Optional[str]:
    t = (item.get("estate") or item.get("category") or "").lower()
    if "apartment" in t or "apartamento" in t:
        return "apartamento"
    if "house" in t or "moradia" in t:
        return "moradia"
    if "land" in t or "terreno" in t:
        return "terreno"
    if title:
        return _infer_from_title(title)
    return None


def _infer_from_title(title: str) -> Optional[str]:
    t = title.lower()
    for kw, ptype in [
        ("apartamento", "apartamento"),
        ("moradia", "moradia"),
        ("terreno", "terreno"),
        ("prédio", "predio"),
        ("loja", "loja"),
    ]:
        if kw in t:
            return ptype
    return None


def _parse_html_fallback(html: str) -> List[ScrapedListing]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("article[data-cy='listing-item']")
    results: List[ScrapedListing] = []
    for card in cards:
        try:
            a = card.select_one("a[href]")
            if not a:
                continue
            url = a.get("href", "")
            if url and not url.startswith("http"):
                url = f"{BASE_URL}{url}"
            title = a.get_text(strip=True) or None

            ad_id = card.get("id") or card.get("data-ad-id")
            if not ad_id:
                match = re.search(r"/ID(\w+)", url)
                ad_id = match.group(1) if match else None
            if not ad_id:
                continue

            price_el = card.select_one("[data-cy='listing-item-price'], [data-sentry-component='Price']")
            price = None
            if price_el:
                price_text = re.sub(r"[^\d]", "", price_el.get_text(" ", strip=True))
                if price_text:
                    price = float(price_text)

            results.append(
                ScrapedListing(
                    source=SOURCE,
                    external_id=str(ad_id),
                    url=url,
                    title=title,
                    price=price,
                )
            )
        except Exception as e:
            logger.debug(f"Imovirtual fallback: skip card — {e}")
    return results


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None
