"""Endpoints de perfil do utilizador autenticado.

Fornece GET /me com informacoes do utilizador e as suas organizacoes.
Usado pelo frontend para o OrganizationSwitcher e contexto de sessao.

NAO requer X-Organization-Id — so precisa de JWT valido.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from src.api.dependencies.auth import get_current_user
from src.database import supabase_rest as db

router = APIRouter()


@router.get("/me")
def get_my_profile(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retorna perfil do utilizador e lista de organizacoes."""
    user_id = user["sub"]

    memberships = db._get(
        "organization_members",
        f"user_id=eq.{user_id}"
        f"&select=organization_id,role,organizations(id,name,slug)",
    )

    return {
        "user_id": user_id,
        "email": user.get("email", ""),
        "organizations": [
            {
                "id": m.get("organizations", {}).get("id", ""),
                "name": m.get("organizations", {}).get("name", ""),
                "slug": m.get("organizations", {}).get("slug", ""),
                "role": m.get("role", "member"),
            }
            for m in memberships
        ],
    }
