"""Schemas Pydantic para o modulo M8 — CRM de Leads."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LeadStage(str, Enum):
    """Estagios do pipeline de leads."""

    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    VISITING = "visiting"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class LeadGrade(str, Enum):
    """Grades de qualificacao do lead (A = melhor)."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------


class LeadCreate(BaseModel):
    """Schema para criacao de lead."""

    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    budget_min: Optional[float] = Field(None, ge=0)
    budget_max: Optional[float] = Field(None, ge=0)
    preferred_typology: Optional[str] = None
    preferred_locations: List[str] = Field(default_factory=list)
    preferred_features: List[str] = Field(default_factory=list)
    timeline: Optional[str] = None
    financing: Optional[str] = None
    buyer_type: Optional[str] = None
    source: Optional[str] = None
    source_listing_id: Optional[str] = None
    source_campaign: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    habta_contact_id: Optional[str] = None
    deal_id: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class LeadUpdate(BaseModel):
    """Schema para actualizacao de lead."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    budget_min: Optional[float] = Field(None, ge=0)
    budget_max: Optional[float] = Field(None, ge=0)
    preferred_typology: Optional[str] = None
    preferred_locations: Optional[List[str]] = None
    preferred_features: Optional[List[str]] = None
    timeline: Optional[str] = None
    financing: Optional[str] = None
    buyer_type: Optional[str] = None
    source: Optional[str] = None
    source_listing_id: Optional[str] = None
    source_campaign: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    deal_id: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class LeadResponse(BaseModel):
    """Schema de resposta para lead."""

    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferred_typology: Optional[str] = None
    preferred_locations: List[str] = Field(default_factory=list)
    preferred_features: List[str] = Field(default_factory=list)
    timeline: Optional[str] = None
    financing: Optional[str] = None
    buyer_type: Optional[str] = None
    stage: str = "new"
    stage_changed_at: Optional[datetime] = None
    score: int = 0
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    grade: str = "D"
    source: Optional[str] = None
    source_listing_id: Optional[str] = None
    source_campaign: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    habta_contact_id: Optional[str] = None
    deal_id: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    interactions_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------


class InteractionCreate(BaseModel):
    """Schema para criacao de interaccao."""

    type: str = Field(..., min_length=1, max_length=50)
    channel: Optional[str] = None
    direction: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    listing_id: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")
    performed_by: Optional[str] = None

    model_config = {"populate_by_name": True}


class InteractionResponse(BaseModel):
    """Schema de resposta para interaccao."""

    id: str
    lead_id: str
    type: str
    channel: Optional[str] = None
    direction: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    listing_id: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")
    performed_by: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------


class LeadMatchResponse(BaseModel):
    """Schema de resposta para match lead-listing."""

    id: str
    lead_id: str
    listing_id: str
    match_score: float
    match_reasons: List[str] = Field(default_factory=list)
    status: str = "suggested"
    sent_at: Optional[datetime] = None
    response_at: Optional[datetime] = None
    listing_info: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------


class LeadScoreBreakdown(BaseModel):
    """Detalhe do calculo de score do lead."""

    demographic: int = 0
    behavioral: int = 0
    communication: int = 0
    urgency: int = 0
    total: int = 0
    grade: str = "D"


# ---------------------------------------------------------------------------
# Nurture
# ---------------------------------------------------------------------------


class NurtureStatus(BaseModel):
    """Estado actual da sequencia de nurturing."""

    id: str
    lead_id: str
    sequence_type: str = "standard"
    current_step: int = 0
    status: str = "active"
    next_action_at: Optional[datetime] = None
    steps_executed: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Pipeline / Stats
# ---------------------------------------------------------------------------


class PipelineSummary(BaseModel):
    """Resumo do pipeline de leads por estagio."""

    stage: str
    count: int
    total_budget: float = 0.0


class LeadStats(BaseModel):
    """Estatisticas globais de leads."""

    total_leads: int = 0
    by_stage: Dict[str, int] = Field(default_factory=dict)
    by_grade: Dict[str, int] = Field(default_factory=dict)
    by_source: Dict[str, int] = Field(default_factory=dict)
    avg_score: float = 0.0
    conversion_rate: float = 0.0
    leads_this_month: int = 0
    leads_last_month: int = 0
    growth_rate: float = 0.0
