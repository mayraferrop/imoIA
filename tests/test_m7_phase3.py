"""Testes M7 Fase 3 — Video Factory + Social Media Manager."""

from __future__ import annotations

import pytest

from src.modules.m7_marketing.video_factory import VIDEO_TEMPLATES, MUSIC_LIBRARY


# ---------------------------------------------------------------------------
# Video Templates + Music
# ---------------------------------------------------------------------------


class TestVideoConstants:
    def test_six_video_templates(self) -> None:
        assert len(VIDEO_TEMPLATES) == 6
        for key in ("property_showcase", "instagram_reel", "tiktok",
                     "before_after", "investor_pitch", "slideshow"):
            assert key in VIDEO_TEMPLATES

    def test_templates_have_specs(self) -> None:
        for key, tmpl in VIDEO_TEMPLATES.items():
            assert "width" in tmpl
            assert "height" in tmpl
            assert "orientation" in tmpl
            assert "duration_range" in tmpl
            assert "music_mood" in tmpl

    def test_five_music_moods(self) -> None:
        assert len(MUSIC_LIBRARY) == 5
        for mood in ("modern", "luxury", "upbeat", "calm", "corporate"):
            assert mood in MUSIC_LIBRARY
            assert len(MUSIC_LIBRARY[mood]) >= 1


# ---------------------------------------------------------------------------
# Video Factory Service
# ---------------------------------------------------------------------------


class TestVideoFactory:
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
        self.m4 = __import__(
            "src.modules.m4_deal_pipeline.service",
            fromlist=["DealPipelineService"],
        ).DealPipelineService()
        self.m7 = __import__(
            "src.modules.m7_marketing.service",
            fromlist=["MarketingService"],
        ).MarketingService()
        self.vf = __import__(
            "src.modules.m7_marketing.video_factory",
            fromlist=["VideoFactory"],
        ).VideoFactory()
        self.sm = __import__(
            "src.modules.m7_marketing.social_media",
            fromlist=["SocialMediaManager"],
        ).SocialMediaManager()
        yield
        from src.database.db import reset_engine as re
        re()

    def _create_listing(self):
        from uuid import uuid4
        from src.database.db import get_session
        from src.database.models_v2 import Property, Tenant
        from sqlalchemy import select
        with get_session() as session:
            tenant = session.execute(
                select(Tenant).where(Tenant.slug == "default")
            ).scalar_one_or_none()
            if not tenant:
                tenant = Tenant(id=str(uuid4()), name="Test", slug="default", country="PT")
                session.add(tenant)
                session.flush()
            prop = Property(
                id=str(uuid4()), tenant_id=tenant.id, source="test",
                country="PT", municipality="Lisboa", parish="Sacavem",
                property_type="apartamento", typology="T2",
                gross_area_m2=85, bedrooms=2, asking_price=295000, status="lead",
            )
            session.add(prop)
            session.flush()
            prop_id = prop.id
        deal = self.m4.create_deal({
            "property_id": prop_id, "investment_strategy": "fix_and_flip",
            "title": "Test Video", "purchase_price": 295000,
            "target_sale_price": 500000,
        })
        listing = self.m7.create_listing(deal["id"], {
            "listing_type": "venda", "listing_price": 500000,
            "auto_generate": False,
        })
        return listing

    # --- Video ---

    def test_create_video_project(self) -> None:
        listing = self._create_listing()
        video = self.vf.create_video_project(listing["id"], "property_showcase")
        assert video["video_type"] == "property_showcase"
        assert video["width"] == 1920
        assert video["height"] == 1080
        assert video["status"] == "pending"

    def test_prepare_remotion_props(self) -> None:
        listing = self._create_listing()
        video = self.vf.create_video_project(listing["id"], "instagram_reel")
        props = self.vf.prepare_remotion_props(video["id"])
        assert "compositionId" in props or "composition_id" in props or "inputProps" in props or "template_props" in props

    def test_remotion_props_has_brand(self) -> None:
        self.m7.create_or_update_brand_kit({"brand_name": "HABTA", "color_primary": "#1E3A5F"})
        listing = self._create_listing()
        video = self.vf.create_video_project(listing["id"], "property_showcase")
        assert video.get("brand_name") is not None or video.get("color_primary") is not None

    def test_render_stub(self) -> None:
        listing = self._create_listing()
        video = self.vf.create_video_project(listing["id"], "property_showcase")
        rendered = self.vf.render_video(video["id"])
        assert rendered["status"] == "completed"

    def test_generate_all_videos(self) -> None:
        listing = self._create_listing()
        videos = self.vf.generate_all_videos(listing["id"])
        assert len(videos) >= 3

    def test_list_video_projects(self) -> None:
        listing = self._create_listing()
        self.vf.create_video_project(listing["id"], "property_showcase")
        self.vf.create_video_project(listing["id"], "instagram_reel")
        videos = self.vf.list_video_projects(listing["id"])
        assert len(videos) == 2

    def test_delete_video_project(self) -> None:
        listing = self._create_listing()
        video = self.vf.create_video_project(listing["id"], "tiktok")
        self.vf.delete_video_project(video["id"])
        assert self.vf.get_video_project(video["id"]) is None

    def test_video_stats(self) -> None:
        listing = self._create_listing()
        self.vf.generate_all_videos(listing["id"])
        stats = self.vf.get_video_stats()
        assert stats["total_count"] >= 3

    # --- Social Media ---

    def _ensure_tenant(self):
        from uuid import uuid4
        from src.database.db import get_session
        from src.database.models_v2 import Tenant
        from sqlalchemy import select
        with get_session() as session:
            tenant = session.execute(
                select(Tenant).where(Tenant.slug == "default")
            ).scalar_one_or_none()
            if not tenant:
                tenant = Tenant(id=str(uuid4()), name="Test", slug="default", country="PT")
                session.add(tenant)
                session.flush()
            return tenant.id

    def test_add_account(self) -> None:
        tid = self._ensure_tenant()
        acc = self.sm.add_account({
            "platform": "instagram", "account_name": "habta_eu",
            "account_type": "business", "tenant_id": tid,
        })
        assert acc["platform"] == "instagram"
        assert acc["is_active"] is True

    def test_list_accounts(self) -> None:
        tid = self._ensure_tenant()
        self.sm.add_account({"platform": "instagram", "account_name": "habta", "tenant_id": tid})
        self.sm.add_account({"platform": "facebook", "account_name": "habta_fb", "tenant_id": tid})
        all_accs = self.sm.list_accounts()
        assert len(all_accs) == 2
        ig_only = self.sm.list_accounts("instagram")
        assert len(ig_only) == 1

    def test_create_social_post(self) -> None:
        listing = self._create_listing()
        post = self.sm.create_post(listing["id"], "instagram_post")
        assert post["platform"] == "instagram_post"
        assert post["status"] == "draft"

    def test_create_all_posts(self) -> None:
        listing = self._create_listing()
        posts = self.sm.create_all_posts(listing["id"])
        assert len(posts) >= 3
        platforms = {p["platform"] for p in posts}
        assert "instagram_post" in platforms
        assert "facebook_post" in platforms
        assert "linkedin_post" in platforms

    def test_publish_stub(self) -> None:
        listing = self._create_listing()
        post = self.sm.create_post(listing["id"], "instagram_post")
        result = self.sm.publish_post(post["id"])
        assert result["status"] in ("published", "stub")

    def test_schedule_post(self) -> None:
        listing = self._create_listing()
        post = self.sm.create_post(listing["id"], "facebook_post")
        scheduled = self.sm.schedule_post(post["id"], "2026-04-01T11:00:00")
        assert scheduled["status"] == "scheduled"
        assert scheduled["scheduled_at"] is not None

    def test_content_calendar(self) -> None:
        listing = self._create_listing()
        post = self.sm.create_post(listing["id"], "instagram_post")
        self.sm.schedule_post(post["id"], "2026-04-01T11:00:00")
        calendar = self.sm.get_content_calendar(30)
        assert isinstance(calendar, dict)

    def test_social_stats(self) -> None:
        listing = self._create_listing()
        self.sm.create_all_posts(listing["id"])
        stats = self.sm.get_social_stats()
        assert stats["total_posts"] >= 3
