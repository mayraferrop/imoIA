"""Endpoints M4 — Deal Pipeline.

Gestao do ciclo de vida de negocios imobiliarios.
Suporta 10 estrategias (investimento + mediacao) com maquina de estados flexivel.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from src.modules.m4_deal_pipeline.schemas import (
    AdvanceDealSchema,
    CMAInputSchema,
    CommissionInvoiceSchema,
    DealCreateSchema,
    DealFromOpportunitySchema,
    DealUpdateSchema,
    MediationDealCreateSchema,
    ProposalCreateSchema,
    ProposalResponseSchema,
    RentalCreateSchema,
    RentalUpdateSchema,
    TaskCreateSchema,
    VisitCreateSchema,
    VisitUpdateSchema,
)
from src.modules.m4_deal_pipeline.service import DealPipelineService
from src.modules.m4_deal_pipeline.state_machine import (
    get_all_statuses,
    get_all_strategies,
)

router = APIRouter()
service = DealPipelineService()


# ---------------------------------------------------------------------------
# Estrategias e estados
# ---------------------------------------------------------------------------


@router.get("/strategies", summary="Listar estrategias de investimento")
def list_strategies() -> List[Dict[str, Any]]:
    """Retorna todas as estrategias suportadas com rotas."""
    return get_all_strategies()


@router.get("/statuses", summary="Listar estados do pipeline")
def list_statuses() -> List[Dict[str, Any]]:
    """Retorna todos os estados com labels e cores."""
    return get_all_statuses()


# ---------------------------------------------------------------------------
# Kanban / Stats
# ---------------------------------------------------------------------------


@router.get("/kanban", summary="Dados para vista kanban")
def get_kanban(
    strategy: Optional[str] = Query(None, description="Filtrar por estrategia"),
) -> Dict[str, Any]:
    """Retorna deals agrupados por estado para vista kanban."""
    return service.get_kanban_data(strategy)


@router.get("/stats", summary="Estatisticas do pipeline")
def get_stats(
    strategy: Optional[str] = Query(None, description="Filtrar por estrategia"),
) -> Dict[str, Any]:
    """Retorna metricas agregadas do pipeline."""
    return service.get_pipeline_stats(strategy)


# ---------------------------------------------------------------------------
# Tasks globais
# ---------------------------------------------------------------------------


@router.get("/tasks/upcoming", summary="Tarefas pendentes")
def get_upcoming_tasks(
    limit: int = Query(20, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Retorna tarefas pendentes ordenadas por data."""
    return service.get_upcoming_tasks(limit)


# ---------------------------------------------------------------------------
# CRUD Deals
# ---------------------------------------------------------------------------


@router.get("/", summary="Listar deals")
def list_deals(
    status: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lista deals com filtros opcionais."""
    return service.list_deals(status, strategy, limit, offset)


@router.post("/", summary="Criar deal")
def create_deal(data: DealCreateSchema) -> Dict[str, Any]:
    """Cria um novo deal."""
    try:
        return service.create_deal(data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/from-opportunity/{opportunity_id}",
    summary="Criar deal a partir de oportunidade M1",
)
def create_from_opportunity(
    opportunity_id: int, data: DealFromOpportunitySchema
) -> Dict[str, Any]:
    """Cria deal a partir de uma Opportunity legacy."""
    try:
        return service.create_deal_from_opportunity(
            opportunity_id, data.model_dump()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{deal_id}", summary="Detalhe de um deal")
def get_deal(deal_id: str) -> Dict[str, Any]:
    """Retorna detalhe completo de um deal."""
    result = service.get_deal(deal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Deal nao encontrado")
    return result


@router.patch("/{deal_id}", summary="Actualizar deal")
def update_deal(deal_id: str, data: DealUpdateSchema) -> Dict[str, Any]:
    """Actualiza campos de um deal."""
    try:
        result = service.update_deal(deal_id, data.model_dump(exclude_unset=True))
        if not result:
            raise HTTPException(status_code=404, detail="Deal nao encontrado")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


@router.get("/{deal_id}/next-actions", summary="Proximas accoes")
def get_next_actions(deal_id: str) -> Dict[str, Any]:
    """Retorna estados para os quais o deal pode avancar."""
    try:
        return service.get_next_actions(deal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{deal_id}/advance", summary="Avancar estado do deal")
def advance_deal(deal_id: str, data: AdvanceDealSchema) -> Dict[str, Any]:
    """Avanca o estado de um deal (com validacao de transicao)."""
    try:
        return service.advance_deal(
            deal_id, data.target_status, data.reason, data.changed_by
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{deal_id}/history", summary="Historico de estados")
def get_history(deal_id: str) -> List[Dict[str, Any]]:
    """Retorna historico de transicoes de estado."""
    return service.get_deal_history(deal_id)


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


@router.get("/{deal_id}/proposals", summary="Listar propostas")
def list_proposals(deal_id: str) -> List[Dict[str, Any]]:
    """Lista propostas de um deal."""
    return service.list_proposals(deal_id)


@router.post("/{deal_id}/proposals", summary="Criar proposta")
def create_proposal(
    deal_id: str, data: ProposalCreateSchema
) -> Dict[str, Any]:
    """Cria uma proposta para um deal."""
    try:
        return service.create_proposal(deal_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/proposals/{proposal_id}", summary="Responder a proposta")
def respond_to_proposal(
    proposal_id: str, data: ProposalResponseSchema
) -> Dict[str, Any]:
    """Responde a uma proposta (accepted/rejected/counter)."""
    try:
        return service.respond_to_proposal(
            proposal_id, data.status, data.response_notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@router.post("/{deal_id}/tasks", summary="Criar tarefa")
def create_task(deal_id: str, data: TaskCreateSchema) -> Dict[str, Any]:
    """Cria uma tarefa para um deal."""
    try:
        return service.create_task(deal_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/tasks/{task_id}/complete", summary="Completar tarefa")
def complete_task(task_id: str) -> Dict[str, Any]:
    """Marca uma tarefa como concluida."""
    try:
        return service.complete_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Rentals
# ---------------------------------------------------------------------------


@router.post("/{deal_id}/rental", summary="Adicionar arrendamento")
def add_rental(deal_id: str, data: RentalCreateSchema) -> Dict[str, Any]:
    """Adiciona dados de arrendamento a um deal."""
    try:
        return service.add_rental(deal_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/rentals/{rental_id}", summary="Actualizar arrendamento")
def update_rental(
    rental_id: str, data: RentalUpdateSchema
) -> Dict[str, Any]:
    """Actualiza dados de arrendamento."""
    try:
        return service.update_rental(
            rental_id, data.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Mediacao
# ---------------------------------------------------------------------------


@router.post("/mediation", summary="Criar deal de mediacao")
def create_mediation_deal(data: MediationDealCreateSchema) -> Dict[str, Any]:
    """Cria deal de mediacao (role=mediador)."""
    try:
        return service.create_mediation_deal(data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deal_id}/cma", summary="Gerar CMA")
def generate_cma(deal_id: str, data: CMAInputSchema) -> Dict[str, Any]:
    """Gera CMA (Comparative Market Analysis) a partir de comparaveis."""
    try:
        return service.generate_cma(
            deal_id, data.comparables, data.recommended_price
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{deal_id}/cma", summary="Obter CMA")
def get_cma(deal_id: str) -> Dict[str, Any]:
    """Retorna dados do CMA de um deal."""
    deal = service.get_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal nao encontrado")
    return {
        "deal_id": deal["id"],
        "estimated_value": deal.get("cma_estimated_value"),
        "min_value": deal.get("cma_min_value"),
        "max_value": deal.get("cma_max_value"),
        "recommended_price": deal.get("cma_recommended_price"),
    }


@router.get("/stats/mediation", summary="Estatisticas de mediacao")
def get_mediation_stats() -> Dict[str, Any]:
    """Retorna metricas especificas de mediacao."""
    return service.get_mediation_stats()


# ---------------------------------------------------------------------------
# Visitas
# ---------------------------------------------------------------------------


@router.get("/{deal_id}/visits", summary="Listar visitas")
def list_visits(deal_id: str) -> List[Dict[str, Any]]:
    """Lista visitas de um deal."""
    return service.list_visits(deal_id)


@router.post("/{deal_id}/visits", summary="Registar visita")
def register_visit(
    deal_id: str, data: VisitCreateSchema
) -> Dict[str, Any]:
    """Regista uma visita ao imovel."""
    try:
        return service.register_visit(deal_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/visits/{visit_id}", summary="Actualizar visita")
def update_visit(
    visit_id: str, data: VisitUpdateSchema
) -> Dict[str, Any]:
    """Actualiza feedback de uma visita."""
    try:
        return service.update_visit(visit_id, data.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Comissoes
# ---------------------------------------------------------------------------


@router.get("/{deal_id}/commission", summary="Calcular comissao")
def calculate_commission(
    deal_id: str,
    sale_price: Optional[float] = Query(None, description="Preco de venda (override)"),
) -> Dict[str, Any]:
    """Calcula comissao com breakdown (bruto, IVA, partilha)."""
    try:
        return service.calculate_commission(deal_id, sale_price)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deal_id}/commission", summary="Registar comissao")
def create_commission(
    deal_id: str,
    sale_price: float = Query(..., description="Preco de venda"),
) -> Dict[str, Any]:
    """Cria registo de comissao com calculo completo."""
    try:
        return service.create_commission_record(deal_id, sale_price)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/commissions/{commission_id}/invoice", summary="Registar factura")
def invoice_commission(
    commission_id: str, data: CommissionInvoiceSchema
) -> Dict[str, Any]:
    """Regista factura numa comissao."""
    try:
        return service.invoice_commission(
            commission_id, data.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
