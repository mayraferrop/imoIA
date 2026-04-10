"""Helpers e dependencies de role para FastAPI.

Verifica roles (owner, admin, member) em organization_members
via PostgREST (Supabase). Criado na Fase 2B Dia 1.

Roles suportados:
  - owner: todas as permissoes, incluindo accoes destrutivas
  - admin: gestao da organizacao (convites, configs), sem accoes destrutivas
  - member: acesso basico (leitura e operacoes normais)

Dependencies:
  - require_admin: exige owner ou admin (403 se member ou nao-membro)
  - require_owner: exige owner (403 se admin, member ou nao-membro)
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, HTTPException, status
from loguru import logger

from src.api.dependencies.auth import get_current_organization, get_current_user


# ---------------------------------------------------------------------------
# Helpers: consulta de role via PostgREST
# ---------------------------------------------------------------------------


async def get_user_role_in_org(
    user_id: str,
    organization_id: str,
) -> Optional[str]:
    """Retorna o role do utilizador na organizacao especificada.

    Retorna None se o utilizador nao pertencer a organizacao
    ou se houver erro na consulta.
    """
    supa_url = os.getenv("SUPABASE_URL", "")
    supa_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{supa_url}/rest/v1/organization_members"
            f"?user_id=eq.{user_id}&organization_id=eq.{organization_id}"
            f"&select=role&limit=1",
            headers=headers,
            timeout=10,
        )

    if resp.status_code != 200:
        logger.warning(f"Erro ao consultar role: HTTP {resp.status_code}")
        return None

    rows = resp.json()
    if not rows:
        return None

    return rows[0].get("role")


async def is_user_admin_or_owner(
    user_id: str,
    organization_id: str,
) -> bool:
    """Verifica se o utilizador e admin ou owner da organizacao."""
    role = await get_user_role_in_org(user_id, organization_id)
    return role in ("owner", "admin")


async def is_user_owner(
    user_id: str,
    organization_id: str,
) -> bool:
    """Verifica se o utilizador e owner da organizacao."""
    role = await get_user_role_in_org(user_id, organization_id)
    return role == "owner"


# ---------------------------------------------------------------------------
# Dependencies FastAPI
# ---------------------------------------------------------------------------


async def require_admin(
    user: Dict[str, Any] = Depends(get_current_user),
    organization_id: str = Depends(get_current_organization),
) -> Dict[str, Any]:
    """Dependency que verifica se o utilizador e admin ou owner.

    Se nao for, levanta HTTPException 403.

    Uso em endpoints:
        @router.post("/admin-only", dependencies=[Depends(require_admin)])
        async def admin_endpoint():
            ...
    """
    user_id = user["sub"]
    if not await is_user_admin_or_owner(user_id, organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores da organizacao podem aceder a este recurso.",
        )
    return user


async def require_owner(
    user: Dict[str, Any] = Depends(get_current_user),
    organization_id: str = Depends(get_current_organization),
) -> Dict[str, Any]:
    """Dependency que verifica se o utilizador e owner.

    Para accoes destrutivas (eliminar org, transferir ownership).
    Se nao for owner, levanta HTTPException 403.

    Uso em endpoints:
        @router.delete("/org", dependencies=[Depends(require_owner)])
        async def delete_org():
            ...
    """
    user_id = user["sub"]
    if not await is_user_owner(user_id, organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas o proprietario da organizacao pode executar esta accao.",
        )
    return user
