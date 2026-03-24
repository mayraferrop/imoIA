"""Plugin Trolto — criativos premium e vídeos flythrough via API.

Trolto é uma plataforma de marketing imobiliário que gera:
- Criativos estáticos premium (branded, com fotos reais)
- Vídeos flythrough cinematográficos a partir de fotos
- Virtual staging (mobilar virtualmente divisões vazias)

API: https://api.trolto.com (requer API key)
Pricing: por render (créditos)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.config import get_settings
from src.modules.m7_marketing.plugins.base import CreativePlugin, VideoPlugin


class TroltoCreativePlugin(CreativePlugin):
    """Gera criativos premium via Trolto API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = getattr(settings, "trolto_api_key", "") or ""
        self.base_url = getattr(settings, "trolto_base_url", "") or "https://api.trolto.com"

    @property
    def name(self) -> str:
        return "trolto"

    @property
    def label(self) -> str:
        return "Trolto AI (premium)"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    @property
    def supported_types(self) -> List[str]:
        return [
            "ig_post", "ig_story", "fb_post", "property_card",
            "virtual_staging", "twilight_photo", "sky_replacement",
        ]

    def generate(
        self,
        creative_type: str,
        width: int,
        height: int,
        template_data: Dict[str, Any],
    ) -> Optional[bytes]:
        """Gera criativo via Trolto API."""
        if not self.api_key:
            logger.warning("Trolto API key não configurada")
            return None

        try:
            # Mapear tipo para endpoint Trolto
            endpoint_map = {
                "ig_post": "/v1/render/social-post",
                "ig_story": "/v1/render/social-story",
                "fb_post": "/v1/render/social-post",
                "property_card": "/v1/render/property-card",
                "virtual_staging": "/v1/staging/render",
                "twilight_photo": "/v1/enhance/twilight",
                "sky_replacement": "/v1/enhance/sky",
            }
            endpoint = endpoint_map.get(creative_type, "/v1/render/social-post")

            payload = {
                "width": width,
                "height": height,
                "title": template_data.get("title", ""),
                "price": template_data.get("price_formatted", ""),
                "location": template_data.get("location", ""),
                "photos": template_data.get("photos", []),
                "cover_photo": template_data.get("cover_photo", ""),
                "brand": {
                    "name": template_data.get("brand_name", ""),
                    "logo_url": template_data.get("logo_url", ""),
                    "color_primary": template_data.get("color_primary", "#1E3A5F"),
                    "color_accent": template_data.get("color_accent", "#E76F51"),
                    "font_heading": template_data.get("font_heading", "Montserrat"),
                },
                "features": {
                    "bedrooms": template_data.get("bedrooms"),
                    "bathrooms": template_data.get("bathrooms"),
                    "area": template_data.get("area"),
                },
            }

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()

                # Trolto retorna imagem directamente ou URL
                content_type = response.headers.get("content-type", "")
                if "image/" in content_type:
                    logger.info(
                        f"Trolto render: {creative_type} {width}x{height} "
                        f"({len(response.content):,} bytes)"
                    )
                    return response.content
                else:
                    # JSON com URL para download
                    data = response.json()
                    image_url = data.get("url") or data.get("image_url")
                    if image_url:
                        img_resp = client.get(image_url)
                        img_resp.raise_for_status()
                        return img_resp.content

            return None

        except httpx.HTTPStatusError as exc:
            logger.warning(f"Trolto API erro {exc.response.status_code}: {exc}")
            return None
        except Exception as exc:
            logger.warning(f"Trolto render falhou: {exc}")
            return None

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "description": "Criativos premium via Trolto AI. Fotos profissionais, virtual staging, sky replacement.",
            "requirements": ["TROLTO_API_KEY no .env"],
            "cost": "Por crédito (~€0.50-2.00 por render)",
            "quality": "Premium (fotos reais processadas por IA)",
            "settings": {
                "trolto_api_key": {"type": "string", "required": True, "label": "API Key"},
                "trolto_base_url": {"type": "string", "default": "https://api.trolto.com", "label": "Base URL"},
            },
        }


class TroltoVideoPlugin(VideoPlugin):
    """Gera vídeos flythrough cinematográficos via Trolto API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = getattr(settings, "trolto_api_key", "") or ""
        self.base_url = getattr(settings, "trolto_base_url", "") or "https://api.trolto.com"

    @property
    def name(self) -> str:
        return "trolto_video"

    @property
    def label(self) -> str:
        return "Trolto Flythrough (premium)"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    @property
    def supported_types(self) -> List[str]:
        return ["flythrough", "photo_animation", "virtual_tour_video"]

    def generate(
        self,
        video_type: str,
        props: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Inicia geração de vídeo flythrough via Trolto."""
        if not self.api_key:
            return {"status": "error", "message": "Trolto API key não configurada"}

        try:
            endpoint_map = {
                "flythrough": "/v1/video/flythrough",
                "photo_animation": "/v1/video/animate",
                "virtual_tour_video": "/v1/video/tour",
            }
            endpoint = endpoint_map.get(video_type, "/v1/video/flythrough")

            payload = {
                "photos": props.get("photos", []),
                "duration": props.get("duration", 30),
                "music": props.get("music"),
                "brand": props.get("brand", {}),
                "style": props.get("style", "modern"),
                "resolution": props.get("resolution", "1080p"),
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "status": "processing",
                    "job_id": data.get("job_id") or data.get("id"),
                    "estimated_time": data.get("estimated_time", 120),
                    "message": "Vídeo em processamento no Trolto",
                }

        except Exception as exc:
            logger.warning(f"Trolto video falhou: {exc}")
            return {"status": "error", "message": str(exc)}

    def check_status(self, job_id: str) -> Dict[str, Any]:
        """Verifica status de um job Trolto."""
        if not self.api_key:
            return {"status": "error"}

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{self.base_url}/v1/video/status/{job_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return {"status": "unknown"}

    def download(self, job_id: str) -> Optional[bytes]:
        """Download do vídeo gerado."""
        if not self.api_key:
            return None

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.get(
                    f"{self.base_url}/v1/video/download/{job_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                response.raise_for_status()
                return response.content
        except Exception:
            return None

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "description": "Vídeos flythrough cinematográficos a partir de fotos. IA transforma fotos estáticas em vídeos com movimentos de câmara suaves.",
            "requirements": ["TROLTO_API_KEY no .env"],
            "cost": "~€5-15 por vídeo",
            "quality": "Cinematográfica",
        }
