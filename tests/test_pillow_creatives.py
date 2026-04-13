"""Testes para Pillow creative engine — M7 marketing."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.modules.m7_marketing.creative_service import CreativeService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_template_data(**overrides):
    """Template data minimo para testes."""
    base = {
        "title": "T2 Renovado em Campanha",
        "price_formatted": "185 000 EUR",
        "brand_name": "HABTA",
        "location": "Porto, Campanha",
        "bedrooms": 2,
        "bathrooms": 1,
        "area": 85,
        "cover_photo": "",
        "color_primary": "#1E3A5F",
        "color_accent": "#E76F51",
        "typology": "T2",
        "badge": "Novo",
        "listing_type": "venda",
        "short_description": "Apartamento renovado com vista rio.",
        "website_url": "habta.eu",
        "contact_phone": "+351 912 345 678",
    }
    base.update(overrides)
    return base


def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """Retorna (width, height) de bytes PNG."""
    img = Image.open(io.BytesIO(png_bytes))
    return img.size


# ---------------------------------------------------------------------------
# Unit: ig_post (1080x1080)
# ---------------------------------------------------------------------------


class TestIGPostTemplate:
    def test_generates_correct_dimensions(self):
        data = _base_template_data()
        result = CreativeService._render_ig_post(1080, 1080, data)
        assert result is not None
        w, h = _png_dimensions(result)
        assert w == 1080
        assert h == 1080

    def test_generates_without_optional_fields(self):
        data = _base_template_data(
            bedrooms=None, bathrooms=None, area=None,
            location="", badge="", typology="",
        )
        result = CreativeService._render_ig_post(1080, 1080, data)
        assert result is not None
        assert len(result) > 1000  # PNG valido, nao vazio


# ---------------------------------------------------------------------------
# Unit: ig_story (1080x1920)
# ---------------------------------------------------------------------------


class TestIGStoryTemplate:
    def test_generates_correct_dimensions(self):
        data = _base_template_data()
        result = CreativeService._render_ig_story(1080, 1920, data)
        assert result is not None
        w, h = _png_dimensions(result)
        assert w == 1080
        assert h == 1920

    def test_no_crash_with_long_title(self):
        data = _base_template_data(title="A" * 50)
        result = CreativeService._render_ig_story(1080, 1920, data)
        assert result is not None


# ---------------------------------------------------------------------------
# Unit: fb_post (1200x630)
# ---------------------------------------------------------------------------


class TestFBPostTemplate:
    def test_generates_correct_dimensions(self):
        data = _base_template_data()
        result = CreativeService._render_fb_post(1200, 630, data)
        assert result is not None
        w, h = _png_dimensions(result)
        assert w == 1200
        assert h == 630

    def test_handles_long_title_wrap(self):
        data = _base_template_data(
            title="Apartamento T3 com Terraço e Vista Panorâmica para o Rio Douro"
        )
        result = CreativeService._render_fb_post(1200, 630, data)
        assert result is not None


# ---------------------------------------------------------------------------
# Unit: property_card (1080x1350)
# ---------------------------------------------------------------------------


class TestPropertyCardTemplate:
    def test_generates_correct_dimensions(self):
        data = _base_template_data()
        result = CreativeService._render_property_card(1080, 1350, data)
        assert result is not None
        w, h = _png_dimensions(result)
        assert w == 1080
        assert h == 1350


# ---------------------------------------------------------------------------
# Integration: dispatcher _try_pillow_fallback
# ---------------------------------------------------------------------------


class TestPillowDispatcher:
    def test_dispatches_ig_post(self):
        data = _base_template_data()
        result = CreativeService._try_pillow_fallback(1080, 1080, data)
        assert result is not None
        assert _png_dimensions(result) == (1080, 1080)

    def test_dispatches_ig_story(self):
        data = _base_template_data()
        result = CreativeService._try_pillow_fallback(1080, 1920, data)
        assert result is not None
        assert _png_dimensions(result) == (1080, 1920)

    def test_dispatches_fb_post(self):
        data = _base_template_data()
        result = CreativeService._try_pillow_fallback(1200, 630, data)
        assert result is not None
        assert _png_dimensions(result) == (1200, 630)

    def test_dispatches_property_card(self):
        data = _base_template_data()
        result = CreativeService._try_pillow_fallback(1080, 1350, data)
        assert result is not None
        assert _png_dimensions(result) == (1080, 1350)

    def test_fallback_generic_square(self):
        """Dimensoes nao mapeadas mas quadradas devem usar ig_post."""
        data = _base_template_data()
        result = CreativeService._try_pillow_fallback(800, 800, data)
        assert result is not None
        assert _png_dimensions(result) == (800, 800)

    def test_fallback_generic_vertical(self):
        """Dimensoes verticais devem usar ig_story."""
        data = _base_template_data()
        result = CreativeService._try_pillow_fallback(900, 1600, data)
        assert result is not None
        assert _png_dimensions(result) == (900, 1600)

    def test_fallback_generic_horizontal(self):
        """Dimensoes horizontais devem usar fb_post."""
        data = _base_template_data()
        result = CreativeService._try_pillow_fallback(1400, 700, data)
        assert result is not None
        assert _png_dimensions(result) == (1400, 700)
