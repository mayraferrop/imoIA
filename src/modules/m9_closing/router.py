"""Endpoints M9 — Fecho + P&L.

Closing: workflow administrativo de fecho (CPCV → escritura → registo).
P&L: calculo real vs estimado, portfolio e relatorio fiscal.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from src.modules.m9_closing.schemas import (
    ClosingProcessCreate,
    ClosingProcessUpdate,
    ClosingStatusUpdate,
    DealPnLUpdate,
    PreferenceRightCreate,
    TaxGuideCreate,
)
from src.modules.m9_closing.service import ClosingService, PnLService

router = APIRouter()
closing_service = ClosingService()
pnl_service = PnLService()


# ---------------------------------------------------------------------------
# Non-parameterized routes FIRST
# ---------------------------------------------------------------------------


@router.get(
    "/portfolio/summary",
    summary="Resumo agregado do portfolio",
)
def get_portfolio_summary() -> Dict[str, Any]:
    """Retorna resumo de todos os deals com P&L."""
    return pnl_service.get_portfolio_summary()


@router.get(
    "/portfolio/fiscal-report",
    summary="Relatorio fiscal anual",
)
def get_fiscal_report(
    year: int = Query(..., description="Ano fiscal"),
) -> Dict[str, Any]:
    """Gera relatorio fiscal com mais-valias, dedutiveis e imposto estimado."""
    return pnl_service.generate_fiscal_report(year)


# ---------------------------------------------------------------------------
# Closing endpoints
# ---------------------------------------------------------------------------


@router.post("/closing", summary="Criar processo de fecho")
def create_closing(body: ClosingProcessCreate) -> Dict[str, Any]:
    """Cria processo de fecho com checklist auto-gerada por tipo."""
    try:
        return closing_service.create_closing(body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/closing", summary="Listar processos de fecho")
def list_closings(
    deal_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Lista processos de fecho com filtros opcionais."""
    return closing_service.list_closings(deal_id=deal_id, status=status)


@router.get("/closing/{closing_id}", summary="Detalhe de processo de fecho")
def get_closing(closing_id: str) -> Dict[str, Any]:
    """Retorna detalhe de um processo de fecho."""
    result = closing_service.get_closing(closing_id)
    if not result:
        raise HTTPException(status_code=404, detail="Closing nao encontrado")
    return result


@router.put("/closing/{closing_id}", summary="Actualizar processo de fecho")
def update_closing(
    closing_id: str, body: ClosingProcessUpdate
) -> Dict[str, Any]:
    """Actualiza campos do processo de fecho."""
    try:
        return closing_service.update_closing(
            closing_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/closing/{closing_id}/status",
    summary="Avancar status do closing",
)
def advance_closing_status(
    closing_id: str, body: ClosingStatusUpdate
) -> Dict[str, Any]:
    """Avanca o status do closing com validacao de transicao."""
    try:
        return closing_service.advance_status(
            closing_id, body.target_status, body.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/closing/{closing_id}/tax-guide",
    summary="Emitir guia fiscal (IMT/IS)",
)
def issue_tax_guide(
    closing_id: str, body: TaxGuideCreate
) -> Dict[str, Any]:
    """Emite guia fiscal com validade 48 horas."""
    try:
        return closing_service.issue_tax_guide(
            closing_id, body.guide_type, body.amount
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/closing/{closing_id}/preference-right",
    summary="Notificar direito de preferencia",
)
def notify_preference_right(
    closing_id: str, body: PreferenceRightCreate
) -> Dict[str, Any]:
    """Regista notificacao do direito de preferencia (prazo 10 dias)."""
    try:
        return closing_service.notify_preference_right(
            closing_id, body.entities, body.notification_date
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/closing/{closing_id}/checklist/{item_key}",
    summary="Marcar item da checklist",
)
def update_checklist_item(
    closing_id: str,
    item_key: str,
    done: bool = Query(True, description="Marcar como feito"),
) -> Dict[str, Any]:
    """Marca ou desmarca item da checklist."""
    try:
        return closing_service.update_checklist_item(closing_id, item_key, done)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/closing/deal/{deal_id}",
    summary="Processos de fecho de um deal",
)
def get_closings_for_deal(deal_id: str) -> List[Dict[str, Any]]:
    """Retorna todos os processos de fecho de um deal."""
    return closing_service.get_closings_for_deal(deal_id)


# ---------------------------------------------------------------------------
# P&L endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/pnl/{deal_id}/calculate",
    summary="Calcular P&L (auto-pull M3/M6)",
)
def calculate_pnl(
    deal_id: str,
    sale_price: float = Query(0, description="Preco de venda"),
    sale_commission: float = Query(0, description="Comissao de venda"),
    sale_costs: float = Query(0, description="Custos de venda"),
    holding_months: int = Query(0, description="Meses de holding"),
    holding_costs: float = Query(0, description="Custos de holding"),
) -> Dict[str, Any]:
    """Calcula P&L real, puxando dados de M3, M6 e closing automaticamente."""
    try:
        return pnl_service.calculate_pnl(
            deal_id=deal_id,
            sale_price=sale_price,
            sale_commission=sale_commission,
            sale_costs=sale_costs,
            holding_months=holding_months,
            holding_costs=holding_costs,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pnl/{deal_id}", summary="Obter P&L de um deal")
def get_pnl(deal_id: str) -> Dict[str, Any]:
    """Retorna P&L de um deal."""
    result = pnl_service.get_pnl(deal_id)
    if not result:
        raise HTTPException(status_code=404, detail="P&L nao encontrado")
    return result


@router.put("/pnl/{deal_id}", summary="Actualizar P&L manualmente")
def update_pnl(deal_id: str, body: DealPnLUpdate) -> Dict[str, Any]:
    """Actualiza P&L manualmente e recalcula metricas."""
    try:
        return pnl_service.update_pnl(
            deal_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/pnl/{deal_id}/finalize",
    summary="Marcar P&L como final",
)
def finalize_pnl(deal_id: str) -> Dict[str, Any]:
    """Marca P&L como final (imutavel)."""
    try:
        return pnl_service.finalize_pnl(deal_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
