"""Plugin Playwright — render HTML→PNG via Chromium headless.

Engine interno gratuito. Usa templates HTML com Jinja2 e CSS branded.
Melhor qualidade que Pillow, sem custo por render.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from src.modules.m7_marketing.plugins.base import CreativePlugin


class PlaywrightPlugin(CreativePlugin):
    """Renderiza templates HTML para PNG via Playwright Chromium."""

    @property
    def name(self) -> str:
        return "playwright"

    @property
    def label(self) -> str:
        return "Playwright (interno)"

    @property
    def is_available(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            return False

    @property
    def supported_types(self) -> List[str]:
        return ["ig_post", "ig_story", "fb_post", "property_card", "linkedin_post"]

    def generate(
        self,
        creative_type: str,
        width: int,
        height: int,
        template_data: Dict[str, Any],
    ) -> Optional[bytes]:
        """Renderiza template HTML com Playwright."""
        try:
            from playwright.sync_api import sync_playwright
            import jinja2

            # Seleccionar template por tipo
            template_map = {
                "ig_post": "ig_post.html",
                "ig_story": "ig_story.html",
                "fb_post": "fb_post.html",
                "property_card": "property_card.html",
                "linkedin_post": "fb_post.html",
            }
            tmpl_name = template_map.get(creative_type, "ig_post.html")
            tmpl_dir = Path(__file__).parent.parent / "templates"
            tmpl_path = tmpl_dir / tmpl_name

            if not tmpl_path.exists():
                logger.warning(f"Template {tmpl_name} não encontrado em {tmpl_dir}")
                return None

            # Render Jinja2
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(tmpl_dir)),
                autoescape=False,
            )
            template = env.get_template(tmpl_name)
            html = template.render(
                width=width,
                height=height,
                **template_data,
            )

            # Render com Playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    viewport={"width": width, "height": height}
                )
                page.set_content(html, wait_until="networkidle")
                png_bytes = page.screenshot(type="png", full_page=False)
                browser.close()

            logger.info(
                f"Playwright render: {creative_type} {width}x{height} "
                f"({len(png_bytes):,} bytes)"
            )
            return png_bytes

        except ImportError:
            logger.debug("Playwright não instalado")
            return None
        except Exception as exc:
            logger.warning(f"Playwright render falhou: {exc}")
            return None

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "description": "Renderiza templates HTML em imagens PNG via Chromium headless.",
            "requirements": ["playwright", "chromium browser"],
            "cost": "Gratuito",
            "quality": "Alta (HTML/CSS real)",
        }
