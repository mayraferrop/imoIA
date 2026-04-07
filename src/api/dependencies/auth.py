"""Dependencias de autenticacao para FastAPI.

Valida JWT do Supabase Auth via JWKS (chave publica ECC P-256)
e verifica membership em organizacoes.
Usado como Depends() em todos os endpoints que acedem dados.

Fluxo:
  1. get_current_user() — extrai e valida JWT do header Authorization
  2. get_current_organization() — le X-Organization-Id e verifica membership
     Define current_org_id contextvar para filtragem automatica no supabase_rest.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request
from loguru import logger

# JWKS client com cache (recarrega chaves a cada 10 min)
_jwks_client: Optional[PyJWKClient] = None
_JWKS_CACHE_SECONDS = 600


def _get_jwks_client() -> PyJWKClient:
    """Retorna PyJWKClient singleton para o projecto Supabase."""
    global _jwks_client
    if _jwks_client is None:
        supabase_url = os.getenv("SUPABASE_URL", "")
        if not supabase_url:
            raise RuntimeError("SUPABASE_URL nao configurado")
        jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=_JWKS_CACHE_SECONDS)
    return _jwks_client


def get_current_user(request: Request) -> Dict[str, Any]:
    """Extrai e valida JWT do header Authorization.

    Valida a assinatura via JWKS (chave publica do Supabase).
    Retorna o payload do token com sub (user_id), email, role, etc.
    Lanca HTTPException 401 se ausente, mal formado ou invalido.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header ausente")

    parts = auth_header.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Formato invalido. Esperado: Bearer <token>")

    token = parts[1]

    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError as e:
        logger.debug(f"JWT invalido: {e}")
        raise HTTPException(status_code=401, detail="Token invalido")
    except Exception as e:
        logger.error(f"Erro ao validar JWT: {e}")
        raise HTTPException(status_code=401, detail="Erro na validacao do token")

    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Token sem user_id (sub)")

    return payload


async def get_current_organization(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
) -> str:
    """Le X-Organization-Id do header e verifica que o user pertence a essa org.

    Async para que o contextvar current_org_id seja definido no event loop,
    visivel a todos os endpoints async e ao supabase_rest.

    Retorna o organization_id validado.
    Lanca HTTPException 400 se header ausente, 403 se user nao e membro.
    """
    from src.database.supabase_rest import current_org_id

    org_id = request.headers.get("X-Organization-Id", "")
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Header X-Organization-Id ausente",
        )

    user_id = user["sub"]

    # Verificar membership via HTTP directo (async context)
    supa_url = os.getenv("SUPABASE_URL", "")
    supa_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{supa_url}/rest/v1/organization_members"
            f"?user_id=eq.{user_id}&organization_id=eq.{org_id}&limit=1",
            headers=headers,
            timeout=10,
        )

    if resp.status_code != 200 or not resp.json():
        logger.warning(f"User {user_id[:8]}... tentou aceder org {org_id[:8]}... sem membership")
        raise HTTPException(
            status_code=403,
            detail="Sem acesso a esta organizacao",
        )

    # Definir contexto de org para filtragem automatica no supabase_rest
    current_org_id.set(org_id)

    return org_id
