"""Endpoint de health check."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check() -> dict:
    """Verifica se a API esta operacional."""
    return {"status": "ok", "service": "imoia"}
