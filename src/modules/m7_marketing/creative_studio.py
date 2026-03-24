"""CreativeStudio — M7 Phase 2.

Gera pecas visuais/criativas (imagens, PDFs, HTML) para listings imobiliarios
a partir de templates Jinja2 e do brand kit do tenant.

Suporta: ig_post, ig_story, fb_post, property_card, flyer_a4, email_new_property.
Renderizacao: html2image/Pillow (PNG), WeasyPrint (PDF), HTML directo.
"""

from __future__ import annotations

import base64
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import jinja2
from loguru import logger
from sqlalchemy import select

from src.database.db import get_session
from src.database.models_v2 import (
    BrandKit,
    Deal,
    Listing,
    ListingCreative,
    Property,
    Tenant,
)
from src.shared.document_storage import DocumentStorageService

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Diretório base dos templates (relativo a este ficheiro)
_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Mapa de tipos de criativo com dimensoes e formato de saida
CREATIVE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ig_post": {
        "template": "ig_post.html",
        "width": 1080,
        "height": 1080,
        "format": "png",
        "mime_type": "image/png",
        "description": "Post Instagram (1080×1080)",
    },
    "ig_story": {
        "template": "ig_story.html",
        "width": 1080,
        "height": 1920,
        "format": "png",
        "mime_type": "image/png",
        "description": "Story Instagram (1080×1920)",
    },
    "fb_post": {
        "template": "fb_post.html",
        "width": 1200,
        "height": 630,
        "format": "png",
        "mime_type": "image/png",
        "description": "Post Facebook (1200×630)",
    },
    "property_card": {
        "template": "property_card.html",
        "width": 1080,
        "height": 1350,
        "format": "png",
        "mime_type": "image/png",
        "description": "Property Card (1080×1350)",
    },
    "flyer_a4": {
        "template": "flyer_a4.html",
        "width": None,
        "height": None,
        "format": "pdf",
        "mime_type": "application/pdf",
        "description": "Flyer A4 (impressao/PDF)",
    },
    "email_new_property": {
        "template": "email_new_property.html",
        "width": None,
        "height": None,
        "format": "html",
        "mime_type": "text/html",
        "description": "Email — Nova Propriedade (max-width 600px)",
    },
}


# ---------------------------------------------------------------------------
# Helpers de serialização
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
        "template_name": c.template_name,
        "template_data": c.template_data or {},
        "status": c.status,
        "approved_by": c.approved_by,
        "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


# ---------------------------------------------------------------------------
# CreativeStudio
# ---------------------------------------------------------------------------


class CreativeStudio:
    """Gerador de pecas criativas para listings imobiliarios.

    Carrega templates Jinja2 da pasta ``templates/``, popula com dados do
    listing + brand kit e gera ficheiros PNG, PDF ou HTML conforme o tipo.

    Uso tipico
    ----------
    ::

        studio = CreativeStudio()
        result = studio.generate_creative(listing_id, "ig_post")
        # result["file_url"] → caminho local do ficheiro gerado
    """

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def generate_creative(
        self,
        listing_id: str,
        creative_type: str,
        language: str = "pt-PT",
    ) -> Dict[str, Any]:
        """Gera uma peca criativa para um listing.

        Parametros
        ----------
        listing_id:
            ID do listing de origem.
        creative_type:
            Tipo de criativo (ver CREATIVE_TEMPLATES).
        language:
            Idioma do conteudo textual (ex: 'pt-PT', 'en', 'fr').

        Retorna
        -------
        Dict com metadados do ListingCreative criado.

        Raises
        ------
        ValueError
            Se o tipo de criativo for inválido ou o listing nao existir.
        """
        if creative_type not in CREATIVE_TEMPLATES:
            raise ValueError(
                f"Tipo de criativo invalido: '{creative_type}'. "
                f"Opcoes: {list(CREATIVE_TEMPLATES)}"
            )

        config = CREATIVE_TEMPLATES[creative_type]

        with get_session() as session:
            # --- Obter listing e entidades relacionadas ---
            listing = session.get(Listing, listing_id)
            if not listing:
                raise ValueError(f"Listing nao encontrado: {listing_id}")

            deal: Optional[Deal] = None
            prop: Optional[Property] = None
            brand_kit: Optional[BrandKit] = None

            if listing.deal_id:
                deal = session.get(Deal, listing.deal_id)

            if deal and deal.property_id:
                prop = session.get(Property, deal.property_id)

            # BrandKit do tenant
            brand_kit = session.execute(
                select(BrandKit).where(BrandKit.tenant_id == listing.tenant_id)
            ).scalar_one_or_none()

            # --- Construir dados do template ---
            tdata = self._build_template_data(
                listing=listing,
                deal=deal,
                prop=prop,
                brand_kit=brand_kit,
                config=config,
                language=language,
            )

            # --- Renderizar HTML ---
            tmpl = self._load_template(config["template"])
            html = tmpl.render(**tdata)

            # --- Converter para formato final ---
            fmt = config["format"]
            if fmt in ("png", "jpg", "jpeg"):
                file_bytes = self._render_to_image(
                    html,
                    width=config["width"],
                    height=config["height"],
                )
                ext = f".{fmt}"
            elif fmt == "pdf":
                file_bytes = self._render_to_pdf(html)
                ext = ".pdf"
            else:
                # html — guardar directamente
                file_bytes = html.encode("utf-8")
                ext = ".html"

            # --- Guardar via DocumentStorageService ---
            filename = f"{creative_type}_{listing_id[:8]}{ext}"
            storage = DocumentStorageService(
                session=session,
                base_path="storage/creatives",
            )
            doc_result = storage.upload_document(
                file_content=file_bytes,
                filename=filename,
                tenant_id=listing.tenant_id,
                deal_id=deal.id if deal else None,
                document_type="creative",
                title=f"{config['description']} — {tdata.get('title', '')}",
                description=f"Peca criativa {creative_type} gerada automaticamente",
                uploaded_by="creative_studio",
            )

            # --- Criar registo ListingCreative ---
            creative = ListingCreative(
                id=str(uuid4()),
                tenant_id=listing.tenant_id,
                listing_id=listing_id,
                creative_type=creative_type,
                format=fmt,
                width=config.get("width"),
                height=config.get("height"),
                language=language,
                document_id=doc_result.get("id"),
                file_url=doc_result.get("file_path"),
                file_size=len(file_bytes),
                title_used=tdata.get("title"),
                template_name=config["template"],
                template_data={k: v for k, v in tdata.items() if isinstance(v, (str, int, float, bool, type(None)))},
                status="generated",
            )
            session.add(creative)
            session.flush()

            logger.info(
                f"CreativeStudio: {creative_type} gerado para listing {listing_id} "
                f"({fmt}, {len(file_bytes)} bytes)"
            )
            return _creative_to_dict(creative)

    def generate_all_creatives(
        self,
        listing_id: str,
        language: str = "pt-PT",
    ) -> List[Dict[str, Any]]:
        """Gera todos os criativos principais para um listing.

        Tipos gerados: ig_post, ig_story, fb_post, property_card, flyer_a4.
        O email_new_property nao e incluido (gerado separadamente com dados de campanha).

        Parametros
        ----------
        listing_id:
            ID do listing.
        language:
            Idioma do conteudo.

        Retorna
        -------
        Lista de dicts com metadados de cada ListingCreative criado.
        """
        types = ["ig_post", "ig_story", "fb_post", "property_card", "flyer_a4"]
        results: List[Dict[str, Any]] = []
        errors: List[str] = []

        for ctype in types:
            try:
                result = self.generate_creative(listing_id, ctype, language=language)
                results.append(result)
            except Exception as exc:
                logger.warning(
                    f"CreativeStudio: erro ao gerar {ctype} "
                    f"para listing {listing_id}: {exc}"
                )
                errors.append(f"{ctype}: {exc}")

        if errors:
            logger.warning(
                f"CreativeStudio: {len(errors)} erros em generate_all_creatives "
                f"para listing {listing_id}: {errors}"
            )

        logger.info(
            f"CreativeStudio: {len(results)}/{len(types)} criativos gerados "
            f"para listing {listing_id}"
        )
        return results

    def list_creatives(
        self,
        listing_id: str,
        creative_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista criativos gerados para um listing.

        Parametros
        ----------
        listing_id:
            ID do listing.
        creative_type:
            Filtro por tipo (opcional).

        Retorna
        -------
        Lista de dicts com metadados dos criativos.
        """
        with get_session() as session:
            stmt = select(ListingCreative).where(
                ListingCreative.listing_id == listing_id
            )
            if creative_type:
                stmt = stmt.where(ListingCreative.creative_type == creative_type)

            stmt = stmt.order_by(ListingCreative.created_at.desc())
            creatives = session.execute(stmt).scalars().all()
            return [_creative_to_dict(c) for c in creatives]

    def delete_creative(self, creative_id: str) -> bool:
        """Elimina um criativo e o ficheiro associado.

        Parametros
        ----------
        creative_id:
            ID do ListingCreative a eliminar.

        Retorna
        -------
        True se eliminado, False se nao encontrado.
        """
        with get_session() as session:
            creative = session.get(ListingCreative, creative_id)
            if not creative:
                logger.warning(
                    f"CreativeStudio.delete_creative: id nao encontrado: {creative_id}"
                )
                return False

            # Tentar eliminar o ficheiro fisico
            if creative.file_url:
                try:
                    fpath = Path(creative.file_url)
                    if fpath.exists():
                        fpath.unlink()
                        logger.debug(
                            f"CreativeStudio: ficheiro eliminado: {fpath}"
                        )
                except Exception as exc:
                    logger.warning(
                        f"CreativeStudio: nao foi possivel eliminar ficheiro "
                        f"{creative.file_url}: {exc}"
                    )

            session.delete(creative)
            logger.info(f"CreativeStudio: criativo {creative_id} eliminado")
            return True

    # ------------------------------------------------------------------
    # Metodos privados de renderizacao
    # ------------------------------------------------------------------

    def _render_to_image(
        self,
        html: str,
        width: int,
        height: int,
    ) -> bytes:
        """Converte HTML para imagem PNG.

        Tenta html2image primeiro; se nao disponivel usa Pillow como fallback
        criando uma imagem solida com texto sobreposto.

        Parametros
        ----------
        html:
            HTML renderizado.
        width:
            Largura em pixeis.
        height:
            Altura em pixeis.

        Retorna
        -------
        Bytes da imagem PNG.
        """
        # Tentativa 1: html2image
        try:
            from html2image import Html2Image  # type: ignore

            hti = Html2Image(size=(width, height), output_path="/tmp")
            out_file = f"creative_{uuid4().hex}.png"
            hti.screenshot(html_str=html, save_as=out_file)
            out_path = Path("/tmp") / out_file
            if out_path.exists():
                data = out_path.read_bytes()
                out_path.unlink(missing_ok=True)
                logger.debug("CreativeStudio._render_to_image: html2image OK")
                return data
        except ImportError:
            logger.debug(
                "CreativeStudio._render_to_image: html2image nao instalado, "
                "usando fallback Pillow"
            )
        except Exception as exc:
            logger.warning(
                f"CreativeStudio._render_to_image: html2image falhou ({exc}), "
                "usando fallback Pillow"
            )

        # Fallback: Pillow — imagem de placeholder com informacao basica
        return self._pillow_fallback(html, width, height)

    def _pillow_fallback(self, html: str, width: int, height: int) -> bytes:
        """Gera imagem de placeholder com Pillow.

        Cria uma imagem com cor de fundo da marca e texto extraido do HTML.
        Usado quando html2image nao esta disponivel.

        Parametros
        ----------
        html:
            HTML renderizado (usado para extrair texto de fallback).
        width:
            Largura em pixeis.
        height:
            Altura em pixeis.

        Retorna
        -------
        Bytes da imagem PNG.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont  # type: ignore

            # Extrair cor primaria do HTML se possivel (heuristica simples)
            bg_color = "#1E3A5F"
            accent_color = "#E76F51"
            if 'color_primary' in html:
                import re
                m = re.search(r'#([0-9A-Fa-f]{6})', html)
                if m:
                    bg_color = f"#{m.group(1)}"

            img = Image.new("RGB", (width, height), color=bg_color)
            draw = ImageDraw.Draw(img)

            # Gradiente simulado na zona inferior
            overlay_height = height // 2
            for y in range(overlay_height):
                alpha = int(180 * (1 - y / overlay_height))
                draw.line(
                    [(0, height - overlay_height + y), (width, height - overlay_height + y)],
                    fill=(0, 0, 0),
                )

            # Texto de placeholder
            try:
                font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
                font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
            except Exception:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Extrair titulo e preco do HTML (heuristica)
            import re
            title_match = re.search(r'<[^>]*class="property-title[^"]*"[^>]*>([^<]+)<', html)
            price_match = re.search(r'<[^>]*class="property-price[^"]*"[^>]*>([^<]+)<', html)
            title_text = title_match.group(1).strip() if title_match else "Propriedade"
            price_text = price_match.group(1).strip() if price_match else ""

            # Desenhar texto centrado
            draw.text(
                (width // 2, height // 2 - 60),
                title_text[:40],
                font=font_large,
                fill="white",
                anchor="mm",
            )
            if price_text:
                draw.text(
                    (width // 2, height // 2 + 40),
                    price_text,
                    font=font_small,
                    fill=accent_color,
                    anchor="mm",
                )

            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            logger.debug(
                f"CreativeStudio._pillow_fallback: imagem {width}x{height} gerada"
            )
            return buf.read()

        except ImportError:
            logger.warning(
                "CreativeStudio._pillow_fallback: Pillow nao instalado. "
                "A retornar HTML como bytes de fallback final."
            )
            return html.encode("utf-8")
        except Exception as exc:
            logger.error(f"CreativeStudio._pillow_fallback erro: {exc}")
            return html.encode("utf-8")

    def _render_to_pdf(self, html: str) -> bytes:
        """Converte HTML para PDF.

        Tenta WeasyPrint; se nao disponivel guarda o HTML como bytes.

        Parametros
        ----------
        html:
            HTML renderizado.

        Retorna
        -------
        Bytes do PDF (ou HTML como fallback).
        """
        try:
            from weasyprint import HTML as WeasyprintHTML  # type: ignore

            buf = io.BytesIO()
            WeasyprintHTML(string=html).write_pdf(buf)
            buf.seek(0)
            data = buf.read()
            logger.debug(
                f"CreativeStudio._render_to_pdf: PDF gerado ({len(data)} bytes)"
            )
            return data
        except ImportError:
            logger.warning(
                "CreativeStudio._render_to_pdf: WeasyPrint nao instalado. "
                "A guardar HTML como fallback."
            )
            return html.encode("utf-8")
        except Exception as exc:
            logger.warning(
                f"CreativeStudio._render_to_pdf: WeasyPrint falhou ({exc}). "
                "A guardar HTML como fallback."
            )
            return html.encode("utf-8")

    def _generate_qr_code(self, url: str) -> str:
        """Gera QR code como data URI base64 (PNG).

        Parametros
        ----------
        url:
            URL ou texto a codificar no QR.

        Retorna
        -------
        Data URI ``data:image/png;base64,...`` ou string vazia se falhar.
        """
        try:
            import qrcode  # type: ignore
            from qrcode.image.styledpil import StyledPilImage  # type: ignore

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode("utf-8")
            return f"data:image/png;base64,{b64}"
        except ImportError:
            logger.debug(
                "CreativeStudio._generate_qr_code: qrcode nao instalado, "
                "a omitir QR code"
            )
            return ""
        except Exception as exc:
            logger.warning(f"CreativeStudio._generate_qr_code erro: {exc}")
            return ""

    def _load_template(self, template_name: str) -> jinja2.Template:
        """Carrega um template Jinja2 da pasta templates/.

        Parametros
        ----------
        template_name:
            Nome do ficheiro de template (ex: 'ig_post.html').

        Retorna
        -------
        Objecto jinja2.Template pronto a usar.

        Raises
        ------
        FileNotFoundError
            Se o template nao existir.
        """
        template_path = _TEMPLATES_DIR / template_name
        if not template_path.exists():
            raise FileNotFoundError(
                f"Template nao encontrado: {template_path}"
            )

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=jinja2.select_autoescape(["html"]),
            undefined=jinja2.Undefined,  # variaveis indefinidas rendem string vazia
        )
        return env.get_template(template_name)

    # ------------------------------------------------------------------
    # Construtor de dados para o template
    # ------------------------------------------------------------------

    def _build_template_data(
        self,
        listing: Listing,
        deal: Optional[Deal],
        prop: Optional[Property],
        brand_kit: Optional[BrandKit],
        config: Dict[str, Any],
        language: str,
    ) -> Dict[str, Any]:
        """Constroi o dicionario de dados que sera injectado no template.

        Combina dados do listing, property, deal e brand kit, com fallbacks
        para valores por omissao da marca.

        Parametros
        ----------
        listing:
            Listing de origem.
        deal:
            Deal associado (pode ser None).
        prop:
            Property associada (pode ser None).
        brand_kit:
            BrandKit do tenant (pode ser None, usa defaults).
        config:
            Configuracao do tipo de criativo (de CREATIVE_TEMPLATES).
        language:
            Idioma preferencial para texto.

        Retorna
        -------
        Dict com todas as variaveis do template.
        """
        # --- Dados da marca (com defaults ImoIA) ---
        bk_primary = "#1E3A5F"
        bk_secondary = "#F4A261"
        bk_accent = "#E76F51"
        bk_font_heading = "Montserrat"
        bk_font_body = "Inter"
        bk_brand_name = "ImoIA"
        bk_tagline = ""
        bk_website = ""
        bk_phone = ""
        bk_email = ""
        bk_instagram = ""
        bk_facebook = ""
        bk_linkedin = ""

        if brand_kit:
            bk_primary = brand_kit.color_primary or bk_primary
            bk_secondary = brand_kit.color_secondary or bk_secondary
            bk_accent = brand_kit.color_accent or bk_accent
            bk_font_heading = brand_kit.font_heading or bk_font_heading
            bk_font_body = brand_kit.font_body or bk_font_body
            bk_brand_name = brand_kit.brand_name or bk_brand_name
            bk_tagline = brand_kit.tagline or ""
            bk_website = brand_kit.website_url or ""
            bk_phone = brand_kit.contact_phone or ""
            bk_email = brand_kit.contact_email or ""
            bk_instagram = brand_kit.social_instagram or ""
            bk_facebook = brand_kit.social_facebook or ""
            bk_linkedin = brand_kit.social_linkedin or ""

        # --- Titulo localizado ---
        lang_map = {
            "pt-PT": "pt",
            "pt": "pt",
            "en": "en",
            "fr": "fr",
            "pt-BR": "pt_br",
            "zh": "zh",
        }
        lang_key = lang_map.get(language, "pt")

        title = (
            getattr(listing, f"title_{lang_key}", None)
            or listing.title_pt
            or "Propriedade"
        )

        short_description = (
            getattr(listing, f"short_description_{lang_key}", None)
            or getattr(listing, "short_description_pt", None)
            or ""
        )

        # --- Preco formatado ---
        currency = listing.currency or "EUR"
        price_value = listing.listing_price
        if currency == "EUR":
            price_formatted = f"{price_value:,.0f} €".replace(",", ".")
        elif currency == "BRL":
            price_formatted = f"R$ {price_value:,.0f}".replace(",", ".")
        else:
            price_formatted = f"{price_value:,.0f} {currency}"

        if listing.price_negotiable:
            price_formatted += " (neg.)"

        # --- Dados da property ---
        bedrooms: Optional[int] = None
        bathrooms: Optional[int] = None
        area: Optional[str] = None
        energy_cert: Optional[str] = None
        location: Optional[str] = None
        property_type: Optional[str] = None

        if prop:
            bedrooms = prop.bedrooms
            bathrooms = prop.bathrooms
            if prop.gross_area_m2:
                area = str(int(prop.gross_area_m2))
            elif prop.net_area_m2:
                area = str(int(prop.net_area_m2))
            energy_cert = prop.energy_certificate
            property_type = prop.typology or prop.property_type

            # Localizacao: parish, municipality, district
            loc_parts = [
                p for p in [prop.parish, prop.municipality, prop.district] if p
            ]
            location = ", ".join(loc_parts[:2]) if loc_parts else None

        # --- Foto de capa ---
        cover_photo = listing.cover_photo_url
        if not cover_photo and listing.photos:
            photos = listing.photos
            if isinstance(photos, list) and photos:
                cover_photo = photos[0]

        # --- Badge ---
        badge = None
        highlights = listing.highlights or []
        if highlights:
            first = highlights[0] if isinstance(highlights, list) else None
            if first and len(str(first)) <= 20:
                badge = str(first).upper()

        # --- QR code (para flyer e property_card) ---
        qr_data_uri = ""
        creative_type_name = config.get("template", "").replace(".html", "")
        if creative_type_name in ("flyer_a4", "property_card"):
            qr_url = bk_website or f"https://imoia.pt/listing/{listing.id}"
            qr_data_uri = self._generate_qr_code(qr_url)

        # --- Montar dict final ---
        data: Dict[str, Any] = {
            # Dimensoes
            "width": config.get("width", 1080),
            "height": config.get("height", 1080),
            # Conteudo
            "title": title,
            "price": price_formatted,
            "short_description": short_description,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "area": area,
            "energy_cert": energy_cert,
            "location": location,
            "property_type": property_type,
            "listing_type": listing.listing_type,
            "highlights": highlights,
            "badge": badge,
            # Media
            "cover_photo": cover_photo,
            "logo_url": None,  # sem logo ficheiro por defeito
            # Brand
            "brand_name": bk_brand_name,
            "tagline": bk_tagline,
            "color_primary": bk_primary,
            "color_secondary": bk_secondary,
            "color_accent": bk_accent,
            "color_text": "#1a1a1a",
            "color_background": "#111111",
            "font_heading": bk_font_heading,
            "font_body": bk_font_body,
            # Contactos
            "contact_name": bk_brand_name,
            "contact_phone": bk_phone,
            "contact_email": bk_email,
            "website_url": bk_website,
            "social_instagram": bk_instagram,
            "social_facebook": bk_facebook,
            "social_linkedin": bk_linkedin,
            # QR
            "qr_data_uri": qr_data_uri,
            # Email especificos
            "email_subject": listing.content_email_subject or f"Nova propriedade: {title}",
            "cta_url": bk_website or "",
            "cta_label": "Ver imóvel completo",
            "unsubscribe_url": "",
        }

        return data
