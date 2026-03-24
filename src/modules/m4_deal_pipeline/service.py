"""Servico M4 — Deal Pipeline.

Logica de negocio para gestao de deals, propostas, tasks e arrendamentos.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.db import get_session
from src.database.models import Opportunity
from src.database.models_v2 import (
    Deal,
    DealApproval,
    DealCommission,
    DealRental,
    DealStateHistory,
    DealTask,
    DealVisit,
    Property,
    Proposal,
    Tenant,
)
from src.modules.m4_deal_pipeline.state_machine import (
    AUTO_TASKS,
    INVESTMENT_STRATEGIES,
    STATUS_CONFIG,
    STRATEGY_ROUTES,
    can_transition,
    get_all_strategies,
    get_all_statuses,
    get_next_statuses,
    get_progress_pct,
    is_mediation_strategy,
)

_DEFAULT_TENANT_SLUG = "default"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_default_tenant(session: Session) -> str:
    """Garante que o tenant default existe e retorna o id."""
    tenant = session.execute(
        select(Tenant).where(Tenant.slug == _DEFAULT_TENANT_SLUG)
    ).scalar_one_or_none()

    if tenant is None:
        tenant = Tenant(
            id=str(uuid4()),
            name="ImoIA",
            slug=_DEFAULT_TENANT_SLUG,
            country="PT",
        )
        session.add(tenant)
        session.flush()
        logger.info("Tenant default criado")

    return tenant.id


def _deal_to_dict(deal: Deal) -> Dict[str, Any]:
    """Serializa Deal para dict."""
    cfg = STATUS_CONFIG.get(deal.status, {})
    route = STRATEGY_ROUTES.get(deal.investment_strategy, [])
    strategy_info = INVESTMENT_STRATEGIES.get(deal.investment_strategy, {})

    # Calcular dias no estado actual
    days_in_status = 0
    if deal.status_changed_at:
        delta = datetime.now(timezone.utc) - deal.status_changed_at.replace(
            tzinfo=timezone.utc
        )
        days_in_status = delta.days

    return {
        "id": deal.id,
        "tenant_id": deal.tenant_id,
        "property_id": deal.property_id,
        "investment_strategy": deal.investment_strategy,
        "strategy_label": strategy_info.get("label", deal.investment_strategy),
        "strategy_icon": strategy_info.get("icon", ""),
        "status": deal.status,
        "status_label": cfg.get("label", deal.status),
        "status_color": cfg.get("color", "#666"),
        "status_icon": cfg.get("icon", ""),
        "title": deal.title,
        "purchase_price": deal.purchase_price,
        "target_sale_price": deal.target_sale_price,
        "actual_sale_price": deal.actual_sale_price,
        "monthly_rent": deal.monthly_rent,
        "renovation_budget": deal.renovation_budget,
        "actual_renovation_cost": deal.actual_renovation_cost,
        "contact_name": deal.contact_name,
        "contact_phone": deal.contact_phone,
        "contact_email": deal.contact_email,
        "contact_role": deal.contact_role,
        "status_changed_at": (
            deal.status_changed_at.isoformat() if deal.status_changed_at else None
        ),
        "days_in_status": days_in_status,
        "cpcv_date": deal.cpcv_date.isoformat() if deal.cpcv_date else None,
        "escritura_date": (
            deal.escritura_date.isoformat() if deal.escritura_date else None
        ),
        "obra_start_date": (
            deal.obra_start_date.isoformat() if deal.obra_start_date else None
        ),
        "obra_end_date": (
            deal.obra_end_date.isoformat() if deal.obra_end_date else None
        ),
        "sale_date": deal.sale_date.isoformat() if deal.sale_date else None,
        "closed_at": deal.closed_at.isoformat() if deal.closed_at else None,
        "is_financed": deal.is_financed,
        "is_off_market": deal.is_off_market,
        "discard_reason": deal.discard_reason,
        "pause_reason": deal.pause_reason,
        "source_opportunity_id": deal.source_opportunity_id,
        "notes": deal.notes,
        "tags": deal.tags or [],
        "assigned_to": deal.assigned_to,
        "progress_pct": get_progress_pct(deal.status, deal.investment_strategy),
        "role": deal.role,
        "owner_name": deal.owner_name,
        "owner_phone": deal.owner_phone,
        "owner_email": deal.owner_email,
        "mediation_contract_type": deal.mediation_contract_type,
        "commission_pct": deal.commission_pct,
        "commission_amount": deal.commission_amount,
        "commission_split_pct": deal.commission_split_pct,
        "commission_split_agent": deal.commission_split_agent,
        "cma_estimated_value": deal.cma_estimated_value,
        "cma_min_value": deal.cma_min_value,
        "cma_max_value": deal.cma_max_value,
        "cma_recommended_price": deal.cma_recommended_price,
        "created_at": deal.created_at.isoformat() if deal.created_at else None,
        "updated_at": deal.updated_at.isoformat() if deal.updated_at else None,
    }


def _proposal_to_dict(p: Proposal) -> Dict[str, Any]:
    """Serializa Proposal para dict."""
    return {
        "id": p.id,
        "deal_id": p.deal_id,
        "proposal_type": p.proposal_type,
        "amount": p.amount,
        "deposit_pct": p.deposit_pct,
        "conditions": p.conditions,
        "validity_days": p.validity_days,
        "status": p.status,
        "sent_at": p.sent_at.isoformat() if p.sent_at else None,
        "response_at": p.response_at.isoformat() if p.response_at else None,
        "response_notes": p.response_notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _task_to_dict(t: DealTask) -> Dict[str, Any]:
    """Serializa DealTask para dict."""
    return {
        "id": t.id,
        "deal_id": t.deal_id,
        "title": t.title,
        "description": t.description,
        "task_type": t.task_type,
        "priority": t.priority,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "is_completed": t.is_completed,
        "assigned_to": t.assigned_to,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _rental_to_dict(r: DealRental) -> Dict[str, Any]:
    """Serializa DealRental para dict."""
    return {
        "id": r.id,
        "deal_id": r.deal_id,
        "rental_type": r.rental_type,
        "monthly_rent": r.monthly_rent,
        "deposit_months": r.deposit_months,
        "tenant_name": r.tenant_name,
        "tenant_phone": r.tenant_phone,
        "tenant_email": r.tenant_email,
        "lease_start": r.lease_start.isoformat() if r.lease_start else None,
        "lease_end": r.lease_end.isoformat() if r.lease_end else None,
        "lease_duration_months": r.lease_duration_months,
        "al_license_number": r.al_license_number,
        "platform": r.platform,
        "average_daily_rate": r.average_daily_rate,
        "occupancy_rate_pct": r.occupancy_rate_pct,
        "condominio_monthly": r.condominio_monthly,
        "imi_annual": r.imi_annual,
        "insurance_annual": r.insurance_annual,
        "management_fee_pct": r.management_fee_pct,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _history_to_dict(h: DealStateHistory) -> Dict[str, Any]:
    """Serializa DealStateHistory para dict."""
    return {
        "id": h.id,
        "deal_id": h.deal_id,
        "from_status": h.from_status,
        "to_status": h.to_status,
        "changed_by": h.changed_by,
        "reason": h.reason,
        "metadata_json": h.metadata_json,
        "created_at": h.created_at.isoformat() if h.created_at else None,
    }


def _visit_to_dict(v: DealVisit) -> Dict[str, Any]:
    """Serializa DealVisit para dict."""
    return {
        "id": v.id, "deal_id": v.deal_id,
        "visitor_name": v.visitor_name, "visitor_phone": v.visitor_phone,
        "visitor_email": v.visitor_email,
        "visit_date": v.visit_date.isoformat() if v.visit_date else None,
        "visit_type": v.visit_type, "duration_minutes": v.duration_minutes,
        "interest_level": v.interest_level, "feedback": v.feedback,
        "objections": v.objections, "wants_second_visit": v.wants_second_visit,
        "made_proposal": v.made_proposal, "proposal_amount": v.proposal_amount,
        "accompanied_by": v.accompanied_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _commission_to_dict(c: DealCommission) -> Dict[str, Any]:
    """Serializa DealCommission para dict."""
    return {
        "id": c.id, "deal_id": c.deal_id,
        "sale_price": c.sale_price, "commission_pct": c.commission_pct,
        "commission_gross": c.commission_gross, "vat_pct": c.vat_pct,
        "commission_with_vat": c.commission_with_vat,
        "is_shared": c.is_shared, "share_pct": c.share_pct,
        "my_commission": c.my_commission,
        "other_agent_name": c.other_agent_name,
        "other_agent_agency": c.other_agent_agency,
        "other_agent_commission": c.other_agent_commission,
        "payment_status": c.payment_status,
        "invoice_number": c.invoice_number,
        "paid_amount": c.paid_amount,
        "paid_date": c.paid_date.isoformat() if c.paid_date else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DealPipelineService:
    """Logica de negocio do M4 — Deal Pipeline."""

    # --- CRUD Deals ---

    def create_deal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo deal."""
        strategy = data.get("investment_strategy", "")
        if strategy not in INVESTMENT_STRATEGIES:
            raise ValueError(f"Estrategia invalida: {strategy}")

        with get_session() as session:
            tenant_id = _ensure_default_tenant(session)

            prop = session.get(Property, data["property_id"])
            if not prop:
                raise ValueError(f"Property nao encontrada: {data['property_id']}")

            now = datetime.now(timezone.utc)
            deal = Deal(
                id=str(uuid4()),
                tenant_id=tenant_id,
                property_id=data["property_id"],
                investment_strategy=strategy,
                status="lead",
                title=data.get("title", ""),
                purchase_price=data.get("purchase_price"),
                target_sale_price=data.get("target_sale_price"),
                monthly_rent=data.get("monthly_rent"),
                renovation_budget=data.get("renovation_budget"),
                contact_name=data.get("contact_name"),
                contact_phone=data.get("contact_phone"),
                contact_email=data.get("contact_email"),
                contact_role=data.get("contact_role"),
                is_financed=data.get("is_financed", False),
                is_off_market=data.get("is_off_market", False),
                notes=data.get("notes"),
                tags=data.get("tags", []),
                status_changed_at=now,
            )
            session.add(deal)

            # Registar estado inicial no historico
            history = DealStateHistory(
                id=str(uuid4()),
                tenant_id=tenant_id,
                deal_id=deal.id,
                from_status="",
                to_status="lead",
                changed_by=data.get("changed_by", "system"),
                reason="Deal criado",
            )
            session.add(history)

            session.flush()
            logger.info(
                f"Deal criado: {deal.id} ({deal.title}, {strategy})"
            )
            return _deal_to_dict(deal)

    def create_deal_from_opportunity(
        self, opportunity_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria deal a partir de uma Opportunity do M1."""
        strategy = data.get("investment_strategy", "")
        if strategy not in INVESTMENT_STRATEGIES:
            raise ValueError(f"Estrategia invalida: {strategy}")

        with get_session() as session:
            tenant_id = _ensure_default_tenant(session)

            opp = session.get(Opportunity, opportunity_id)
            if not opp or not opp.is_opportunity:
                raise ValueError("Oportunidade nao encontrada ou invalida")

            # Procurar ou criar Property para esta oportunidade
            prop = session.execute(
                select(Property).where(
                    Property.source_opportunity_id == opportunity_id
                )
            ).scalar_one_or_none()

            if not prop:
                prop = Property(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    source="whatsapp",
                    source_opportunity_id=opp.id,
                    country="PT",
                    district=opp.district,
                    municipality=opp.municipality,
                    parish=opp.parish,
                    property_type=opp.property_type,
                    asking_price=opp.price_mentioned,
                    gross_area_m2=opp.area_m2,
                    bedrooms=opp.bedrooms,
                    is_off_market="off_market"
                    in (opp.opportunity_type or "").lower(),
                    status="oportunidade",
                    notes=opp.ai_reasoning,
                )
                session.add(prop)
                session.flush()

            location = " ".join(
                filter(None, [opp.parish, opp.municipality, opp.district])
            )
            title = data.get("title") or f"{opp.property_type or 'Imovel'} {location}".strip()

            now = datetime.now(timezone.utc)
            deal = Deal(
                id=str(uuid4()),
                tenant_id=tenant_id,
                property_id=prop.id,
                investment_strategy=strategy,
                status="lead",
                title=title,
                purchase_price=data.get("purchase_price") or opp.price_mentioned,
                target_sale_price=data.get("target_sale_price"),
                monthly_rent=data.get("monthly_rent"),
                renovation_budget=data.get("renovation_budget"),
                is_off_market="off_market"
                in (opp.opportunity_type or "").lower(),
                source_opportunity_id=opp.id,
                notes=data.get("notes") or opp.ai_reasoning,
                status_changed_at=now,
            )
            session.add(deal)

            history = DealStateHistory(
                id=str(uuid4()),
                tenant_id=tenant_id,
                deal_id=deal.id,
                from_status="",
                to_status="lead",
                changed_by="system",
                reason=f"Criado a partir de Opportunity #{opp.id}",
            )
            session.add(history)

            session.flush()
            logger.info(
                f"Deal {deal.id} criado a partir de Opportunity {opp.id}"
            )
            return _deal_to_dict(deal)

    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Retorna um deal por ID."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                return None
            return _deal_to_dict(deal)

    def list_deals(
        self,
        status: Optional[str] = None,
        strategy: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Lista deals com filtros."""
        with get_session() as session:
            stmt = select(Deal)

            if status:
                stmt = stmt.where(Deal.status == status)
            if strategy:
                stmt = stmt.where(Deal.investment_strategy == strategy)

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = session.execute(count_stmt).scalar() or 0

            stmt = stmt.order_by(Deal.updated_at.desc())
            stmt = stmt.offset(offset).limit(limit)

            deals = session.execute(stmt).scalars().all()
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": [_deal_to_dict(d) for d in deals],
            }

    def update_deal(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Actualiza campos de um deal."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                return None

            # Validar estrategia se estiver a ser alterada
            new_strategy = data.get("investment_strategy")
            if new_strategy and new_strategy not in INVESTMENT_STRATEGIES:
                raise ValueError(f"Estrategia invalida: {new_strategy}")

            for field_name, value in data.items():
                if hasattr(deal, field_name):
                    setattr(deal, field_name, value)

            session.flush()
            logger.info(f"Deal {deal_id} actualizado: {list(data.keys())}")
            return _deal_to_dict(deal)

    # --- State machine ---

    def advance_deal(
        self,
        deal_id: str,
        target_status: str,
        reason: Optional[str] = None,
        changed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Avanca o estado de um deal com validacao."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            if not can_transition(deal.status, target_status):
                raise ValueError(
                    f"Transicao invalida: {deal.status} -> {target_status}"
                )

            old_status = deal.status
            now = datetime.now(timezone.utc)

            deal.status = target_status
            deal.status_changed_at = now

            # Flags especiais
            if target_status == "descartado":
                deal.discard_reason = reason
            elif target_status == "em_pausa":
                deal.pause_reason = reason
            elif target_status == "concluido":
                deal.closed_at = now

            # Registar historico
            history = DealStateHistory(
                id=str(uuid4()),
                tenant_id=deal.tenant_id,
                deal_id=deal.id,
                from_status=old_status,
                to_status=target_status,
                changed_by=changed_by or "user",
                reason=reason,
            )
            session.add(history)

            # Criar tasks automaticas
            self._create_auto_tasks(session, deal, target_status)

            # M5: gerar checklist de due diligence automaticamente
            if target_status == "due_diligence":
                try:
                    from src.modules.m5_due_diligence.service import DueDiligenceService
                    dd_service = DueDiligenceService()
                    dd_result = dd_service.generate_checklist_in_session(
                        session, deal
                    )
                    logger.info(
                        f"Checklist DD gerado: {dd_result.get('total_items', 0)} itens"
                    )
                except Exception as e:
                    logger.warning(f"Erro ao gerar checklist DD: {e}")

            # M6: criar obra automaticamente
            if target_status == "obra":
                try:
                    from src.modules.m6_renovation.service import RenovationService
                    reno_service = RenovationService()
                    reno_result = reno_service.create_renovation_in_session(
                        session, deal
                    )
                    logger.info(
                        f"Obra criada: {reno_result.get('milestone_count', 0)} milestones"
                    )
                except Exception as e:
                    logger.warning(f"Erro ao criar obra: {e}")

            # M7: marketing hooks
            marketing_hooks = {
                "em_venda", "arrendamento", "marketing_activo",
                "cpcv_venda", "escritura_venda",
            }
            if target_status in marketing_hooks:
                try:
                    from src.modules.m7_marketing.service import MarketingService
                    mkt_service = MarketingService()
                    mkt_service.handle_deal_advance(session, deal, target_status)
                    logger.info(f"M7 hook: {target_status}")
                except Exception as e:
                    logger.warning(f"M7 hook falhou: {e}")

            session.flush()
            logger.info(
                f"Deal {deal_id}: {old_status} -> {target_status}"
            )
            return _deal_to_dict(deal)

    def get_next_actions(
        self, deal_id: str
    ) -> Dict[str, Any]:
        """Retorna proximas accoes possiveis para um deal."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            next_statuses = get_next_statuses(
                deal.status, deal.investment_strategy
            )
            return {
                "deal_id": deal.id,
                "current_status": deal.status,
                "investment_strategy": deal.investment_strategy,
                "next_statuses": [
                    {
                        "status": s,
                        **STATUS_CONFIG.get(s, {"label": s, "color": "#666", "icon": ""}),
                    }
                    for s in next_statuses
                ],
                "progress_pct": get_progress_pct(
                    deal.status, deal.investment_strategy
                ),
            }

    def get_deal_history(self, deal_id: str) -> List[Dict[str, Any]]:
        """Retorna historico de estados de um deal."""
        with get_session() as session:
            stmt = (
                select(DealStateHistory)
                .where(DealStateHistory.deal_id == deal_id)
                .order_by(DealStateHistory.created_at.desc())
            )
            items = session.execute(stmt).scalars().all()
            return [_history_to_dict(h) for h in items]

    # --- Proposals ---

    def create_proposal(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria uma proposta para um deal."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            now = datetime.now(timezone.utc)
            proposal = Proposal(
                id=str(uuid4()),
                tenant_id=deal.tenant_id,
                deal_id=deal.id,
                proposal_type=data.get("proposal_type", "offer"),
                amount=data["amount"],
                deposit_pct=data.get("deposit_pct", 10.0),
                conditions=data.get("conditions"),
                validity_days=data.get("validity_days", 5),
                status="sent",
                sent_at=now,
            )
            session.add(proposal)
            session.flush()
            logger.info(
                f"Proposta {proposal.id} criada para deal {deal_id}: "
                f"{proposal.amount}EUR"
            )
            return _proposal_to_dict(proposal)

    def respond_to_proposal(
        self, proposal_id: str, status: str, response_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Responde a uma proposta (accepted/rejected/counter)."""
        with get_session() as session:
            proposal = session.get(Proposal, proposal_id)
            if not proposal:
                raise ValueError(f"Proposta nao encontrada: {proposal_id}")

            proposal.status = status
            proposal.response_at = datetime.now(timezone.utc)
            proposal.response_notes = response_notes

            session.flush()
            logger.info(f"Proposta {proposal_id}: {status}")
            return _proposal_to_dict(proposal)

    def list_proposals(self, deal_id: str) -> List[Dict[str, Any]]:
        """Lista propostas de um deal."""
        with get_session() as session:
            stmt = (
                select(Proposal)
                .where(Proposal.deal_id == deal_id)
                .order_by(Proposal.created_at.desc())
            )
            items = session.execute(stmt).scalars().all()
            return [_proposal_to_dict(p) for p in items]

    # --- Tasks ---

    def create_task(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria uma tarefa manual para um deal."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            task = DealTask(
                id=str(uuid4()),
                tenant_id=deal.tenant_id,
                deal_id=deal.id,
                title=data["title"],
                description=data.get("description"),
                task_type=data.get("task_type", "manual"),
                priority=data.get("priority", "medium"),
                due_date=data.get("due_date"),
                assigned_to=data.get("assigned_to"),
            )
            session.add(task)
            session.flush()
            logger.info(f"Task criada: {task.title} (deal {deal_id})")
            return _task_to_dict(task)

    def complete_task(self, task_id: str) -> Dict[str, Any]:
        """Marca uma tarefa como concluida."""
        with get_session() as session:
            task = session.get(DealTask, task_id)
            if not task:
                raise ValueError(f"Task nao encontrada: {task_id}")

            task.is_completed = True
            task.completed_at = datetime.now(timezone.utc)

            session.flush()
            logger.info(f"Task concluida: {task.title}")
            return _task_to_dict(task)

    def get_upcoming_tasks(
        self, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retorna tarefas pendentes ordenadas por due_date."""
        with get_session() as session:
            stmt = (
                select(DealTask)
                .where(DealTask.is_completed == False)  # noqa: E712
                .order_by(
                    DealTask.due_date.asc().nullslast(),
                    DealTask.priority.desc(),
                )
                .limit(limit)
            )
            items = session.execute(stmt).scalars().all()
            return [_task_to_dict(t) for t in items]

    def _create_auto_tasks(
        self, session: Session, deal: Deal, new_status: str
    ) -> None:
        """Cria tasks automaticas com base no novo estado."""
        templates = AUTO_TASKS.get(new_status, [])
        for tmpl in templates:
            task = DealTask(
                id=str(uuid4()),
                tenant_id=deal.tenant_id,
                deal_id=deal.id,
                title=tmpl["title"],
                task_type="auto",
                priority=tmpl.get("priority", "medium"),
            )
            session.add(task)

    # --- Rentals ---

    def add_rental(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adiciona dados de arrendamento a um deal."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            rental = DealRental(
                id=str(uuid4()),
                tenant_id=deal.tenant_id,
                deal_id=deal.id,
                rental_type=data.get("rental_type", "longa_duracao"),
                monthly_rent=data["monthly_rent"],
                deposit_months=data.get("deposit_months", 2),
                tenant_name=data.get("tenant_name"),
                tenant_phone=data.get("tenant_phone"),
                tenant_email=data.get("tenant_email"),
                lease_start=data.get("lease_start"),
                lease_end=data.get("lease_end"),
                lease_duration_months=data.get("lease_duration_months"),
                al_license_number=data.get("al_license_number"),
                platform=data.get("platform"),
                average_daily_rate=data.get("average_daily_rate"),
                occupancy_rate_pct=data.get("occupancy_rate_pct"),
                condominio_monthly=data.get("condominio_monthly", 0),
                imi_annual=data.get("imi_annual", 0),
                insurance_annual=data.get("insurance_annual", 0),
                management_fee_pct=data.get("management_fee_pct", 0),
            )
            session.add(rental)

            # Actualizar renda mensal no deal
            deal.monthly_rent = data["monthly_rent"]

            session.flush()
            logger.info(
                f"Rental adicionado ao deal {deal_id}: {rental.monthly_rent}EUR/mes"
            )
            return _rental_to_dict(rental)

    def update_rental(
        self, rental_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualiza dados de arrendamento."""
        with get_session() as session:
            rental = session.get(DealRental, rental_id)
            if not rental:
                raise ValueError(f"Rental nao encontrado: {rental_id}")

            for field_name, value in data.items():
                if hasattr(rental, field_name):
                    setattr(rental, field_name, value)

            # Actualizar renda mensal no deal se alterada
            if "monthly_rent" in data:
                deal = session.get(Deal, rental.deal_id)
                if deal:
                    deal.monthly_rent = data["monthly_rent"]

            session.flush()
            return _rental_to_dict(rental)

    # --- Kanban / Stats ---

    def get_kanban_data(
        self, strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retorna dados para vista kanban, agrupados por estado."""
        with get_session() as session:
            stmt = select(Deal).where(
                Deal.status.notin_(["concluido", "descartado"])
            )
            if strategy:
                stmt = stmt.where(Deal.investment_strategy == strategy)

            deals = session.execute(stmt).scalars().all()

            columns: Dict[str, List[Dict[str, Any]]] = {}
            for deal in deals:
                status = deal.status
                if status not in columns:
                    columns[status] = []
                columns[status].append(_deal_to_dict(deal))

            # Ordenar colunas pela rota da estrategia (se especificada)
            if strategy and strategy in STRATEGY_ROUTES:
                route = STRATEGY_ROUTES[strategy]
                ordered = {}
                for s in route:
                    if s in columns:
                        ordered[s] = columns[s]
                # Adicionar estados nao na rota
                for s, deals_list in columns.items():
                    if s not in ordered:
                        ordered[s] = deals_list
                columns = ordered

            return {
                "strategy": strategy,
                "columns": columns,
                "status_config": STATUS_CONFIG,
            }

    def get_pipeline_stats(
        self, strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retorna estatisticas do pipeline."""
        with get_session() as session:
            stmt = select(Deal)
            if strategy:
                stmt = stmt.where(Deal.investment_strategy == strategy)

            deals = session.execute(stmt).scalars().all()

            active = [
                d for d in deals if d.status not in ("concluido", "descartado")
            ]
            completed = [d for d in deals if d.status == "concluido"]
            discarded = [d for d in deals if d.status == "descartado"]

            total_invested = sum(d.purchase_price or 0 for d in active)
            total_monthly_rent = sum(
                d.monthly_rent or 0
                for d in active
                if d.status == "arrendamento"
            )
            avg_roi = 0.0
            if completed:
                prices = [
                    (d.actual_sale_price or 0) - (d.purchase_price or 0)
                    for d in completed
                    if d.purchase_price
                ]
                investments = [d.purchase_price for d in completed if d.purchase_price]
                if investments:
                    total_profit = sum(prices)
                    total_inv = sum(investments)
                    avg_roi = (total_profit / total_inv * 100) if total_inv else 0

            # Distribuicao por estrategia
            by_strategy: Dict[str, int] = {}
            for d in deals:
                by_strategy[d.investment_strategy] = (
                    by_strategy.get(d.investment_strategy, 0) + 1
                )

            # Valor por estado
            by_status: Dict[str, Dict[str, Any]] = {}
            for d in active:
                if d.status not in by_status:
                    by_status[d.status] = {"count": 0, "value": 0}
                by_status[d.status]["count"] += 1
                by_status[d.status]["value"] += d.purchase_price or 0

            return {
                "total_deals": len(deals),
                "active_deals": len(active),
                "completed_deals": len(completed),
                "discarded_deals": len(discarded),
                "total_invested": total_invested,
                "total_monthly_rent": total_monthly_rent,
                "avg_roi_pct": round(avg_roi, 2),
                "by_strategy": by_strategy,
                "by_status": by_status,
            }

    # --- Mediation ---

    def create_mediation_deal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria deal de mediacao. Requer role='mediador'."""
        strategy = data.get("investment_strategy", "")
        if strategy not in INVESTMENT_STRATEGIES:
            raise ValueError(f"Estrategia invalida: {strategy}")
        if not is_mediation_strategy(strategy):
            raise ValueError(f"Estrategia {strategy} nao e de mediacao")

        with get_session() as session:
            tenant_id = _ensure_default_tenant(session)
            prop = session.get(Property, data["property_id"])
            if not prop:
                raise ValueError(f"Property nao encontrada: {data['property_id']}")

            now = datetime.now(timezone.utc)
            deal = Deal(
                id=str(uuid4()),
                tenant_id=tenant_id,
                property_id=data["property_id"],
                investment_strategy=strategy,
                status="lead",
                title=data.get("title", ""),
                role="mediador",
                # Owner
                owner_name=data.get("owner_name"),
                owner_phone=data.get("owner_phone"),
                owner_email=data.get("owner_email"),
                # Commission
                commission_pct=data.get("commission_pct"),
                commission_vat_included=data.get("commission_vat_included", False),
                commission_split_pct=data.get("commission_split_pct"),
                commission_split_agent=data.get("commission_split_agent"),
                commission_split_agency=data.get("commission_split_agency"),
                # Contract
                mediation_contract_type=data.get("mediation_contract_type"),
                # Prices
                purchase_price=data.get("purchase_price"),
                target_sale_price=data.get("target_sale_price"),
                monthly_rent=data.get("monthly_rent"),
                contact_name=data.get("contact_name"),
                contact_phone=data.get("contact_phone"),
                notes=data.get("notes"),
                tags=data.get("tags", []),
                status_changed_at=now,
                is_off_market=data.get("is_off_market", False),
            )
            session.add(deal)
            history = DealStateHistory(
                id=str(uuid4()), tenant_id=tenant_id, deal_id=deal.id,
                from_status="", to_status="lead",
                changed_by="system", reason="Deal mediacao criado",
            )
            session.add(history)
            session.flush()
            logger.info(f"Deal mediacao criado: {deal.id} ({strategy})")
            return _deal_to_dict(deal)

    def generate_cma(self, deal_id: str, comparables: List[Dict], recommended_price: Optional[float] = None) -> Dict[str, Any]:
        """Gera CMA simplificado a partir de comparaveis manuais."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            if not comparables:
                raise ValueError("Pelo menos 1 comparavel necessario")

            prices_m2 = []
            for c in comparables:
                if c.get("area_m2") and c["area_m2"] > 0:
                    prices_m2.append(c["price"] / c["area_m2"])

            prices = sorted([c["price"] for c in comparables])
            min_val = prices[0]
            max_val = prices[-1]
            median_val = prices[len(prices) // 2]

            now = datetime.now(timezone.utc)
            deal.cma_min_value = min_val
            deal.cma_max_value = max_val
            deal.cma_estimated_value = median_val
            deal.cma_recommended_price = recommended_price or median_val
            deal.cma_date = now

            session.flush()
            logger.info(f"CMA gerado para deal {deal_id}: {min_val}-{max_val}, mediana {median_val}")
            return {
                "deal_id": deal.id,
                "min_value": min_val,
                "max_value": max_val,
                "estimated_value": median_val,
                "recommended_price": deal.cma_recommended_price,
                "comparables_count": len(comparables),
                "price_per_m2": round(sum(prices_m2) / len(prices_m2), 2) if prices_m2 else None,
                "cma_date": now.isoformat(),
            }

    def register_visit(self, deal_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Regista uma visita ao imovel."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            visit = DealVisit(
                id=str(uuid4()),
                tenant_id=deal.tenant_id,
                deal_id=deal.id,
                visitor_name=data["visitor_name"],
                visitor_phone=data.get("visitor_phone"),
                visitor_email=data.get("visitor_email"),
                visit_date=data["visit_date"],
                visit_type=data.get("visit_type", "presencial"),
                duration_minutes=data.get("duration_minutes"),
                accompanied_by=data.get("accompanied_by"),
            )
            session.add(visit)
            session.flush()
            logger.info(f"Visita registada: {visit.visitor_name} ao deal {deal_id}")
            return _visit_to_dict(visit)

    def update_visit(self, visit_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza feedback de uma visita."""
        with get_session() as session:
            visit = session.get(DealVisit, visit_id)
            if not visit:
                raise ValueError(f"Visita nao encontrada: {visit_id}")
            for field_name, value in data.items():
                if hasattr(visit, field_name):
                    setattr(visit, field_name, value)
            session.flush()
            return _visit_to_dict(visit)

    def list_visits(self, deal_id: str) -> List[Dict[str, Any]]:
        """Lista visitas de um deal."""
        with get_session() as session:
            stmt = (
                select(DealVisit)
                .where(DealVisit.deal_id == deal_id)
                .order_by(DealVisit.visit_date.desc())
            )
            items = session.execute(stmt).scalars().all()
            return [_visit_to_dict(v) for v in items]

    def calculate_commission(self, deal_id: str, sale_price: Optional[float] = None) -> Dict[str, Any]:
        """Calcula comissao baseada no preco e condicoes do deal."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            price = sale_price or deal.actual_sale_price or deal.target_sale_price or deal.purchase_price or 0
            pct = deal.commission_pct or 5.0
            gross = price * pct / 100
            vat_pct = 23.0
            if deal.commission_vat_included:
                commission_with_vat = gross
                commission_net = gross / (1 + vat_pct / 100)
            else:
                commission_net = gross
                commission_with_vat = gross * (1 + vat_pct / 100)

            is_shared = bool(deal.commission_split_pct and deal.commission_split_pct < 100)
            share_pct = deal.commission_split_pct or 100.0
            my_commission = commission_with_vat * share_pct / 100
            other_commission = commission_with_vat - my_commission if is_shared else 0

            return {
                "deal_id": deal.id,
                "sale_price": price,
                "commission_pct": pct,
                "commission_gross": round(gross, 2),
                "vat_pct": vat_pct,
                "commission_with_vat": round(commission_with_vat, 2),
                "commission_net": round(commission_net, 2),
                "is_shared": is_shared,
                "share_pct": share_pct,
                "my_commission": round(my_commission, 2),
                "other_agent_name": deal.commission_split_agent,
                "other_agent_commission": round(other_commission, 2),
            }

    def create_commission_record(self, deal_id: str, sale_price: float) -> Dict[str, Any]:
        """Cria registo de comissao com calculo completo."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            pct = deal.commission_pct or 5.0
            gross = sale_price * pct / 100
            vat_pct = 23.0
            with_vat = gross * (1 + vat_pct / 100) if not deal.commission_vat_included else gross

            is_shared = bool(deal.commission_split_pct and deal.commission_split_pct < 100)
            share_pct = deal.commission_split_pct or 100.0
            my_part = with_vat * share_pct / 100
            other_part = with_vat - my_part if is_shared else 0

            commission = DealCommission(
                id=str(uuid4()),
                tenant_id=deal.tenant_id,
                deal_id=deal.id,
                sale_price=sale_price,
                commission_pct=pct,
                commission_gross=round(gross, 2),
                vat_pct=vat_pct,
                commission_with_vat=round(with_vat, 2),
                is_shared=is_shared,
                share_pct=share_pct,
                my_commission=round(my_part, 2),
                other_agent_name=deal.commission_split_agent,
                other_agent_agency=deal.commission_split_agency,
                other_agent_commission=round(other_part, 2),
            )
            session.add(commission)
            deal.commission_amount = round(my_part, 2)
            session.flush()
            return _commission_to_dict(commission)

    def invoice_commission(self, commission_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Regista factura numa comissao."""
        with get_session() as session:
            commission = session.get(DealCommission, commission_id)
            if not commission:
                raise ValueError(f"Comissao nao encontrada: {commission_id}")
            commission.invoice_number = data.get("invoice_number")
            commission.invoice_url = data.get("invoice_url")
            if data.get("paid_amount"):
                commission.paid_amount = data["paid_amount"]
            if data.get("paid_date"):
                commission.paid_date = data["paid_date"]
            commission.payment_status = "facturado"
            if commission.paid_amount and commission.paid_amount >= (commission.my_commission or 0):
                commission.payment_status = "pago"
            session.flush()
            return _commission_to_dict(commission)

    def get_mediation_stats(self) -> Dict[str, Any]:
        """Stats especificas de mediacao."""
        with get_session() as session:
            stmt = select(Deal).where(Deal.role == "mediador")
            deals = session.execute(stmt).scalars().all()

            active = [d for d in deals if d.status not in ("concluido", "descartado")]
            completed = [d for d in deals if d.status == "concluido"]

            total_portfolio = sum(
                d.target_sale_price or d.purchase_price or 0 for d in active
            )
            potential_commission = sum(
                (d.target_sale_price or d.purchase_price or 0) * (d.commission_pct or 5.0) / 100
                for d in active
            )
            realized_commission = sum(d.commission_amount or 0 for d in completed)

            total_angariados = len(deals)
            conversion = (len(completed) / total_angariados * 100) if total_angariados else 0

            # Count visits
            visit_count = session.execute(
                select(func.count()).select_from(DealVisit)
                .where(DealVisit.deal_id.in_([d.id for d in deals]) if deals else False)
            ).scalar() or 0

            return {
                "active_mediations": len(active),
                "completed_mediations": len(completed),
                "total_portfolio_value": round(total_portfolio, 2),
                "potential_commission": round(potential_commission, 2),
                "realized_commission": round(realized_commission, 2),
                "conversion_rate_pct": round(conversion, 1),
                "total_visits": visit_count,
                "visits_per_deal": round(visit_count / len(active), 1) if active else 0,
            }
