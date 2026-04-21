"""Cliente Supabase Storage — armazenamento de ficheiros via signed URLs.

Substitui o filesystem local (src/shared/document_storage.py). Todos os
ficheiros (criativos M7, logos brand kit, documentos M5) sao uploaded para
buckets Supabase Storage e servidos via signed URLs (TTL configuravel).

Uso tipico:
    from src.shared.storage_provider import upload_file, get_signed_url

    path = upload_file("creatives", "tenants/{tid}/creative.png", png_bytes, "image/png")
    url = get_signed_url("creatives", path, expires_in=3600)

Autenticacao: usa SUPABASE_SERVICE_ROLE_KEY (backend trusted). Nunca expor a
key no frontend — a leitura no browser e feita via signed URLs publicas.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Dict, Optional, Tuple

import httpx
from loguru import logger


# Cache in-memory dos signed URLs: (bucket, path) -> (url, expires_epoch).
# TTL efectivo = expires_in - _SIGNED_URL_SAFETY_MARGIN, para não devolver
# URLs quase-a-expirar. Thread-safe via lock.
_SIGNED_URL_CACHE: Dict[Tuple[str, str], Tuple[str, float]] = {}
_SIGNED_URL_LOCK = threading.Lock()
_SIGNED_URL_SAFETY_MARGIN = 300  # segundos de margem antes da expiração real


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_SUPA_URL: str = ""
_SUPA_KEY: str = ""

# Buckets padrao do projecto. Criados pelo script init_supabase_storage.py.
BUCKET_CREATIVES = "creatives"       # M7 — criativos gerados (PNG, PDF)
BUCKET_BRAND_ASSETS = "brand-assets" # M7 — logos de brand kit
BUCKET_DOCUMENTS = "documents"        # M5 — documentos de due diligence
BUCKET_PROPERTIES = "properties"      # M1 — fotos de propriedades (futuro)

ALL_BUCKETS = [
    BUCKET_CREATIVES,
    BUCKET_BRAND_ASSETS,
    BUCKET_DOCUMENTS,
    BUCKET_PROPERTIES,
]


def _ensure_config() -> None:
    """Carrega SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY das env vars."""
    global _SUPA_URL, _SUPA_KEY
    if not _SUPA_URL:
        _SUPA_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
        _SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not _SUPA_URL or not _SUPA_KEY:
        raise RuntimeError(
            "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY sao obrigatorias para o "
            "storage provider."
        )


def _headers(content_type: Optional[str] = None) -> dict:
    _ensure_config()
    h = {
        "apikey": _SUPA_KEY,
        "Authorization": f"Bearer {_SUPA_KEY}",
    }
    if content_type:
        h["Content-Type"] = content_type
    return h


# ---------------------------------------------------------------------------
# Operacoes de bucket (criacao idempotente)
# ---------------------------------------------------------------------------


def list_buckets() -> list[dict]:
    """Lista buckets existentes no projecto Supabase Storage."""
    _ensure_config()
    url = f"{_SUPA_URL}/storage/v1/bucket"
    resp = httpx.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def create_bucket(bucket_id: str, public: bool = False) -> dict:
    """Cria um bucket. Idempotente — retorna dict mesmo se ja existe.

    Parametros
    ----------
    bucket_id: identificador do bucket (e tambem o nome visivel)
    public: se True, objectos sao acessiveis sem signed URL (apenas para
            dados nao sensiveis, ex: logos publicos do brand kit).
            Default False — signed URLs sao o padrao seguro.
    """
    _ensure_config()
    url = f"{_SUPA_URL}/storage/v1/bucket"
    payload = {
        "id": bucket_id,
        "name": bucket_id,
        "public": public,
    }
    resp = httpx.post(url, headers=_headers("application/json"), json=payload, timeout=15)
    if resp.status_code == 409 or (
        resp.status_code >= 400 and "already exists" in resp.text.lower()
    ):
        logger.info(f"Bucket '{bucket_id}' ja existe")
        return {"id": bucket_id, "existed": True}
    resp.raise_for_status()
    logger.info(f"Bucket '{bucket_id}' criado (public={public})")
    return resp.json()


# ---------------------------------------------------------------------------
# Operacoes de objecto
# ---------------------------------------------------------------------------


def upload_file(
    bucket: str,
    path: str,
    content: bytes,
    content_type: str = "application/octet-stream",
    upsert: bool = True,
) -> str:
    """Upload de bytes para bucket/path.

    Parametros
    ----------
    bucket: id do bucket (ex: "creatives")
    path: caminho dentro do bucket (ex: "tenants/{tid}/{creative_id}.png")
    content: bytes do ficheiro
    content_type: MIME type (ex: "image/png", "application/pdf")
    upsert: se True, sobrepoe ficheiro existente no mesmo path

    Retorna
    -------
    path do objecto no bucket (para reuso em get_signed_url).
    """
    _ensure_config()
    url = f"{_SUPA_URL}/storage/v1/object/{bucket}/{path}"
    h = _headers(content_type)
    if upsert:
        h["x-upsert"] = "true"
    resp = httpx.post(url, headers=h, content=content, timeout=30)
    if resp.status_code >= 400:
        logger.error(
            f"Upload falhou bucket={bucket} path={path} "
            f"status={resp.status_code} body={resp.text[:200]}"
        )
        resp.raise_for_status()
    logger.info(f"Upload OK bucket={bucket} path={path} size={len(content)}")
    return path


def get_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    """Gera signed URL para download de um objecto.

    Usa cache in-memory: se existir URL ainda válida (com margem de
    _SIGNED_URL_SAFETY_MARGIN), devolve sem chamar Supabase. Evita o custo
    de POST síncrono por foto em endpoints com múltiplos assets.

    Parametros
    ----------
    bucket: id do bucket
    path: caminho do objecto no bucket
    expires_in: segundos ate a URL expirar (default: 3600 = 1h)

    Retorna
    -------
    URL absoluta e publica (sem necessidade de auth) valida durante expires_in.
    """
    cache_key = (bucket, path)
    now = time.time()
    with _SIGNED_URL_LOCK:
        cached = _SIGNED_URL_CACHE.get(cache_key)
        if cached and cached[1] > now:
            return cached[0]

    _ensure_config()
    url = f"{_SUPA_URL}/storage/v1/object/sign/{bucket}/{path}"
    resp = httpx.post(
        url,
        headers=_headers("application/json"),
        json={"expiresIn": expires_in},
        timeout=15,
    )
    if resp.status_code >= 400:
        logger.error(
            f"Signed URL falhou bucket={bucket} path={path} "
            f"status={resp.status_code} body={resp.text[:200]}"
        )
        resp.raise_for_status()
    data = resp.json()
    signed_path = data.get("signedURL") or data.get("signedUrl") or ""
    if not signed_path:
        raise RuntimeError(f"Resposta inesperada do signed URL: {data}")
    # Supabase devolve path relativo — prefixa com URL do projecto
    if signed_path.startswith("/"):
        full_url = f"{_SUPA_URL}/storage/v1{signed_path}"
    elif signed_path.startswith("http"):
        full_url = signed_path
    else:
        full_url = f"{_SUPA_URL}/storage/v1/{signed_path}"

    expires_epoch = now + max(expires_in - _SIGNED_URL_SAFETY_MARGIN, 60)
    with _SIGNED_URL_LOCK:
        _SIGNED_URL_CACHE[cache_key] = (full_url, expires_epoch)
    return full_url


def get_public_url(bucket: str, path: str) -> str:
    """URL publica para buckets marcados como public (sem auth).

    Usa-se apenas em buckets public=True. Para buckets privados, usar
    get_signed_url().
    """
    _ensure_config()
    return f"{_SUPA_URL}/storage/v1/object/public/{bucket}/{path}"


def delete_file(bucket: str, path: str) -> bool:
    """Apaga um objecto do bucket."""
    _ensure_config()
    url = f"{_SUPA_URL}/storage/v1/object/{bucket}/{path}"
    resp = httpx.delete(url, headers=_headers(), timeout=15)
    if resp.status_code >= 400:
        logger.error(
            f"Delete falhou bucket={bucket} path={path} "
            f"status={resp.status_code}"
        )
        return False
    logger.info(f"Delete OK bucket={bucket} path={path}")
    return True


def download_file(bucket: str, path: str) -> bytes:
    """Download de um objecto (usa service role — so backend)."""
    _ensure_config()
    url = f"{_SUPA_URL}/storage/v1/object/{bucket}/{path}"
    resp = httpx.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.content
