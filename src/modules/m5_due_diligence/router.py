"""Endpoints M5 — Due Diligence.

Checklists automaticos de documentos e verificacoes por pais e tipo de imovel.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from loguru import logger

from src.modules.m5_due_diligence.schemas import (
    DDCustomItemSchema,
    DDItemUpdateSchema,
    DDRedFlagSchema,
    DDResolveFlagSchema,
)
from src.modules.m5_due_diligence.service import DueDiligenceService

router = APIRouter()
service = DueDiligenceService()


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------


@router.post("/deals/{deal_id}/generate", summary="Gerar checklist")
async def generate_checklist(deal_id: str) -> Dict[str, Any]:
    """Gera checklist automatico de due diligence para um deal."""
    try:
        return service.generate_checklist(deal_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deals/{deal_id}/checklist", summary="Obter checklist")
async def get_checklist(deal_id: str) -> Dict[str, Any]:
    """Retorna checklist completo com progresso."""
    result = service.get_checklist(deal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Checklist nao encontrado")
    return result


@router.get("/deals/{deal_id}/can-proceed", summary="Pode avancar?")
async def can_proceed(deal_id: str) -> Dict[str, Any]:
    """Verifica se o deal pode sair de due diligence."""
    try:
        return service.can_proceed(deal_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Itens
# ---------------------------------------------------------------------------


@router.get("/deals/{deal_id}/items", summary="Listar itens de due diligence")
async def list_items(deal_id: str) -> Dict[str, Any]:
    """Lista itens do checklist de due diligence para um deal."""
    result = service.get_checklist(deal_id)
    if not result:
        return {"deal_id": deal_id, "items": [], "total": 0, "verified": 0}
    return result


@router.patch("/items/{item_id}", summary="Actualizar item")
async def update_item(
    item_id: str, data: DDItemUpdateSchema
) -> Dict[str, Any]:
    """Actualiza status, documento, notas de um item."""
    try:
        return service.update_item(item_id, data.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deals/{deal_id}/items", summary="Adicionar item personalizado")
async def add_custom_item(
    deal_id: str, data: DDCustomItemSchema
) -> Dict[str, Any]:
    """Adiciona item personalizado ao checklist."""
    try:
        return service.add_custom_item(deal_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Documentos de DD items
# ---------------------------------------------------------------------------


@router.post("/items/{item_id}/upload", summary="Upload documento para item")
async def upload_item_document(
    item_id: str,
    file: UploadFile = File(...),
    uploaded_by: str = Form("system"),
) -> Dict[str, Any]:
    """Upload de ficheiro associado a um item de DD."""
    try:
        content = await file.read()
        return service.upload_item_document(
            item_id, content, file.filename or "document", uploaded_by
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/items/{item_id}/document", summary="Remover documento de item")
async def remove_item_document(item_id: str) -> Dict[str, Any]:
    """Remove documento associado a um item."""
    result = service.remove_item_document(item_id)
    return {"success": result}


@router.get("/items/{item_id}/documents", summary="Listar documentos de item")
async def get_item_documents(item_id: str) -> List[Dict[str, Any]]:
    """Lista documentos de um item de DD."""
    return service.get_item_documents(item_id)


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


@router.post("/items/{item_id}/red-flag", summary="Adicionar red flag")
async def add_red_flag(
    item_id: str, data: DDRedFlagSchema
) -> Dict[str, Any]:
    """Marca item com red flag."""
    try:
        return service.add_red_flag(item_id, data.severity, data.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/items/{item_id}/resolve-flag", summary="Resolver red flag")
async def resolve_red_flag(
    item_id: str, data: DDResolveFlagSchema
) -> Dict[str, Any]:
    """Remove red flag com nota de resolucao."""
    try:
        return service.resolve_red_flag(item_id, data.resolution)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/red-flags", summary="Listar red flags")
async def get_red_flags(
    deal_id: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Lista red flags activos."""
    return service.get_red_flags(deal_id)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", summary="Estatisticas de due diligence")
async def get_dd_stats() -> Dict[str, Any]:
    """Retorna metricas gerais de due diligence."""
    return service.get_dd_stats()
