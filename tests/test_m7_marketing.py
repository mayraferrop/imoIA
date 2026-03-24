"""Testes M7 — Marketing Engine.

Testa brand kit, listings, geracao de conteudo, integracao M4.
"""

from __future__ import annotations

import pytest

from src.modules.m7_marketing.languages import SUPPORTED_LANGUAGES, CHANNEL_SPECS


# ---------------------------------------------------------------------------
# Languages + Channels
# ---------------------------------------------------------------------------


class TestLanguages:
    def test_five_languages(self) -> None:
        assert len(SUPPORTED_LANGUAGES) == 5
        assert "pt-PT" in SUPPORTED_LANGUAGES
        assert "pt-BR" in SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES
        assert "fr" in SUPPORTED_LANGUAGES
        assert "zh" in SUPPORTED_LANGUAGES

    def test_each_has_required_fields(self) -> None:
        for key, lang in SUPPORTED_LANGUAGES.items():
            assert "label" in lang
            assert "flag" in lang
            assert "claude_instruction" in lang

    def test_channels_exist(self) -> None:
        expected = {
            "website", "instagram_post", "instagram_story",
            "facebook_post", "facebook_group", "linkedin",
            "tiktok", "whatsapp", "portal", "email",
        }
        assert expected.issubset(set(CHANNEL_SPECS.keys()))


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TestMarketingService:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        import os
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
        from src.database.db import reset_engine, _get_engine
        from src.database.models import Base
        reset_engine()
        import src.database.models_v2  # noqa: F401
        engine = _get_engine()
        Base.metadata.create_all(bind=engine)
        self.service = __import__(
            "src.modules.m7_marketing.service",
            fromlist=["MarketingService"],
        ).MarketingService()
        self.m4_service = __import__(
            "src.modules.m4_deal_pipeline.service",
            fromlist=["DealPipelineService"],
        ).DealPipelineService()
        yield
        from src.database.db import reset_engine as re
        re()

    def _create_deal(self, strategy="fix_and_flip"):
        from uuid import uuid4
        from src.database.db import get_session
        from src.database.models_v2 import Property, Tenant
        from sqlalchemy import select
        with get_session() as session:
            tenant = session.execute(
                select(Tenant).where(Tenant.slug == "default")
            ).scalar_one_or_none()
            if not tenant:
                tenant = Tenant(
                    id=str(uuid4()), name="Test", slug="default", country="PT"
                )
                session.add(tenant)
                session.flush()
            prop = Property(
                id=str(uuid4()), tenant_id=tenant.id, source="test",
                country="PT", municipality="Lisboa", parish="Sacavem",
                property_type="apartamento", typology="T2",
                gross_area_m2=85, bedrooms=2,
                asking_price=295000, status="lead",
            )
            session.add(prop)
            session.flush()
            prop_id = prop.id
        return self.m4_service.create_deal({
            "property_id": prop_id,
            "investment_strategy": strategy,
            "title": "Test M7",
            "purchase_price": 295000,
            "target_sale_price": 500000,
        })

    # --- Brand Kit ---

    def test_create_brand_kit(self) -> None:
        bk = self.service.create_or_update_brand_kit({
            "brand_name": "HABTA",
            "tagline": "Investimento imobiliario inteligente",
            "color_primary": "#1E3A5F",
            "voice_tone": "profissional",
            "active_languages": ["pt-PT", "en"],
        })
        assert bk["brand_name"] == "HABTA"
        assert bk["color_primary"] == "#1E3A5F"

    def test_update_brand_kit(self) -> None:
        self.service.create_or_update_brand_kit({"brand_name": "Test"})
        updated = self.service.create_or_update_brand_kit({
            "brand_name": "HABTA Updated",
        })
        assert updated["brand_name"] == "HABTA Updated"

    def test_get_brand_kit(self) -> None:
        self.service.create_or_update_brand_kit({"brand_name": "HABTA"})
        bk = self.service.get_brand_kit()
        assert bk is not None
        assert bk["brand_name"] == "HABTA"

    # --- Listings ---

    def test_create_listing(self) -> None:
        deal = self._create_deal()
        listing = self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": False,
        })
        assert listing["listing_type"] == "venda"
        assert listing["listing_price"] == 500000
        assert listing["status"] == "draft"

    def test_create_listing_auto_generate(self) -> None:
        self.service.create_or_update_brand_kit({"brand_name": "Test"})
        deal = self._create_deal()
        listing = self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": True,
            "languages": ["pt-PT"],
        })
        # Content should be generated (or placeholder if no API key)
        assert listing["status"] in ("draft", "content_generated")

    def test_list_listings(self) -> None:
        deal = self._create_deal()
        self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": False,
        })
        result = self.service.list_listings()
        assert result["total"] >= 1

    def test_update_listing(self) -> None:
        deal = self._create_deal()
        listing = self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": False,
        })
        updated = self.service.update_listing(listing["id"], {
            "title_pt": "T2 Renovado em Sacavem",
        })
        assert updated["title_pt"] == "T2 Renovado em Sacavem"

    def test_approve_content(self) -> None:
        deal = self._create_deal()
        listing = self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": False,
        })
        approved = self.service.approve_content(listing["id"])
        assert approved["status"] == "aprovado"

    # --- Preco ---

    def test_change_price(self) -> None:
        deal = self._create_deal()
        listing = self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": False,
        })
        updated = self.service.change_price(listing["id"], 480000, "Ajuste mercado")
        assert updated["listing_price"] == 480000
        history = self.service.get_price_history(listing["id"])
        assert len(history) == 1
        assert history[0]["old_price"] == 500000
        assert history[0]["new_price"] == 480000

    # --- Status ---

    def test_mark_as_sold(self) -> None:
        deal = self._create_deal()
        listing = self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": False,
        })
        sold = self.service.mark_as_sold(listing["id"], 495000)
        assert sold["status"] == "vendido"

    def test_mark_as_rented(self) -> None:
        deal = self._create_deal()
        listing = self.service.create_listing(deal["id"], {
            "listing_type": "arrendamento",
            "listing_price": 1500,
            "auto_generate": False,
        })
        rented = self.service.mark_as_rented(listing["id"])
        assert rented["status"] == "arrendado"

    # --- Stats ---

    def test_marketing_stats(self) -> None:
        deal = self._create_deal()
        self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": False,
        })
        stats = self.service.get_marketing_stats()
        assert stats["active_listings"] >= 1
        assert stats["total_value"] >= 500000

    # --- M4 Integration ---

    def test_auto_create_on_em_venda(self) -> None:
        deal = self._create_deal()
        for target in ["oportunidade", "analise", "proposta", "negociacao",
                        "cpcv_compra", "due_diligence", "escritura_compra",
                        "obra", "em_venda"]:
            deal = self.m4_service.advance_deal(deal["id"], target)

        # Listing should have been auto-created by M7 hook
        listing = self.service.get_listing_by_deal(deal["id"])
        assert listing is not None
        assert listing["listing_type"] == "venda"

    def test_auto_create_on_arrendamento(self) -> None:
        deal = self._create_deal("buy_and_hold")
        # Set monthly_rent for arrendamento listing
        self.m4_service.update_deal(deal["id"], {"monthly_rent": 1500})
        for target in ["oportunidade", "analise", "proposta", "negociacao",
                        "cpcv_compra", "escritura_compra", "arrendamento"]:
            deal = self.m4_service.advance_deal(deal["id"], target)

        listing = self.service.get_listing_by_deal(deal["id"])
        assert listing is not None
        assert listing["listing_type"] == "arrendamento"

    # --- Publishers (stubs) ---

    def test_publish_to_habta_stub(self) -> None:
        deal = self._create_deal()
        listing = self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": False,
        })
        result = self.service.publish_to_habta(listing["id"])
        assert "status" in result  # stub returns placeholder

    def test_send_to_whatsapp_stub(self) -> None:
        deal = self._create_deal()
        listing = self.service.create_listing(deal["id"], {
            "listing_type": "venda",
            "listing_price": 500000,
            "auto_generate": False,
        })
        result = self.service.send_to_whatsapp(listing["id"])
        assert "status" in result  # stub returns placeholder
