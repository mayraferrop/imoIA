"""Endpoints de convites de organizacao — Fase 2B Dia 2.

5 endpoints:
  POST   /invites                  admin: criar convite + enviar email
  GET    /invites                  admin: listar convites da org
  GET    /invites/validate/{token} publico: validar token
  POST   /invites/{token}/accept   auth: aceitar convite
  DELETE /invites/{invite_id}      admin: revogar convite
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src.api.dependencies.auth import get_current_organization, get_current_user
from src.api.dependencies.roles import require_admin
from src.api.schemas.invites import (
    InviteAcceptResponse,
    InviteCreate,
    InviteResponse,
    InviteValidateResponse,
)
from src.api.services.invites import (
    accept_invite,
    create_invite,
    get_invite_by_token,
    list_invites,
    revoke_invite,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Admin: criar convite
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=InviteResponse,
    status_code=201,
    summary="Criar convite e enviar email",
)
async def create_invite_endpoint(
    body: InviteCreate,
    user: Dict[str, Any] = Depends(require_admin),
    organization_id: str = Depends(get_current_organization),
) -> InviteResponse:
    """Cria um convite para um email e envia notificacao via Resend."""
    try:
        result = await create_invite(
            organization_id=organization_id,
            email=body.email,
            role=body.role,
            invited_by=user["sub"],
        )
        return InviteResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Admin: listar convites
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[InviteResponse],
    summary="Listar convites da organizacao",
)
async def list_invites_endpoint(
    user: Dict[str, Any] = Depends(require_admin),
    organization_id: str = Depends(get_current_organization),
) -> List[InviteResponse]:
    """Lista todos os convites da organizacao (pendentes primeiro)."""
    results = await list_invites(organization_id)
    return [InviteResponse(**r) for r in results]


# ---------------------------------------------------------------------------
# Publico: validar token
# ---------------------------------------------------------------------------


@router.get(
    "/validate/{token}",
    response_model=InviteValidateResponse,
    summary="Validar token de convite (publico)",
)
async def validate_invite_endpoint(token: str) -> InviteValidateResponse:
    """Valida um token de convite sem necessidade de autenticacao."""
    invite = await get_invite_by_token(token)
    if not invite:
        return InviteValidateResponse(
            valid=False,
            error="Convite invalido, expirado ou ja utilizado.",
        )

    org = invite.get("organizations", {})
    return InviteValidateResponse(
        valid=True,
        organization_name=org.get("name"),
        role=invite.get("role"),
        expires_at=invite.get("expires_at"),
    )


# ---------------------------------------------------------------------------
# Auth: aceitar convite
# ---------------------------------------------------------------------------


@router.post(
    "/{token}/accept",
    response_model=InviteAcceptResponse,
    summary="Aceitar convite",
)
async def accept_invite_endpoint(
    token: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> InviteAcceptResponse:
    """Aceita um convite e adiciona o utilizador a organizacao."""
    user_email = user.get("email", "")
    user_id = user["sub"]

    try:
        result = await accept_invite(
            token=token,
            user_id=user_id,
            user_email=user_email,
        )
        return InviteAcceptResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Admin: revogar convite
# ---------------------------------------------------------------------------


@router.delete(
    "/{invite_id}",
    status_code=204,
    summary="Revogar convite",
)
async def revoke_invite_endpoint(
    invite_id: str,
    user: Dict[str, Any] = Depends(require_admin),
    organization_id: str = Depends(get_current_organization),
) -> None:
    """Revoga um convite pendente."""
    success = await revoke_invite(invite_id, organization_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Convite nao encontrado ou ja utilizado/revogado.",
        )
