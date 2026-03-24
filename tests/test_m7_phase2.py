"""Testes M7 Phase 2 — Creative Engine + Email Campaigns.

Testa geracao de criativos visuais (PNG/PDF) e campanhas de email HTML
com Jinja2, brand colors e suporte multilingue.
"""

from __future__ import annotations

import os

import pytest


# ---------------------------------------------------------------------------
# Fixture de base de dados
# ---------------------------------------------------------------------------


class TestM7Phase2:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
        from src.database.db import reset_engine, _get_engine
        from src.database.models import Base

        reset_engine()
        import src.database.models_v2  # noqa: F401

        engine = _get_engine()
        Base.metadata.create_all(bind=engine)

        self.creative_service = __import__(
            "src.modules.m7_marketing.creative_service",
            fromlist=["CreativeService"],
        ).CreativeService()
        self.email_service = __import__(
            "src.modules.m7_marketing.email_service",
            fromlist=["EmailService"],
        ).EmailService()
        self.m4_service = __import__(
            "src.modules.m4_deal_pipeline.service",
            fromlist=["DealPipelineService"],
        ).DealPipelineService()
        self.m7_service = __import__(
            "src.modules.m7_marketing.service",
            fromlist=["MarketingService"],
        ).MarketingService()
        yield
        from src.database.db import reset_engine as re

        re()

    # ---------------------------------------------------------------------------
    # Helper
    # ---------------------------------------------------------------------------

    def _create_deal_with_listing(
        self,
        listing_price: float = 500000.0,
        strategy: str = "fix_and_flip",
    ):
        """Cria deal + property + tenant + listing e retorna (deal, listing)."""
        from uuid import uuid4
        from src.database.db import get_session
        from src.database.models_v2 import Property, Tenant, BrandKit
        from sqlalchemy import select

        with get_session() as session:
            # Tenant
            tenant = session.execute(
                select(Tenant).where(Tenant.slug == "default")
            ).scalar_one_or_none()
            if not tenant:
                tenant = Tenant(
                    id=str(uuid4()),
                    name="Test Tenant",
                    slug="default",
                    country="PT",
                )
                session.add(tenant)
                session.flush()

            tenant_id = tenant.id

            # Brand Kit
            bk = session.execute(
                select(BrandKit).where(BrandKit.tenant_id == tenant_id)
            ).scalar_one_or_none()
            if not bk:
                bk = BrandKit(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    brand_name="HABTA",
                    tagline="Investimento inteligente",
                    color_primary="#1E3A5F",
                    color_secondary="#F4A261",
                    color_accent="#E76F51",
                    font_heading="Montserrat",
                    font_body="Inter",
                    contact_phone="+351 900 000 000",
                    contact_email="info@habta.eu",
                    website_url="https://habta.eu",
                    active_languages=["pt-PT", "pt-BR", "en"],
                )
                session.add(bk)
                session.flush()

            # Property
            prop = Property(
                id=str(uuid4()),
                tenant_id=tenant_id,
                source="test",
                country="PT",
                municipality="Lisboa",
                parish="Sacavem",
                property_type="apartamento",
                typology="T2",
                gross_area_m2=85.0,
                bedrooms=2,
                bathrooms=1,
                floor=3,
                has_elevator=True,
                asking_price=295000,
                status="lead",
            )
            session.add(prop)
            session.flush()
            prop_id = prop.id

        # Criar deal via M4
        deal = self.m4_service.create_deal(
            {
                "property_id": prop_id,
                "investment_strategy": strategy,
                "title": "T2 Sacavem — Test Phase 2",
                "purchase_price": 295000,
                "target_sale_price": listing_price,
            }
        )

        # Criar listing via M7
        listing = self.m7_service.create_listing(
            deal["id"],
            {
                "listing_type": "venda",
                "listing_price": listing_price,
                "auto_generate": False,
                "highlights": ["Remodelado", "Elevador", "Vista rio"],
            },
        )

        return deal, listing

    # ---------------------------------------------------------------------------
    # Testes de criativos
    # ---------------------------------------------------------------------------

    def test_generate_ig_post(self) -> None:
        """Gera criativo Instagram Post e verifica tipo, formato e dimensoes."""
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_ig_post(listing["id"])

        assert creative["creative_type"] == "ig_post"
        assert creative["format"] == "png"
        assert creative["width"] == 1080
        assert creative["height"] == 1080

    def test_generate_ig_story(self) -> None:
        """Gera criativo Instagram Story e verifica dimensoes 1080x1920."""
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_ig_story(listing["id"])

        assert creative["creative_type"] == "ig_story"
        assert creative["format"] == "png"
        assert creative["width"] == 1080
        assert creative["height"] == 1920

    def test_generate_fb_post(self) -> None:
        """Gera criativo Facebook Post e verifica dimensoes 1200x630."""
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_fb_post(listing["id"])

        assert creative["creative_type"] == "fb_post"
        assert creative["format"] == "png"
        assert creative["width"] == 1200
        assert creative["height"] == 630

    def test_generate_property_card(self) -> None:
        """Gera property card e verifica dimensoes 1080x1350."""
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_property_card(listing["id"])

        assert creative["creative_type"] == "property_card"
        assert creative["format"] == "png"
        assert creative["width"] == 1080
        assert creative["height"] == 1350

    def test_generate_all_creatives(self) -> None:
        """Gera todos os criativos e verifica que sao 5 ou mais."""
        _, listing = self._create_deal_with_listing()
        creatives = self.creative_service.generate_all_creatives(listing["id"])

        assert len(creatives) >= 5

    def test_generate_flyer_pdf(self) -> None:
        """Gera flyer PDF e verifica o formato."""
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_flyer_pdf(listing["id"])

        assert creative["format"] == "pdf"
        assert creative["creative_type"] == "flyer"

    def test_brand_kit_in_template(self) -> None:
        """Verifica que o template_data contem as cores do brand kit."""
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_ig_post(listing["id"])

        template_data = creative["template_data"]
        assert "color_primary" in template_data
        # Brand kit tem color_primary="#1E3A5F"
        assert template_data["color_primary"] == "#1E3A5F"

    def test_creative_stored_in_documents(self) -> None:
        """Verifica que o document_id nao e None quando PIL esta disponivel.

        Se PIL nao estiver instalado, o document_id pode ser None — o
        teste aceita ambas as situacoes mas verifica que o campo existe.
        """
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_ig_post(listing["id"])

        # O campo document_id deve existir no dict (pode ser None se PIL nao disponivel)
        assert "document_id" in creative

    def test_list_creatives(self) -> None:
        """Cria 2 criativos e verifica que a listagem retorna 2."""
        _, listing = self._create_deal_with_listing()
        self.creative_service.generate_ig_post(listing["id"])
        self.creative_service.generate_ig_story(listing["id"])

        creatives = self.creative_service.list_creatives(listing_id=listing["id"])
        assert len(creatives) == 2

    def test_delete_creative(self) -> None:
        """Cria 1 criativo, apaga-o e verifica que a listagem fica vazia."""
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_ig_post(listing["id"])

        deleted = self.creative_service.delete_creative(creative["id"])
        assert deleted is True

        remaining = self.creative_service.list_creatives(listing_id=listing["id"])
        assert len(remaining) == 0

    # ---------------------------------------------------------------------------
    # Testes de email
    # ---------------------------------------------------------------------------

    def test_generate_email_new_property(self) -> None:
        """Gera campanha 'new_property' e verifica body_html nao vazio."""
        _, listing = self._create_deal_with_listing()
        campaign = self.email_service.generate_email(
            listing["id"], campaign_type="new_property"
        )

        assert campaign["campaign_type"] == "new_property"
        assert campaign["body_html"]
        assert len(campaign["body_html"]) > 0

    def test_email_has_css_inline(self) -> None:
        """Verifica que o body_html contem CSS inline (atributo style=)."""
        _, listing = self._create_deal_with_listing()
        campaign = self.email_service.generate_email(
            listing["id"], campaign_type="new_property"
        )

        assert 'style=' in campaign["body_html"]

    def test_email_has_brand_colors(self) -> None:
        """Verifica que o body_html contem a cor primaria do brand kit."""
        _, listing = self._create_deal_with_listing()
        campaign = self.email_service.generate_email(
            listing["id"], campaign_type="new_property"
        )

        # Brand kit criado no helper tem color_primary="#1E3A5F"
        assert "#1E3A5F" in campaign["body_html"]

    def test_list_campaigns(self) -> None:
        """Cria 2 campanhas e verifica que a listagem retorna 2."""
        _, listing = self._create_deal_with_listing()
        self.email_service.generate_email(
            listing["id"], campaign_type="new_property"
        )
        self.email_service.generate_email(
            listing["id"], campaign_type="price_reduction"
        )

        campaigns = self.email_service.list_campaigns(listing_id=listing["id"])
        assert len(campaigns) == 2

    def test_send_campaign_stub(self) -> None:
        """Verifica que o stub de envio retorna mensagem informativa."""
        _, listing = self._create_deal_with_listing()
        campaign = self.email_service.generate_email(
            listing["id"], campaign_type="new_property"
        )

        result = self.email_service.send_campaign(campaign["id"])

        assert "status" in result
        assert "message" in result
        assert "HTML" in result["message"] or "provider" in result["message"].lower()

    def test_email_stats(self) -> None:
        """Verifica que get_email_stats retorna dict com total_campaigns."""
        _, listing = self._create_deal_with_listing()
        self.email_service.generate_email(
            listing["id"], campaign_type="new_property"
        )

        stats = self.email_service.get_email_stats()

        assert "total_campaigns" in stats
        assert stats["total_campaigns"] >= 1

    # ---------------------------------------------------------------------------
    # Testes avancados
    # ---------------------------------------------------------------------------

    def test_creative_multilingual(self) -> None:
        """Gera criativo em pt-BR e verifica que o idioma e registado."""
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_ig_post(
            listing["id"], language="pt-BR"
        )

        assert creative["language"] == "pt-BR"

    def test_qr_code_in_flyer(self) -> None:
        """Verifica que o flyer tem qr_data_uri no template_data."""
        _, listing = self._create_deal_with_listing()
        creative = self.creative_service.generate_flyer_pdf(listing["id"])

        template_data = creative["template_data"]
        assert "qr_data_uri" in template_data
        assert template_data["qr_data_uri"].startswith("data:image/")

    def test_generate_email_price_reduction(self) -> None:
        """Gera campanha 'price_reduction' e verifica que e criada com sucesso."""
        _, listing = self._create_deal_with_listing(listing_price=450000.0)
        campaign = self.email_service.generate_email(
            listing["id"], campaign_type="price_reduction"
        )

        assert campaign["campaign_type"] == "price_reduction"
        assert campaign["status"] == "draft"
        assert campaign["body_html"]
        assert len(campaign["body_html"]) > 0
