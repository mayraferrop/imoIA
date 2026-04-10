"""Schemas de membros de organizacao — Fase 2B Dia 4."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MemberResponse(BaseModel):
    user_id: str
    email: str
    role: str
    created_at: Optional[str] = None


class MemberRoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(admin|member)$")
