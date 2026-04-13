"""Service de membros de organizacao — Fase 2B Dia 4.

Lista membros e altera roles via PostgREST + Supabase Auth admin API.

Usa JWT do utilizador (via current_user_token) para queries a
organization_members, respeitando RLS. SERVICE_ROLE_KEY mantido
apenas para a admin API (/auth/v1/admin/users/).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


# ---------------------------------------------------------------------------
# Config Supabase
# ---------------------------------------------------------------------------

def _supa_headers() -> Dict[str, str]:
    """Headers com SERVICE_ROLE_KEY — usado apenas para admin API."""
    supa_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    return {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _jwt_or_supa_headers() -> Dict[str, str]:
    """Headers com JWT do utilizador quando disponivel, SERVICE_ROLE_KEY como fallback.

    Usa JWT para respeitar RLS nas tabelas com policies para 'authenticated'
    (organization_members, organizations). Fallback para SERVICE_ROLE_KEY em
    contextos sem request HTTP (workers, scripts).
    """
    from src.database.supabase_rest import current_user_token

    try:
        user_jwt = current_user_token.get()
        anon_key = os.getenv("SUPABASE_ANON_KEY", "")
        return {
            "apikey": anon_key,
            "Authorization": f"Bearer {user_jwt}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
    except LookupError:
        return _supa_headers()


def _supa_url() -> str:
    return os.getenv("SUPABASE_URL", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_user_email(user_id: str) -> Optional[str]:
    """Busca email do user via Supabase Auth admin API."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_supa_url()}/auth/v1/admin/users/{user_id}",
            headers=_supa_headers(),
            timeout=10,
        )

    if resp.status_code == 200:
        return resp.json().get("email")
    return None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_members(organization_id: str) -> List[Dict[str, Any]]:
    """Lista todos os membros de uma organizacao com emails."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_supa_url()}/rest/v1/organization_members"
            f"?organization_id=eq.{organization_id}"
            f"&select=user_id,role,created_at&order=created_at.asc",
            headers=_jwt_or_supa_headers(),
            timeout=10,
        )

    if resp.status_code != 200:
        return []

    members = resp.json()

    result = []
    for m in members:
        email = await _get_user_email(m["user_id"])
        result.append({
            "user_id": m["user_id"],
            "email": email or "desconhecido",
            "role": m["role"],
            "created_at": m.get("created_at", ""),
        })

    return result


async def update_member_role(
    organization_id: str,
    target_user_id: str,
    new_role: str,
    requesting_user_id: str,
) -> Dict[str, Any]:
    """Muda o role de um membro.

    Validacoes:
    - new_role deve ser 'admin' ou 'member'
    - Nao pode alterar o proprio role
    - Nao pode alterar role de owner
    """
    if new_role not in ("admin", "member"):
        raise ValueError("Role deve ser 'admin' ou 'member'.")

    if target_user_id == requesting_user_id:
        raise ValueError("Nao pode alterar o proprio role.")

    # Buscar role actual do target
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_supa_url()}/rest/v1/organization_members"
            f"?user_id=eq.{target_user_id}&organization_id=eq.{organization_id}"
            f"&select=role&limit=1",
            headers=_jwt_or_supa_headers(),
            timeout=10,
        )

    if resp.status_code != 200 or not resp.json():
        raise ValueError("Membro nao encontrado nesta organizacao.")

    current_role = resp.json()[0]["role"]

    if current_role == "owner":
        raise ValueError("Nao pode alterar o role de um owner.")

    # Actualizar role
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{_supa_url()}/rest/v1/organization_members"
            f"?user_id=eq.{target_user_id}&organization_id=eq.{organization_id}",
            headers={**_jwt_or_supa_headers(), "Prefer": "return=representation"},
            json={"role": new_role},
            timeout=10,
        )

    if resp.status_code != 200 or not resp.json():
        logger.error(f"Erro ao alterar role: {resp.status_code} {resp.text}")
        raise RuntimeError("Erro ao alterar role do membro.")

    return {"user_id": target_user_id, "role": new_role}
