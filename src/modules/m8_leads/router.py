"""Endpoints M8 — CRM de Leads.

Pipeline de compradores: CRUD, scoring, matching, nurturing, analytics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from src.modules.m8_leads.schemas import (
    InteractionCreate,
    LeadCreate,
    LeadUpdate,
)
from src.modules.m8_leads.service import LeadService

router = APIRouter()
service = LeadService()


# ---------------------------------------------------------------------------
# Non-parameterized routes FIRST (avoid FastAPI treating them as {lead_id})
# ---------------------------------------------------------------------------


@router.get("/stats", summary="Estatisticas globais de leads")
async def get_stats() -> Dict[str, Any]:
    """Retorna estatisticas globais de leads."""
    return service.get_stats()


@router.get("/pipeline-summary", summary="Resumo do pipeline")
async def get_pipeline_summary() -> List[Dict[str, Any]]:
    """Retorna contagens por estagio do pipeline."""
    return service.get_pipeline_summary()


@router.get("/conversion-funnel", summary="Funil de conversao")
async def get_conversion_funnel() -> List[Dict[str, Any]]:
    """Retorna funil de conversao com percentagens."""
    return service.get_conversion_funnel()


@router.get("/source-breakdown", summary="Distribuicao por fonte")
async def get_source_breakdown() -> List[Dict[str, Any]]:
    """Retorna distribuicao de leads por fonte de captacao."""
    return service.get_source_breakdown()


@router.get("/grades-summary", summary="Resumo por grade")
async def get_grades_summary() -> Dict[str, int]:
    """Retorna contagem de leads por grade (A/B/C/D)."""
    return service.get_grades_summary()


@router.post("/sync-habta", summary="Sincronizar contactos Habta")
async def sync_habta(contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Importa ou actualiza leads a partir de contactos Habta."""
    try:
        return service.sync_from_habta(contacts)
    except Exception as e:
        logger.error(f"Erro ao sincronizar Habta: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nurture/execute-pending", summary="Executar nurtures pendentes")
async def execute_pending_nurtures() -> Dict[str, Any]:
    """Executa todas as sequencias de nurturing com accao pendente."""
    return await service.execute_pending_nurtures()


@router.post("/rescore-batch", summary="Re-scoring em batch (admin)")
async def rescore_batch(
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """Re-score em batch. Body: {"lead_ids": [...], "with_ai": true}."""
    lead_ids = body.get("lead_ids", [])
    if not lead_ids or not isinstance(lead_ids, list):
        raise HTTPException(status_code=400, detail="lead_ids obrigatorio (lista)")
    with_ai = body.get("with_ai", True)
    return await service.rescore_batch(lead_ids, with_ai=with_ai)


# ---------------------------------------------------------------------------
# CRUD — Lead
# ---------------------------------------------------------------------------


@router.post("/", summary="Criar lead")
async def create_lead(data: LeadCreate) -> Dict[str, Any]:
    """Cria um novo lead no CRM."""
    try:
        return service.create_lead(data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", summary="Listar leads")
async def list_leads(
    stage: Optional[str] = Query(None, description="Filtrar por estagio"),
    grade: Optional[str] = Query(None, description="Filtrar por grade (A/B/C/D)"),
    source: Optional[str] = Query(None, description="Filtrar por fonte"),
    search: Optional[str] = Query(None, description="Pesquisa por nome/email/telefone"),
    sort_by: str = Query("created_at", description="Campo de ordenacao"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lista leads com filtros e paginacao."""
    return service.list_leads(
        stage=stage,
        grade=grade,
        source=source,
        search=search,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Parameterized routes — Lead by ID
# ---------------------------------------------------------------------------


@router.get("/{lead_id}", summary="Obter lead")
async def get_lead(lead_id: str) -> Dict[str, Any]:
    """Retorna detalhes de um lead incluindo contagem de interaccoes."""
    result = service.get_lead(lead_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")
    return result


@router.put("/{lead_id}", summary="Actualizar lead")
async def update_lead(lead_id: str, data: LeadUpdate) -> Dict[str, Any]:
    """Actualiza dados de um lead."""
    result = service.update_lead(lead_id, data.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")
    return result


@router.delete("/{lead_id}", summary="Remover lead")
async def delete_lead(lead_id: str) -> Dict[str, str]:
    """Remove um lead e todos os dados associados."""
    success = service.delete_lead(lead_id)
    if not success:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")
    return {"message": f"Lead {lead_id} removido com sucesso"}


# ---------------------------------------------------------------------------
# Stage Management
# ---------------------------------------------------------------------------


@router.patch("/{lead_id}/stage", summary="Avancar estagio")
async def advance_stage(lead_id: str, new_stage: str) -> Dict[str, Any]:
    """Avanca o estagio do lead no pipeline."""
    try:
        return service.advance_stage(lead_id, new_stage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------


@router.post("/{lead_id}/interactions", summary="Adicionar interaccao")
async def add_interaction(
    lead_id: str, data: InteractionCreate
) -> Dict[str, Any]:
    """Regista uma interaccao com o lead."""
    try:
        return service.add_interaction(lead_id, data.model_dump(by_alias=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{lead_id}/interactions", summary="Listar interaccoes")
async def list_interactions(
    lead_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lista interaccoes de um lead."""
    try:
        return service.list_interactions(lead_id, limit=limit, offset=offset)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{lead_id}/timeline", summary="Timeline do lead")
async def get_timeline(lead_id: str) -> List[Dict[str, Any]]:
    """Retorna timeline cronologica completa do lead."""
    try:
        return service.get_timeline(lead_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@router.post("/{lead_id}/recalculate-score", summary="Recalcular score")
async def recalculate_score(
    lead_id: str,
    with_ai: bool = Query(False, description="Enriquecer com AI scoring"),
    force_ai: bool = Query(False, description="Forcar re-analise AI (ignora cache)"),
) -> Dict[str, Any]:
    """Recalcula o score e grade do lead (opt-in AI enrichment)."""
    try:
        return service.recalculate_score(lead_id, with_ai=with_ai, force_ai=force_ai)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


@router.get("/{lead_id}/matches", summary="Encontrar matches")
async def find_matches(lead_id: str) -> List[Dict[str, Any]]:
    """Encontra listings compativeis com as preferencias do lead."""
    try:
        return service.find_matches(lead_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{lead_id}/matches/{listing_id}/send",
    summary="Enviar listing ao lead",
)
async def send_listing_to_lead(
    lead_id: str, listing_id: str
) -> Dict[str, Any]:
    """Envia uma listing ao lead e regista a interaccao."""
    try:
        return service.send_listing_to_lead(lead_id, listing_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Nurturing
# ---------------------------------------------------------------------------


@router.post("/{lead_id}/nurture/start", summary="Iniciar nurturing")
async def start_nurture(
    lead_id: str,
    sequence_type: str = Query("standard"),
    listing_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Inicia sequencia de nurturing automatico para o lead."""
    try:
        return service.start_nurture(lead_id, sequence_type, listing_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{lead_id}/nurture/status", summary="Estado do nurturing")
async def get_nurture_status(lead_id: str) -> Dict[str, Any]:
    """Retorna estado actual da sequencia de nurturing."""
    result = service.get_nurture_status(lead_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail="Nenhum nurture encontrado"
        )
    return result


@router.post("/{lead_id}/nurture/pause", summary="Pausar nurturing")
async def pause_nurture(lead_id: str) -> Dict[str, Any]:
    """Pausa a sequencia de nurturing activa."""
    try:
        return service.pause_nurture(lead_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{lead_id}/nurture/resume", summary="Retomar nurturing")
async def resume_nurture(lead_id: str) -> Dict[str, Any]:
    """Retoma a sequencia de nurturing pausada."""
    try:
        return service.resume_nurture(lead_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
