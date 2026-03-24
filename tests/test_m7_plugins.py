"""Testes M7 — Plugin Architecture."""

from __future__ import annotations

import pytest


class TestPluginRegistry:
    def test_registry_loads(self) -> None:
        from src.modules.m7_marketing.plugins.registry import get_plugin_registry
        registry = get_plugin_registry()
        assert registry is not None

    def test_creative_engines_available(self) -> None:
        from src.modules.m7_marketing.plugins.registry import get_plugin_registry
        registry = get_plugin_registry()
        engines = registry.list_creative_engines()
        assert len(engines) >= 1
        names = [e["name"] for e in engines]
        assert "playwright" in names or "pillow" in names

    def test_playwright_plugin_exists(self) -> None:
        from src.modules.m7_marketing.plugins.playwright_plugin import PlaywrightPlugin
        pw = PlaywrightPlugin()
        assert pw.name == "playwright"

    def test_playwright_render_if_available(self) -> None:
        from src.modules.m7_marketing.plugins.playwright_plugin import PlaywrightPlugin
        pw = PlaywrightPlugin()
        if not pw.is_available:
            pytest.skip("Playwright não instalado neste ambiente")
        result = pw.generate("ig_post", 540, 540, {
            "title": "Test", "price_formatted": "100€",
            "brand_name": "TEST", "color_primary": "#1E3A5F",
            "color_accent": "#E76F51", "font_heading": "Arial",
            "font_body": "Arial",
        })
        assert result is not None
        assert len(result) > 1000

    def test_pillow_fallback(self) -> None:
        from src.modules.m7_marketing.plugins.pillow_plugin import PillowPlugin
        pl = PillowPlugin()
        result = pl.generate("ig_post", 540, 540, {
            "title": "Test", "price_formatted": "100€",
            "brand_name": "TEST", "color_primary": "#1E3A5F",
            "color_accent": "#E76F51",
        })
        assert result is not None
        assert len(result) > 100

    def test_trolto_not_available_without_key(self) -> None:
        from src.modules.m7_marketing.plugins.trolto_plugin import TroltoCreativePlugin
        tc = TroltoCreativePlugin()
        assert tc.is_available is False

    def test_registry_auto_select(self) -> None:
        from src.modules.m7_marketing.plugins.registry import get_plugin_registry
        registry = get_plugin_registry()
        result = registry.generate_creative("ig_post", 540, 540, {
            "title": "Auto Test", "price_formatted": "200€",
            "brand_name": "TEST", "color_primary": "#1E3A5F",
            "color_accent": "#E76F51", "font_heading": "Arial",
            "font_body": "Arial",
        })
        assert result is not None

    def test_video_engines_list(self) -> None:
        from src.modules.m7_marketing.plugins.registry import get_plugin_registry
        registry = get_plugin_registry()
        engines = registry.list_video_engines()
        assert isinstance(engines, list)

    def test_base_classes_abstract(self) -> None:
        from src.modules.m7_marketing.plugins.base import CreativePlugin
        with pytest.raises(TypeError):
            CreativePlugin()
