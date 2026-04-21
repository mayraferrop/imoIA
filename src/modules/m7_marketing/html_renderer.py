"""Cliente HTTP do Cloudflare Worker que renderiza criativos via @vercel/og.

Ponto único de integração: `render_via_worker(creative_type, template_data) -> bytes`.

Env vars:
    CREATIVES_WORKER_URL    ex: https://imoia-creatives.xxxx.workers.dev
    CREATIVES_WORKER_SECRET shared secret do header X-Worker-Secret

Sem estas vars, a função retorna None e o chamador faz fallback para Pillow.
"""

from __future__ import annotations

import hashlib
import io
import os
from typing import Any, Dict, Optional

import httpx
from loguru import logger
from PIL import Image


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

    primary_image_src = _to_worker_compatible_url(_abs_url(primary_image_url))
    if not primary_image_src:
        logger.warning(
            f"[html_renderer] falha ao preparar imagem para {creative_type}; fallback"
        )
        return None

    logo_src = _to_worker_compatible_url(_abs_url(template_data.get("logo_url")))
    payload = {
        "template": template,
        "brand": {
            "brand_name": template_data.get("brand_name", ""),
            "tagline": template_data.get("tagline"),
            "logo_primary_url": logo_src,
            "logo_white_url": logo_src,
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
            "primary_image_url": primary_image_src,
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


def _is_jpeg_or_png_url(url: str) -> bool:
    """True se a URL aponta claramente para ficheiro JPEG/PNG (por extensão)."""
    lower = url.lower().split("?", 1)[0]
    return lower.endswith((".jpg", ".jpeg", ".png"))


def _to_worker_compatible_url(
    url: Optional[str],
    max_dim: int = 4096,
    quality: int = 95,
) -> Optional[str]:
    """Garante uma URL HTTPS que o Worker consegue fetch + Satori decode.

    Satori/Resvg (workers-og 0.0.27) não suporta data URIs de forma fiável
    e WebP falha intermitentemente com CF error 1102. Estratégia:

    - Já é URL Supabase Storage signed → passa direto (Satori aceita JPEG/PNG).
    - Termina em .jpg/.jpeg/.png → passa direto (evita round-trip desnecessário).
    - Outro caso (WebP, AVIF, relativa, data:) → baixa, converte para JPEG
      com Pillow preservando qualidade original (quality=95, sem downscale para
      dimensões ≤4096px), upload a bucket `creatives` em `source-cache/<sha1>.jpg`
      (idempotente — cache natural por hash da URL) e devolve signed URL.
    """
    if not url:
        return None
    if url.startswith("data:"):
        return _rehost_bytes(
            _data_uri_to_bytes(url), url_hint=url[:60], max_dim=max_dim, quality=quality
        )
    if url.startswith(("http://", "https://")):
        if _is_supabase_signed(url):
            return url
        if _is_jpeg_or_png_url(url):
            return url
        try:
            resp = httpx.get(url, timeout=15.0, follow_redirects=True)
            resp.raise_for_status()
            return _rehost_bytes(
                resp.content, url_hint=url, max_dim=max_dim, quality=quality
            )
        except httpx.HTTPError as exc:
            logger.warning(
                f"[html_renderer] fetch falhou ({url[:80]}): {exc}"
            )
            return None
    return None


def _is_supabase_signed(url: str) -> bool:
    supa = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not supa:
        return False
    return url.startswith(f"{supa}/storage/v1/object/sign/")


def _data_uri_to_bytes(url: str) -> bytes:
    import base64 as _b64

    head, _, body = url.partition(",")
    if ";base64" in head:
        return _b64.b64decode(body)
    return body.encode()


def _rehost_bytes(
    raw: bytes, url_hint: str, max_dim: int, quality: int
) -> Optional[str]:
    """Decodifica `raw` com Pillow, converte p/ JPEG e hospeda no Supabase."""
    try:
        img = Image.open(io.BytesIO(raw))
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=False)
        jpeg_bytes = buf.getvalue()
    except (OSError, ValueError) as exc:
        logger.warning(f"[html_renderer] Pillow falhou ({url_hint[:80]}): {exc}")
        return None

    try:
        from src.shared.storage_provider import (
            BUCKET_CREATIVES,
            get_signed_url,
            upload_file,
        )

        digest = hashlib.sha1(url_hint.encode("utf-8")).hexdigest()[:16]
        path = f"source-cache/{digest}.jpg"
        upload_file(BUCKET_CREATIVES, path, jpeg_bytes, "image/jpeg", upsert=True)
        return get_signed_url(BUCKET_CREATIVES, path, expires_in=3600)
    except (RuntimeError, httpx.HTTPError) as exc:
        logger.warning(
            f"[html_renderer] upload Supabase falhou ({url_hint[:80]}): {exc}"
        )
        return None
