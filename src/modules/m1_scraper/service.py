"""Pipeline do scraper M1: fetch → classify → persist.

Orquestra a execução completa:
1. Scrapes Idealista + Imovirtual para URLs configuradas
2. Envia cada listing ao OpportunityClassifier (mesmo que usa a
   estratégia activa do tenant para mensagens WhatsApp)
3. Persiste apenas `is_opportunity=true` em properties (dedup + price history)

Reaproveita:
- OpportunityClassifier (m1_ingestor.classifier) — estratégia via tenant_id
- supabase_rest — helpers CRUD
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from src.database import supabase_rest as db
from src.modules.m1_ingestor.classifier import (
    OpportunityClassifier,
    OpportunityResult,
)
from src.modules.m1_scraper.base import RespectfulScraper, ScrapedListing
from src.modules.m1_scraper.parsers import idealista_pt, imovirtual_pt


# URLs default — por agora só Imovirtual (Idealista tem DataDome anti-bot
# que exige JS rendering; reactivar quando user contratar API oficial paga).
# Cobertura: Lisboa + Porto × apartamento + moradia = 4 buscas × 2 páginas
# = ~140 listings brutos/run (Imovirtual devolve ~35 items/página).
DEFAULT_SEARCH_URLS: List[Dict[str, Any]] = [
    {"portal": "imovirtual_pt", "property_type": "apartamento", "slug": "lisboa", "pages": 2},
    {"portal": "imovirtual_pt", "property_type": "apartamento", "slug": "porto", "pages": 2},
    {"portal": "imovirtual_pt", "property_type": "moradia", "slug": "lisboa", "pages": 2},
    {"portal": "imovirtual_pt", "property_type": "moradia", "slug": "porto", "pages": 2},
]


@dataclass
class ScraperRunResult:
    listings_fetched: int = 0
    listings_classified: int = 0
    opportunities_found: int = 0
    properties_created: int = 0
    properties_updated: int = 0
    price_changes: int = 0
    errors: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "listings_fetched": self.listings_fetched,
            "listings_classified": self.listings_classified,
            "opportunities_found": self.opportunities_found,
            "properties_created": self.properties_created,
            "properties_updated": self.properties_updated,
            "price_changes": self.price_changes,
            "errors": self.errors,
        }


def run_scraper_pipeline(
    organization_id: str,
    tenant_id: Optional[str] = None,
    search_urls: Optional[List[Dict[str, Any]]] = None,
    max_listings: int = 200,
) -> ScraperRunResult:
    """Executa o pipeline completo.

    Args:
        organization_id: obrigatório (multi-tenant isolation)
        tenant_id: para carregar a estratégia activa no classifier
        search_urls: URLs a scrapar. Se None, usa DEFAULT_SEARCH_URLS.
        max_listings: tecto de segurança antes da classificação.
    """
    result = ScraperRunResult()
    urls = search_urls or DEFAULT_SEARCH_URLS

    # 1. Fetch
    all_listings: List[ScrapedListing] = []
    try:
        with RespectfulScraper() as scraper:
            for conf in urls:
                listings = _fetch_portal(scraper, conf)
                all_listings.extend(listings)
                if len(all_listings) >= max_listings:
                    logger.info(
                        f"Scraper: atingido max_listings={max_listings} — parar fetch"
                    )
                    break
    except Exception as e:
        result.errors.append(f"fetch: {type(e).__name__}: {e}")
        logger.exception("Scraper: falha no fetch")

    result.listings_fetched = len(all_listings)
    if not all_listings:
        logger.warning("Scraper: 0 listings obtidos")
        return result

    # 2. Deduplicar fetches desta corrida (mesmo portal pode ter repetição cross-páginas)
    seen: set[tuple[str, str]] = set()
    unique: List[ScrapedListing] = []
    for lst in all_listings:
        key = (lst.source, lst.external_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(lst)

    # 3. Classificar
    try:
        classifier = OpportunityClassifier(tenant_id=tenant_id)
        classifier_input = [
            {"index": i, "text": lst.to_classifier_text(), "group": lst.source}
            for i, lst in enumerate(unique)
        ]
        classifications = classifier.classify_batch(classifier_input)
        result.listings_classified = len(classifications)
    except Exception as e:
        result.errors.append(f"classify: {type(e).__name__}: {e}")
        logger.exception("Scraper: falha no classifier")
        return result

    # 4. Persistir oportunidades (alinhamento por índice — um-para-um)
    classifications_by_index = {c.message_index: c for c in classifications}
    for i, lst in enumerate(unique):
        cls = classifications_by_index.get(i)
        if cls is None:
            continue
        if not cls.is_opportunity:
            continue
        try:
            op = _upsert_property(lst, cls, organization_id, tenant_id)
            result.opportunities_found += 1
            if op == "created":
                result.properties_created += 1
            elif op == "updated":
                result.properties_updated += 1
            elif op == "price_change":
                result.properties_updated += 1
                result.price_changes += 1
        except Exception as e:
            result.errors.append(f"persist {lst.external_id}: {type(e).__name__}: {e}")
            logger.exception(f"Scraper: falha a persistir {lst.source}:{lst.external_id}")

    logger.info(
        f"Scraper done: fetched={result.listings_fetched} "
        f"classified={result.listings_classified} "
        f"opportunities={result.opportunities_found} "
        f"created={result.properties_created} "
        f"updated={result.properties_updated} "
        f"price_changes={result.price_changes} "
        f"errors={len(result.errors)}"
    )
    return result


def _fetch_portal(
    scraper: RespectfulScraper, conf: Dict[str, Any]
) -> List[ScrapedListing]:
    """Expande config → URLs → chama parser correcto."""
    portal = conf["portal"]
    pages = int(conf.get("pages", 1))
    listings: List[ScrapedListing] = []

    if portal == "idealista_pt":
        for page in range(1, pages + 1):
            url = idealista_pt.build_search_url(conf["slug"], page=page)
            listings.extend(idealista_pt.scrape_search_page(scraper, url))
    elif portal == "imovirtual_pt":
        for page in range(1, pages + 1):
            url = imovirtual_pt.build_search_url(
                conf.get("property_type", "apartamento"),
                conf["slug"],
                page=page,
            )
            listings.extend(imovirtual_pt.scrape_search_page(scraper, url))
    else:
        logger.warning(f"Scraper: portal desconhecido '{portal}' — ignorar")

    return listings


def _upsert_property(
    listing: ScrapedListing,
    cls: OpportunityResult,
    organization_id: str,
    tenant_id: Optional[str],
) -> str:
    """Cria ou actualiza um property vindo do scraper.

    Returns:
        'created' | 'updated' | 'price_change'
    """
    existing = db.list_rows(
        "properties",
        filters=(
            f"source=eq.{listing.source}"
            f"&source_external_id=eq.{listing.external_id}"
        ),
        limit=1,
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    price = listing.price or cls.price

    payload = {
        "source": listing.source,
        "source_url": listing.url,
        "source_external_id": listing.external_id,
        "source_confidence": cls.confidence,
        "source_reasoning": cls.reasoning,
        "source_last_seen_at": now_iso,
        "asking_price": price,
        "currency": listing.currency,
        "country": "PT",
        "property_type": listing.property_type or cls.property_type,
        "typology": listing.typology,
        "gross_area_m2": listing.area_m2 or cls.area_m2,
        "bedrooms": listing.bedrooms or cls.bedrooms,
        "district": listing.district or cls.district,
        "municipality": listing.municipality or cls.municipality,
        "parish": listing.parish or cls.parish,
        "address": listing.address,
        "notes": listing.description,
        "status": "lead",
        "is_off_market": False,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    if existing:
        row = existing[0]
        old_price = row.get("asking_price")
        property_id = row["id"]

        db.update("properties", property_id, payload)

        if price and old_price and abs(float(old_price) - float(price)) > 0.5:
            db.insert(
                "property_price_history",
                {
                    "property_id": property_id,
                    "organization_id": organization_id,
                    "old_price": old_price,
                    "new_price": price,
                    "source": listing.source,
                },
            )
            return "price_change"
        return "updated"

    payload["tenant_id"] = tenant_id or db.ensure_tenant()
    payload["organization_id"] = organization_id
    db.insert("properties", payload)
    return "created"
