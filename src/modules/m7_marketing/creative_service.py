"""Servico M7b — Creative Engine.

Gera pecas visuais e criativas (imagens PNG, flyer PDF) para listings:
Instagram post/story, Facebook post, property card, flyer.

As pecas sao geradas como metadados estruturados (template_data) e
registadas na tabela listing_creatives. A geracao de ficheiros reais
(PIL/ReportLab) e opcional — sem dependencias obrigatorias.
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import select

from src.database.db import get_session
from src.database.models_v2 import (
    BrandKit,
    Deal,
    Document,
    Listing,
    ListingCreative,
    Property,
    Tenant,
)

from pathlib import Path as _Path

_DEFAULT_TENANT_SLUG = "default"

# ---------------------------------------------------------------------------
# Normalizacao de acentos PT-PT para termos imobiliarios e toponimos
# ---------------------------------------------------------------------------

_PT_ACCENT_MAP: dict[str, str] = {
    # Toponimos comuns (freguesias/concelhos)
    "Campanha": "Campanhã",
    "CAMPANHA": "CAMPANHÃ",
    "campanha": "campanhã",
    "Alcochete": "Alcochete",
    "Sao": "São",
    "SAO": "SÃO",
    "sao": "são",
    "Belem": "Belém",
    "BELEM": "BELÉM",
    "Setubal": "Setúbal",
    "SETUBAL": "SETÚBAL",
    "Evora": "Évora",
    "EVORA": "ÉVORA",
    "Santarem": "Santarém",
    "SANTAREM": "SANTARÉM",
    "Obidos": "Óbidos",
    "OBIDOS": "ÓBIDOS",
    "Guimaraes": "Guimarães",
    "GUIMARAES": "GUIMARÃES",
    "Povoa": "Póvoa",
    "POVOA": "PÓVOA",
    "Avila": "Ávila",
    "Estremoz": "Estremoz",
    "Alcacer": "Alcácer",
    "Fundao": "Fundão",
    "FUNDAO": "FUNDÃO",
    "Tomar": "Tomar",
    "Lousa": "Lousã",
    "LOUSA": "LOUSÃ",
    "Mafamude": "Mafamude",
    "Gondomar": "Gondomar",
    "Matosinhos": "Matosinhos",
    # Termos imobiliarios
    "Fraccao": "Fracção",
    "FRACCAO": "FRACÇÃO",
    "fraccao": "fracção",
    "Fracao": "Fração",
    "fracao": "fração",
    "area": "área",
    "Area": "Área",
    "AREA": "ÁREA",
    "sotao": "sótão",
    "Sotao": "Sótão",
    "SOTAO": "SÓTÃO",
    "reabilitacao": "reabilitação",
    "Reabilitacao": "Reabilitação",
    "remodelacao": "remodelação",
    "Remodelacao": "Remodelação",
    "localizacao": "localização",
    "Localizacao": "Localização",
    "construcao": "construção",
    "Construcao": "Construção",
    "habitacao": "habitação",
    "Habitacao": "Habitação",
    "garagem": "garagem",
    "valorizacao": "valorização",
    "Valorizacao": "Valorização",
    "fraccoes": "fracções",
    "Fraccoes": "Fracções",
    "negociaveis": "negociáveis",
    "rustico": "rústico",
    "Rustico": "Rústico",
}


def _normalize_pt_accents(text: str) -> str:
    """Aplica correcoes de acentuacao PT-PT a um texto.

    Substitui palavras conhecidas sem acentos pelas versoes correctas.
    Utiliza word-boundary matching para evitar substituicoes parciais.
    """
    if not text:
        return text
    import re
    result = text
    for wrong, correct in _PT_ACCENT_MAP.items():
        # Usar word boundary para evitar substituicoes parciais
        pattern = r'\b' + re.escape(wrong) + r'\b'
        result = re.sub(pattern, correct, result)
    return result

# Especificacoes de formatos por tipo de criativo
_CREATIVE_SPECS: Dict[str, Dict[str, Any]] = {
    "ig_post": {
        "format": "png",
        "width": 1080,
        "height": 1080,
        "label": "Instagram Post (Feed)",
    },
    "ig_story": {
        "format": "png",
        "width": 1080,
        "height": 1920,
        "label": "Instagram Story",
    },
    "fb_post": {
        "format": "png",
        "width": 1200,
        "height": 630,
        "label": "Facebook Post",
    },
    "property_card": {
        "format": "png",
        "width": 1080,
        "height": 1350,
        "label": "Property Card",
    },
    "flyer": {
        "format": "pdf",
        "width": 794,
        "height": 1123,
        "label": "Flyer A4 PDF",
    },
    "whatsapp_card": {
        "format": "png",
        "width": 800,
        "height": 600,
        "label": "WhatsApp Card",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creative_to_dict(c: ListingCreative) -> Dict[str, Any]:
    """Serializa ListingCreative para dict."""
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "listing_id": c.listing_id,
        "creative_type": c.creative_type,
        "format": c.format,
        "width": c.width,
        "height": c.height,
        "language": c.language,
        "document_id": c.document_id,
        "file_url": c.file_url,
        "file_size": c.file_size,
        "title_used": c.title_used,
        "description_used": c.description_used,
        "photos_used": c.photos_used or [],
        "template_name": c.template_name,
        "template_data": c.template_data or {},
        "status": c.status,
        "approved_by": c.approved_by,
        "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _qr_placeholder_data_uri() -> str:
    """Gera um data URI de placeholder para QR code (1x1 pixel transparente)."""
    # PNG transparente 1x1
    _TRANSPARENT_PNG_B64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9Q"
        "DwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return f"data:image/png;base64,{_TRANSPARENT_PNG_B64}"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CreativeService:
    """Logica de negocio M7b — Creative Engine.

    Gera pecas visuais para publicacao em redes sociais e materiais
    impressos. Cada criativo e registado na tabela listing_creatives
    com metadados completos (template_data, dimensoes, idioma).

    A geracao de ficheiros de imagem/PDF reais e feita se as
    bibliotecas PIL e ReportLab estiverem disponiveis; caso contrario,
    o criativo e registado apenas com template_data.
    """

    # --- Geracao por tipo ---

    def generate_ig_post(
        self, listing_id: str, language: str = "pt-PT"
    ) -> Dict[str, Any]:
        """Gera um criativo para Instagram Post (1080x1080 PNG).

        Parametros
        ----------
        listing_id:
            ID do listing.
        language:
            Codigo de idioma.

        Retorna
        -------
        Dict com os dados do criativo gerado.
        """
        return self._generate_creative(listing_id, "ig_post", language)

    def generate_ig_story(
        self, listing_id: str, language: str = "pt-PT"
    ) -> Dict[str, Any]:
        """Gera um criativo para Instagram Story (1080x1920 PNG).

        Parametros
        ----------
        listing_id:
            ID do listing.
        language:
            Codigo de idioma.

        Retorna
        -------
        Dict com os dados do criativo gerado.
        """
        return self._generate_creative(listing_id, "ig_story", language)

    def generate_fb_post(
        self, listing_id: str, language: str = "pt-PT"
    ) -> Dict[str, Any]:
        """Gera um criativo para Facebook Post (1200x630 PNG).

        Parametros
        ----------
        listing_id:
            ID do listing.
        language:
            Codigo de idioma.

        Retorna
        -------
        Dict com os dados do criativo gerado.
        """
        return self._generate_creative(listing_id, "fb_post", language)

    def generate_property_card(
        self, listing_id: str, language: str = "pt-PT"
    ) -> Dict[str, Any]:
        """Gera um property card (1080x1350 PNG).

        Parametros
        ----------
        listing_id:
            ID do listing.
        language:
            Codigo de idioma.

        Retorna
        -------
        Dict com os dados do criativo gerado.
        """
        return self._generate_creative(listing_id, "property_card", language)

    def generate_flyer_pdf(
        self, listing_id: str, language: str = "pt-PT"
    ) -> Dict[str, Any]:
        """Gera um flyer A4 em PDF.

        Inclui QR code placeholder (qr_data_uri) no template_data.

        Parametros
        ----------
        listing_id:
            ID do listing.
        language:
            Codigo de idioma.

        Retorna
        -------
        Dict com os dados do criativo gerado.
        """
        return self._generate_creative(
            listing_id, "flyer", language, include_qr=True
        )

    def generate_all_creatives(
        self, listing_id: str, language: str = "pt-PT"
    ) -> List[Dict[str, Any]]:
        """Gera todos os tipos de criativos para um listing.

        Gera: ig_post, ig_story, fb_post, property_card, flyer
        (5 criativos no total).

        Parametros
        ----------
        listing_id:
            ID do listing.
        language:
            Codigo de idioma.

        Retorna
        -------
        Lista de dicts com os criativos gerados.
        """
        types = ["ig_post", "ig_story", "fb_post", "property_card", "flyer"]
        results = []
        for creative_type in types:
            include_qr = creative_type == "flyer"
            try:
                c = self._generate_creative(
                    listing_id, creative_type, language, include_qr=include_qr
                )
                results.append(c)
            except Exception as exc:
                logger.warning(
                    f"Erro ao gerar {creative_type} para listing "
                    f"{listing_id}: {exc}"
                )
        return results

    # --- CRUD ---

    def get_creative(self, creative_id: str) -> Optional[Dict[str, Any]]:
        """Retorna um criativo por ID.

        Parametros
        ----------
        creative_id:
            ID do criativo.

        Retorna
        -------
        Dict com os dados do criativo ou None se nao existir.
        """
        with get_session() as session:
            creative = session.get(ListingCreative, creative_id)
            return _creative_to_dict(creative) if creative else None

    def list_creatives(
        self,
        listing_id: Optional[str] = None,
        creative_type: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista criativos com filtros opcionais.

        Parametros
        ----------
        listing_id:
            Filtro por listing (opcional).
        creative_type:
            Filtro por tipo (opcional).
        language:
            Filtro por idioma (opcional).

        Retorna
        -------
        Lista de dicts com os criativos.
        """
        with get_session() as session:
            stmt = select(ListingCreative).order_by(
                ListingCreative.created_at.desc()
            )
            if listing_id:
                stmt = stmt.where(ListingCreative.listing_id == listing_id)
            if creative_type:
                stmt = stmt.where(
                    ListingCreative.creative_type == creative_type
                )
            if language:
                stmt = stmt.where(ListingCreative.language == language)

            creatives = session.execute(stmt).scalars().all()
            return [_creative_to_dict(c) for c in creatives]

    def delete_creative(self, creative_id: str) -> bool:
        """Remove um criativo da base de dados.

        Parametros
        ----------
        creative_id:
            ID do criativo a remover.

        Retorna
        -------
        True se removido com sucesso, False se nao encontrado.
        """
        with get_session() as session:
            creative = session.get(ListingCreative, creative_id)
            if not creative:
                return False

            session.delete(creative)
            logger.info(f"Criativo {creative_id} removido")
            return True

    def approve_creative(self, creative_id: str, approved_by: str = "user") -> Optional[Dict[str, Any]]:
        """Aprova um criativo.

        Parametros
        ----------
        creative_id:
            ID do criativo.
        approved_by:
            Identificador do utilizador que aprovou.

        Retorna
        -------
        Dict com o criativo actualizado ou None se nao existir.
        """
        with get_session() as session:
            creative = session.get(ListingCreative, creative_id)
            if not creative:
                return None

            creative.status = "approved"
            creative.approved_by = approved_by
            creative.approved_at = datetime.now(tz=timezone.utc)
            session.flush()
            logger.info(f"Criativo {creative_id} aprovado por {approved_by}")
            return _creative_to_dict(creative)

    def get_creative_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas globais de criativos.

        Retorna
        -------
        Dict com total, distribuicao por tipo, formato e idioma.
        """
        with get_session() as session:
            all_creatives = (
                session.execute(select(ListingCreative)).scalars().all()
            )

            by_type: Dict[str, int] = {}
            by_format: Dict[str, int] = {}
            by_language: Dict[str, int] = {}
            for c in all_creatives:
                by_type[c.creative_type] = by_type.get(c.creative_type, 0) + 1
                by_format[c.format] = by_format.get(c.format, 0) + 1
                by_language[c.language] = by_language.get(c.language, 0) + 1

            return {
                "total_creatives": len(all_creatives),
                "by_type": by_type,
                "by_format": by_format,
                "by_language": by_language,
            }

    # --- Metodos privados ---

    def _generate_creative(
        self,
        listing_id: str,
        creative_type: str,
        language: str = "pt-PT",
        include_qr: bool = False,
    ) -> Dict[str, Any]:
        """Motor central de geracao de criativos.

        Carrega listing, deal, property e brand kit; constroi o
        template_data; tenta gerar ficheiro de imagem/PDF se as
        bibliotecas estiverem disponiveis; regista na BD.

        Parametros
        ----------
        listing_id:
            ID do listing.
        creative_type:
            Tipo de criativo ('ig_post', 'ig_story', 'fb_post',
            'property_card', 'flyer', 'whatsapp_card').
        language:
            Codigo de idioma.
        include_qr:
            Se True, inclui qr_data_uri no template_data.

        Retorna
        -------
        Dict com os dados do criativo registado.
        """
        spec = _CREATIVE_SPECS.get(creative_type, {})

        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                raise ValueError(f"Listing nao encontrada: {listing_id}")

            deal = session.get(Deal, listing.deal_id) if listing.deal_id else None
            prop = (
                session.get(Property, deal.property_id) if deal else None
            )
            brand_kit = session.execute(
                select(BrandKit).where(BrandKit.tenant_id == listing.tenant_id)
            ).scalar_one_or_none()

            # Construir template_data
            template_data = self._build_template_data(
                listing=listing,
                deal=deal,
                prop=prop,
                brand_kit=brand_kit,
                creative_type=creative_type,
                language=language,
                session=session,
            )

            # QR placeholder para flyer
            if include_qr:
                template_data["qr_data_uri"] = _qr_placeholder_data_uri()

            # Titulo e descricao usados
            title_used = template_data.get("title", "")
            description_used = template_data.get("short_description", "")

            # Tentar criar ficheiro de imagem/PDF
            document_id, file_url, file_size = self._try_generate_file(
                creative_type=creative_type,
                spec=spec,
                template_data=template_data,
                listing=listing,
                session=session,
            )

            creative = ListingCreative(
                id=str(uuid4()),
                tenant_id=listing.tenant_id,
                listing_id=listing_id,
                creative_type=creative_type,
                format=spec.get("format", "png"),
                width=spec.get("width"),
                height=spec.get("height"),
                language=language,
                document_id=document_id,
                file_url=file_url,
                file_size=file_size,
                title_used=title_used,
                description_used=description_used,
                template_name=creative_type,
                template_data=template_data,
                status="generated",
            )
            session.add(creative)
            session.flush()

            logger.info(
                f"Criativo {creative.id} gerado: listing={listing_id}, "
                f"type={creative_type}, lang={language}, "
                f"doc={document_id}"
            )
            return _creative_to_dict(creative)

    @staticmethod
    def _resolve_document_to_data_uri(
        url: Optional[str], session: Any
    ) -> str:
        """Converte URL de API (/api/v1/documents/xxx/download) para data URI base64.

        Playwright headless nao consegue aceder a file:// nem a localhost,
        por isso embedimos a imagem directamente no HTML como data URI.
        """
        if not url:
            return ""
        # Se ja for URL absoluta (https://) ou data URI, retornar directamente
        if url.startswith(("http://", "https://", "data:")):
            return url
        # Extrair document_id do padrao /api/v1/documents/{id}/download
        import re
        m = re.search(r'/api/v1/documents/([a-f0-9-]+)/download', url)
        if not m:
            return url
        doc_id = m.group(1)
        doc = session.get(Document, doc_id)
        if not doc:
            return ""
        file_path = _Path(doc.file_path)
        if not file_path.is_absolute():
            file_path = _Path.cwd() / file_path
        if not file_path.exists():
            return ""
        # Converter para data URI base64
        raw = file_path.read_bytes()
        mime = doc.mime_type or "image/jpeg"
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def _build_template_data(
        self,
        listing: Listing,
        deal: Optional[Deal],
        prop: Optional[Property],
        brand_kit: Optional[BrandKit],
        creative_type: str,
        language: str,
        session: Any = None,
    ) -> Dict[str, Any]:
        """Constroi o dict de dados do template para o criativo."""
        # Cores e marca — Design System HABTA
        color_primary = "#1a3e5c"
        color_secondary = "#8f7350"
        color_accent = "#c9a872"
        font_heading = "Montserrat"
        brand_name = "HABTA"
        tagline = ""
        contact_phone = ""
        contact_whatsapp = ""
        website_url = ""
        logo_url = ""

        if brand_kit:
            color_primary = brand_kit.color_primary or color_primary
            color_secondary = brand_kit.color_secondary or color_secondary
            color_accent = brand_kit.color_accent or color_accent
            font_heading = brand_kit.font_heading or font_heading
            brand_name = brand_kit.brand_name or brand_name
            tagline = brand_kit.tagline or ""
            contact_phone = brand_kit.contact_phone or ""
            contact_whatsapp = brand_kit.contact_whatsapp or ""
            website_url = brand_kit.website_url or ""
            # Resolver logo para file:// URI (Playwright precisa de acesso local)
            if session:
                logo_url = self._resolve_document_to_data_uri(
                    brand_kit.logo_white_url or brand_kit.logo_primary_url, session
                )

        # Dados do imóvel — extrair da listing (highlights) ou fallback property
        bedrooms: Optional[int] = None
        bathrooms: Optional[int] = None
        area: Optional[float] = None
        typology = ""
        condition = ""

        # Tentar extrair dados per-fracção dos highlights
        import re
        highlights = listing.highlights or []
        for h in highlights:
            h_lower = h.lower()
            # Bedrooms: "T1 — 1q", "T2 — 2 quartos", "1 quarto"
            m = re.search(r'(\d+)\s*(?:q\b|quarto)', h_lower)
            if m and bedrooms is None:
                bedrooms = int(m.group(1))
            # Bathrooms: "2 WCs", "2 wc", "2 casas de banho"
            m = re.search(r'(\d+)\s*(?:wc|casas? de banho)', h_lower)
            if m and bathrooms is None:
                bathrooms = int(m.group(1))
            # Area: "118,44m²", "118.44 m2", "106,78m²"
            m = re.search(r'([\d,.]+)\s*m[²2]', h_lower)
            if m and area is None:
                area_str = m.group(1).replace(',', '.')
                try:
                    area = float(area_str)
                except ValueError:
                    pass
            # Typology: "T1", "T2", "T3 Duplex"
            m = re.search(r'\bT(\d)\b', h)
            if m and not typology:
                typology = f"T{m.group(1)}"

        # Fallback to property if not found in highlights
        if prop:
            if bedrooms is None:
                bedrooms = prop.bedrooms
            if area is None:
                area = prop.gross_area_m2
            if not typology:
                typology = prop.typology or prop.property_type or ""
            condition = prop.condition or ""

        # Location — avoid duplicates (Porto, Porto → Campanhã, Porto)
        location_parts = []
        if prop:
            parish = prop.parish or ""
            municipality = prop.municipality or ""
            district = prop.district or ""
            if parish:
                location_parts.append(parish)
            if municipality and municipality != parish:
                location_parts.append(municipality)
            if district and district != municipality and district != parish:
                location_parts.append(district)
        location = ", ".join(location_parts)

        # Titulo
        title_field = "title_pt"
        if language == "pt-BR":
            title_field = "title_pt_br"
        elif language == "en":
            title_field = "title_en"
        elif language == "fr":
            title_field = "title_fr"
        elif language == "zh":
            title_field = "title_zh"

        price = listing.listing_price
        # Formato PT: 399.000 € (ponto separador milhares, € no final)
        price_formatted = f"{int(price):,}".replace(",", ".") + " €"

        title = getattr(listing, title_field, None) or (
            f"{typology} — {price_formatted}"
            if typology
            else f"{listing.listing_type.capitalize()} — {price_formatted}"
        )

        # Descricao curta
        short_desc_field = "short_description_pt"
        if language == "en":
            short_desc_field = "short_description_en"
        short_description = getattr(listing, short_desc_field, None) or (
            f"{typology} em {location}" if location else title
        )

        # Labels singular/plural
        bedrooms_label = f"{bedrooms} {'quarto' if bedrooms == 1 else 'quartos'}" if bedrooms else None
        bathrooms_label = f"{bathrooms} {'casa de banho' if bathrooms == 1 else 'casas de banho'}" if bathrooms else None

        # Resolver cover_photo — rodar foto por tipo de criativo
        # Cada tipo usa foto diferente para variedade visual
        photos_list = listing.photos or []
        photo_index_map = {
            "property_card": 0,
            "ig_post": 1,
            "ig_story": 2,
            "fb_post": 3,
            "flyer": 0,
            "whatsapp_card": 0,
        }
        desired_idx = photo_index_map.get(creative_type, 0)

        cover_photo_url = listing.cover_photo_url or ""
        if photos_list and len(photos_list) > desired_idx:
            photo_entry = photos_list[desired_idx]
            if isinstance(photo_entry, dict):
                cover_photo_url = photo_entry.get("url", "") or photo_entry.get("document_id", "")
                if photo_entry.get("document_id") and not cover_photo_url.startswith(("http", "data:")):
                    cover_photo_url = f"/api/v1/documents/{photo_entry['document_id']}/download"
            elif isinstance(photo_entry, str):
                cover_photo_url = photo_entry
        elif photos_list:
            # Fallback to first photo
            photo_entry = photos_list[0]
            if isinstance(photo_entry, dict):
                cover_photo_url = photo_entry.get("url", "") or ""
                if photo_entry.get("document_id") and not cover_photo_url.startswith(("http", "data:")):
                    cover_photo_url = f"/api/v1/documents/{photo_entry['document_id']}/download"

        cover_photo = cover_photo_url
        if session:
            cover_photo = self._resolve_document_to_data_uri(cover_photo, session)

        # Normalizar acentos PT-PT em todos os textos visiveis
        title = _normalize_pt_accents(title)
        short_description = _normalize_pt_accents(short_description)
        location = _normalize_pt_accents(location)
        if bedrooms_label:
            bedrooms_label = _normalize_pt_accents(bedrooms_label)
        if bathrooms_label:
            bathrooms_label = _normalize_pt_accents(bathrooms_label)
        highlights_clean = [
            _normalize_pt_accents(h) for h in (listing.highlights or [])
        ]

        return {
            # Identidade
            "brand_name": brand_name,
            "tagline": tagline,
            "website_url": website_url,
            "contact_phone": contact_phone,
            "contact_whatsapp": contact_whatsapp,
            "logo_url": logo_url,
            # Cores e tipografia
            "color_primary": color_primary,
            "color_secondary": color_secondary,
            "color_accent": color_accent,
            "font_heading": font_heading,
            # Dados do imovel
            "title": title,
            "short_description": short_description,
            "price_formatted": price_formatted,
            "price": price,
            "currency": listing.currency,
            "typology": typology,
            "area": area,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "bedrooms_label": bedrooms_label,
            "bathrooms_label": bathrooms_label,
            "location": location,
            "condition": condition,
            "highlights": highlights_clean,
            "cover_photo": cover_photo,
            "cover_photo_url": listing.cover_photo_url,
            # Meta
            "language": language,
            "creative_type": creative_type,
            "year": datetime.now(tz=timezone.utc).year,
        }

    def _try_generate_file(
        self,
        creative_type: str,
        spec: Dict[str, Any],
        template_data: Dict[str, Any],
        listing: Listing,
        session: Any,
    ) -> tuple[Optional[str], Optional[str], Optional[int]]:
        """Tenta gerar um ficheiro de imagem ou PDF.

        Se PIL (Pillow) estiver instalado, gera uma imagem PNG simples
        com as cores do brand kit e regista um Document.
        Se ReportLab estiver instalado, gera um PDF para 'flyer'.
        Caso contrario, retorna (None, None, None).

        Parametros
        ----------
        creative_type:
            Tipo de criativo.
        spec:
            Especificacoes de dimensoes e formato.
        template_data:
            Dados do template (cores, textos).
        listing:
            Listing associada.
        session:
            Sessao SQLAlchemy activa.

        Retorna
        -------
        Tuplo (document_id, file_url, file_size) ou (None, None, None).
        """
        fmt = spec.get("format", "png")
        width = spec.get("width", 800)
        height = spec.get("height", 800)

        raw_bytes: Optional[bytes] = None

        if fmt == "pdf":
            raw_bytes = self._try_generate_pdf(
                width=width, height=height, template_data=template_data
            )
        else:
            raw_bytes = self._try_generate_png(
                width=width, height=height, template_data=template_data
            )

        if raw_bytes is None:
            return None, None, None

        # Guardar ficheiro no disco
        storage_dir = _Path("storage/creatives") / (listing.deal_id or "general")
        storage_dir.mkdir(parents=True, exist_ok=True)

        document_id = str(uuid4())
        stored_filename = f"{document_id}.{fmt}"
        file_path = storage_dir / stored_filename
        file_path.write_bytes(raw_bytes)

        # Registar Document
        doc = Document(
            id=document_id,
            tenant_id=listing.tenant_id,
            entity_type="listing_creative",
            entity_id=listing.id,
            filename=f"{creative_type}.{fmt}",
            stored_filename=stored_filename,
            file_path=str(file_path),
            file_size=len(raw_bytes),
            mime_type="application/pdf" if fmt == "pdf" else "image/png",
            file_extension=fmt,
            document_type="creative",
            title=template_data.get("title", ""),
            uploaded_by="system",
        )
        session.add(doc)
        session.flush()

        file_url = f"/api/v1/documents/{document_id}/download"
        return document_id, file_url, len(raw_bytes)

    @staticmethod
    def _try_generate_png(
        width: int, height: int, template_data: Dict[str, Any]
    ) -> Optional[bytes]:
        """Gera PNG via Playwright (HTML→screenshot) ou Pillow fallback."""
        # Tentar Playwright primeiro (alta qualidade)
        pw_result = CreativeService._try_playwright_render(width, height, template_data)
        if pw_result:
            return pw_result

        # Fallback: Pillow (placeholder branded)
        return CreativeService._try_pillow_fallback(width, height, template_data)

    @staticmethod
    def _try_playwright_render(
        width: int, height: int, template_data: Dict[str, Any]
    ) -> Optional[bytes]:
        """Renderiza template HTML com Playwright Chromium.

        Executa numa thread separada para evitar conflito com asyncio
        (FastAPI corre dentro de um event loop).
        """
        try:
            from playwright.sync_api import sync_playwright
            import jinja2

            # Determinar template — dimensoes exactas primeiro, aspect ratio depois
            if width == 1080 and height == 1080:
                tmpl_name = "ig_post.html"
            elif width == 1080 and height == 1350:
                tmpl_name = "property_card.html"
            elif width == 1080 and height == 1920:
                tmpl_name = "ig_story.html"
            elif width == 1200 and height == 630:
                tmpl_name = "fb_post.html"
            elif height > width:
                tmpl_name = "ig_story.html"
            else:
                tmpl_name = "ig_post.html"

            tmpl_dir = _Path(__file__).parent / "templates"
            tmpl_path = tmpl_dir / tmpl_name

            if not tmpl_path.exists():
                logger.debug(f"Template {tmpl_name} não encontrado")
                return None

            # Carregar e renderizar template Jinja2
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(tmpl_dir)),
                autoescape=False,
            )
            template = env.get_template(tmpl_name)

            # Preparar dados para o template
            render_data = {
                "width": width,
                "height": height,
                "title": template_data.get("title", ""),
                "price": template_data.get("price_formatted", ""),
                "cover_photo": template_data.get("cover_photo", ""),
                "logo_url": template_data.get("logo_url", ""),
                "badge": template_data.get("badge", ""),
                "bedrooms": template_data.get("bedrooms"),
                "bathrooms": template_data.get("bathrooms"),
                "bedrooms_label": template_data.get("bedrooms_label", ""),
                "bathrooms_label": template_data.get("bathrooms_label", ""),
                "area": template_data.get("area"),
                "energy_cert": template_data.get("energy_cert"),
                "location": template_data.get("location", ""),
                "brand_name": template_data.get("brand_name", "HABTA"),
                "contact_phone": template_data.get("contact_phone", ""),
                "website_url": template_data.get("website_url", ""),
                "highlights": template_data.get("highlights", []),
                "font_heading": template_data.get("font_heading", "Montserrat"),
                "font_body": template_data.get("font_body", "Inter"),
                "color_primary": template_data.get("color_primary", "#1a3e5c"),
                "color_secondary": template_data.get("color_secondary", "#8f7350"),
                "color_accent": template_data.get("color_accent", "#c9a872"),
                "color_text": template_data.get("color_text", "#1a1a1a"),
                "color_background": template_data.get("color_background", "#ffffff"),
                "qr_data_uri": template_data.get("qr_data_uri", ""),
                "short_description": template_data.get("short_description", ""),
                "typology": template_data.get("typology", ""),
                "listing_type": template_data.get("listing_type", ""),
            }
            html = template.render(**render_data)

            # Render com Playwright numa thread separada (evita conflito asyncio)
            def _do_render() -> bytes:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.set_content(html, wait_until="networkidle")
                    png_bytes = page.screenshot(type="png", full_page=False)
                    browser.close()
                return png_bytes

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                png_bytes = pool.submit(_do_render).result(timeout=30)

            logger.info(f"Playwright render: {width}x{height} ({len(png_bytes)} bytes)")
            return png_bytes

        except ImportError:
            logger.debug("Playwright não disponível — a tentar Pillow")
            return None
        except Exception as exc:
            logger.warning(f"Playwright render falhou: {exc}")
            return None

    @staticmethod
    def _try_pillow_fallback(
        width: int, height: int, template_data: Dict[str, Any]
    ) -> Optional[bytes]:
        """Fallback: gera PNG com foto real + overlay + texto profissional."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            color_primary = template_data.get("color_primary", "#1E3A5F")
            color_accent = template_data.get("color_accent", "#E76F51")
            pr = int(color_primary[1:3], 16)
            pg = int(color_primary[3:5], 16)
            pb = int(color_primary[5:7], 16)
            ar = int(color_accent[1:3], 16)
            ag = int(color_accent[3:5], 16)
            ab = int(color_accent[5:7], 16)

            # Tentar carregar foto real como fundo
            cover_photo = template_data.get("cover_photo", "")
            photo_path = None
            if cover_photo.startswith("file://"):
                photo_path = _Path(cover_photo.replace("file://", ""))
            elif cover_photo and not cover_photo.startswith(("http", "data:")):
                photo_path = _Path(cover_photo)

            if photo_path and photo_path.exists():
                # Abrir foto real, resize com crop central
                photo = Image.open(photo_path).convert("RGB")
                # Calcular crop ao centro mantendo aspect ratio
                pw, ph = photo.size
                target_ratio = width / height
                photo_ratio = pw / ph
                if photo_ratio > target_ratio:
                    new_h = ph
                    new_w = int(ph * target_ratio)
                    left = (pw - new_w) // 2
                    photo = photo.crop((left, 0, left + new_w, ph))
                else:
                    new_w = pw
                    new_h = int(pw / target_ratio)
                    top = (ph - new_h) // 2
                    photo = photo.crop((0, top, pw, top + new_h))
                img = photo.resize((width, height), Image.LANCZOS)
            else:
                # Fundo solido como ultimo recurso
                img = Image.new("RGB", (width, height), color=(pr, pg, pb))

            # Overlay semi-transparente escuro
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            # Gradiente: mais escuro em baixo
            for y in range(height):
                alpha = int(40 + (y / height) * 160)  # 40 no topo, 200 em baixo
                draw_overlay.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, overlay)
            img = img.convert("RGB")

            draw = ImageDraw.Draw(img)

            title = template_data.get("title", "HABTA")[:50]
            price = template_data.get("price_formatted", "")
            brand = template_data.get("brand_name", "HABTA")
            location = template_data.get("location", "")
            bedrooms = template_data.get("bedrooms")
            bathrooms = template_data.get("bathrooms")
            area_val = template_data.get("area")

            # Carregar fonte (tentar Montserrat/DejaVu, fallback default)
            def _load_font(size: int) -> ImageFont.FreeTypeFont:
                for name in [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "/System/Library/Fonts/SFNSDisplay.ttf",
                ]:
                    try:
                        return ImageFont.truetype(name, size)
                    except (OSError, IOError):
                        continue
                return ImageFont.load_default()

            scale = min(width, height) / 1080
            margin = int(48 * scale)

            # Brand name no topo
            font_brand = _load_font(int(28 * scale))
            draw.text((margin, margin), brand.upper(), fill=(255, 255, 255), font=font_brand)

            # Titulo
            font_title = _load_font(int(44 * scale))
            ty = height - int(280 * scale)
            draw.text((margin, ty), title, fill=(255, 255, 255), font=font_title)

            # Preco
            font_price = _load_font(int(52 * scale))
            draw.text((margin, ty + int(60 * scale)), price, fill=(ar, ag, ab), font=font_price)

            # Features line
            features_parts = []
            if bedrooms:
                features_parts.append(f"{bedrooms} quartos")
            if bathrooms:
                features_parts.append(f"{bathrooms} WC")
            if area_val:
                features_parts.append(f"{area_val} m2")
            if features_parts:
                font_feat = _load_font(int(24 * scale))
                feat_text = "  |  ".join(features_parts)
                draw.text(
                    (margin, ty + int(130 * scale)),
                    feat_text,
                    fill=(255, 255, 255, 200),
                    font=font_feat,
                )

            # Location
            if location:
                font_loc = _load_font(int(22 * scale))
                draw.text(
                    (margin, ty + int(170 * scale)),
                    f"📍 {location}",
                    fill=(255, 255, 255),
                    font=font_loc,
                )

            # Barra de cor inferior
            bar_h = int(8 * scale)
            draw.rectangle(
                [(0, height - bar_h), (width, height)],
                fill=(ar, ag, ab),
            )

            buf = io.BytesIO()
            img.save(buf, format="PNG", quality=95)
            return buf.getvalue()
        except ImportError:
            return None
        except Exception as exc:
            logger.warning(f"Pillow fallback falhou: {exc}")
            return None

    @staticmethod
    def _try_generate_pdf(
        width: int, height: int, template_data: Dict[str, Any]
    ) -> Optional[bytes]:
        """Gera PDF: tenta ReportLab, fallback Playwright PNG→PDF via img2pdf."""
        # 1. Tentar ReportLab
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas as rl_canvas

            buf = io.BytesIO()
            c = rl_canvas.Canvas(buf, pagesize=A4)

            color_primary = template_data.get("color_primary", "#1a3e5c")
            r = int(color_primary[1:3], 16) / 255
            g = int(color_primary[3:5], 16) / 255
            b = int(color_primary[5:7], 16) / 255

            page_w, page_h = A4
            c.setFillColorRGB(r, g, b)
            c.rect(0, page_h - 80 * mm, page_w, 80 * mm, fill=True, stroke=False)

            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 24)
            title = template_data.get("title", "Imovel")[:60]
            c.drawString(20 * mm, page_h - 40 * mm, title)

            c.setFont("Helvetica", 16)
            price = template_data.get("price_formatted", "")
            c.drawString(20 * mm, page_h - 60 * mm, price)

            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 12)
            desc = template_data.get("short_description", "")[:120]
            c.drawString(20 * mm, page_h - 110 * mm, desc)

            c.save()
            return buf.getvalue()
        except ImportError:
            logger.debug("ReportLab indisponivel — a tentar Playwright PDF fallback")
        except Exception as exc:
            logger.warning(f"Erro ReportLab: {exc} — a tentar Playwright fallback")

        # 2. Fallback: Playwright render → PNG → PDF com img2pdf
        try:
            from playwright.sync_api import sync_playwright
            import jinja2

            tmpl_dir = _Path(__file__).parent / "templates"
            tmpl_path = tmpl_dir / "flyer_a4.html"
            if not tmpl_path.exists():
                # Usar property_card como fallback para flyer
                tmpl_path = tmpl_dir / "property_card.html"
            if not tmpl_path.exists():
                logger.debug("Nenhum template disponivel para PDF")
                return None

            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(tmpl_dir)),
                autoescape=False,
            )
            template = env.get_template(tmpl_path.name)

            render_data = {
                "title": template_data.get("title", ""),
                "price": template_data.get("price_formatted", ""),
                "cover_photo": template_data.get("cover_photo", ""),
                "logo_url": template_data.get("logo_url", ""),
                "bedrooms_label": template_data.get("bedrooms_label", ""),
                "bathrooms_label": template_data.get("bathrooms_label", ""),
                "area": template_data.get("area"),
                "location": template_data.get("location", ""),
                "brand_name": template_data.get("brand_name", "HABTA"),
                "contact_phone": template_data.get("contact_phone", ""),
                "website_url": template_data.get("website_url", ""),
                "short_description": template_data.get("short_description", ""),
                "color_primary": template_data.get("color_primary", "#1a3e5c"),
                "color_secondary": template_data.get("color_secondary", "#8f7350"),
                "color_accent": template_data.get("color_accent", "#c9a872"),
            }
            html = template.render(**render_data)

            # Render a 2x para qualidade (A4 ~794x1123 → 1588x2246)
            render_w = width * 2
            render_h = height * 2

            def _do_render() -> bytes:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(
                        viewport={"width": render_w, "height": render_h}
                    )
                    page.set_content(html, wait_until="networkidle")
                    png_bytes = page.screenshot(type="png", full_page=False)
                    browser.close()
                return png_bytes

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                png_bytes = pool.submit(_do_render).result(timeout=30)

            # Converter PNG → PDF com img2pdf
            try:
                import img2pdf
                pdf_bytes = img2pdf.convert(png_bytes)
                logger.info(
                    f"Playwright PDF fallback: {render_w}x{render_h} "
                    f"({len(pdf_bytes)} bytes)"
                )
                return pdf_bytes
            except ImportError:
                # img2pdf indisponivel — devolver PNG como fallback
                logger.info(
                    f"Playwright PNG (sem img2pdf): {render_w}x{render_h} "
                    f"({len(png_bytes)} bytes)"
                )
                return png_bytes

        except ImportError:
            logger.debug("Playwright indisponivel para PDF fallback")
            return None
        except Exception as exc:
            logger.warning(f"Playwright PDF fallback falhou: {exc}")
            return None
