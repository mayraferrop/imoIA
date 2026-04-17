"""Cliente HTTP do Cloudflare Worker que renderiza criativos via @vercel/og.

Ponto único de integração: `render_via_worker(creative_type, template_data) -> bytes`.

Env vars:
    CREATIVES_WORKER_URL    ex: https://imoia-creatives.xxxx.workers.dev
    CREATIVES_WORKER_SECRET shared secret do header X-Worker-Secret

Sem estas vars, a função retorna None e o chamador faz fallback para Pillow.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from loguru import logger


# Mapeamento creative_type -> template do Worker.
# Templates ainda não implementados caem para None e o chamador faz fallback.
_TEMPLATE_MAP: Dict[str, str] = {
    "property_card": "property_card",
    "listing_main": "listing_main",
    # Próximos (ainda não implementados no Worker):
    # "ig_post": "ig_post",
    # "ig_story": "ig_story",
    # "fb_post": "fb_post",
}


def render_via_worker(
    creative_type: str, template_data: Dict[str, Any]
) -> Optional[bytes]:
    """Renderiza um criativo chamando o Cloudflare Worker.

    Retorna bytes do PNG em sucesso, None se o Worker não estiver configurado,
    não suportar o template, ou falhar a chamada (chamador faz fallback).
    """
    worker_url = os.getenv("CREATIVES_WORKER_URL")
    worker_secret = os.getenv("CREATIVES_WORKER_SECRET")
    if not worker_url or not worker_secret:
        return None

    template = _TEMPLATE_MAP.get(creative_type)
    if not template:
        return None

    primary_image_url = template_data.get("cover_photo") or template_data.get(
        "cover_photo_url"
    )
    if not primary_image_url:
        logger.warning(
            f"[html_renderer] sem primary_image_url para {creative_type}; fallback"
        )
        return None

    payload = {
        "template": template,
        "brand": {
            "brand_name": template_data.get("brand_name", ""),
            "tagline": template_data.get("tagline"),
            "logo_primary_url": _abs_url(template_data.get("logo_url")),
            "logo_white_url": _abs_url(template_data.get("logo_url")),
            "primary_color": template_data.get("color_primary"),
            "secondary_color": template_data.get("color_secondary"),
            "accent_color": template_data.get("color_accent"),
            "font_heading": template_data.get("font_heading"),
            "website": template_data.get("website_url"),
            "phone": template_data.get("contact_phone"),
        },
        "listing": {
            "title": template_data.get("title", ""),
            "short_description": template_data.get("short_description"),
            "price_eur": template_data.get("price"),
            "location": template_data.get("location"),
            "typology": template_data.get("typology"),
            "area_m2": template_data.get("area"),
            "bedrooms": template_data.get("bedrooms"),
            "bathrooms": template_data.get("bathrooms"),
            "energy_rating": template_data.get("energy_rating"),
            "highlights": template_data.get("highlights", []) or [],
            "primary_image_url": _abs_url(primary_image_url),
        },
    }

    try:
        resp = httpx.post(
            f"{worker_url.rstrip('/')}/render",
            json=payload,
            headers={"X-Worker-Secret": worker_secret},
            timeout=30.0,
        )
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith(
            "image/png"
        ):
            logger.info(
                f"[html_renderer] OK {creative_type} "
                f"({resp.headers.get('X-Dimensions')}) {len(resp.content)} bytes"
            )
            return resp.content
        logger.warning(
            f"[html_renderer] falhou {creative_type}: "
            f"status={resp.status_code} body={resp.text[:200]}"
        )
        return None
    except httpx.HTTPError as exc:
        logger.error(f"[html_renderer] erro HTTP {creative_type}: {exc}")
        return None


def _abs_url(url: Optional[str]) -> Optional[str]:
    """Converte URLs relativos do backend (/api/v1/...) em absolutos.

    O Worker precisa de URLs que ele próprio consiga fetch — logo, para caminhos
    `/api/v1/documents/...` prefixamos com o domínio público do backend.
    """
    if not url:
        return url
    if url.startswith(("http://", "https://", "data:")):
        return url
    backend = os.getenv("BACKEND_PUBLIC_URL", "https://imoia.onrender.com")
    return f"{backend.rstrip('/')}{url}"
