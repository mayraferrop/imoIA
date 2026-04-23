"""Servico M7 — Marketing Engine.

Logica de negocio para gestao de brand kits, listings, conteudo multilingue,
historico de precos e publicacao multicanal.

Persistencia via Supabase REST (sem SQLAlchemy).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger


def _as_list(value: Any) -> List[Any]:
    """Normaliza campos jsonb que podem chegar como str (double-encoded legacy).

    PostgREST devolve jsonb nativo como list/dict, mas registos antigos foram
    gravados via json.dumps() antes do insert — acabaram como string. Este
    helper tenta fazer o parse seguro; em caso de falha devolve [].
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    return []

# FIXME(jwt-refactor): migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'
from src.database import supabase_rest as db
from src.modules.m7_marketing.content_generator import ContentGenerator

_DEFAULT_TENANT_SLUG = "default"


def _resolve_photo_urls(
    photos: List[Any], cover_only: bool = False
) -> List[Any]:
    """Troca URLs /api/v1/documents/.../download por signed URLs directas.

    Motivação: tags `<img>` não enviam Authorization, logo o endpoint
    protegido devolve 401. Signed URL do Supabase carrega directo, sem auth.

    - `cover_only=True`: resolve apenas a foto de cover (1 req a Supabase por
      listing). Usado em list_listings para evitar N*M requests.
    - `cover_only=False`: resolve todas (paralelizado). Usado em get_listing.

    Em falha por foto, preserva URL original (fallback gracioso).
    """
    target_photos = [p for p in photos if isinstance(p, dict) and p.get("document_id")]
    if cover_only:
        cover = next((p for p in target_photos if p.get("is_cover")), None)
        target_photos = [cover] if cover else (target_photos[:1] if target_photos else [])
    if not target_photos:
        return photos

    try:
        from concurrent.futures import ThreadPoolExecutor
        from src.database.db import get_session
        from src.database.models_v2 import Document
        from src.shared.storage_provider import get_signed_url

        doc_ids = [p["document_id"] for p in target_photos]
        with get_session() as session:
            docs = session.query(Document).filter(Document.id.in_(doc_ids)).all()
            doc_map = {str(d.id): d.file_path for d in docs}

        def _sign(doc_id: str) -> Optional[str]:
            file_path = doc_map.get(doc_id)
            if not file_path or ":" not in file_path:
                return None
            bucket, bucket_path = file_path.split(":", 1)
            try:
                return get_signed_url(bucket, bucket_path, expires_in=3600)
            except Exception as exc:
                logger.warning(f"[photo_urls] signed URL falhou doc={doc_id}: {exc}")
                return None

        # Paralelização: mais rápido que serial para N>2
        url_by_doc: Dict[str, str] = {}
        if len(target_photos) == 1:
            signed = _sign(doc_ids[0])
            if signed:
                url_by_doc[doc_ids[0]] = signed
        else:
            with ThreadPoolExecutor(max_workers=min(10, len(doc_ids))) as ex:
                for doc_id, signed in zip(doc_ids, ex.map(_sign, doc_ids)):
                    if signed:
                        url_by_doc[doc_id] = signed

        resolved = []
        for p in photos:
            if not isinstance(p, dict):
                resolved.append(p)
                continue
            new = dict(p)
            doc_id = new.get("document_id")
            if doc_id and doc_id in url_by_doc:
                new["url"] = url_by_doc[doc_id]
            resolved.append(new)
        return resolved
    except Exception as exc:
        logger.warning(f"[photo_urls] fallback batch doc lookup falhou: {exc}")
        return photos


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_default_tenant() -> str:
    """Garante que o tenant default existe e retorna o id."""
    return db.ensure_tenant()


def _brand_kit_to_dict(bk: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza dict de BrandKit vindo do Supabase."""
    return {
        "id": bk.get("id"),
        "tenant_id": bk.get("tenant_id"),
        "brand_name": bk.get("brand_name"),
        "tagline": bk.get("tagline"),
        "website_url": bk.get("website_url"),
        # Logos
        "logo_primary_url": bk.get("logo_primary_url"),
        "logo_white_url": bk.get("logo_white_url"),
        "logo_icon_url": bk.get("logo_icon_url"),
        # Cores e fontes
        "color_primary": bk.get("color_primary"),
        "color_secondary": bk.get("color_secondary"),
        "color_accent": bk.get("color_accent"),
        "font_heading": bk.get("font_heading"),
        "font_body": bk.get("font_body"),
        "voice_tone": bk.get("voice_tone"),
        "voice_description": bk.get("voice_description"),
        "voice_forbidden_words": bk.get("voice_forbidden_words") or [],
        "voice_preferred_words": bk.get("voice_preferred_words") or [],
        "contact_phone": bk.get("contact_phone"),
        "contact_email": bk.get("contact_email"),
        "contact_whatsapp": bk.get("contact_whatsapp"),
        "social_instagram": bk.get("social_instagram"),
        "social_facebook": bk.get("social_facebook"),
        "social_linkedin": bk.get("social_linkedin"),
        "active_languages": bk.get("active_languages") or ["pt-PT"],
        "template_style": bk.get("template_style"),
        "created_at": bk.get("created_at"),
        "updated_at": bk.get("updated_at"),
    }


def _listing_to_dict(listing: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza dict de Listing vindo do Supabase."""
    return {
        "id": listing.get("id"),
        "tenant_id": listing.get("tenant_id"),
        "deal_id": listing.get("deal_id"),
        # Tipo e preco
        "listing_type": listing.get("listing_type"),
        "listing_price": listing.get("listing_price"),
        "floor_price": listing.get("floor_price"),
        "currency": listing.get("currency"),
        "price_negotiable": listing.get("price_negotiable"),
        "price_on_request": listing.get("price_on_request"),
        # Conteudo PT-PT
        "title_pt": listing.get("title_pt"),
        "description_pt": listing.get("description_pt"),
        "short_description_pt": listing.get("short_description_pt"),
        # Conteudo EN
        "title_en": listing.get("title_en"),
        "description_en": listing.get("description_en"),
        "short_description_en": listing.get("short_description_en"),
        # Conteudo PT-BR
        "title_pt_br": listing.get("title_pt_br"),
        "description_pt_br": listing.get("description_pt_br"),
        # Conteudo FR
        "title_fr": listing.get("title_fr"),
        "description_fr": listing.get("description_fr"),
        # Conteudo ZH
        "title_zh": listing.get("title_zh"),
        "description_zh": listing.get("description_zh"),
        # SEO e destaques
        "highlights": _as_list(listing.get("highlights")),
        "meta_title": listing.get("meta_title"),
        "meta_description": listing.get("meta_description"),
        "keywords": _as_list(listing.get("keywords")),
        "slug": listing.get("slug"),
        # Media
        "photos": _as_list(listing.get("photos")),
        "cover_photo_url": listing.get("cover_photo_url"),
        "video_url": listing.get("video_url"),
        "virtual_tour_url": listing.get("virtual_tour_url"),
        # Conteudo por canal
        "content_whatsapp": listing.get("content_whatsapp"),
        "content_instagram_post": listing.get("content_instagram_post"),
        "content_facebook_post": listing.get("content_facebook_post"),
        "content_linkedin": listing.get("content_linkedin"),
        "content_portal": listing.get("content_portal"),
        "content_email_subject": listing.get("content_email_subject"),
        "content_email_body": listing.get("content_email_body"),
        # Estado
        "status": listing.get("status"),
        # Habta
        "habta_published": listing.get("habta_published"),
        "habta_project_id": listing.get("habta_project_id"),
        "habta_url": listing.get("habta_url"),
        "habta_published_at": listing.get("habta_published_at"),
        "habta_last_synced_at": listing.get("habta_last_synced_at"),
        # WhatsApp
        "whatsapp_sent": listing.get("whatsapp_sent"),
        "whatsapp_sent_at": listing.get("whatsapp_sent_at"),
        "whatsapp_groups_sent": _as_list(listing.get("whatsapp_groups_sent")),
        "published_at": listing.get("published_at"),
        # Metricas
        "days_on_market": listing.get("days_on_market"),
        "total_views": listing.get("total_views"),
        "total_contacts": listing.get("total_contacts"),
        "total_proposals": listing.get("total_proposals"),
        # Meta
        "notes": listing.get("notes"),
        "created_at": listing.get("created_at"),
        "updated_at": listing.get("updated_at"),
    }


def _price_history_to_dict(ph: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza dict de ListingPriceHistory vindo do Supabase."""
    return {
        "id": ph.get("id"),
        "listing_id": ph.get("listing_id"),
        "old_price": ph.get("old_price"),
        "new_price": ph.get("new_price"),
        "reason": ph.get("reason"),
        "changed_by": ph.get("changed_by"),
        "created_at": ph.get("created_at"),
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MarketingService:
    """Logica de negocio do M7 — Marketing Engine."""

    # --- Brand Kit ---

    def get_brand_kit(self, tenant_id: str = "default") -> Optional[Dict[str, Any]]:
        """Retorna o brand kit de um tenant.

        Parametros
        ----------
        tenant_id:
            ID ou slug do tenant. Se 'default', resolve o ID automaticamente.

        Retorna
        -------
        Dict com os dados do brand kit ou None se nao existir.
        """
        resolved_id = self._resolve_tenant_id(tenant_id)
        if not resolved_id:
            return None

        rows = db.list_rows(
            "brand_kits",
            filters=f"tenant_id=eq.{resolved_id}",
            limit=1,
        )
        return _brand_kit_to_dict(rows[0]) if rows else None

    def create_or_update_brand_kit(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria ou actualiza o brand kit (upsert por tenant_id).

        Parametros
        ----------
        data:
            Dados do brand kit. Requer 'tenant_id' ou usa o tenant default.

        Retorna
        -------
        Dict com os dados do brand kit criado/actualizado.
        """
        tenant_id = data.get("tenant_id")
        if not tenant_id:
            tenant_id = _ensure_default_tenant()

        rows = db.list_rows(
            "brand_kits",
            filters=f"tenant_id=eq.{tenant_id}",
            limit=1,
        )

        updatable_fields = (
            "brand_name", "tagline", "website_url",
            "color_primary", "color_secondary", "color_accent",
            "font_heading", "font_body",
            "voice_tone", "voice_description",
            "voice_forbidden_words", "voice_preferred_words",
            "contact_phone", "contact_email", "contact_whatsapp",
            "social_instagram", "social_facebook", "social_linkedin",
            "active_languages", "template_style",
        )

        if not rows:
            # Criar
            row_data = {
                "id": db.new_id(),
                "tenant_id": tenant_id,
                "brand_name": data.get("brand_name", "ImoIA"),
            }
            for field in updatable_fields:
                if field in data:
                    row_data[field] = data[field]
            bk = db.insert("brand_kits", row_data)
            logger.info(f"BrandKit criado para tenant {tenant_id}")
        else:
            # Actualizar
            update_data = {}
            for field in updatable_fields:
                if field in data:
                    update_data[field] = data[field]
            bk = db.update("brand_kits", rows[0]["id"], update_data) if update_data else rows[0]
            logger.info(f"BrandKit actualizado para tenant {tenant_id}")

        return _brand_kit_to_dict(bk)

    # --- Listings ---

    def create_listing(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria um Listing a partir de um deal.

        Obtem informacao da property associada ao deal para popular campos
        automaticamente. Opcionalmente gera conteudo IA se auto_generate=True.

        Parametros
        ----------
        deal_id:
            ID do deal.
        data:
            Dados adicionais do listing (listing_type, listing_price, etc.).

        Retorna
        -------
        Dict com os dados do listing criado.
        """
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        tenant_id = deal.get("tenant_id")

        # Determinar preco de listagem
        listing_type = data.get("listing_type", "venda")
        if listing_type == "arrendamento":
            listing_price = data.get("listing_price") or deal.get("monthly_rent")
        else:
            listing_price = (
                data.get("listing_price")
                or deal.get("target_sale_price")
                or deal.get("purchase_price")
            )

        if not listing_price:
            raise ValueError("listing_price e obrigatorio (ou definir target_sale_price/monthly_rent no deal)")

        listing_id = db.new_id()
        listing = db.insert("listings", {
            "id": listing_id,
            "tenant_id": tenant_id,
            "deal_id": deal_id,
            "listing_type": listing_type,
            "listing_price": float(listing_price),
            "floor_price": data.get("floor_price"),
            "currency": data.get("currency", "EUR"),
            "price_negotiable": data.get("price_negotiable", True),
            "price_on_request": data.get("price_on_request", False),
            "habta_published": False,
            "whatsapp_sent": False,
            "days_on_market": 0,
            "total_views": 0,
            "total_contacts": 0,
            "total_proposals": 0,
            "highlights": data.get("highlights", []),
            "notes": data.get("notes"),
            "status": "draft",
        })

        logger.info(
            f"Listing {listing_id} criado para deal {deal_id} "
            f"({listing_type}, {listing_price} EUR)"
        )
        result = _listing_to_dict(listing)

        # Gerar conteudo IA se solicitado
        if data.get("auto_generate", False):
            try:
                generator = ContentGenerator()
                languages = data.get("languages")
                generator.generate_all_content(listing_id, languages=languages)
                logger.info(f"Conteudo gerado automaticamente para listing {listing_id}")
            except Exception as exc:
                logger.warning(f"Erro na geracao automatica de conteudo: {exc}")

        return result

    def create_listing_in_session(
        self,
        deal: Dict[str, Any],
        target_status: str,
    ) -> Dict[str, Any]:
        """Cria listing (chamado pelo hook do M4).

        Determina o tipo de listing com base no target_status do deal:
        - 'em_venda' -> listing_type='venda'
        - 'arrendamento' -> listing_type='arrendamento'
        - 'marketing_activo' -> listing_type='venda'

        Usa deal.target_sale_price ou deal.monthly_rent como preco de listagem.

        Parametros
        ----------
        deal:
            Dict do deal para o qual criar o listing.
        target_status:
            Novo estado do deal que despoleta a criacao do listing.

        Retorna
        -------
        Dict com os dados do listing criado.
        """
        deal_id = deal.get("id") or deal.get("deal_id")

        # Verificar se ja existe listing activo para este deal
        existing = db.list_rows(
            "listings",
            filters=(
                f"deal_id=eq.{deal_id}"
                "&status=not.in.(vendido,arrendado,cancelado)"
            ),
            limit=1,
        )

        if existing:
            logger.warning(
                f"Listing ja existe para deal {deal_id}: {existing[0]['id']}"
            )
            return _listing_to_dict(existing[0])

        # Determinar tipo e preco
        if target_status == "arrendamento":
            listing_type = "arrendamento"
            listing_price = deal.get("monthly_rent")
        else:
            # em_venda, marketing_activo
            listing_type = "venda"
            listing_price = deal.get("target_sale_price")

        if not listing_price:
            logger.warning(
                f"Listing nao criado para deal {deal_id}: preco nao definido"
            )
            return {}

        # Herdar fotos da property associada ao deal (M1 -> M7)
        # Se o utilizador cadastrou fotos em M1, o listing nasce com elas.
        inherited_photos: List[Dict[str, Any]] = []
        inherited_cover: Optional[str] = None
        property_id = deal.get("property_id")
        if property_id:
            prop = db.get_by_id("properties", property_id)
            if prop:
                inherited_photos = _as_list(prop.get("photos"))
                inherited_cover = prop.get("cover_photo_url")

        listing_id = db.new_id()
        listing_row: Dict[str, Any] = {
            "id": listing_id,
            "tenant_id": deal.get("tenant_id"),
            "deal_id": deal_id,
            "listing_type": listing_type,
            "listing_price": float(listing_price),
            "currency": "EUR",
            "price_negotiable": True,
            "price_on_request": False,
            "status": "draft",
            "photos": inherited_photos,
            "habta_published": False,
            "whatsapp_sent": False,
            "days_on_market": 0,
            "total_views": 0,
            "total_contacts": 0,
            "total_proposals": 0,
        }
        if inherited_cover:
            listing_row["cover_photo_url"] = inherited_cover

        listing = db.insert("listings", listing_row)

        logger.info(
            f"Listing {listing_id} criado para deal {deal_id} "
            f"({listing_type}, {listing_price} EUR, trigger: {target_status}, "
            f"{len(inherited_photos)} fotos herdadas da property {property_id or 'n/a'})"
        )
        return _listing_to_dict(listing)

    def get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Retorna um listing completo por ID.

        Resolve signed URLs directas para fotos (elimina redirect 302 do
        endpoint /documents/{id}/download — cada <img> vai directo a Supabase).
        Só no detalhe porque em listagens o custo N*signed URL é proibitivo.
        """
        listing = db.get_by_id("listings", listing_id)
        if not listing:
            return None
        result = _listing_to_dict(listing)
        result["photos"] = _resolve_photo_urls(result["photos"])
        return result

    def get_listing_by_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Retorna listing associada a um deal."""
        rows = db.list_rows(
            "listings",
            filters=f"deal_id=eq.{deal_id}",
            limit=1,
        )
        return _listing_to_dict(rows[0]) if rows else None

    def list_listings(
        self,
        status: Optional[str] = None,
        listing_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Lista listings com filtros e paginacao.

        Parametros
        ----------
        status:
            Filtro por estado (ex: 'draft', 'aprovado', 'publicado').
        listing_type:
            Filtro por tipo (ex: 'venda', 'arrendamento').
        limit:
            Numero maximo de resultados.
        offset:
            Deslocamento para paginacao.

        Retorna
        -------
        Dict com total, limit, offset e items.
        """
        filter_parts = []
        if status:
            filter_parts.append(f"status=eq.{status}")
        if listing_type:
            filter_parts.append(f"listing_type=eq.{listing_type}")
        filters = "&".join(filter_parts)

        result = db.list_with_count(
            "listings",
            filters=filters,
            order="updated_at.desc",
            limit=limit,
            offset=offset,
        )
        items = [_listing_to_dict(lst) for lst in result["items"]]
        # Resolver apenas a foto de cover de cada listing (1 signed URL/listing)
        # para que os thumbs dos cards carreguem sem passar pelo backend.
        for item in items:
            item["photos"] = _resolve_photo_urls(item["photos"], cover_only=True)
        return {
            "total": result["total"],
            "limit": limit,
            "offset": offset,
            "items": items,
        }

    def update_listing(
        self, listing_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Actualiza campos de um listing.

        Parametros
        ----------
        listing_id:
            ID do listing.
        data:
            Campos a actualizar.

        Retorna
        -------
        Dict com o listing actualizado ou None se nao existir.
        """
        listing = db.get_by_id("listings", listing_id)
        if not listing:
            return None

        # Filtrar apenas campos validos
        update_data = {k: v for k, v in data.items() if k != "id"}
        if update_data:
            listing = db.update("listings", listing_id, update_data)

        logger.info(f"Listing {listing_id} actualizado: {list(data.keys())}")
        return _listing_to_dict(listing)

    # --- Geracao de conteudo ---

    def generate_content(
        self, listing_id: str, languages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Delega a geracao de conteudo ao ContentGenerator.

        Parametros
        ----------
        listing_id:
            ID do listing.
        languages:
            Lista de codigos de idioma. Se None, usa os idiomas do brand kit.

        Retorna
        -------
        Dict com conteudo gerado por idioma.
        """
        generator = ContentGenerator()
        return generator.generate_all_content(listing_id, languages=languages)

    def approve_content(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Aprova o conteudo de um listing, passando o estado para 'aprovado'.

        Parametros
        ----------
        listing_id:
            ID do listing.

        Retorna
        -------
        Dict com o listing actualizado ou None se nao existir.
        """
        listing = db.get_by_id("listings", listing_id)
        if not listing:
            return None

        listing = db.update("listings", listing_id, {"status": "aprovado"})
        logger.info(f"Listing {listing_id} aprovado")
        return _listing_to_dict(listing)

    # --- Preco ---

    def change_price(
        self,
        listing_id: str,
        new_price: float,
        reason: Optional[str] = None,
        changed_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Altera o preco de um listing e regista o historico.

        Parametros
        ----------
        listing_id:
            ID do listing.
        new_price:
            Novo preco de listagem.
        reason:
            Motivo da alteracao de preco.
        changed_by:
            Identificador do utilizador que fez a alteracao.

        Retorna
        -------
        Dict com o listing actualizado ou None se nao existir.
        """
        listing = db.get_by_id("listings", listing_id)
        if not listing:
            return None

        old_price = listing.get("listing_price")

        # Registar historico
        db.insert("listing_price_history", {
            "id": db.new_id(),
            "listing_id": listing_id,
            "old_price": old_price,
            "new_price": new_price,
            "reason": reason,
            "changed_by": changed_by or "user",
        })

        listing = db.update("listings", listing_id, {"listing_price": new_price})

        logger.info(
            f"Listing {listing_id}: preco alterado "
            f"{old_price} -> {new_price} EUR"
        )
        return _listing_to_dict(listing)

    def get_price_history(self, listing_id: str) -> List[Dict[str, Any]]:
        """Retorna historico de precos de um listing.

        Parametros
        ----------
        listing_id:
            ID do listing.

        Retorna
        -------
        Lista de registos de historico de precos.
        """
        items = db.list_rows(
            "listing_price_history",
            filters=f"listing_id=eq.{listing_id}",
            order="created_at.desc",
        )
        return [_price_history_to_dict(ph) for ph in items]

    # --- Estado final ---

    def mark_as_sold(
        self, listing_id: str, sale_price: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Marca um listing como vendido.

        Parametros
        ----------
        listing_id:
            ID do listing.
        sale_price:
            Preco de venda final (opcional, actualiza listing_price se fornecido).

        Retorna
        -------
        Dict com o listing actualizado ou None se nao existir.
        """
        listing = db.get_by_id("listings", listing_id)
        if not listing:
            return None

        update_data: Dict[str, Any] = {"status": "vendido"}

        if sale_price is not None:
            old_price = listing.get("listing_price")
            update_data["listing_price"] = sale_price
            db.insert("listing_price_history", {
                "id": db.new_id(),
                "listing_id": listing_id,
                "old_price": old_price,
                "new_price": sale_price,
                "reason": "Preco de venda final",
                "changed_by": "system",
            })

        listing = db.update("listings", listing_id, update_data)
        logger.info(f"Listing {listing_id} marcado como vendido")
        return _listing_to_dict(listing)

    def mark_as_rented(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Marca um listing como arrendado.

        Parametros
        ----------
        listing_id:
            ID do listing.

        Retorna
        -------
        Dict com o listing actualizado ou None se nao existir.
        """
        listing = db.get_by_id("listings", listing_id)
        if not listing:
            return None

        listing = db.update("listings", listing_id, {"status": "arrendado"})
        logger.info(f"Listing {listing_id} marcado como arrendado")
        return _listing_to_dict(listing)

    # --- Publicacao (stubs) ---

    def publish_to_habta(self, listing_id: str) -> Dict[str, Any]:
        """Publica um listing no portal Habta.

        TODO: implementar publisher Habta.

        Parametros
        ----------
        listing_id:
            ID do listing a publicar.

        Retorna
        -------
        Dict com resultado da publicacao (placeholder).
        """
        logger.info(f"TODO: implement publisher — publish_to_habta({listing_id})")
        return {
            "listing_id": listing_id,
            "status": "pending",
            "message": "TODO: implement Habta publisher",
            "habta_url": None,
        }

    def send_to_whatsapp(
        self, listing_id: str, group_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Envia o conteudo de um listing para grupos de WhatsApp.

        TODO: implementar publisher WhatsApp.

        Parametros
        ----------
        listing_id:
            ID do listing a enviar.
        group_ids:
            Lista de IDs de grupos WhatsApp (opcional).

        Retorna
        -------
        Dict com resultado do envio (placeholder).
        """
        logger.info(
            f"TODO: implement publisher — send_to_whatsapp({listing_id}, {group_ids})"
        )
        return {
            "listing_id": listing_id,
            "status": "pending",
            "message": "TODO: implement WhatsApp publisher",
            "groups_sent": [],
        }

    # --- Estatisticas ---

    def get_marketing_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas globais de marketing.

        Inclui: listings activos, valor total, dias no mercado (media),
        total de visualizacoes e total de contactos.

        Retorna
        -------
        Dict com as estatisticas.
        """
        listings = db.list_rows(
            "listings",
            filters="status=in.(draft,aprovado,publicado)",
            limit=1000,
        )

        total_value = sum(lst.get("listing_price", 0) or 0 for lst in listings)
        avg_days = (
            round(
                sum(lst.get("days_on_market", 0) or 0 for lst in listings) / len(listings), 1
            )
            if listings
            else 0.0
        )
        total_views = sum(lst.get("total_views", 0) or 0 for lst in listings)
        total_contacts = sum(lst.get("total_contacts", 0) or 0 for lst in listings)

        # Distribuicao por tipo
        by_type: Dict[str, int] = {}
        for lst in listings:
            lt = lst.get("listing_type", "unknown")
            by_type[lt] = by_type.get(lt, 0) + 1

        # Distribuicao por estado
        by_status: Dict[str, int] = {}
        for lst in listings:
            st = lst.get("status", "unknown")
            by_status[st] = by_status.get(st, 0) + 1

        return {
            "active_listings": len(listings),
            "total_value": total_value,
            "avg_days_on_market": avg_days,
            "total_views": total_views,
            "total_contacts": total_contacts,
            "by_type": by_type,
            "by_status": by_status,
        }

    # --- Hook M4 ---

    def handle_deal_advance(
        self,
        deal: Dict[str, Any],
        new_status: str,
    ) -> None:
        """Chamado pelo M4 quando um deal avanca de estado.

        Cria ou actualiza listings com base no novo estado:
        - 'em_venda' -> cria listing do tipo 'venda'
        - 'arrendamento' -> cria listing do tipo 'arrendamento'
        - 'marketing_activo' -> cria/activa listing do tipo 'venda'
        - 'cpcv_venda' -> sem accao (listing ja criado)
        - 'escritura_venda' -> marca listing como vendido

        Parametros
        ----------
        deal:
            Dict do deal que avancou de estado.
        new_status:
            Novo estado do deal.
        """
        deal_id = deal.get("id") or deal.get("deal_id")
        try:
            if new_status in ("em_venda", "arrendamento", "marketing_activo"):
                result = self.create_listing_in_session(deal, new_status)
                if result:
                    logger.info(
                        f"M7: Listing criado para deal {deal_id} "
                        f"(trigger: {new_status})"
                    )

            elif new_status == "escritura_venda":
                # Marcar listing activo como vendido
                existing = db.list_rows(
                    "listings",
                    filters=(
                        f"deal_id=eq.{deal_id}"
                        "&status=not.in.(vendido,arrendado,cancelado)"
                    ),
                    limit=1,
                )

                if existing:
                    update_data: Dict[str, Any] = {"status": "vendido"}
                    sale_price = deal.get("actual_sale_price") or deal.get("target_sale_price")
                    if sale_price:
                        update_data["listing_price"] = sale_price
                    db.update("listings", existing[0]["id"], update_data)
                    logger.info(
                        f"M7: Listing {existing[0]['id']} marcado como vendido "
                        f"(deal {deal_id}, escritura)"
                    )

            elif new_status == "cpcv_venda":
                # Sem accao especifica no M7; listing continua activo
                logger.debug(
                    f"M7: CPCV assinado para deal {deal_id} — "
                    f"listing permanece activo"
                )

        except Exception as exc:
            logger.warning(
                f"M7 handle_deal_advance erro (deal {deal_id}, "
                f"status {new_status}): {exc}"
            )

    def handle_deal_advance_rest(
        self,
        deal_id: str,
        new_status: str,
    ) -> None:
        """Variante REST chamada pelo M4: busca o deal e delega em handle_deal_advance."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            logger.warning(f"M7: deal {deal_id} nao encontrado para hook {new_status}")
            return
        self.handle_deal_advance(deal, new_status)

    # --- Helpers privados ---

    def _resolve_tenant_id(self, tenant_id: str) -> Optional[str]:
        """Resolve o ID de um tenant a partir do ID ou slug."""
        if tenant_id == _DEFAULT_TENANT_SLUG or len(tenant_id) != 36:
            # Pode ser um slug — procurar por slug ou id
            rows = db._get(
                "tenants",
                f"or=(slug.eq.{tenant_id},id.eq.{tenant_id})&limit=1",
            )
            return rows[0]["id"] if rows else None
        return tenant_id
