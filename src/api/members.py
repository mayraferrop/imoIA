"""Endpoints de membros de organizacao — Fase 2B Dia 4.

2 endpoints:
  GET   /members                  admin: listar membros da org
  PATCH /members/{user_id}/role   admin: alterar role de membro
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies.auth import get_current_organization, get_current_user
from src.api.dependencies.roles import require_admin
from src.api.schemas.members import MemberResponse, MemberRoleUpdate
from src.api.services.members import list_members, update_member_role

router = APIRouter()


# ---------------------------------------------------------------------------
# Admin: listar membros
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[MemberResponse],
    summary="Listar membros da organizacao",
)
async def list_members_endpoint(
    user: Dict[str, Any] = Depends(require_admin),
    organization_id: str = Depends(get_current_organization),
) -> List[MemberResponse]:
    """Lista todos os membros da organizacao com email e role."""
    results = await list_members(organization_id)
    return [MemberResponse(**r) for r in results]


# ---------------------------------------------------------------------------
# Admin: alterar role
# ---------------------------------------------------------------------------


@router.patch(
    "/{user_id}/role",
    response_model=MemberResponse,
    summary="Alterar role de membro",
)
async def update_member_role_endpoint(
    user_id: str,
    body: MemberRoleUpdate,
    user: Dict[str, Any] = Depends(require_admin),
    organization_id: str = Depends(get_current_organization),
) -> MemberResponse:
    """Altera o role de um membro (admin ou member). Owners nao podem ser alterados."""
    try:
        result = await update_member_role(
            organization_id=organization_id,
            target_user_id=user_id,
            new_role=body.role,
            requesting_user_id=user["sub"],
        )
        return MemberResponse(
            user_id=result["user_id"],
            email="",
            role=result["role"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
