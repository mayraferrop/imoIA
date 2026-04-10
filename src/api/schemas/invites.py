"""Schemas Pydantic para convites de organizacao — Fase 2B Dia 2."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InviteCreate(BaseModel):
    """Body para criar um convite."""

    email: str = Field(..., min_length=5, max_length=255)
    role: str = Field("member", pattern="^(admin|member)$")


class InviteResponse(BaseModel):
    """Resposta ao criar/listar um convite."""

    id: str
    email: str
    role: str
    status: str
    expires_at: str
    created_at: str
    organization_name: Optional[str] = None


class InviteAcceptResponse(BaseModel):
    """Resposta ao aceitar um convite."""

    success: bool
    organization_id: str
    role: str


class InviteValidateResponse(BaseModel):
    """Resposta ao validar um token de convite (endpoint publico)."""

    valid: bool
    organization_name: Optional[str] = None
    role: Optional[str] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None
