"""Endpoints M6 — Gestao de Obra.

Orcamento, cronograma, milestones, despesas, fotos de progresso.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from loguru import logger
from pydantic import BaseModel

from src.modules.m6_renovation.schemas import (
    ExpenseCreateSchema,
    ExpenseUpdateSchema,
    MilestoneCreateSchema,
    MilestoneUpdateSchema,
    RenovationCreateSchema,
    RenovationUpdateSchema,
)
from src.modules.m6_renovation.service import RenovationService

router = APIRouter()
service = RenovationService()


# ---------------------------------------------------------------------------
# Obra
# ---------------------------------------------------------------------------


@router.post("/deals/{deal_id}/create", summary="Criar obra")
async def create_renovation(
    deal_id: str, data: RenovationCreateSchema
) -> Dict[str, Any]:
    """Cria obra para um deal com milestones auto-gerados."""
    try:
        return service.create_renovation(deal_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deals/{deal_id}", summary="Obter obra completa")
async def get_renovation(deal_id: str) -> Dict[str, Any]:
    """Retorna obra com milestones, despesas, fotos e alertas."""
    result = service.get_renovation(deal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Obra nao encontrada")
    return result


@router.patch("/{renovation_id}", summary="Actualizar obra")
async def update_renovation(
    renovation_id: str, data: RenovationUpdateSchema
) -> Dict[str, Any]:
    """Actualiza dados da obra."""
    try:
        result = service.update_renovation(
            renovation_id, data.model_dump(exclude_unset=True)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Obra nao encontrada")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


@router.get("/{renovation_id}/milestones", summary="Listar milestones")
async def list_milestones(renovation_id: str) -> List[Dict[str, Any]]:
    """Lista milestones de uma obra."""
    return service.get_milestones(renovation_id)


@router.post("/{renovation_id}/milestones", summary="Adicionar milestone")
async def add_milestone(
    renovation_id: str, data: MilestoneCreateSchema
) -> Dict[str, Any]:
    """Adiciona milestone a uma obra."""
    try:
        return service.add_milestone(renovation_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/milestones/{milestone_id}", summary="Actualizar milestone")
async def update_milestone(
    milestone_id: str, data: MilestoneUpdateSchema
) -> Dict[str, Any]:
    """Actualiza milestone."""
    try:
        return service.update_milestone(
            milestone_id, data.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/milestones/{milestone_id}/start", summary="Iniciar milestone"
)
async def start_milestone(milestone_id: str) -> Dict[str, Any]:
    """Marca milestone como em curso."""
    try:
        return service.start_milestone(milestone_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/milestones/{milestone_id}/complete", summary="Concluir milestone"
)
async def complete_milestone(milestone_id: str) -> Dict[str, Any]:
    """Marca milestone como concluido."""
    try:
        return service.complete_milestone(milestone_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/milestones/{milestone_id}", summary="Remover milestone"
)
async def delete_milestone(milestone_id: str) -> Dict[str, Any]:
    """Remove milestone e despesas/fotos associadas."""
    try:
        return {"success": service.delete_milestone(milestone_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Despesas
# ---------------------------------------------------------------------------


@router.get("/{renovation_id}/expenses", summary="Listar despesas")
async def list_expenses(
    renovation_id: str,
    milestone_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Lista despesas de uma obra."""
    return service.list_expenses(renovation_id, milestone_id, category)


@router.post("/{renovation_id}/expenses", summary="Adicionar despesa")
async def add_expense(
    renovation_id: str, data: ExpenseCreateSchema
) -> Dict[str, Any]:
    """Adiciona despesa a uma obra."""
    try:
        return service.add_expense(renovation_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/expenses/{expense_id}", summary="Actualizar despesa")
async def update_expense(
    expense_id: str, data: ExpenseUpdateSchema
) -> Dict[str, Any]:
    """Actualiza despesa."""
    try:
        return service.update_expense(
            expense_id, data.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/expenses/{expense_id}", summary="Remover despesa")
async def delete_expense(expense_id: str) -> Dict[str, Any]:
    """Remove despesa e recalcula totais."""
    try:
        return {"success": service.delete_expense(expense_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/expenses/{expense_id}/paid", summary="Marcar como paga")
async def mark_expense_paid(expense_id: str) -> Dict[str, Any]:
    """Marca despesa como paga."""
    try:
        return service.mark_expense_paid(expense_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/expenses/{expense_id}/invoice", summary="Upload factura"
)
async def upload_invoice(
    expense_id: str,
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """Upload de factura para uma despesa."""
    try:
        content = await file.read()
        return service.upload_invoice(
            expense_id, content, file.filename or "factura.pdf"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{renovation_id}/expense-summary", summary="Resumo de despesas"
)
async def get_expense_summary(renovation_id: str) -> Dict[str, Any]:
    """Retorna resumo financeiro da obra."""
    return service.get_expense_summary(renovation_id)


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------


@router.get("/{renovation_id}/photos", summary="Listar fotos")
async def list_photos(
    renovation_id: str,
    photo_type: Optional[str] = Query(None),
    milestone_id: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Lista fotos de progresso."""
    return service.list_photos(renovation_id, photo_type, milestone_id)


@router.post("/{renovation_id}/photos", summary="Upload foto")
async def upload_photo(
    renovation_id: str,
    file: UploadFile = File(...),
    photo_type: str = Form("progresso"),
    milestone_id: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    room_area: Optional[str] = Form(None),
    taken_by: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Upload de foto de progresso."""
    try:
        content = await file.read()
        return service.upload_photo(
            renovation_id, content, file.filename or "photo.jpg",
            {
                "photo_type": photo_type,
                "milestone_id": milestone_id,
                "caption": caption,
                "room_area": room_area,
                "taken_by": taken_by,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Alertas e Stats
# ---------------------------------------------------------------------------


@router.get("/{renovation_id}/alerts", summary="Alertas de orcamento")
async def get_alerts(renovation_id: str) -> List[Dict[str, Any]]:
    """Retorna alertas de orcamento e cronograma."""
    return service.get_budget_alerts(renovation_id)


@router.get("/stats", summary="Estatisticas globais de obras")
async def get_stats() -> Dict[str, Any]:
    """Retorna stats de todas as obras."""
    return service.get_renovation_stats()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@router.post("/{renovation_id}/complete", summary="Concluir obra")
async def complete_renovation(renovation_id: str) -> Dict[str, Any]:
    """Finaliza a obra e actualiza o deal."""
    try:
        return service.complete_renovation(renovation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Cash Flow Pro sync
# ---------------------------------------------------------------------------


@router.get("/{renovation_id}/cashflow/projects", summary="Listar projectos CFP")
async def list_cashflow_projects(renovation_id: str) -> List[Dict[str, Any]]:
    """Lista projectos activos do Cash Flow Pro."""
    from src.modules.m6_renovation.cashflow_sync import CashFlowSyncService
    try:
        return CashFlowSyncService().list_cashflow_projects()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class LinkProjectSchema(BaseModel):
    cashflow_project_id: str
    cashflow_project_name: str


@router.post("/{renovation_id}/cashflow/link", summary="Ligar projecto CFP")
async def link_cashflow_project(
    renovation_id: str, data: LinkProjectSchema
) -> Dict[str, Any]:
    """Liga um projecto do Cash Flow Pro a uma renovacao."""
    from src.modules.m6_renovation.cashflow_sync import CashFlowSyncService
    try:
        return CashFlowSyncService().link_project(
            renovation_id, data.cashflow_project_id, data.cashflow_project_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{renovation_id}/cashflow/sync", summary="Sincronizar gastos CFP")
async def sync_cashflow_expenses(renovation_id: str) -> Dict[str, Any]:
    """Puxa despesas do Cash Flow Pro para o M6."""
    from src.modules.m6_renovation.cashflow_sync import CashFlowSyncService
    try:
        return CashFlowSyncService().sync_expenses(renovation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{renovation_id}/cashflow/auto-assign", summary="Auto-assign milestones")
async def auto_assign_milestones(renovation_id: str) -> Dict[str, Any]:
    """Atribui despesas sem milestone a milestones por heuristica."""
    from src.modules.m6_renovation.cashflow_sync import CashFlowSyncService
    try:
        return CashFlowSyncService().auto_assign_milestones(renovation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
