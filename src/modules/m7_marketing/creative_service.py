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
from src.shared.storage_provider import (
    BUCKET_CREATIVES,
    get_signed_url,
    upload_file,
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


def _creative_to_dict(
    c: ListingCreative, session: Optional[Any] = None
) -> Dict[str, Any]:
    """Serializa ListingCreative para dict.

    Quando o Document associado esta em Supabase Storage (file_path no formato
    ``{bucket}:{path}``), inclui ``signed_url`` com TTL de 1h para render
    directo no frontend via tag <img> sem auth adicional.
    """
    signed_url: Optional[str] = None
    if session and c.document_id:
        try:
            doc = session.get(Document, c.document_id)
            if doc and doc.file_path and ":" in doc.file_path and not doc.file_path.startswith("/"):
                bucket, bucket_path = doc.file_path.split(":", 1)
                signed_url = get_signed_url(bucket, bucket_path, expires_in=3600)
        except Exception as exc:
            logger.warning(
                f"Nao foi possivel gerar signed_url para creative {c.id}: {exc}"
            )

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
        "signed_url": signed_url,
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
            return _creative_to_dict(creative, session) if creative else None

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
            return [_creative_to_dict(c, session) for c in creatives]

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
            return _creative_to_dict(creative, session)

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
                organization_id=listing.organization_id,
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
            return _creative_to_dict(creative, session)

    @staticmethod
    def _resolve_document_to_data_uri(
        url: Optional[str], session: Any
    ) -> str:
        """Converte URL de API (/api/v1/documents/xxx/download) para URL acessivel.

        Suporta dois tipos de storage no Document:
        - Supabase Storage (file_path = "{bucket}:{path}") → retorna signed URL.
          O Worker (e qualquer cliente externo) consegue fazer fetch sem auth.
        - Filesystem legacy (file_path absoluto no disco) → retorna data URI
          base64 (necessario para Playwright headless que nao acede a local).
        """
        if not url:
            return ""
        if url.startswith(("http://", "https://", "data:")):
            return url
        import re
        m = re.search(r'/api/v1/documents/([a-f0-9-]+)/download', url)
        if not m:
            return url
        doc_id = m.group(1)
        doc = session.get(Document, doc_id)
        if not doc or not doc.file_path:
            return ""

        # Supabase Storage: file_path = "{bucket}:{path_no_leading_slash}"
        if ":" in doc.file_path and not doc.file_path.startswith("/"):
            bucket, bucket_path = doc.file_path.split(":", 1)
            try:
                from src.shared.storage_provider import get_signed_url
                return get_signed_url(bucket, bucket_path, expires_in=3600)
            except Exception as exc:
                logger.warning(
                    f"Signed URL falhou para doc={doc_id}: {exc}"
                )
                return ""

        # Legacy filesystem → data URI
        file_path = _Path(doc.file_path)
        if not file_path.is_absolute():
            file_path = _Path.cwd() / file_path
        if not file_path.exists():
            return ""
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
        from src.modules.m7_marketing.service import _as_list
        photos_list = _as_list(listing.photos)
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

        # Upload para Supabase Storage (bucket privado, acesso via signed URL)
        document_id = str(uuid4())
        stored_filename = f"{document_id}.{fmt}"
        bucket_path = f"tenants/{listing.tenant_id}/{stored_filename}"
        mime_type = "application/pdf" if fmt == "pdf" else "image/png"
        upload_file(BUCKET_CREATIVES, bucket_path, raw_bytes, mime_type)

        # Registar Document com referencia ao bucket (formato "{bucket}:{path}")
        doc = Document(
            id=document_id,
            tenant_id=listing.tenant_id,
            organization_id=listing.organization_id,
            entity_type="listing_creative",
            entity_id=listing.id,
            filename=f"{creative_type}.{fmt}",
            stored_filename=stored_filename,
            file_path=f"{BUCKET_CREATIVES}:{bucket_path}",
            file_size=len(raw_bytes),
            mime_type=mime_type,
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
        """Gera PNG via Worker @vercel/og (primeiro), Playwright ou Pillow (fallbacks)."""
        # 1) Cloudflare Worker com @vercel/og — renderer principal
        from src.modules.m7_marketing.html_renderer import render_via_worker
        creative_type = template_data.get("creative_type", "")
        worker_result = render_via_worker(creative_type, template_data)
        if worker_result:
            return worker_result

        # 2) Playwright local (legacy, alta qualidade mas lento)
        pw_result = CreativeService._try_playwright_render(width, height, template_data)
        if pw_result:
            return pw_result

        # 3) Pillow (placeholder branded, último recurso)
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

    # ------------------------------------------------------------------
    # Pillow template engine — gera PNGs profissionais por tipo
    # ------------------------------------------------------------------

    @staticmethod
    def _load_photo(
        cover_photo: str, width: int, height: int,
    ) -> "Image.Image":
        """Carrega foto de capa, crop central e resize. Fallback: fundo solido."""
        from PIL import Image

        photo_path = None
        if cover_photo.startswith("file://"):
            photo_path = _Path(cover_photo.replace("file://", ""))
        elif cover_photo and not cover_photo.startswith(("http", "data:")):
            photo_path = _Path(cover_photo)

        if photo_path and photo_path.exists():
            photo = Image.open(photo_path).convert("RGB")
            pw, ph = photo.size
            target_ratio = width / height
            photo_ratio = pw / ph
            if photo_ratio > target_ratio:
                new_w = int(ph * target_ratio)
                left = (pw - new_w) // 2
                photo = photo.crop((left, 0, left + new_w, ph))
            else:
                new_h = int(pw / target_ratio)
                top = (ph - new_h) // 2
                photo = photo.crop((0, top, pw, top + new_h))
            return photo.resize((width, height), Image.LANCZOS)

        return Image.new("RGB", (width, height), color=(30, 58, 95))

    @staticmethod
    def _apply_gradient(
        img: "Image.Image",
        alpha_top: int = 30,
        alpha_bottom: int = 210,
        start_pct: float = 0.0,
    ) -> "Image.Image":
        """Aplica gradiente escuro sobre a imagem (de start_pct ate ao fundo)."""
        from PIL import Image, ImageDraw

        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)
        start_y = int(h * start_pct)
        span = h - start_y or 1
        for y in range(start_y, h):
            alpha = int(alpha_top + ((y - start_y) / span) * (alpha_bottom - alpha_top))
            draw_ov.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        return img.convert("RGB")

    @staticmethod
    def _load_font(size: int) -> "ImageFont.FreeTypeFont":
        """Carrega fonte com fallback chain."""
        from PIL import ImageFont

        for name in [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]:
            try:
                return ImageFont.truetype(name, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        """Converte hex (#RRGGBB) para tuplo RGB."""
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return (30, 58, 95)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    @staticmethod
    def _extract_template_fields(template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai campos comuns do template_data."""
        return {
            "title": template_data.get("title", "HABTA")[:50],
            "price": template_data.get("price_formatted", ""),
            "brand": template_data.get("brand_name", "HABTA"),
            "location": template_data.get("location", ""),
            "bedrooms": template_data.get("bedrooms"),
            "bathrooms": template_data.get("bathrooms"),
            "area": template_data.get("area"),
            "cover_photo": template_data.get("cover_photo", ""),
            "color_primary": template_data.get("color_primary", "#1E3A5F"),
            "color_accent": template_data.get("color_accent", "#E76F51"),
            "typology": template_data.get("typology", ""),
            "badge": template_data.get("badge", ""),
            "listing_type": template_data.get("listing_type", ""),
            "short_description": template_data.get("short_description", ""),
            "website_url": template_data.get("website_url", ""),
            "contact_phone": template_data.get("contact_phone", ""),
        }

    @staticmethod
    def _build_features_line(fields: Dict[str, Any]) -> str:
        """Constroi linha de features: '3 quartos | 2 WC | 120 m2'."""
        parts = []
        if fields["bedrooms"]:
            parts.append(f"{fields['bedrooms']} quartos")
        if fields["bathrooms"]:
            parts.append(f"{fields['bathrooms']} WC")
        if fields["area"]:
            parts.append(f"{fields['area']} m\u00b2")
        return "  |  ".join(parts)

    @staticmethod
    def _draw_accent_bar(
        draw: "ImageDraw.Draw", width: int, height: int,
        accent_rgb: tuple, bar_h: int = 8,
    ) -> None:
        """Desenha barra de cor accent no fundo."""
        draw.rectangle([(0, height - bar_h), (width, height)], fill=accent_rgb)

    # -- Template: Instagram Post (1080x1080) / generico quadrado -----------

    @staticmethod
    def _render_ig_post(
        width: int, height: int, template_data: Dict[str, Any],
    ) -> bytes:
        """Layout feed quadrado: foto full, gradiente inferior, info em baixo."""
        from PIL import ImageDraw

        f = CreativeService._extract_template_fields(template_data)
        accent = CreativeService._hex_to_rgb(f["color_accent"])

        img = CreativeService._load_photo(f["cover_photo"], width, height)
        img = CreativeService._apply_gradient(img, 10, 220, 0.35)
        draw = ImageDraw.Draw(img)

        scale = min(width, height) / 1080
        m = int(48 * scale)

        # Badge / tipologia no topo
        badge_text = f["badge"] or f["typology"] or f["listing_type"]
        if badge_text:
            fb = CreativeService._load_font(int(22 * scale))
            bw = draw.textlength(badge_text.upper(), font=fb)
            pad = int(12 * scale)
            draw.rounded_rectangle(
                [m, m, m + bw + pad * 2, m + int(34 * scale)],
                radius=int(6 * scale), fill=accent,
            )
            draw.text(
                (m + pad, m + int(6 * scale)),
                badge_text.upper(), fill=(255, 255, 255), font=fb,
            )

        # Brand no topo direito
        fb_brand = CreativeService._load_font(int(24 * scale))
        brand_w = draw.textlength(f["brand"].upper(), font=fb_brand)
        draw.text(
            (width - m - brand_w, m + int(4 * scale)),
            f["brand"].upper(), fill=(255, 255, 255, 200), font=fb_brand,
        )

        # Bloco inferior: titulo, preco, features, localizacao
        ty = height - int(280 * scale)
        ft = CreativeService._load_font(int(42 * scale))
        draw.text((m, ty), f["title"], fill=(255, 255, 255), font=ft)

        fp = CreativeService._load_font(int(52 * scale))
        draw.text((m, ty + int(56 * scale)), f["price"], fill=accent, font=fp)

        feat = CreativeService._build_features_line(f)
        if feat:
            ff = CreativeService._load_font(int(22 * scale))
            draw.text((m, ty + int(124 * scale)), feat, fill=(255, 255, 255), font=ff)

        if f["location"]:
            fl = CreativeService._load_font(int(20 * scale))
            draw.text(
                (m, ty + int(160 * scale)),
                f["location"], fill=(255, 255, 255, 200), font=fl,
            )

        CreativeService._draw_accent_bar(draw, width, height, accent, int(6 * scale))

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    # -- Template: Instagram Story (1080x1920) ------------------------------

    @staticmethod
    def _render_ig_story(
        width: int, height: int, template_data: Dict[str, Any],
    ) -> bytes:
        """Layout vertical story: foto 60% superior, bloco info inferior escuro."""
        from PIL import Image, ImageDraw

        f = CreativeService._extract_template_fields(template_data)
        primary = CreativeService._hex_to_rgb(f["color_primary"])
        accent = CreativeService._hex_to_rgb(f["color_accent"])

        # Foto ocupa 60% superior
        photo_h = int(height * 0.6)
        photo = CreativeService._load_photo(f["cover_photo"], width, photo_h)

        # Canvas completo
        img = Image.new("RGB", (width, height), color=primary)
        img.paste(photo, (0, 0))

        # Gradiente suave na transicao foto → bloco
        img = CreativeService._apply_gradient(img, 0, 180, 0.45)
        draw = ImageDraw.Draw(img)

        # Painel inferior semi-opaco
        panel_y = photo_h - int(height * 0.05)
        panel = Image.new("RGBA", (width, height - panel_y), (*primary, 200))
        img_rgba = img.convert("RGBA")
        img_rgba.paste(panel, (0, panel_y), panel)
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

        scale = width / 1080
        m = int(56 * scale)
        cy = photo_h + int(40 * scale)

        # Brand
        fb = CreativeService._load_font(int(26 * scale))
        draw.text((m, cy), f["brand"].upper(), fill=(255, 255, 255, 180), font=fb)

        # Titulo
        ft = CreativeService._load_font(int(48 * scale))
        draw.text((m, cy + int(50 * scale)), f["title"], fill=(255, 255, 255), font=ft)

        # Preco
        fp = CreativeService._load_font(int(60 * scale))
        draw.text((m, cy + int(115 * scale)), f["price"], fill=accent, font=fp)

        # Linha separadora accent
        sep_y = cy + int(195 * scale)
        draw.rectangle(
            [(m, sep_y), (m + int(80 * scale), sep_y + int(4 * scale))],
            fill=accent,
        )

        # Features
        feat = CreativeService._build_features_line(f)
        if feat:
            ff = CreativeService._load_font(int(26 * scale))
            draw.text((m, sep_y + int(24 * scale)), feat, fill=(255, 255, 255), font=ff)

        # Localizacao
        if f["location"]:
            fl = CreativeService._load_font(int(24 * scale))
            draw.text(
                (m, sep_y + int(68 * scale)),
                f["location"], fill=(255, 255, 255, 200), font=fl,
            )

        # CTA / website no fundo
        if f["website_url"] or f["contact_phone"]:
            cta = f["website_url"] or f["contact_phone"]
            fc = CreativeService._load_font(int(22 * scale))
            cta_w = draw.textlength(cta, font=fc)
            draw.text(
                ((width - cta_w) / 2, height - int(80 * scale)),
                cta, fill=(255, 255, 255, 160), font=fc,
            )

        # Barra accent no topo (diferencia do post)
        draw.rectangle([(0, 0), (width, int(6 * scale))], fill=accent)

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    # -- Template: Facebook Post (1200x630) ---------------------------------

    @staticmethod
    def _render_fb_post(
        width: int, height: int, template_data: Dict[str, Any],
    ) -> bytes:
        """Layout horizontal FB: foto full + overlay + info lateral esquerda."""
        from PIL import Image, ImageDraw

        f = CreativeService._extract_template_fields(template_data)
        primary = CreativeService._hex_to_rgb(f["color_primary"])
        accent = CreativeService._hex_to_rgb(f["color_accent"])

        img = CreativeService._load_photo(f["cover_photo"], width, height)
        img = CreativeService._apply_gradient(img, 20, 200, 0.0)
        draw = ImageDraw.Draw(img)

        scale = min(width, height) / 630
        m = int(40 * scale)

        # Painel lateral esquerdo semi-opaco
        panel_w = int(width * 0.48)
        panel = Image.new("RGBA", (panel_w, height), (*primary, 180))
        img_rgba = img.convert("RGBA")
        img_rgba.paste(panel, (0, 0), panel)
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

        # Brand
        fb = CreativeService._load_font(int(20 * scale))
        draw.text((m, m), f["brand"].upper(), fill=(255, 255, 255, 180), font=fb)

        # Titulo
        cy = int(height * 0.22)
        ft = CreativeService._load_font(int(34 * scale))
        # Quebrar titulo se muito longo
        title = f["title"]
        max_chars = 28
        if len(title) > max_chars:
            split = title[:max_chars].rfind(" ")
            if split > 10:
                line1 = title[:split]
                line2 = title[split + 1:]
            else:
                line1 = title[:max_chars]
                line2 = title[max_chars:]
            draw.text((m, cy), line1, fill=(255, 255, 255), font=ft)
            draw.text((m, cy + int(42 * scale)), line2[:max_chars], fill=(255, 255, 255), font=ft)
            cy += int(42 * scale)
        else:
            draw.text((m, cy), title, fill=(255, 255, 255), font=ft)

        # Preco
        fp = CreativeService._load_font(int(44 * scale))
        draw.text((m, cy + int(52 * scale)), f["price"], fill=accent, font=fp)

        # Features
        feat = CreativeService._build_features_line(f)
        if feat:
            ff = CreativeService._load_font(int(18 * scale))
            draw.text((m, cy + int(110 * scale)), feat, fill=(255, 255, 255), font=ff)

        # Localizacao
        if f["location"]:
            fl = CreativeService._load_font(int(18 * scale))
            draw.text(
                (m, cy + int(142 * scale)),
                f["location"], fill=(255, 255, 255, 200), font=fl,
            )

        # Barra accent lateral direita
        bar_w = int(6 * scale)
        draw.rectangle(
            [(panel_w - bar_w, 0), (panel_w, height)],
            fill=accent,
        )

        # Website em baixo
        if f["website_url"]:
            fw = CreativeService._load_font(int(16 * scale))
            draw.text(
                (m, height - m - int(16 * scale)),
                f["website_url"], fill=(255, 255, 255, 140), font=fw,
            )

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    # -- Template: Property Card (1080x1350) --------------------------------

    @staticmethod
    def _render_property_card(
        width: int, height: int, template_data: Dict[str, Any],
    ) -> bytes:
        """Layout vertical elegante: foto 55% + ficha tecnica inferior."""
        from PIL import Image, ImageDraw

        f = CreativeService._extract_template_fields(template_data)
        primary = CreativeService._hex_to_rgb(f["color_primary"])
        accent = CreativeService._hex_to_rgb(f["color_accent"])

        # Foto 55% superior
        photo_h = int(height * 0.55)
        photo = CreativeService._load_photo(f["cover_photo"], width, photo_h)

        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        img.paste(photo, (0, 0))

        # Gradiente suave na foto
        img = CreativeService._apply_gradient(img, 0, 120, 0.3)
        draw = ImageDraw.Draw(img)

        scale = width / 1080
        m = int(48 * scale)

        # Badge sobre a foto
        badge_text = f["badge"] or f["typology"] or f["listing_type"]
        if badge_text:
            fba = CreativeService._load_font(int(20 * scale))
            bw = draw.textlength(badge_text.upper(), font=fba)
            pad = int(10 * scale)
            draw.rounded_rectangle(
                [m, photo_h - int(50 * scale), m + bw + pad * 2, photo_h - int(16 * scale)],
                radius=int(5 * scale), fill=accent,
            )
            draw.text(
                (m + pad, photo_h - int(46 * scale)),
                badge_text.upper(), fill=(255, 255, 255), font=fba,
            )

        # Ficha inferior sobre fundo branco
        card_y = photo_h + int(24 * scale)

        # Barra accent fina
        draw.rectangle(
            [(m, card_y), (m + int(60 * scale), card_y + int(4 * scale))],
            fill=accent,
        )

        # Titulo
        ft = CreativeService._load_font(int(38 * scale))
        draw.text((m, card_y + int(20 * scale)), f["title"], fill=primary, font=ft)

        # Preco
        fp = CreativeService._load_font(int(48 * scale))
        draw.text((m, card_y + int(72 * scale)), f["price"], fill=accent, font=fp)

        # Features em "pills"
        feat = CreativeService._build_features_line(f)
        if feat:
            ff = CreativeService._load_font(int(22 * scale))
            draw.text(
                (m, card_y + int(138 * scale)), feat,
                fill=(100, 100, 100), font=ff,
            )

        # Localizacao
        if f["location"]:
            fl = CreativeService._load_font(int(20 * scale))
            draw.text(
                (m, card_y + int(176 * scale)),
                f["location"], fill=(120, 120, 120), font=fl,
            )

        # Descricao curta
        desc = f["short_description"][:100] if f["short_description"] else ""
        if desc:
            fd = CreativeService._load_font(int(18 * scale))
            draw.text(
                (m, card_y + int(216 * scale)),
                desc, fill=(140, 140, 140), font=fd,
            )

        # Brand + contacto no fundo
        fb = CreativeService._load_font(int(20 * scale))
        brand_line = f["brand"].upper()
        if f["contact_phone"]:
            brand_line += f"  |  {f['contact_phone']}"
        draw.text(
            (m, height - m - int(24 * scale)),
            brand_line, fill=primary, font=fb,
        )

        # Barra accent inferior
        CreativeService._draw_accent_bar(draw, width, height, accent, int(6 * scale))

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    # -- Dispatcher: escolhe template por dimensoes -------------------------

    @staticmethod
    def _try_pillow_fallback(
        width: int, height: int, template_data: Dict[str, Any]
    ) -> Optional[bytes]:
        """Gera PNG profissional com Pillow — escolhe template por dimensoes."""
        try:
            from PIL import Image  # noqa: F401 — verifica disponibilidade

            # Escolher template por dimensoes exactas ou aspect ratio
            if width == 1080 and height == 1920:
                return CreativeService._render_ig_story(width, height, template_data)
            elif width == 1200 and height == 630:
                return CreativeService._render_fb_post(width, height, template_data)
            elif width == 1080 and height == 1350:
                return CreativeService._render_property_card(width, height, template_data)
            elif width == 1080 and height == 1080:
                return CreativeService._render_ig_post(width, height, template_data)
            elif height / width > 1.5:
                # Vertical alto → story
                return CreativeService._render_ig_story(width, height, template_data)
            elif width / height > 1.5:
                # Horizontal largo → fb
                return CreativeService._render_fb_post(width, height, template_data)
            else:
                # Quadrado ou proximo → ig_post
                return CreativeService._render_ig_post(width, height, template_data)
        except ImportError:
            return None
        except Exception as exc:
            logger.warning(f"Pillow render falhou: {exc}")
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
