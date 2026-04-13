"""Servico M7h — Email Campaign Engine.

Gera campanhas de email HTML com base nos dados do listing, deal, property
e brand kit do tenant, usando templates Jinja2.
Envio real via Resend (src/shared/email_provider.py).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger
from sqlalchemy import func, select

from src.database.db import get_session
from src.database.models_v2 import (
    BrandKit,
    Deal,
    EmailCampaign,
    Listing,
    Property,
    Tenant,
)
from src.shared.email_provider import send_email, validate_email

_DEFAULT_TENANT_SLUG = "default"

# Directorio de templates HTML
_TEMPLATES_DIR = Path(__file__).parent / "email_templates"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_default_tenant_id(session: Any) -> str:
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
        logger.info("Tenant default criado (email_service)")

    return tenant.id


def _campaign_to_dict(c: EmailCampaign) -> Dict[str, Any]:
    """Serializa EmailCampaign para dict."""
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "listing_id": c.listing_id,
        "campaign_type": c.campaign_type,
        "subject": c.subject,
        "body_html": c.body_html,
        "body_text": c.body_text,
        "language": c.language,
        "recipient_count": c.recipient_count,
        "recipient_filter": c.recipient_filter or {},
        "status": c.status,
        "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
        "sent_at": c.sent_at.isoformat() if c.sent_at else None,
        "delivered": c.delivered,
        "opened": c.opened,
        "clicked": c.clicked,
        "open_rate": c.open_rate,
        "click_rate": c.click_rate,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ---------------------------------------------------------------------------
# Templates inline (fallback quando nao existe ficheiro externo)
# ---------------------------------------------------------------------------

_INLINE_TEMPLATES: Dict[str, str] = {
    "new_property": """\
<!DOCTYPE html>
<html lang="{{ language }}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{ subject }}</title>
  <style>
    body { margin: 0; padding: 0; font-family: {{ font_body }}, Arial, sans-serif; background: #f5f5f5; }
    .wrapper { max-width: 600px; margin: 32px auto; background: #fff; border-radius: 8px; overflow: hidden; }
    .header { background: {{ color_primary }}; padding: 32px 24px; text-align: center; }
    .header h1 { margin: 0; color: #fff; font-family: {{ font_heading }}, sans-serif; font-size: 24px; }
    .header p { margin: 8px 0 0; color: rgba(255,255,255,0.85); font-size: 14px; }
    .body { padding: 32px 24px; color: #333; }
    .body h2 { color: {{ color_primary }}; font-family: {{ font_heading }}, sans-serif; margin-top: 0; }
    .highlight-box { background: #f9f9f9; border-left: 4px solid {{ color_accent }}; padding: 16px 20px; margin: 24px 0; border-radius: 0 4px 4px 0; }
    .highlight-box p { margin: 0; font-size: 15px; }
    .price { font-size: 28px; font-weight: bold; color: {{ color_primary }}; margin: 8px 0; }
    .details-grid { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }
    .detail-item { background: #f0f0f0; border-radius: 4px; padding: 8px 14px; font-size: 13px; color: #555; }
    .cta-btn { display: inline-block; background: {{ color_accent }}; color: #fff; text-decoration: none; padding: 14px 32px; border-radius: 6px; font-family: {{ font_heading }}, sans-serif; font-weight: bold; font-size: 15px; margin: 24px 0; }
    .footer { background: #f5f5f5; padding: 20px 24px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #e0e0e0; }
    .footer a { color: {{ color_primary }}; text-decoration: none; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>{{ brand_name }}</h1>
      {% if tagline %}<p>{{ tagline }}</p>{% endif %}
    </div>
    <div class="body">
      <h2>{{ title }}</h2>
      <div class="highlight-box">
        <p>{{ short_description }}</p>
      </div>
      <div class="price" style="color: {{ color_primary }};">{{ price_formatted }}</div>
      <div class="details-grid">
        {% if typology %}<div class="detail-item">{{ typology }}</div>{% endif %}
        {% if area %}<div class="detail-item">{{ area }} m²</div>{% endif %}
        {% if location %}<div class="detail-item">📍 {{ location }}</div>{% endif %}
        {% if bedrooms %}<div class="detail-item">{{ bedrooms }} quartos</div>{% endif %}
      </div>
      {% if description %}
      <p style="line-height: 1.7; color: #444;">{{ description }}</p>
      {% endif %}
      {% if highlights %}
      <ul style="padding-left: 20px; color: #444; line-height: 1.8;">
        {% for h in highlights %}<li>{{ h }}</li>{% endfor %}
      </ul>
      {% endif %}
      {% if contact_phone or contact_email %}
      <p style="margin-top: 24px; font-size: 14px; color: #666;">
        Para mais informacoes:
        {% if contact_phone %} <strong>{{ contact_phone }}</strong>{% endif %}
        {% if contact_email %} | <a href="mailto:{{ contact_email }}" style="color: {{ color_primary }};">{{ contact_email }}</a>{% endif %}
      </p>
      {% endif %}
    </div>
    <div class="footer">
      <p>&copy; {{ year }} {{ brand_name }}. Todos os direitos reservados.</p>
      {% if website_url %}<p><a href="{{ website_url }}">{{ website_url }}</a></p>{% endif %}
    </div>
  </div>
</body>
</html>
""",
    "price_reduction": """\
<!DOCTYPE html>
<html lang="{{ language }}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{ subject }}</title>
  <style>
    body { margin: 0; padding: 0; font-family: {{ font_body }}, Arial, sans-serif; background: #f5f5f5; }
    .wrapper { max-width: 600px; margin: 32px auto; background: #fff; border-radius: 8px; overflow: hidden; }
    .header { background: {{ color_primary }}; padding: 32px 24px; text-align: center; }
    .header h1 { margin: 0; color: #fff; font-family: {{ font_heading }}, sans-serif; font-size: 24px; }
    .badge { display: inline-block; background: {{ color_accent }}; color: #fff; padding: 6px 18px; border-radius: 20px; font-size: 13px; font-weight: bold; margin-top: 12px; }
    .body { padding: 32px 24px; color: #333; }
    .body h2 { color: {{ color_primary }}; font-family: {{ font_heading }}, sans-serif; margin-top: 0; }
    .price-reduction { text-align: center; margin: 24px 0; padding: 20px; background: #fff8f0; border: 2px solid {{ color_accent }}; border-radius: 8px; }
    .price-old { font-size: 16px; color: #999; text-decoration: line-through; }
    .price-new { font-size: 32px; font-weight: bold; color: {{ color_primary }}; margin-top: 4px; }
    .footer { background: #f5f5f5; padding: 20px 24px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #e0e0e0; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>{{ brand_name }}</h1>
      <div class="badge">Reducao de Preco</div>
    </div>
    <div class="body">
      <h2>{{ title }}</h2>
      <p style="color: #555;">{{ short_description }}</p>
      <div class="price-reduction">
        <div class="price-old">{{ old_price_formatted }}</div>
        <div class="price-new" style="color: {{ color_primary }};">{{ price_formatted }}</div>
        {% if price_reduction_pct %}<div style="font-size: 14px; color: {{ color_accent }}; margin-top: 4px;">{{ price_reduction_pct }}% de reducao</div>{% endif %}
      </div>
      {% if location %}<p>📍 {{ location }}</p>{% endif %}
      {% if contact_phone or contact_email %}
      <p style="font-size: 14px; color: #666;">
        Contacte-nos:
        {% if contact_phone %} <strong>{{ contact_phone }}</strong>{% endif %}
        {% if contact_email %} | <a href="mailto:{{ contact_email }}" style="color: {{ color_primary }};">{{ contact_email }}</a>{% endif %}
      </p>
      {% endif %}
    </div>
    <div class="footer">
      <p>&copy; {{ year }} {{ brand_name }}.</p>
    </div>
  </div>
</body>
</html>
""",
    "generic": """\
<!DOCTYPE html>
<html lang="{{ language }}">
<head>
  <meta charset="UTF-8" />
  <title>{{ subject }}</title>
  <style>
    body { margin: 0; padding: 0; font-family: {{ font_body }}, Arial, sans-serif; background: #f5f5f5; }
    .wrapper { max-width: 600px; margin: 32px auto; background: #fff; border-radius: 8px; overflow: hidden; }
    .header { background: {{ color_primary }}; padding: 32px 24px; text-align: center; }
    .header h1 { margin: 0; color: #fff; font-size: 22px; }
    .body { padding: 32px 24px; color: #333; line-height: 1.7; }
    .footer { background: #f5f5f5; padding: 20px 24px; text-align: center; font-size: 12px; color: #888; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header"><h1>{{ brand_name }}</h1></div>
    <div class="body">
      <h2 style="color: {{ color_primary }};">{{ title }}</h2>
      <p>{{ short_description }}</p>
      {% if description %}<p>{{ description }}</p>{% endif %}
    </div>
    <div class="footer"><p>&copy; {{ year }} {{ brand_name }}.</p></div>
  </div>
</body>
</html>
""",
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EmailService:
    """Logica de negocio M7h — Email Campaign Engine.

    Gera campanhas de email HTML usando Jinja2, com base nos dados do
    listing, deal, property e brand kit. As campanhas ficam em estado
    'draft'; o envio real requer configuracao de provider externo.
    """

    def __init__(self) -> None:
        """Inicializa o servico e o ambiente Jinja2."""
        # Tentar carregar templates do disco; fallback para templates inline
        if _TEMPLATES_DIR.is_dir():
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(_TEMPLATES_DIR)),
                autoescape=select_autoescape(["html"]),
            )
        else:
            self._jinja_env = Environment(
                loader=None,
                autoescape=select_autoescape(["html"]),
            )
        logger.debug("EmailService inicializado")

    # --- Geracao de campanha ---

    def generate_email(
        self,
        listing_id: str,
        campaign_type: str,
        language: str = "pt-PT",
    ) -> Dict[str, Any]:
        """Gera uma campanha de email para um listing.

        Carrega os dados do listing, deal, property e brand kit;
        renderiza o template HTML com Jinja2; cria um registo
        EmailCampaign com status='draft'.

        Parametros
        ----------
        listing_id:
            ID do listing.
        campaign_type:
            Tipo de campanha ('new_property', 'price_reduction', etc.).
        language:
            Codigo de idioma (default 'pt-PT').

        Retorna
        -------
        Dict com os dados da campanha criada.
        """
        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                raise ValueError(f"Listing nao encontrada: {listing_id}")

            deal = session.get(Deal, listing.deal_id) if listing.deal_id else None
            prop = (
                session.get(Property, deal.property_id) if deal else None
            )

            # Brand kit
            brand_kit = session.execute(
                select(BrandKit).where(BrandKit.tenant_id == listing.tenant_id)
            ).scalar_one_or_none()

            # Contexto do template
            ctx = self._build_template_context(
                listing=listing,
                deal=deal,
                prop=prop,
                brand_kit=brand_kit,
                campaign_type=campaign_type,
                language=language,
            )

            # Renderizar HTML
            body_html = self._render_html(campaign_type, ctx)

            # Assunto da campanha
            subject = self._build_subject(campaign_type, listing, ctx, language)

            campaign = EmailCampaign(
                id=str(uuid4()),
                tenant_id=listing.tenant_id,
                listing_id=listing_id,
                campaign_type=campaign_type,
                subject=subject,
                body_html=body_html,
                body_text=self._html_to_text(body_html),
                language=language,
                status="draft",
                recipient_count=0,
                recipient_filter={},
                delivered=0,
                opened=0,
                clicked=0,
                open_rate=0.0,
                click_rate=0.0,
            )
            session.add(campaign)
            session.flush()

            logger.info(
                f"EmailCampaign {campaign.id} criada: listing={listing_id}, "
                f"type={campaign_type}, lang={language}"
            )
            return _campaign_to_dict(campaign)

    async def send_campaign(
        self,
        campaign_id: str,
        recipients: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Envia uma campanha de email via Resend.

        Parametros
        ----------
        campaign_id:
            ID da campanha a enviar.
        recipients:
            Lista de emails. Se None, usa recipient_filter da campanha.

        Retorna
        -------
        Dict com sent_count, failed_count e details.
        """
        with get_session() as session:
            campaign = session.get(EmailCampaign, campaign_id)
            if not campaign:
                raise ValueError(f"Campanha nao encontrada: {campaign_id}")

            if campaign.status == "sent":
                return {
                    "status": "already_sent",
                    "campaign_id": campaign_id,
                    "message": "Campanha ja foi enviada.",
                }

            if not recipients:
                return {
                    "status": "no_recipients",
                    "campaign_id": campaign_id,
                    "message": "Lista de destinatarios vazia.",
                }

            subject = campaign.subject
            html_body = campaign.body_html

        # Filtrar emails invalidos
        valid = [e for e in recipients if validate_email(e)]
        invalid = [e for e in recipients if not validate_email(e)]

        if invalid:
            logger.warning(f"Emails invalidos ignorados: {invalid}")

        sent_count = 0
        failed_count = len(invalid)
        details: List[Dict[str, Any]] = []

        for email_addr in valid:
            result = await send_email(
                to=email_addr,
                subject=subject,
                html_body=html_body,
            )
            if result.get("sent"):
                sent_count += 1
                details.append({"email": email_addr, "sent": True, "id": result.get("id")})
            else:
                failed_count += 1
                details.append({"email": email_addr, "sent": False, "reason": result.get("reason")})

            # Rate limiting: 10 emails/segundo (conservador)
            await asyncio.sleep(0.1)

        # Actualizar campanha
        with get_session() as session:
            campaign = session.get(EmailCampaign, campaign_id)
            if campaign:
                campaign.status = "sent" if sent_count > 0 else "failed"
                campaign.sent_at = datetime.now(tz=timezone.utc)
                campaign.recipient_count = sent_count
                campaign.delivered = sent_count
                session.flush()

        logger.info(
            f"Campanha {campaign_id}: {sent_count} enviados, "
            f"{failed_count} falhados"
        )

        return {
            "status": "sent" if sent_count > 0 else "failed",
            "campaign_id": campaign_id,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "details": details,
        }

    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Retorna uma campanha por ID.

        Parametros
        ----------
        campaign_id:
            ID da campanha.

        Retorna
        -------
        Dict com os dados da campanha ou None se nao existir.
        """
        with get_session() as session:
            campaign = session.get(EmailCampaign, campaign_id)
            return _campaign_to_dict(campaign) if campaign else None

    def list_campaigns(
        self,
        listing_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista campanhas com filtros opcionais.

        Parametros
        ----------
        listing_id:
            Filtro por listing (opcional).
        status:
            Filtro por estado (opcional).

        Retorna
        -------
        Lista de dicts com as campanhas.
        """
        with get_session() as session:
            stmt = select(EmailCampaign).order_by(
                EmailCampaign.created_at.desc()
            )
            if listing_id:
                stmt = stmt.where(EmailCampaign.listing_id == listing_id)
            if status:
                stmt = stmt.where(EmailCampaign.status == status)

            campaigns = session.execute(stmt).scalars().all()
            return [_campaign_to_dict(c) for c in campaigns]

    def get_email_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas globais das campanhas de email.

        Inclui: total de campanhas, media de open_rate e click_rate,
        distribuicao por estado e por tipo.

        Retorna
        -------
        Dict com as estatisticas.
        """
        with get_session() as session:
            all_campaigns = (
                session.execute(select(EmailCampaign)).scalars().all()
            )

            total = len(all_campaigns)
            sent = [c for c in all_campaigns if c.status == "sent"]

            avg_open_rate = (
                round(sum(c.open_rate for c in sent) / len(sent), 2)
                if sent
                else 0.0
            )
            avg_click_rate = (
                round(sum(c.click_rate for c in sent) / len(sent), 2)
                if sent
                else 0.0
            )

            by_status: Dict[str, int] = {}
            by_type: Dict[str, int] = {}
            for c in all_campaigns:
                by_status[c.status] = by_status.get(c.status, 0) + 1
                by_type[c.campaign_type] = by_type.get(c.campaign_type, 0) + 1

            return {
                "total_campaigns": total,
                "total_sent": len(sent),
                "avg_open_rate": avg_open_rate,
                "avg_click_rate": avg_click_rate,
                "by_status": by_status,
                "by_type": by_type,
            }

    # --- Metodos privados ---

    def _build_template_context(
        self,
        listing: Listing,
        deal: Optional[Deal],
        prop: Optional[Property],
        brand_kit: Optional[BrandKit],
        campaign_type: str,
        language: str,
    ) -> Dict[str, Any]:
        """Constroi o contexto para o template Jinja2."""
        # Cores e tipografia do brand kit (com defaults)
        color_primary = "#1E3A5F"
        color_secondary = "#F4A261"
        color_accent = "#E76F51"
        font_heading = "Montserrat"
        font_body = "Inter"
        brand_name = "ImoIA"
        tagline = ""
        website_url = ""
        contact_phone = ""
        contact_email = ""

        if brand_kit:
            color_primary = brand_kit.color_primary or color_primary
            color_secondary = brand_kit.color_secondary or color_secondary
            color_accent = brand_kit.color_accent or color_accent
            font_heading = brand_kit.font_heading or font_heading
            font_body = brand_kit.font_body or font_body
            brand_name = brand_kit.brand_name or brand_name
            tagline = brand_kit.tagline or ""
            website_url = brand_kit.website_url or ""
            contact_phone = brand_kit.contact_phone or ""
            contact_email = brand_kit.contact_email or ""

        # Dados da propriedade
        location_parts = []
        typology = ""
        area: Optional[float] = None
        bedrooms: Optional[int] = None
        if prop:
            location_parts = [
                p for p in [prop.parish, prop.municipality, prop.district]
                if p
            ]
            typology = prop.typology or prop.property_type or ""
            area = prop.gross_area_m2
            bedrooms = prop.bedrooms

        location = ", ".join(location_parts)

        # Preco
        price = listing.listing_price
        price_formatted = f"{price:,.0f} {listing.currency}"

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

        title = getattr(listing, title_field, None) or (
            f"{typology} — {price_formatted}"
            if typology
            else f"{listing.listing_type.capitalize()} — {price_formatted}"
        )

        # Descricao curta
        desc_field = "short_description_pt"
        if language == "en":
            desc_field = "short_description_en"
        short_description = getattr(listing, desc_field, None) or (
            f"{typology} em {location}" if location else title
        )

        # Descricao longa
        long_desc_field = "description_pt"
        if language == "pt-BR":
            long_desc_field = "description_pt_br"
        elif language == "en":
            long_desc_field = "description_en"
        elif language == "fr":
            long_desc_field = "description_fr"
        elif language == "zh":
            long_desc_field = "description_zh"
        description = getattr(listing, long_desc_field, None) or ""

        # Preco antigo (para price_reduction)
        old_price: Optional[float] = None
        old_price_formatted = ""
        price_reduction_pct: Optional[str] = None
        if campaign_type == "price_reduction" and deal:
            old_price = deal.target_sale_price
            if old_price and old_price > price:
                old_price_formatted = f"{old_price:,.0f} {listing.currency}"
                pct = round((old_price - price) / old_price * 100, 1)
                price_reduction_pct = f"{pct:.1f}"

        return {
            # Identidade da marca
            "brand_name": brand_name,
            "tagline": tagline,
            "website_url": website_url,
            "contact_phone": contact_phone,
            "contact_email": contact_email,
            "color_primary": color_primary,
            "color_secondary": color_secondary,
            "color_accent": color_accent,
            "font_heading": font_heading,
            "font_body": font_body,
            # Conteudo do imovel
            "title": title,
            "short_description": short_description,
            "description": description,
            "price_formatted": price_formatted,
            "old_price_formatted": old_price_formatted,
            "price_reduction_pct": price_reduction_pct,
            "typology": typology,
            "area": area,
            "bedrooms": bedrooms,
            "location": location,
            "highlights": listing.highlights or [],
            # Meta
            "language": language,
            "campaign_type": campaign_type,
            "year": datetime.now(tz=timezone.utc).year,
            "subject": "",  # preenchido apos
        }

    def _render_html(self, campaign_type: str, ctx: Dict[str, Any]) -> str:
        """Renderiza o template HTML para o tipo de campanha.

        Tenta carregar o template do disco; se nao existir, usa o
        template inline definido em _INLINE_TEMPLATES.

        Parametros
        ----------
        campaign_type:
            Tipo de campanha ('new_property', 'price_reduction', etc.).
        ctx:
            Contexto para o Jinja2.

        Retorna
        -------
        String HTML renderizada.
        """
        template_filename = f"email_{campaign_type}.html"

        # Tentar ficheiro externo
        if _TEMPLATES_DIR.is_dir():
            template_path = _TEMPLATES_DIR / template_filename
            if template_path.exists():
                try:
                    tmpl = self._jinja_env.get_template(template_filename)
                    return tmpl.render(**ctx)
                except Exception as exc:
                    logger.warning(
                        f"Erro ao renderizar template externo "
                        f"'{template_filename}': {exc}. "
                        "A usar template inline."
                    )

        # Fallback: template inline
        template_str = _INLINE_TEMPLATES.get(
            campaign_type, _INLINE_TEMPLATES["generic"]
        )
        jinja_env = Environment(autoescape=select_autoescape(["html"]))
        tmpl = jinja_env.from_string(template_str)
        return tmpl.render(**ctx)

    def _build_subject(
        self,
        campaign_type: str,
        listing: Listing,
        ctx: Dict[str, Any],
        language: str,
    ) -> str:
        """Constroi o assunto do email com base no tipo de campanha e idioma."""
        price_formatted = ctx.get("price_formatted", "")
        title = ctx.get("title", "")
        location = ctx.get("location", "")

        subjects = {
            "new_property": {
                "pt-PT": f"Nova oportunidade: {title}",
                "pt-BR": f"Nova oportunidade: {title}",
                "en": f"New property: {title}",
                "fr": f"Nouveau bien: {title}",
                "zh": f"新房产: {title}",
            },
            "price_reduction": {
                "pt-PT": f"Reducao de preco — {title}",
                "pt-BR": f"Reducao de preco — {title}",
                "en": f"Price reduction — {title}",
                "fr": f"Reduction de prix — {title}",
                "zh": f"降价通知 — {title}",
            },
            "open_house": {
                "pt-PT": f"Jornada de portas abertas — {location or title}",
                "pt-BR": f"Jornada de portas abertas — {location or title}",
                "en": f"Open house — {location or title}",
                "fr": f"Portes ouvertes — {location or title}",
                "zh": f"开放参观日 — {location or title}",
            },
        }

        lang_subjects = subjects.get(campaign_type, {})
        return (
            lang_subjects.get(language)
            or lang_subjects.get("pt-PT")
            or f"{campaign_type.replace('_', ' ').capitalize()} — {title}"
        )[:255]

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Converte HTML para texto simples (strip de tags).

        Implementacao minima sem dependencia de biblioteca externa.

        Parametros
        ----------
        html:
            HTML a converter.

        Retorna
        -------
        Texto simples sem tags HTML.
        """
        import re

        text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
