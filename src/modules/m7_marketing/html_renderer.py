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
from typing import Any, Dict, Optional, Tuple

import httpx
from loguru import logger
from PIL import Image, ImageFilter


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

# Dimensões finais do canvas por template. Mirror de TEMPLATE_SPECS no Worker
# (worker-creatives/src/types.ts). Usadas para pré-croppar a imagem primária
# com LANCZOS localmente em vez de deixar Satori/Resvg reescalar com qualidade
# inferior.
_TEMPLATE_DIMS: Dict[str, Tuple[int, int]] = {
    "property_card": (1080, 1350),
    "listing_main": (1200, 900),
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

    target_w, target_h = _TEMPLATE_DIMS.get(template, (None, None))
    primary_image_src = _to_worker_compatible_url(
        _abs_url(primary_image_url), target_w=target_w, target_h=target_h
    )
    if not primary_image_src:
        logger.warning(
            f"[html_renderer] falha ao preparar imagem para {creative_type}; fallback"
        )
        return None

    # Logo mantém aspect ratio original — não passar target dims.
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
    target_w: Optional[int] = None,
    target_h: Optional[int] = None,
    max_dim: int = 4096,
    quality: int = 95,
) -> Optional[str]:
    """Garante uma URL HTTPS que o Worker consegue fetch + Satori decode.

    Satori/Resvg (workers-og 0.0.27) não suporta data URIs de forma fiável
    e WebP falha intermitentemente com CF error 1102.

    Quando `target_w` e `target_h` são fornecidos, a imagem é **pré-croppada e
    redimensionada com Pillow LANCZOS + UnsharpMask** para as dimensões exactas
    do canvas do template. Isto move o resampling da cadeia Resvg (bilinear
    básico) para Pillow (LANCZOS + sharpen), o que produz bordas nítidas mesmo
    quando a fonte tem de ser upscaled para preencher formatos portrait. Sem
    target dims (ex: logos), mantém aspect ratio original.

    Fluxo:
    - Supabase Storage signed ou .jpg/.jpeg/.png sem target dims → passa direto.
    - Qualquer outro caso (ou com target dims) → Pillow processa → JPEG 95 →
      upload a bucket `creatives` em `source-cache/<digest>.jpg` (idempotente
      por hash da URL + dims) → signed URL.
    """
    if not url:
        return None

    need_processing = target_w is not None and target_h is not None

    if url.startswith("data:"):
        return _prepare_bytes(
            _data_uri_to_bytes(url),
            url_hint=url[:60],
            target_w=target_w,
            target_h=target_h,
            max_dim=max_dim,
            quality=quality,
        )

    if url.startswith(("http://", "https://")):
        # Backward-compat: sem target dims, URLs já JPEG/PNG ou Supabase
        # signed passam direto (Satori aceita e poupamos round-trip).
        if not need_processing:
            if _is_supabase_signed(url) or _is_jpeg_or_png_url(url):
                return url
        try:
            resp = httpx.get(url, timeout=15.0, follow_redirects=True)
            resp.raise_for_status()
            return _prepare_bytes(
                resp.content,
                url_hint=url,
                target_w=target_w,
                target_h=target_h,
                max_dim=max_dim,
                quality=quality,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                f"[html_renderer] fetch falhou ({url[:80]}): {exc}"
            )
            return None
    return None


def _cover_crop_resize(
    img: Image.Image, target_w: int, target_h: int
) -> Image.Image:
    """Equivalente Pillow LANCZOS de CSS `object-fit: cover`.

    Crop centrado para aspect ratio alvo, depois LANCZOS para dims exactas.
    Produz resampling muito superior ao de Resvg (bilinear), o que importa
    quando o canvas tem aspect ratio diferente da foto e há upscale local.
    """
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        new_w = int(round(src_h * target_ratio))
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    elif src_ratio < target_ratio:
        new_h = int(round(src_w / target_ratio))
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))

    if img.size == (target_w, target_h):
        return img
    return img.resize((target_w, target_h), Image.Resampling.LANCZOS)


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


def _prepare_bytes(
    raw: bytes,
    url_hint: str,
    target_w: Optional[int],
    target_h: Optional[int],
    max_dim: int,
    quality: int,
) -> Optional[str]:
    """Decodifica, processa (crop+LANCZOS+sharpen se target dims) e hospeda.

    Com target dims: crop tipo `object-fit: cover` + resize LANCZOS +
    UnsharpMask leve. Entrega ao Worker JPEG com dimensões exactas do canvas
    → Satori faz paste 1:1 sem reinterpolar (qualidade muito superior).

    Sem target dims: apenas converte formato (WebP/AVIF → JPEG) preservando
    resolução original até `max_dim`.
    """
    try:
        img = Image.open(io.BytesIO(raw))
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        if target_w and target_h:
            img = _cover_crop_resize(img, target_w, target_h)
            # Sharpen conservador: compensa softness de upscale sem criar halos.
            # radius=1.0, percent=40, threshold=3 são valores seguros para fotos.
            img = img.filter(
                ImageFilter.UnsharpMask(radius=1.0, percent=40, threshold=3)
            )
        elif max(img.size) > max_dim:
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

        # Cache key inclui dims para não colidir entre templates com aspect
        # ratios diferentes (property_card 1080x1350 vs listing_main 1200x900).
        dims_tag = f"_{target_w}x{target_h}" if target_w and target_h else ""
        cache_input = f"{url_hint}|q{quality}{dims_tag}"
        digest = hashlib.sha1(cache_input.encode("utf-8")).hexdigest()[:16]
        path = f"source-cache/{digest}.jpg"
        upload_file(BUCKET_CREATIVES, path, jpeg_bytes, "image/jpeg", upsert=True)
        return get_signed_url(BUCKET_CREATIVES, path, expires_in=3600)
    except (RuntimeError, httpx.HTTPError) as exc:
        logger.warning(
            f"[html_renderer] upload Supabase falhou ({url_hint[:80]}): {exc}"
        )
        return None
