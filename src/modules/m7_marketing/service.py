"""Servico M7 — Marketing Engine.

Logica de negocio para gestao de brand kits, listings, conteudo multilingue,
historico de precos e publicacao multicanal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.db import get_session
from src.database.models_v2 import (
    BrandKit,
    Deal,
    Listing,
    ListingContent,
    ListingPriceHistory,
    Property,
    Tenant,
)
from src.modules.m7_marketing.content_generator import ContentGenerator

_DEFAULT_TENANT_SLUG = "default"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_default_tenant(session: Session) -> str:
    """Garante que o tenant default existe e retorna o id."""
    tenant = session.execute(
        select(Tenant).where(Tenant.slug == _DEFAULT_TENANT_SLUG)
    ).scalar_one_or_none()

    if tenant is None:
        tenant = Tenant(
            id=str(uuid4()),
            name="ImoIA",
            slug=_DEFAULT_TENANT_SLUG,
            country="PT",
        )
        session.add(tenant)
        session.flush()
        logger.info("Tenant default criado")

    return tenant.id


def _brand_kit_to_dict(bk: BrandKit) -> Dict[str, Any]:
    """Serializa BrandKit para dict."""
    return {
        "id": bk.id,
        "tenant_id": bk.tenant_id,
        "brand_name": bk.brand_name,
        "tagline": bk.tagline,
        "website_url": bk.website_url,
        # Logos
        "logo_primary_url": bk.logo_primary_url,
        "logo_white_url": bk.logo_white_url,
        "logo_icon_url": bk.logo_icon_url,
        # Cores e fontes
        "color_primary": bk.color_primary,
        "color_secondary": bk.color_secondary,
        "color_accent": bk.color_accent,
        "font_heading": bk.font_heading,
        "font_body": bk.font_body,
        "voice_tone": bk.voice_tone,
        "voice_description": bk.voice_description,
        "voice_forbidden_words": bk.voice_forbidden_words or [],
        "voice_preferred_words": bk.voice_preferred_words or [],
        "contact_phone": bk.contact_phone,
        "contact_email": bk.contact_email,
        "contact_whatsapp": bk.contact_whatsapp,
        "social_instagram": bk.social_instagram,
        "social_facebook": bk.social_facebook,
        "social_linkedin": bk.social_linkedin,
        "active_languages": bk.active_languages or ["pt-PT"],
        "template_style": bk.template_style,
        "created_at": bk.created_at.isoformat() if bk.created_at else None,
        "updated_at": bk.updated_at.isoformat() if bk.updated_at else None,
    }


def _listing_to_dict(listing: Listing) -> Dict[str, Any]:
    """Serializa Listing para dict (todos os campos)."""
    return {
        "id": listing.id,
        "tenant_id": listing.tenant_id,
        "deal_id": listing.deal_id,
        # Tipo e preco
        "listing_type": listing.listing_type,
        "listing_price": listing.listing_price,
        "floor_price": listing.floor_price,
        "currency": listing.currency,
        "price_negotiable": listing.price_negotiable,
        "price_on_request": listing.price_on_request,
        # Conteudo PT-PT
        "title_pt": listing.title_pt,
        "description_pt": listing.description_pt,
        "short_description_pt": listing.short_description_pt,
        # Conteudo EN
        "title_en": listing.title_en,
        "description_en": listing.description_en,
        "short_description_en": listing.short_description_en,
        # Conteudo PT-BR
        "title_pt_br": listing.title_pt_br,
        "description_pt_br": listing.description_pt_br,
        # Conteudo FR
        "title_fr": listing.title_fr,
        "description_fr": listing.description_fr,
        # Conteudo ZH
        "title_zh": listing.title_zh,
        "description_zh": listing.description_zh,
        # SEO e destaques
        "highlights": listing.highlights or [],
        "meta_title": listing.meta_title,
        "meta_description": listing.meta_description,
        "keywords": listing.keywords or [],
        "slug": listing.slug,
        # Media
        "photos": listing.photos or [],
        "cover_photo_url": listing.cover_photo_url,
        "video_url": listing.video_url,
        "virtual_tour_url": listing.virtual_tour_url,
        # Conteudo por canal
        "content_whatsapp": listing.content_whatsapp,
        "content_instagram_post": listing.content_instagram_post,
        "content_facebook_post": listing.content_facebook_post,
        "content_linkedin": listing.content_linkedin,
        "content_portal": listing.content_portal,
        "content_email_subject": listing.content_email_subject,
        "content_email_body": listing.content_email_body,
        # Estado
        "status": listing.status,
        # Habta
        "habta_published": listing.habta_published,
        "habta_project_id": listing.habta_project_id,
        "habta_url": listing.habta_url,
        "habta_published_at": (
            listing.habta_published_at.isoformat()
            if listing.habta_published_at
            else None
        ),
        "habta_last_synced_at": (
            listing.habta_last_synced_at.isoformat()
            if listing.habta_last_synced_at
            else None
        ),
        # WhatsApp
        "whatsapp_sent": listing.whatsapp_sent,
        "whatsapp_sent_at": (
            listing.whatsapp_sent_at.isoformat()
            if listing.whatsapp_sent_at
            else None
        ),
        "whatsapp_groups_sent": listing.whatsapp_groups_sent or [],
        "published_at": (
            listing.published_at.isoformat() if listing.published_at else None
        ),
        # Metricas
        "days_on_market": listing.days_on_market,
        "total_views": listing.total_views,
        "total_contacts": listing.total_contacts,
        "total_proposals": listing.total_proposals,
        # Meta
        "notes": listing.notes,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
        "updated_at": listing.updated_at.isoformat() if listing.updated_at else None,
    }


def _price_history_to_dict(ph: ListingPriceHistory) -> Dict[str, Any]:
    """Serializa ListingPriceHistory para dict."""
    return {
        "id": ph.id,
        "listing_id": ph.listing_id,
        "old_price": ph.old_price,
        "new_price": ph.new_price,
        "reason": ph.reason,
        "changed_by": ph.changed_by,
        "created_at": ph.created_at.isoformat() if ph.created_at else None,
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
        with get_session() as session:
            # Resolver slug para ID se necessario
            resolved_id = self._resolve_tenant_id(session, tenant_id)
            if not resolved_id:
                return None

            bk = session.execute(
                select(BrandKit).where(BrandKit.tenant_id == resolved_id)
            ).scalar_one_or_none()

            return _brand_kit_to_dict(bk) if bk else None

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
        with get_session() as session:
            tenant_id = data.get("tenant_id")
            if not tenant_id:
                tenant_id = _ensure_default_tenant(session)

            bk = session.execute(
                select(BrandKit).where(BrandKit.tenant_id == tenant_id)
            ).scalar_one_or_none()

            if bk is None:
                bk = BrandKit(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    brand_name=data.get("brand_name", "ImoIA"),
                )
                session.add(bk)
                logger.info(f"BrandKit criado para tenant {tenant_id}")
            else:
                logger.info(f"BrandKit actualizado para tenant {tenant_id}")

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
            for field in updatable_fields:
                if field in data:
                    setattr(bk, field, data[field])

            session.flush()
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
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            prop = session.get(Property, deal.property_id)
            tenant_id = deal.tenant_id

            # Determinar preco de listagem
            listing_type = data.get("listing_type", "venda")
            if listing_type == "arrendamento":
                listing_price = data.get("listing_price") or deal.monthly_rent
            else:
                listing_price = (
                    data.get("listing_price")
                    or deal.target_sale_price
                    or deal.purchase_price
                )

            if not listing_price:
                raise ValueError("listing_price e obrigatorio (ou definir target_sale_price/monthly_rent no deal)")

            listing = Listing(
                id=str(uuid4()),
                tenant_id=tenant_id,
                deal_id=deal_id,
                listing_type=listing_type,
                listing_price=float(listing_price),
                floor_price=data.get("floor_price"),
                currency=data.get("currency", "EUR"),
                price_negotiable=data.get("price_negotiable", True),
                price_on_request=data.get("price_on_request", False),
                highlights=data.get("highlights", []),
                notes=data.get("notes"),
                status="draft",
            )
            session.add(listing)
            session.flush()

            logger.info(
                f"Listing {listing.id} criado para deal {deal_id} "
                f"({listing_type}, {listing_price} EUR)"
            )
            result = _listing_to_dict(listing)

        # Gerar conteudo IA se solicitado (fora da sessao para evitar lock)
        if data.get("auto_generate", False):
            try:
                generator = ContentGenerator()
                languages = data.get("languages")
                generator.generate_all_content(listing.id, languages=languages)
                logger.info(f"Conteudo gerado automaticamente para listing {listing.id}")
            except Exception as exc:
                logger.warning(f"Erro na geracao automatica de conteudo: {exc}")

        return result

    def create_listing_in_session(
        self,
        session: Session,
        deal: Deal,
        target_status: str,
    ) -> Dict[str, Any]:
        """Cria listing usando sessao existente (chamado pelo hook do M4).

        Determina o tipo de listing com base no target_status do deal:
        - 'em_venda' → listing_type='venda'
        - 'arrendamento' → listing_type='arrendamento'
        - 'marketing_activo' → listing_type='venda'

        Usa deal.target_sale_price ou deal.monthly_rent como preco de listagem.

        Parametros
        ----------
        session:
            Sessao SQLAlchemy existente.
        deal:
            Deal para o qual criar o listing.
        target_status:
            Novo estado do deal que despoleta a criacao do listing.

        Retorna
        -------
        Dict com os dados do listing criado.
        """
        # Verificar se ja existe listing activo para este deal
        existing = session.execute(
            select(Listing).where(
                Listing.deal_id == deal.id,
                Listing.status.notin_(["vendido", "arrendado", "cancelado"]),
            )
        ).scalar_one_or_none()

        if existing:
            logger.warning(
                f"Listing ja existe para deal {deal.id}: {existing.id}"
            )
            return _listing_to_dict(existing)

        # Determinar tipo e preco
        if target_status == "arrendamento":
            listing_type = "arrendamento"
            listing_price = deal.monthly_rent
        else:
            # em_venda, marketing_activo
            listing_type = "venda"
            listing_price = deal.target_sale_price

        if not listing_price:
            logger.warning(
                f"Listing nao criado para deal {deal.id}: preco nao definido"
            )
            return {}

        listing = Listing(
            id=str(uuid4()),
            tenant_id=deal.tenant_id,
            deal_id=deal.id,
            listing_type=listing_type,
            listing_price=float(listing_price),
            currency="EUR",
            price_negotiable=True,
            status="draft",
        )
        session.add(listing)
        session.flush()

        logger.info(
            f"Listing {listing.id} criado em sessao para deal {deal.id} "
            f"({listing_type}, {listing_price} EUR, trigger: {target_status})"
        )
        return _listing_to_dict(listing)

    def get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Retorna um listing completo por ID."""
        with get_session() as session:
            listing = session.get(Listing, listing_id)
            return _listing_to_dict(listing) if listing else None

    def get_listing_by_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Retorna listing associada a um deal."""
        with get_session() as session:
            listing = session.execute(
                select(Listing).where(Listing.deal_id == deal_id)
            ).scalar_one_or_none()
            return _listing_to_dict(listing) if listing else None

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
        with get_session() as session:
            stmt = select(Listing)

            if status:
                stmt = stmt.where(Listing.status == status)
            if listing_type:
                stmt = stmt.where(Listing.listing_type == listing_type)

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = session.execute(count_stmt).scalar() or 0

            stmt = stmt.order_by(Listing.updated_at.desc())
            stmt = stmt.offset(offset).limit(limit)

            listings = session.execute(stmt).scalars().all()
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": [_listing_to_dict(lst) for lst in listings],
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
        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                return None

            for field_name, value in data.items():
                if hasattr(listing, field_name):
                    setattr(listing, field_name, value)

            session.flush()
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
        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                return None

            listing.status = "aprovado"
            session.flush()
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
        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                return None

            old_price = listing.listing_price

            history = ListingPriceHistory(
                id=str(uuid4()),
                listing_id=listing_id,
                old_price=old_price,
                new_price=new_price,
                reason=reason,
                changed_by=changed_by or "user",
            )
            session.add(history)

            listing.listing_price = new_price
            session.flush()

            logger.info(
                f"Listing {listing_id}: preco alterado "
                f"{old_price} → {new_price} EUR"
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
        with get_session() as session:
            stmt = (
                select(ListingPriceHistory)
                .where(ListingPriceHistory.listing_id == listing_id)
                .order_by(ListingPriceHistory.created_at.desc())
            )
            items = session.execute(stmt).scalars().all()
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
        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                return None

            if sale_price is not None:
                old_price = listing.listing_price
                listing.listing_price = sale_price
                history = ListingPriceHistory(
                    id=str(uuid4()),
                    listing_id=listing_id,
                    old_price=old_price,
                    new_price=sale_price,
                    reason="Preco de venda final",
                    changed_by="system",
                )
                session.add(history)

            listing.status = "vendido"
            session.flush()
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
        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                return None

            listing.status = "arrendado"
            session.flush()
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
        with get_session() as session:
            active_statuses = ("draft", "aprovado", "publicado")
            stmt = select(Listing).where(Listing.status.in_(active_statuses))
            listings = session.execute(stmt).scalars().all()

            total_value = sum(lst.listing_price for lst in listings)
            avg_days = (
                round(
                    sum(lst.days_on_market for lst in listings) / len(listings), 1
                )
                if listings
                else 0.0
            )
            total_views = sum(lst.total_views for lst in listings)
            total_contacts = sum(lst.total_contacts for lst in listings)

            # Distribuicao por tipo
            by_type: Dict[str, int] = {}
            for lst in listings:
                by_type[lst.listing_type] = by_type.get(lst.listing_type, 0) + 1

            # Distribuicao por estado
            by_status: Dict[str, int] = {}
            for lst in listings:
                by_status[lst.status] = by_status.get(lst.status, 0) + 1

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
        session: Session,
        deal: Deal,
        new_status: str,
    ) -> None:
        """Chamado pelo M4 quando um deal avanca de estado.

        Cria ou actualiza listings com base no novo estado:
        - 'em_venda' → cria listing do tipo 'venda'
        - 'arrendamento' → cria listing do tipo 'arrendamento'
        - 'marketing_activo' → cria/activa listing do tipo 'venda'
        - 'cpcv_venda' → sem accao (listing ja criado)
        - 'escritura_venda' → marca listing como vendido

        Parametros
        ----------
        session:
            Sessao SQLAlchemy existente.
        deal:
            Deal que avancou de estado.
        new_status:
            Novo estado do deal.
        """
        try:
            if new_status in ("em_venda", "arrendamento", "marketing_activo"):
                result = self.create_listing_in_session(session, deal, new_status)
                if result:
                    logger.info(
                        f"M7: Listing criado para deal {deal.id} "
                        f"(trigger: {new_status})"
                    )

            elif new_status == "escritura_venda":
                # Marcar listing activo como vendido
                existing = session.execute(
                    select(Listing).where(
                        Listing.deal_id == deal.id,
                        Listing.status.notin_(["vendido", "arrendado", "cancelado"]),
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.status = "vendido"
                    sale_price = deal.actual_sale_price or deal.target_sale_price
                    if sale_price:
                        existing.listing_price = sale_price
                    session.flush()
                    logger.info(
                        f"M7: Listing {existing.id} marcado como vendido "
                        f"(deal {deal.id}, escritura)"
                    )

            elif new_status == "cpcv_venda":
                # Sem accao especifica no M7; listing continua activo
                logger.debug(
                    f"M7: CPCV assinado para deal {deal.id} — "
                    f"listing permanece activo"
                )

        except Exception as exc:
            logger.warning(
                f"M7 handle_deal_advance erro (deal {deal.id}, "
                f"status {new_status}): {exc}"
            )

    # --- Helpers privados ---

    def _resolve_tenant_id(
        self, session: Session, tenant_id: str
    ) -> Optional[str]:
        """Resolve o ID de um tenant a partir do ID ou slug."""
        if tenant_id == _DEFAULT_TENANT_SLUG or len(tenant_id) != 36:
            # Pode ser um slug
            tenant = session.execute(
                select(Tenant).where(
                    (Tenant.slug == tenant_id) | (Tenant.id == tenant_id)
                )
            ).scalar_one_or_none()
            return tenant.id if tenant else None
        return tenant_id
