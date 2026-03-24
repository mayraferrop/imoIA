"""Registry de plugins — gestão centralizada de engines de criativos e vídeos.

Uso:
    registry = PluginRegistry()

    # Gerar criativo com o melhor engine disponível
    bytes = registry.generate_creative("ig_post", 1080, 1080, data)

    # Gerar com engine específico
    bytes = registry.generate_creative("ig_post", 1080, 1080, data, engine="trolto")

    # Listar engines disponíveis
    engines = registry.list_creative_engines()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from src.modules.m7_marketing.plugins.base import (
    CreativePlugin,
    VideoPlugin,
    TourPlugin,
)


class PluginRegistry:
    """Registo centralizado de plugins de criativos, vídeos e tours."""

    def __init__(self) -> None:
        self._creative_plugins: Dict[str, CreativePlugin] = {}
        self._video_plugins: Dict[str, VideoPlugin] = {}
        self._tour_plugins: Dict[str, TourPlugin] = {}
        self._load_default_plugins()

    def _load_default_plugins(self) -> None:
        """Carrega plugins built-in."""
        # Playwright (interno, gratuito)
        try:
            from src.modules.m7_marketing.plugins.playwright_plugin import (
                PlaywrightPlugin,
            )
            pw = PlaywrightPlugin()
            self._creative_plugins[pw.name] = pw
        except Exception as exc:
            logger.debug(f"Playwright plugin não carregado: {exc}")

        # Trolto (externo, premium)
        try:
            from src.modules.m7_marketing.plugins.trolto_plugin import (
                TroltoCreativePlugin,
                TroltoVideoPlugin,
            )
            tc = TroltoCreativePlugin()
            self._creative_plugins[tc.name] = tc
            tv = TroltoVideoPlugin()
            self._video_plugins[tv.name] = tv
        except Exception as exc:
            logger.debug(f"Trolto plugin não carregado: {exc}")

        # Pillow fallback (sempre disponível)
        try:
            from src.modules.m7_marketing.plugins.pillow_plugin import PillowPlugin
            pl = PillowPlugin()
            self._creative_plugins[pl.name] = pl
        except Exception:
            pass

    # --- Creative engines ---

    def list_creative_engines(self) -> List[Dict[str, Any]]:
        """Lista engines de criativos com status."""
        return [
            {
                "name": p.name,
                "label": p.label,
                "available": p.is_available,
                "supported_types": p.supported_types,
                "config": p.get_config_schema(),
            }
            for p in self._creative_plugins.values()
        ]

    def generate_creative(
        self,
        creative_type: str,
        width: int,
        height: int,
        template_data: Dict[str, Any],
        engine: Optional[str] = None,
    ) -> Optional[bytes]:
        """Gera criativo com o engine especificado ou o melhor disponível.

        Prioridade (se engine=None):
        1. Trolto (se configurado e tipo suportado)
        2. Playwright (se instalado)
        3. Pillow (fallback)
        """
        if engine:
            plugin = self._creative_plugins.get(engine)
            if plugin and plugin.is_available:
                return plugin.generate(creative_type, width, height, template_data)
            logger.warning(f"Engine '{engine}' não disponível")
            return None

        # Auto-select: tentar pela prioridade
        priority = ["trolto", "playwright", "pillow"]
        for name in priority:
            plugin = self._creative_plugins.get(name)
            if (
                plugin
                and plugin.is_available
                and creative_type in plugin.supported_types
            ):
                result = plugin.generate(creative_type, width, height, template_data)
                if result:
                    logger.debug(f"Creative gerado por '{name}'")
                    return result

        logger.warning(f"Nenhum engine disponível para '{creative_type}'")
        return None

    # --- Video engines ---

    def list_video_engines(self) -> List[Dict[str, Any]]:
        """Lista engines de vídeo com status."""
        return [
            {
                "name": p.name,
                "label": p.label,
                "available": p.is_available,
                "supported_types": p.supported_types,
            }
            for p in self._video_plugins.values()
        ]

    def generate_video(
        self,
        video_type: str,
        props: Dict[str, Any],
        engine: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gera vídeo com o engine especificado ou o melhor disponível."""
        if engine:
            plugin = self._video_plugins.get(engine)
            if plugin and plugin.is_available:
                return plugin.generate(video_type, props)
            return {"status": "error", "message": f"Engine '{engine}' não disponível"}

        for plugin in self._video_plugins.values():
            if plugin.is_available and video_type in plugin.supported_types:
                return plugin.generate(video_type, props)

        return {"status": "error", "message": "Nenhum engine de vídeo disponível"}

    # --- Tour engines ---

    def list_tour_engines(self) -> List[Dict[str, Any]]:
        """Lista engines de tour virtual."""
        return [
            {
                "name": p.name,
                "label": p.label,
                "available": p.is_available,
            }
            for p in self._tour_plugins.values()
        ]


# Singleton global
_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """Retorna o registry global de plugins."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry
