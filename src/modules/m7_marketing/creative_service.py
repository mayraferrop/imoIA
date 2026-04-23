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

            # Batch: buscar todos os Documents de uma vez (evita N+1) e
            # paralelizar geração de signed URLs (cada POST ~100-300ms a
            # Supabase; em série com N=6 dá 1-2s).
            doc_ids = [c.document_id for c in creatives if c.document_id]
            doc_map: Dict[str, str] = {}
            if doc_ids:
                docs = (
                    session.query(Document)
                    .filter(Document.id.in_(doc_ids))
                    .all()
                )
                doc_map = {
                    str(d.id): d.file_path
                    for d in docs
                    if d.file_path and ":" in d.file_path and not d.file_path.startswith("/")
                }

            def _resolve(doc_id: str) -> Optional[str]:
                file_path = doc_map.get(doc_id)
                if not file_path:
                    return None
                bucket, bucket_path = file_path.split(":", 1)
                try:
                    return get_signed_url(bucket, bucket_path, expires_in=3600)
                except Exception as exc:
                    logger.warning(
                        f"signed_url falhou creative doc={doc_id}: {exc}"
                    )
                    return None

            url_by_doc: Dict[str, str] = {}
            if doc_ids:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=min(10, len(doc_ids))) as ex:
                    for doc_id, signed in zip(doc_ids, ex.map(_resolve, doc_ids)):
                        if signed:
                            url_by_doc[doc_id] = signed

            # Construir dicts sem passar `session` para não re-fazer lookup
            result = []
            for c in creatives:
                d = _creative_to_dict(c, session=None)
                if c.document_id and c.document_id in url_by_doc:
                    d["signed_url"] = url_by_doc[c.document_id]
                result.append(d)
            return result

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
        """Carrega foto de capa, crop central e resize. Fallback: fundo solido.

        Suporta:
        - file:// e paths locais (filesystem)
        - http(s):// (Supabase signed URLs, URLs externas) via requests
        - data: URIs base64
        """
        from PIL import Image
        from io import BytesIO

        photo = None

        if cover_photo.startswith("file://"):
            photo_path = _Path(cover_photo.replace("file://", ""))
            if photo_path.exists():
                photo = Image.open(photo_path).convert("RGB")
        elif cover_photo.startswith(("http://", "https://")):
            try:
                import requests
                resp = requests.get(cover_photo, timeout=15)
                resp.raise_for_status()
                photo = Image.open(BytesIO(resp.content)).convert("RGB")
            except Exception as exc:
                logger.warning(f"_load_photo HTTP falhou: {exc}")
        elif cover_photo.startswith("data:"):
            try:
                import base64
                header, b64data = cover_photo.split(",", 1)
                photo = Image.open(BytesIO(base64.b64decode(b64data))).convert("RGB")
            except Exception as exc:
                logger.warning(f"_load_photo data URI falhou: {exc}")
        elif cover_photo:
            photo_path = _Path(cover_photo)
            if photo_path.exists():
                photo = Image.open(photo_path).convert("RGB")

        if photo is not None:
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
    def _load_font(size: int, weight: str = "regular") -> "ImageFont.FreeTypeFont":
        """Carrega fonte com peso (regular, bold, light, display).

        Fallback chain cobre macOS, Linux (Docker Render) e último recurso Pillow default.
        """
        from PIL import ImageFont

        chains = {
            "display": [
                "/System/Library/Fonts/Supplemental/Futura.ttc",
                "/System/Library/Fonts/Avenir Next.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Helvetica.ttc",
            ],
            "bold": [
                "/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ],
            "regular": [
                "/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ],
            "light": [
                "/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ],
        }
        chain = chains.get(weight, chains["regular"])
        for name in chain:
            try:
                # Para .ttc (collections macOS) passar índice de face
                if name.endswith(".ttc"):
                    idx = {"display": 0, "bold": 1, "regular": 0, "light": 3}.get(weight, 0)
                    try:
                        return ImageFont.truetype(name, size, index=idx)
                    except (OSError, IOError):
                        return ImageFont.truetype(name, size, index=0)
                return ImageFont.truetype(name, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    @staticmethod
    def _wrap_text(
        text: str, font: "ImageFont.FreeTypeFont",
        max_width: int, max_lines: int = 2,
        draw: Optional["ImageDraw.Draw"] = None,
    ) -> List[str]:
        """Quebra texto em linhas respeitando max_width. Trunca com … se exceder max_lines."""
        if not text:
            return []
        words = text.split()
        if not words:
            return []

        def text_w(s: str) -> float:
            if draw is not None:
                return draw.textlength(s, font=font)
            # Fallback via bbox
            bbox = font.getbbox(s)
            return bbox[2] - bbox[0]

        lines: List[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = current + " " + word
            if text_w(candidate) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
                if len(lines) >= max_lines:
                    break
        if len(lines) < max_lines:
            lines.append(current)

        # Truncar ultima linha com … se ainda sobra texto ou se linha excede
        joined = " ".join(lines)
        if len(joined) < len(text) or text_w(lines[-1]) > max_width:
            last = lines[-1]
            while text_w(last + "…") > max_width and len(last) > 1:
                last = last[:-1]
            # Garantir que adiciona "…" se houve overflow
            if not last.endswith("…"):
                last = last.rstrip() + "…"
            lines[-1] = last
        return lines

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
            "title": template_data.get("title", "HABTA"),
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
            "highlights": template_data.get("highlights", []) or [],
            "tagline": template_data.get("tagline", ""),
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
        """Layout IG Post quadrado: foto full com overlay escuro inferior elegante."""
        from PIL import Image, ImageDraw

        f = CreativeService._extract_template_fields(template_data)
        primary = CreativeService._hex_to_rgb(f["color_primary"])
        accent = CreativeService._hex_to_rgb(f["color_accent"])

        img = CreativeService._load_photo(f["cover_photo"], width, height)
        # Gradiente suave na metade inferior
        img = CreativeService._apply_gradient(img, 0, 230, 0.30)
        draw = ImageDraw.Draw(img)

        scale = min(width, height) / 1080
        m = int(64 * scale)  # margem maior para respiracao

        # --- HEADER: badge esq + brand dir ---
        badge_text = (f["badge"] or f["typology"] or f["listing_type"]).upper()
        if badge_text:
            fb = CreativeService._load_font(int(20 * scale), "bold")
            bw = draw.textlength(badge_text, font=fb)
            pad_x = int(16 * scale)
            pad_y = int(10 * scale)
            box_h = int(40 * scale)
            draw.rounded_rectangle(
                [m, m, m + bw + pad_x * 2, m + box_h],
                radius=int(4 * scale), fill=accent,
            )
            # Centrar verticalmente o texto no badge
            text_y = m + (box_h - int(20 * scale)) // 2 - int(2 * scale)
            draw.text(
                (m + pad_x, text_y),
                badge_text, fill=(255, 255, 255), font=fb,
            )

        fb_brand = CreativeService._load_font(int(26 * scale), "bold")
        brand_txt = f["brand"].upper()
        brand_w = draw.textlength(brand_txt, font=fb_brand)
        draw.text(
            (width - m - brand_w, m + int(6 * scale)),
            brand_txt, fill=(255, 255, 255), font=fb_brand,
        )

        # --- FOOTER BLOCK: titulo wrap, preco XL, separator, features ---
        # Alinhar a partir de baixo com espaco generoso
        block_h = int(380 * scale)
        ty_base = height - block_h

        # Titulo 2 linhas wrap
        title_font = CreativeService._load_font(int(44 * scale), "bold")
        max_tw = width - m * 2
        title_lines = CreativeService._wrap_text(f["title"], title_font, max_tw, 2, draw)
        line_h = int(54 * scale)
        for i, line in enumerate(title_lines):
            draw.text((m, ty_base + i * line_h), line, fill=(255, 255, 255), font=title_font)

        # Preco grande, accent
        price_font = CreativeService._load_font(int(72 * scale), "display")
        price_y = ty_base + len(title_lines) * line_h + int(24 * scale)
        draw.text((m, price_y), f["price"], fill=accent, font=price_font)

        # Separador fino accent
        sep_y = price_y + int(88 * scale)
        draw.rectangle(
            [(m, sep_y), (m + int(72 * scale), sep_y + int(3 * scale))],
            fill=accent,
        )

        # Features + location em linha
        feat = CreativeService._build_features_line(f)
        feat_y = sep_y + int(24 * scale)
        if feat:
            ff = CreativeService._load_font(int(24 * scale), "regular")
            draw.text((m, feat_y), feat, fill=(255, 255, 255), font=ff)

        if f["location"]:
            fl = CreativeService._load_font(int(22 * scale), "light")
            draw.text(
                (m, feat_y + int(42 * scale)),
                f["location"], fill=(230, 230, 230), font=fl,
            )

        # Barra accent fina no fundo
        CreativeService._draw_accent_bar(draw, width, height, accent, int(4 * scale))

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    # -- Template: Instagram Story (1080x1920) ------------------------------

    @staticmethod
    def _render_ig_story(
        width: int, height: int, template_data: Dict[str, Any],
    ) -> bytes:
        """Layout story: foto 65% superior + bloco escuro inferior com hierarquia clara."""
        from PIL import Image, ImageDraw

        f = CreativeService._extract_template_fields(template_data)
        primary = CreativeService._hex_to_rgb(f["color_primary"])
        accent = CreativeService._hex_to_rgb(f["color_accent"])

        photo_h = int(height * 0.65)
        photo = CreativeService._load_photo(f["cover_photo"], width, photo_h)

        img = Image.new("RGB", (width, height), color=primary)
        img.paste(photo, (0, 0))
        # Gradiente escuro na foto (terço inferior)
        img = CreativeService._apply_gradient(img, 0, 180, 0.6)
        draw = ImageDraw.Draw(img)

        scale = width / 1080
        m = int(72 * scale)

        # --- TOPO: Badge sobre foto esquerda + brand dir ---
        badge_text = (f["badge"] or f["typology"] or f["listing_type"]).upper()
        if badge_text:
            fb = CreativeService._load_font(int(22 * scale), "bold")
            bw = draw.textlength(badge_text, font=fb)
            pad_x = int(16 * scale)
            box_h = int(44 * scale)
            draw.rounded_rectangle(
                [m, m + int(40 * scale), m + bw + pad_x * 2, m + int(40 * scale) + box_h],
                radius=int(4 * scale), fill=accent,
            )
            draw.text(
                (m + pad_x, m + int(40 * scale) + (box_h - int(22 * scale)) // 2 - int(2 * scale)),
                badge_text, fill=(255, 255, 255), font=fb,
            )

        # Brand canto sup direito
        fb_brand = CreativeService._load_font(int(28 * scale), "bold")
        brand_txt = f["brand"].upper()
        brand_w = draw.textlength(brand_txt, font=fb_brand)
        draw.text(
            (width - m - brand_w, m + int(46 * scale)),
            brand_txt, fill=(255, 255, 255), font=fb_brand,
        )

        # --- BLOCO INFERIOR: fundo escuro solido ---
        block_y = photo_h
        block_rgba = Image.new("RGBA", (width, height - block_y), (*primary, 255))
        img_rgba = img.convert("RGBA")
        img_rgba.paste(block_rgba, (0, block_y), block_rgba)
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

        # Barra accent horizontal no topo do bloco
        draw.rectangle(
            [(0, block_y), (width, block_y + int(6 * scale))],
            fill=accent,
        )

        cy = block_y + int(70 * scale)

        # Titulo (wrap 3 linhas, display font)
        title_font = CreativeService._load_font(int(46 * scale), "bold")
        title_lines = CreativeService._wrap_text(f["title"], title_font, width - m * 2, 3, draw)
        line_h = int(56 * scale)
        for i, line in enumerate(title_lines):
            draw.text((m, cy + i * line_h), line, fill=(255, 255, 255), font=title_font)

        cy += len(title_lines) * line_h + int(32 * scale)

        # Preco XL, accent
        price_font = CreativeService._load_font(int(82 * scale), "display")
        draw.text((m, cy), f["price"], fill=accent, font=price_font)
        cy += int(104 * scale)

        # Separador accent
        draw.rectangle(
            [(m, cy), (m + int(100 * scale), cy + int(4 * scale))],
            fill=accent,
        )
        cy += int(30 * scale)

        # Features + location
        feat = CreativeService._build_features_line(f)
        if feat:
            ff = CreativeService._load_font(int(28 * scale), "regular")
            draw.text((m, cy), feat, fill=(255, 255, 255), font=ff)
            cy += int(44 * scale)

        if f["location"]:
            fl = CreativeService._load_font(int(26 * scale), "light")
            draw.text((m, cy), f["location"], fill=(220, 220, 220), font=fl)

        # CTA centrado no fundo
        cta = f["website_url"] or f["contact_phone"]
        if cta:
            cta_font = CreativeService._load_font(int(24 * scale), "bold")
            cta_label = cta.upper()
            cta_w = draw.textlength(cta_label, font=cta_font)
            cta_y = height - int(90 * scale)
            # Linha accent acima
            line_w = int(60 * scale)
            draw.rectangle(
                [((width - line_w) / 2, cta_y - int(20 * scale)),
                 ((width + line_w) / 2, cta_y - int(20 * scale) + int(2 * scale))],
                fill=accent,
            )
            draw.text(
                ((width - cta_w) / 2, cta_y),
                cta_label, fill=(255, 255, 255), font=cta_font,
            )

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    # -- Template: Facebook Post (1200x630) ---------------------------------

    @staticmethod
    def _render_fb_post(
        width: int, height: int, template_data: Dict[str, Any],
    ) -> bytes:
        """Layout FB landscape: painel escuro à esquerda (45%) + foto direita (55%)."""
        from PIL import Image, ImageDraw

        f = CreativeService._extract_template_fields(template_data)
        primary = CreativeService._hex_to_rgb(f["color_primary"])
        accent = CreativeService._hex_to_rgb(f["color_accent"])

        scale = min(width, height) / 630
        m = int(56 * scale)

        # Foto à direita — só carrega a porção direita
        panel_w = int(width * 0.45)
        photo_w = width - panel_w
        photo = CreativeService._load_photo(f["cover_photo"], photo_w, height)

        # Canvas: painel sólido esquerda + foto direita
        img = Image.new("RGB", (width, height), color=primary)
        img.paste(photo, (panel_w, 0))
        # Pequeno gradiente vertical na foto
        img = CreativeService._apply_gradient(img, 0, 100, 0.0)
        draw = ImageDraw.Draw(img)

        # Barra accent vertical divisora
        bar_w = int(4 * scale)
        draw.rectangle(
            [(panel_w - bar_w, 0), (panel_w, height)],
            fill=accent,
        )

        # --- PAINEL ESQUERDO (info) ---
        # Topo: brand
        fb_brand = CreativeService._load_font(int(22 * scale), "bold")
        draw.text(
            (m, m), f["brand"].upper(),
            fill=(255, 255, 255), font=fb_brand,
        )

        # Badge abaixo do brand
        cy = m + int(44 * scale)
        badge_text = (f["badge"] or f["typology"] or f["listing_type"]).upper()
        if badge_text:
            fb = CreativeService._load_font(int(16 * scale), "bold")
            bw = draw.textlength(badge_text, font=fb)
            pad_x = int(12 * scale)
            box_h = int(32 * scale)
            draw.rounded_rectangle(
                [m, cy, m + bw + pad_x * 2, cy + box_h],
                radius=int(3 * scale), fill=accent,
            )
            draw.text(
                (m + pad_x, cy + (box_h - int(16 * scale)) // 2 - int(2 * scale)),
                badge_text, fill=(255, 255, 255), font=fb,
            )
            cy += int(56 * scale)
        else:
            cy += int(16 * scale)

        # Titulo wrap 3 linhas (fb landscape tem pouco width)
        title_font = CreativeService._load_font(int(30 * scale), "bold")
        max_tw = panel_w - m * 2
        title_lines = CreativeService._wrap_text(f["title"], title_font, max_tw, 3, draw)
        line_h = int(38 * scale)
        for i, line in enumerate(title_lines):
            draw.text((m, cy + i * line_h), line, fill=(255, 255, 255), font=title_font)
        cy += len(title_lines) * line_h + int(20 * scale)

        # Preco
        price_font = CreativeService._load_font(int(48 * scale), "display")
        draw.text((m, cy), f["price"], fill=accent, font=price_font)
        cy += int(64 * scale)

        # Separador
        draw.rectangle(
            [(m, cy), (m + int(56 * scale), cy + int(3 * scale))],
            fill=accent,
        )
        cy += int(20 * scale)

        # Features
        feat = CreativeService._build_features_line(f)
        if feat:
            ff = CreativeService._load_font(int(20 * scale), "regular")
            draw.text((m, cy), feat, fill=(255, 255, 255), font=ff)
            cy += int(32 * scale)

        # Location
        if f["location"]:
            fl = CreativeService._load_font(int(18 * scale), "light")
            draw.text((m, cy), f["location"], fill=(220, 220, 220), font=fl)

        # Website rodapé
        if f["website_url"]:
            fw = CreativeService._load_font(int(16 * scale), "regular")
            draw.text(
                (m, height - m - int(18 * scale)),
                f["website_url"], fill=(200, 200, 200), font=fw,
            )

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    # -- Template: Property Card (1080x1350) --------------------------------

    @staticmethod
    def _render_property_card(
        width: int, height: int, template_data: Dict[str, Any],
    ) -> bytes:
        """Layout vertical premium: foto 55% + ficha branca elegante + highlights."""
        from PIL import Image, ImageDraw

        f = CreativeService._extract_template_fields(template_data)
        primary = CreativeService._hex_to_rgb(f["color_primary"])
        accent = CreativeService._hex_to_rgb(f["color_accent"])

        photo_h = int(height * 0.55)
        photo = CreativeService._load_photo(f["cover_photo"], width, photo_h)

        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        img.paste(photo, (0, 0))
        # Gradiente subtil só no terço inferior da foto
        img = CreativeService._apply_gradient(img, 0, 130, 0.65)
        draw = ImageDraw.Draw(img)

        scale = width / 1080
        m = int(64 * scale)

        # --- BADGE + BRAND sobre a foto ---
        badge_text = (f["badge"] or f["typology"] or f["listing_type"]).upper()
        if badge_text:
            fba = CreativeService._load_font(int(20 * scale), "bold")
            bw = draw.textlength(badge_text, font=fba)
            pad_x = int(14 * scale)
            box_h = int(38 * scale)
            by = m
            draw.rounded_rectangle(
                [m, by, m + bw + pad_x * 2, by + box_h],
                radius=int(4 * scale), fill=accent,
            )
            draw.text(
                (m + pad_x, by + (box_h - int(20 * scale)) // 2 - int(2 * scale)),
                badge_text, fill=(255, 255, 255), font=fba,
            )

        fb_brand = CreativeService._load_font(int(24 * scale), "bold")
        brand_txt = f["brand"].upper()
        brand_w = draw.textlength(brand_txt, font=fb_brand)
        draw.text(
            (width - m - brand_w, m + int(8 * scale)),
            brand_txt, fill=(255, 255, 255), font=fb_brand,
        )

        # --- FICHA INFERIOR (fundo branco) ---
        card_y = photo_h + int(48 * scale)

        # Barra accent
        draw.rectangle(
            [(m, card_y), (m + int(72 * scale), card_y + int(4 * scale))],
            fill=accent,
        )
        card_y += int(28 * scale)

        # Titulo wrap 2 linhas
        title_font = CreativeService._load_font(int(40 * scale), "bold")
        title_lines = CreativeService._wrap_text(f["title"], title_font, width - m * 2, 2, draw)
        line_h = int(48 * scale)
        for i, line in enumerate(title_lines):
            draw.text((m, card_y + i * line_h), line, fill=primary, font=title_font)
        card_y += len(title_lines) * line_h + int(16 * scale)

        # Preço XL
        price_font = CreativeService._load_font(int(60 * scale), "display")
        draw.text((m, card_y), f["price"], fill=accent, font=price_font)
        card_y += int(80 * scale)

        # Features + location lado a lado
        feat = CreativeService._build_features_line(f)
        if feat:
            ff = CreativeService._load_font(int(22 * scale), "regular")
            draw.text((m, card_y), feat, fill=(80, 80, 80), font=ff)
            card_y += int(36 * scale)

        if f["location"]:
            fl = CreativeService._load_font(int(20 * scale), "light")
            draw.text((m, card_y), f["location"], fill=(120, 120, 120), font=fl)
            card_y += int(36 * scale)

        # Highlights como bullets (máx 3)
        highlights = f["highlights"][:3] if f["highlights"] else []
        if highlights:
            card_y += int(16 * scale)
            fh = CreativeService._load_font(int(18 * scale), "regular")
            bullet_r = int(4 * scale)
            for h in highlights:
                # Bullet
                bx = m + bullet_r
                by = card_y + int(10 * scale)
                draw.ellipse(
                    [(bx - bullet_r, by - bullet_r), (bx + bullet_r, by + bullet_r)],
                    fill=accent,
                )
                draw.text(
                    (m + int(20 * scale), card_y),
                    h, fill=(70, 70, 70), font=fh,
                )
                card_y += int(32 * scale)

        # --- Rodapé: brand + contacto ---
        footer_y = height - int(80 * scale)
        # Linha separadora cinza
        draw.rectangle(
            [(m, footer_y - int(20 * scale)), (width - m, footer_y - int(19 * scale))],
            fill=(220, 220, 220),
        )
        fb_footer = CreativeService._load_font(int(20 * scale), "bold")
        brand_line = f["brand"].upper()
        draw.text((m, footer_y), brand_line, fill=primary, font=fb_footer)
        if f["contact_phone"]:
            contact_font = CreativeService._load_font(int(18 * scale), "regular")
            cw = draw.textlength(f["contact_phone"], font=contact_font)
            draw.text(
                (width - m - cw, footer_y + int(2 * scale)),
                f["contact_phone"], fill=(80, 80, 80), font=contact_font,
            )

        # Barra accent base
        CreativeService._draw_accent_bar(draw, width, height, accent, int(4 * scale))

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
