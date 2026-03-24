"""Plugin Pillow — fallback para ambientes sem Playwright/Chromium."""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from loguru import logger

from src.modules.m7_marketing.plugins.base import CreativePlugin


class PillowPlugin(CreativePlugin):
    """Gera imagens branded simples com Pillow (fallback)."""

    @property
    def name(self) -> str:
        return "pillow"

    @property
    def label(self) -> str:
        return "Pillow (fallback básico)"

    @property
    def is_available(self) -> bool:
        try:
            from PIL import Image
            return True
        except ImportError:
            return False

    @property
    def supported_types(self) -> List[str]:
        return ["ig_post", "ig_story", "fb_post", "property_card"]

    def generate(
        self,
        creative_type: str,
        width: int,
        height: int,
        template_data: Dict[str, Any],
    ) -> Optional[bytes]:
        """Gera imagem placeholder branded com Pillow."""
        try:
            from PIL import Image, ImageDraw

            color_primary = template_data.get("color_primary", "#1E3A5F")
            color_accent = template_data.get("color_accent", "#E76F51")
            pr, pg, pb = int(color_primary[1:3], 16), int(color_primary[3:5], 16), int(color_primary[5:7], 16)
            ar, ag, ab = int(color_accent[1:3], 16), int(color_accent[3:5], 16), int(color_accent[5:7], 16)

            img = Image.new("RGB", (width, height), color=(pr, pg, pb))
            draw = ImageDraw.Draw(img)

            title = template_data.get("title", "")[:50]
            price = template_data.get("price_formatted", "")
            brand = template_data.get("brand_name", "HABTA")
            scale = min(width, height) / 1080
            tx = int(40 * scale)
            ty = height // 2 - int(60 * scale)

            draw.text((int(30 * scale), int(30 * scale)), brand, fill=(255, 255, 255))
            draw.text((tx, ty), title, fill=(255, 255, 255))
            draw.text((tx, ty + int(50 * scale)), price, fill=(ar, ag, ab))
            draw.rectangle([(0, height - int(6 * scale)), (width, height)], fill=(ar, ag, ab))

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except ImportError:
            return None
        except Exception as exc:
            logger.warning(f"Pillow render falhou: {exc}")
            return None

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "description": "Gera placeholders branded simples. Usar apenas como fallback.",
            "requirements": ["Pillow"],
            "cost": "Gratuito",
            "quality": "Básica (texto sobre cor sólida)",
        }
