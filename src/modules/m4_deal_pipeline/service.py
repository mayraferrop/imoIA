"""Servico M4 — Deal Pipeline.

Logica de negocio para gestao de deals, propostas, tasks e arrendamentos.
Persistencia via Supabase REST (sem SQLAlchemy).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

# FIXME(jwt-refactor): migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'
from src.database import supabase_rest as db
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deal_to_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Enriquece dict de deal com campos calculados da state machine."""
    status = d.get("status", "")
    strategy = d.get("investment_strategy", "")
    cfg = STATUS_CONFIG.get(status, {})
    strategy_info = INVESTMENT_STRATEGIES.get(strategy, {})

    # Calcular dias no estado actual
    days_in_status = 0
    status_changed_at = d.get("status_changed_at")
    if status_changed_at:
        if isinstance(status_changed_at, str):
            try:
                dt = datetime.fromisoformat(status_changed_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                dt = None
        else:
            dt = status_changed_at
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days_in_status = (datetime.now(timezone.utc) - dt).days

    return {
        "id": d.get("id"),
        "tenant_id": d.get("tenant_id"),
        "property_id": d.get("property_id"),
        "investment_strategy": strategy,
        "strategy_label": strategy_info.get("label", strategy),
        "strategy_icon": strategy_info.get("icon", ""),
        "status": status,
        "status_label": cfg.get("label", status),
        "status_color": cfg.get("color", "#666"),
        "status_icon": cfg.get("icon", ""),
        "title": d.get("title"),
        "purchase_price": d.get("purchase_price"),
        "target_sale_price": d.get("target_sale_price"),
        "actual_sale_price": d.get("actual_sale_price"),
        "monthly_rent": d.get("monthly_rent"),
        "renovation_budget": d.get("renovation_budget"),
        "actual_renovation_cost": d.get("actual_renovation_cost"),
        "contact_name": d.get("contact_name"),
        "contact_phone": d.get("contact_phone"),
        "contact_email": d.get("contact_email"),
        "contact_role": d.get("contact_role"),
        "status_changed_at": d.get("status_changed_at"),
        "days_in_status": days_in_status,
        "cpcv_date": d.get("cpcv_date"),
        "escritura_date": d.get("escritura_date"),
        "obra_start_date": d.get("obra_start_date"),
        "obra_end_date": d.get("obra_end_date"),
        "sale_date": d.get("sale_date"),
        "closed_at": d.get("closed_at"),
        "is_financed": d.get("is_financed", False),
        "is_off_market": d.get("is_off_market", False),
        "discard_reason": d.get("discard_reason"),
        "pause_reason": d.get("pause_reason"),
        "source_opportunity_id": d.get("source_opportunity_id"),
        "notes": d.get("notes"),
        "tags": d.get("tags") or [],
        "assigned_to": d.get("assigned_to"),
        "progress_pct": get_progress_pct(status, strategy),
        "role": d.get("role"),
        "owner_name": d.get("owner_name"),
        "owner_phone": d.get("owner_phone"),
        "owner_email": d.get("owner_email"),
        "mediation_contract_type": d.get("mediation_contract_type"),
        "commission_pct": d.get("commission_pct"),
        "commission_amount": d.get("commission_amount"),
        "commission_split_pct": d.get("commission_split_pct"),
        "commission_split_agent": d.get("commission_split_agent"),
        "cma_estimated_value": d.get("cma_estimated_value"),
        "cma_min_value": d.get("cma_min_value"),
        "cma_max_value": d.get("cma_max_value"),
        "cma_recommended_price": d.get("cma_recommended_price"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


def _proposal_to_dict(p: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna dict de proposta (ja vem como dict do REST)."""
    return {
        "id": p.get("id"),
        "deal_id": p.get("deal_id"),
        "proposal_type": p.get("proposal_type"),
        "amount": p.get("amount"),
        "deposit_pct": p.get("deposit_pct"),
        "conditions": p.get("conditions"),
        "validity_days": p.get("validity_days"),
        "status": p.get("status"),
        "sent_at": p.get("sent_at"),
        "response_at": p.get("response_at"),
        "response_notes": p.get("response_notes"),
        "created_at": p.get("created_at"),
    }


def _task_to_dict(t: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna dict de task."""
    return {
        "id": t.get("id"),
        "deal_id": t.get("deal_id"),
        "title": t.get("title"),
        "description": t.get("description"),
        "task_type": t.get("task_type"),
        "priority": t.get("priority"),
        "due_date": t.get("due_date"),
        "completed_at": t.get("completed_at"),
        "is_completed": t.get("is_completed", False),
        "assigned_to": t.get("assigned_to"),
        "created_at": t.get("created_at"),
    }


def _rental_to_dict(r: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna dict de rental."""
    return {
        "id": r.get("id"),
        "deal_id": r.get("deal_id"),
        "rental_type": r.get("rental_type"),
        "monthly_rent": r.get("monthly_rent"),
        "deposit_months": r.get("deposit_months"),
        "tenant_name": r.get("tenant_name"),
        "tenant_phone": r.get("tenant_phone"),
        "tenant_email": r.get("tenant_email"),
        "lease_start": r.get("lease_start"),
        "lease_end": r.get("lease_end"),
        "lease_duration_months": r.get("lease_duration_months"),
        "al_license_number": r.get("al_license_number"),
        "platform": r.get("platform"),
        "average_daily_rate": r.get("average_daily_rate"),
        "occupancy_rate_pct": r.get("occupancy_rate_pct"),
        "condominio_monthly": r.get("condominio_monthly"),
        "imi_annual": r.get("imi_annual"),
        "insurance_annual": r.get("insurance_annual"),
        "management_fee_pct": r.get("management_fee_pct"),
        "status": r.get("status"),
        "created_at": r.get("created_at"),
    }


def _history_to_dict(h: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna dict de historico de estado."""
    return {
        "id": h.get("id"),
        "deal_id": h.get("deal_id"),
        "from_status": h.get("from_status"),
        "to_status": h.get("to_status"),
        "changed_by": h.get("changed_by"),
        "reason": h.get("reason"),
        "metadata_json": h.get("metadata_json"),
        "created_at": h.get("created_at"),
    }


def _visit_to_dict(v: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna dict de visita."""
    return {
        "id": v.get("id"),
        "deal_id": v.get("deal_id"),
        "visitor_name": v.get("visitor_name"),
        "visitor_phone": v.get("visitor_phone"),
        "visitor_email": v.get("visitor_email"),
        "visit_date": v.get("visit_date"),
        "visit_type": v.get("visit_type"),
        "duration_minutes": v.get("duration_minutes"),
        "interest_level": v.get("interest_level"),
        "feedback": v.get("feedback"),
        "objections": v.get("objections"),
        "wants_second_visit": v.get("wants_second_visit"),
        "made_proposal": v.get("made_proposal"),
        "proposal_amount": v.get("proposal_amount"),
        "accompanied_by": v.get("accompanied_by"),
        "created_at": v.get("created_at"),
    }


def _commission_to_dict(c: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna dict de comissao."""
    return {
        "id": c.get("id"),
        "deal_id": c.get("deal_id"),
        "sale_price": c.get("sale_price"),
        "commission_pct": c.get("commission_pct"),
        "commission_gross": c.get("commission_gross"),
        "vat_pct": c.get("vat_pct"),
        "commission_with_vat": c.get("commission_with_vat"),
        "is_shared": c.get("is_shared"),
        "share_pct": c.get("share_pct"),
        "my_commission": c.get("my_commission"),
        "other_agent_name": c.get("other_agent_name"),
        "other_agent_agency": c.get("other_agent_agency"),
        "other_agent_commission": c.get("other_agent_commission"),
        "payment_status": c.get("payment_status"),
        "invoice_number": c.get("invoice_number"),
        "paid_amount": c.get("paid_amount"),
        "paid_date": c.get("paid_date"),
        "created_at": c.get("created_at"),
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

        organization_id = data.get("organization_id")
        if not organization_id:
            raise ValueError("organization_id obrigatorio")

        tenant_id = db.ensure_tenant()

        prop = db.get_by_id("properties", data["property_id"])
        if not prop:
            raise ValueError(f"Property nao encontrada: {data['property_id']}")

        now = datetime.now(timezone.utc).isoformat()
        deal_id = db.new_id()

        deal_row = {
            "id": deal_id,
            "tenant_id": tenant_id,
            "organization_id": organization_id,
            "property_id": data["property_id"],
            "investment_strategy": strategy,
            "status": "lead",
            "title": data.get("title", ""),
            "purchase_price": data.get("purchase_price"),
            "target_sale_price": data.get("target_sale_price"),
            "monthly_rent": data.get("monthly_rent"),
            "renovation_budget": data.get("renovation_budget"),
            "contact_name": data.get("contact_name"),
            "contact_phone": data.get("contact_phone"),
            "contact_email": data.get("contact_email"),
            "contact_role": data.get("contact_role"),
            "is_financed": data.get("is_financed", False),
            "is_off_market": data.get("is_off_market", False),
            "notes": data.get("notes"),
            "tags": data.get("tags", []),
            "status_changed_at": now,
        }
        deal = db.insert("deals", deal_row)

        # Registar estado inicial no historico
        db.insert("deal_state_history", {
            "id": db.new_id(),
            "tenant_id": tenant_id,
            "organization_id": organization_id,
            "deal_id": deal_id,
            "from_status": "",
            "to_status": "lead",
            "changed_by": data.get("changed_by", "system"),
            "reason": "Deal criado",
        })

        logger.info(f"Deal criado: {deal_id} ({data.get('title', '')}, {strategy})")
        return _deal_to_dict(deal)

    def create_deal_from_opportunity(
        self, opportunity_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria deal a partir de uma Opportunity do M1."""
        strategy = data.get("investment_strategy", "")
        if strategy not in INVESTMENT_STRATEGIES:
            raise ValueError(f"Estrategia invalida: {strategy}")

        tenant_id = db.ensure_tenant()

        # Buscar oportunidade (tabela legacy)
        opps = db.list_rows(
            "opportunities",
            filters=f"id=eq.{opportunity_id}&is_opportunity=eq.true",
            limit=1,
        )
        if not opps:
            raise ValueError("Oportunidade nao encontrada ou invalida")
        opp = opps[0]

        # Procurar Property existente para esta oportunidade
        props = db.list_rows(
            "properties",
            filters=f"source_opportunity_id=eq.{opportunity_id}",
            limit=1,
        )

        if props:
            prop = props[0]
        else:
            # Criar Property para esta oportunidade
            prop_id = db.new_id()
            is_off_market = "off_market" in (opp.get("opportunity_type") or "").lower()
            prop = db.insert("properties", {
                "id": prop_id,
                "tenant_id": tenant_id,
                "source": "whatsapp",
                "source_opportunity_id": opp["id"],
                "country": "PT",
                "district": opp.get("district"),
                "municipality": opp.get("municipality"),
                "parish": opp.get("parish"),
                "property_type": opp.get("property_type"),
                "asking_price": opp.get("price_mentioned"),
                "gross_area_m2": opp.get("area_m2"),
                "bedrooms": opp.get("bedrooms"),
                "is_off_market": is_off_market,
                "status": "oportunidade",
                "notes": opp.get("ai_reasoning"),
            })

        location = " ".join(
            filter(None, [opp.get("parish"), opp.get("municipality"), opp.get("district")])
        )
        title = data.get("title") or f"{opp.get('property_type') or 'Imovel'} {location}".strip()

        now = datetime.now(timezone.utc).isoformat()
        deal_id = db.new_id()
        is_off_market = "off_market" in (opp.get("opportunity_type") or "").lower()

        deal_row = {
            "id": deal_id,
            "tenant_id": tenant_id,
            "property_id": prop["id"],
            "investment_strategy": strategy,
            "status": "lead",
            "title": title,
            "purchase_price": data.get("purchase_price") or opp.get("price_mentioned"),
            "target_sale_price": data.get("target_sale_price"),
            "monthly_rent": data.get("monthly_rent"),
            "renovation_budget": data.get("renovation_budget"),
            "is_off_market": is_off_market,
            "source_opportunity_id": opp["id"],
            "notes": data.get("notes") or opp.get("ai_reasoning"),
            "status_changed_at": now,
        }
        deal = db.insert("deals", deal_row)

        db.insert("deal_state_history", {
            "id": db.new_id(),
            "tenant_id": tenant_id,
            "deal_id": deal_id,
            "from_status": "",
            "to_status": "lead",
            "changed_by": "system",
            "reason": f"Criado a partir de Opportunity #{opp['id']}",
        })

        logger.info(f"Deal {deal_id} criado a partir de Opportunity {opp['id']}")
        return _deal_to_dict(deal)

    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Retorna um deal por ID."""
        deal = db.get_by_id("deals", deal_id)
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
        filters_parts: List[str] = []
        if status:
            filters_parts.append(f"status=eq.{status}")
        if strategy:
            filters_parts.append(f"investment_strategy=eq.{strategy}")
        filters_str = "&".join(filters_parts)

        result = db.list_with_count(
            "deals",
            filters=filters_str,
            order="updated_at.desc",
            limit=limit,
            offset=offset,
        )
        return {
            "total": result["total"],
            "limit": limit,
            "offset": offset,
            "items": [_deal_to_dict(d) for d in result["items"]],
        }

    def update_deal(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Actualiza campos de um deal."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            return None

        # Validar estrategia se estiver a ser alterada
        new_strategy = data.get("investment_strategy")
        if new_strategy and new_strategy not in INVESTMENT_STRATEGIES:
            raise ValueError(f"Estrategia invalida: {new_strategy}")

        # Filtrar apenas campos validos (nao enviar None keys)
        update_data = {k: v for k, v in data.items() if v is not None}
        if not update_data:
            return _deal_to_dict(deal)

        updated = db.update("deals", deal_id, update_data)
        logger.info(f"Deal {deal_id} actualizado: {list(data.keys())}")
        return _deal_to_dict(updated)

    # --- State machine ---

    def advance_deal(
        self,
        deal_id: str,
        target_status: str,
        reason: Optional[str] = None,
        changed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Avanca o estado de um deal com validacao."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        current_status = deal["status"]
        if not can_transition(current_status, target_status):
            raise ValueError(
                f"Transicao invalida: {current_status} -> {target_status}"
            )

        now = datetime.now(timezone.utc).isoformat()

        # Preparar dados de update
        update_data: Dict[str, Any] = {
            "status": target_status,
            "status_changed_at": now,
        }

        # Flags especiais
        if target_status == "descartado":
            update_data["discard_reason"] = reason
        elif target_status == "em_pausa":
            update_data["pause_reason"] = reason
        elif target_status == "concluido":
            update_data["closed_at"] = now

        updated_deal = db.update("deals", deal_id, update_data)

        # Registar historico
        db.insert("deal_state_history", {
            "id": db.new_id(),
            "tenant_id": deal["tenant_id"],
            "deal_id": deal_id,
            "from_status": current_status,
            "to_status": target_status,
            "changed_by": changed_by or "user",
            "reason": reason,
        })

        # Criar tasks automaticas
        self._create_auto_tasks(deal, target_status)

        # M5: gerar checklist de due diligence automaticamente
        if target_status == "due_diligence":
            try:
                from src.modules.m5_due_diligence.service import DueDiligenceService
                dd_service = DueDiligenceService()
                dd_result = dd_service.generate_checklist(deal_id)
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
                reno_result = reno_service.create_renovation(deal_id, {
                    "initial_budget": float(deal.get("renovation_budget") or 50000),
                })
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
                mkt_service.handle_deal_advance_rest(deal_id, target_status)
                logger.info(f"M7 hook: {target_status}")
            except Exception as e:
                # Fallback: tentar metodo antigo caso o novo nao exista ainda
                try:
                    from src.modules.m7_marketing.service import MarketingService as MS2
                    ms2 = MS2()
                    if hasattr(ms2, "handle_deal_advance_by_id"):
                        ms2.handle_deal_advance_by_id(deal_id, target_status)
                except Exception:
                    pass
                logger.warning(f"M7 hook falhou: {e}")

        logger.info(f"Deal {deal_id}: {current_status} -> {target_status}")
        return _deal_to_dict(updated_deal)

    def get_next_actions(
        self, deal_id: str
    ) -> Dict[str, Any]:
        """Retorna proximas accoes possiveis para um deal."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        status = deal["status"]
        strategy = deal["investment_strategy"]
        next_statuses = get_next_statuses(status, strategy)

        return {
            "deal_id": deal["id"],
            "current_status": status,
            "investment_strategy": strategy,
            "next_statuses": [
                {
                    "status": s,
                    **STATUS_CONFIG.get(s, {"label": s, "color": "#666", "icon": ""}),
                }
                for s in next_statuses
            ],
            "progress_pct": get_progress_pct(status, strategy),
        }

    def get_deal_history(self, deal_id: str) -> List[Dict[str, Any]]:
        """Retorna historico de estados de um deal."""
        items = db.list_rows(
            "deal_state_history",
            filters=f"deal_id=eq.{deal_id}",
            order="created_at.desc",
        )
        return [_history_to_dict(h) for h in items]

    # --- Proposals ---

    def create_proposal(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria uma proposta para um deal."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        now = datetime.now(timezone.utc).isoformat()
        proposal_id = db.new_id()

        proposal = db.insert("proposals", {
            "id": proposal_id,
            "tenant_id": deal["tenant_id"],
            "deal_id": deal_id,
            "proposal_type": data.get("proposal_type", "offer"),
            "amount": data["amount"],
            "deposit_pct": data.get("deposit_pct", 10.0),
            "conditions": data.get("conditions"),
            "validity_days": data.get("validity_days", 5),
            "status": "sent",
            "sent_at": now,
        })

        logger.info(
            f"Proposta {proposal_id} criada para deal {deal_id}: "
            f"{data['amount']}EUR"
        )
        return _proposal_to_dict(proposal)

    def respond_to_proposal(
        self, proposal_id: str, status: str, response_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Responde a uma proposta (accepted/rejected/counter)."""
        proposal = db.get_by_id("proposals", proposal_id)
        if not proposal:
            raise ValueError(f"Proposta nao encontrada: {proposal_id}")

        now = datetime.now(timezone.utc).isoformat()
        updated = db.update("proposals", proposal_id, {
            "status": status,
            "response_at": now,
            "response_notes": response_notes,
        })

        logger.info(f"Proposta {proposal_id}: {status}")
        return _proposal_to_dict(updated)

    def list_proposals(self, deal_id: str) -> List[Dict[str, Any]]:
        """Lista propostas de um deal."""
        items = db.list_rows(
            "proposals",
            filters=f"deal_id=eq.{deal_id}",
            order="created_at.desc",
        )
        return [_proposal_to_dict(p) for p in items]

    # --- Tasks ---

    def create_task(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria uma tarefa manual para um deal."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        task = db.insert("deal_tasks", {
            "id": db.new_id(),
            "tenant_id": deal["tenant_id"],
            "deal_id": deal_id,
            "title": data["title"],
            "description": data.get("description"),
            "task_type": data.get("task_type", "manual"),
            "priority": data.get("priority", "medium"),
            "due_date": data.get("due_date"),
            "assigned_to": data.get("assigned_to"),
        })

        logger.info(f"Task criada: {data['title']} (deal {deal_id})")
        return _task_to_dict(task)

    def complete_task(self, task_id: str) -> Dict[str, Any]:
        """Marca uma tarefa como concluida."""
        task = db.get_by_id("deal_tasks", task_id)
        if not task:
            raise ValueError(f"Task nao encontrada: {task_id}")

        now = datetime.now(timezone.utc).isoformat()
        updated = db.update("deal_tasks", task_id, {
            "is_completed": True,
            "completed_at": now,
        })

        logger.info(f"Task concluida: {task.get('title', task_id)}")
        return _task_to_dict(updated)

    def get_upcoming_tasks(
        self, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retorna tarefas pendentes ordenadas por due_date."""
        items = db.list_rows(
            "deal_tasks",
            filters="is_completed=eq.false",
            order="due_date.asc.nullslast,priority.desc",
            limit=limit,
        )
        return [_task_to_dict(t) for t in items]

    def _create_auto_tasks(
        self, deal: Dict[str, Any], new_status: str
    ) -> None:
        """Cria tasks automaticas com base no novo estado."""
        templates = AUTO_TASKS.get(new_status, [])
        for tmpl in templates:
            db.insert("deal_tasks", {
                "id": db.new_id(),
                "tenant_id": deal["tenant_id"],
                "deal_id": deal["id"],
                "title": tmpl["title"],
                "task_type": "auto",
                "priority": tmpl.get("priority", "medium"),
            })

    # --- Rentals ---

    def add_rental(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adiciona dados de arrendamento a um deal."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        rental = db.insert("deal_rentals", {
            "id": db.new_id(),
            "tenant_id": deal["tenant_id"],
            "deal_id": deal_id,
            "rental_type": data.get("rental_type", "longa_duracao"),
            "monthly_rent": data["monthly_rent"],
            "deposit_months": data.get("deposit_months", 2),
            "tenant_name": data.get("tenant_name"),
            "tenant_phone": data.get("tenant_phone"),
            "tenant_email": data.get("tenant_email"),
            "lease_start": data.get("lease_start"),
            "lease_end": data.get("lease_end"),
            "lease_duration_months": data.get("lease_duration_months"),
            "al_license_number": data.get("al_license_number"),
            "platform": data.get("platform"),
            "average_daily_rate": data.get("average_daily_rate"),
            "occupancy_rate_pct": data.get("occupancy_rate_pct"),
            "condominio_monthly": data.get("condominio_monthly", 0),
            "imi_annual": data.get("imi_annual", 0),
            "insurance_annual": data.get("insurance_annual", 0),
            "management_fee_pct": data.get("management_fee_pct", 0),
        })

        # Actualizar renda mensal no deal
        db.update("deals", deal_id, {"monthly_rent": data["monthly_rent"]})

        logger.info(
            f"Rental adicionado ao deal {deal_id}: {data['monthly_rent']}EUR/mes"
        )
        return _rental_to_dict(rental)

    def update_rental(
        self, rental_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualiza dados de arrendamento."""
        rental = db.get_by_id("deal_rentals", rental_id)
        if not rental:
            raise ValueError(f"Rental nao encontrado: {rental_id}")

        # Filtrar campos validos
        update_data = {k: v for k, v in data.items() if v is not None}
        if update_data:
            rental = db.update("deal_rentals", rental_id, update_data)

        # Actualizar renda mensal no deal se alterada
        if "monthly_rent" in data:
            db.update("deals", rental["deal_id"], {
                "monthly_rent": data["monthly_rent"],
            })

        return _rental_to_dict(rental)

    # --- Kanban / Stats ---

    def get_kanban_data(
        self, strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retorna dados para vista kanban, agrupados por estado."""
        filters_parts = ["status=not.in.(concluido,descartado)"]
        if strategy:
            filters_parts.append(f"investment_strategy=eq.{strategy}")
        filters_str = "&".join(filters_parts)

        deals = db.list_rows("deals", filters=filters_str, limit=500)

        columns: Dict[str, List[Dict[str, Any]]] = {}
        for d in deals:
            status = d.get("status", "")
            if status not in columns:
                columns[status] = []
            columns[status].append(_deal_to_dict(d))

        # Ordenar colunas pela rota da estrategia (se especificada)
        if strategy and strategy in STRATEGY_ROUTES:
            route = STRATEGY_ROUTES[strategy]
            ordered: Dict[str, List[Dict[str, Any]]] = {}
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
        filters_str = ""
        if strategy:
            filters_str = f"investment_strategy=eq.{strategy}"

        deals = db.list_rows("deals", filters=filters_str, limit=1000)

        active = [
            d for d in deals if d.get("status") not in ("concluido", "descartado")
        ]
        completed = [d for d in deals if d.get("status") == "concluido"]
        discarded = [d for d in deals if d.get("status") == "descartado"]

        total_invested = sum(d.get("purchase_price") or 0 for d in active)
        total_monthly_rent = sum(
            d.get("monthly_rent") or 0
            for d in active
            if d.get("status") == "arrendamento"
        )
        avg_roi = 0.0
        if completed:
            prices = [
                (d.get("actual_sale_price") or 0) - (d.get("purchase_price") or 0)
                for d in completed
                if d.get("purchase_price")
            ]
            investments = [
                d["purchase_price"] for d in completed if d.get("purchase_price")
            ]
            if investments:
                total_profit = sum(prices)
                total_inv = sum(investments)
                avg_roi = (total_profit / total_inv * 100) if total_inv else 0

        # Distribuicao por estrategia
        by_strategy: Dict[str, int] = {}
        for d in deals:
            s = d.get("investment_strategy", "")
            by_strategy[s] = by_strategy.get(s, 0) + 1

        # Valor por estado
        by_status: Dict[str, Dict[str, Any]] = {}
        for d in active:
            s = d.get("status", "")
            if s not in by_status:
                by_status[s] = {"count": 0, "value": 0}
            by_status[s]["count"] += 1
            by_status[s]["value"] += d.get("purchase_price") or 0

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

        tenant_id = db.ensure_tenant()

        prop = db.get_by_id("properties", data["property_id"])
        if not prop:
            raise ValueError(f"Property nao encontrada: {data['property_id']}")

        now = datetime.now(timezone.utc).isoformat()
        deal_id = db.new_id()

        deal_row = {
            "id": deal_id,
            "tenant_id": tenant_id,
            "property_id": data["property_id"],
            "investment_strategy": strategy,
            "status": "lead",
            "title": data.get("title", ""),
            "role": "mediador",
            # Owner
            "owner_name": data.get("owner_name"),
            "owner_phone": data.get("owner_phone"),
            "owner_email": data.get("owner_email"),
            # Commission
            "commission_pct": data.get("commission_pct"),
            "commission_vat_included": data.get("commission_vat_included", False),
            "commission_split_pct": data.get("commission_split_pct"),
            "commission_split_agent": data.get("commission_split_agent"),
            "commission_split_agency": data.get("commission_split_agency"),
            # Contract
            "mediation_contract_type": data.get("mediation_contract_type"),
            # Prices
            "purchase_price": data.get("purchase_price"),
            "target_sale_price": data.get("target_sale_price"),
            "monthly_rent": data.get("monthly_rent"),
            "contact_name": data.get("contact_name"),
            "contact_phone": data.get("contact_phone"),
            "notes": data.get("notes"),
            "tags": data.get("tags", []),
            "status_changed_at": now,
            "is_off_market": data.get("is_off_market", False),
        }
        deal = db.insert("deals", deal_row)

        db.insert("deal_state_history", {
            "id": db.new_id(),
            "tenant_id": tenant_id,
            "deal_id": deal_id,
            "from_status": "",
            "to_status": "lead",
            "changed_by": "system",
            "reason": "Deal mediacao criado",
        })

        logger.info(f"Deal mediacao criado: {deal_id} ({strategy})")
        return _deal_to_dict(deal)

    def generate_cma(
        self,
        deal_id: str,
        comparables: List[Dict],
        recommended_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Gera CMA simplificado a partir de comparaveis manuais."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        if not comparables:
            raise ValueError("Pelo menos 1 comparavel necessario")

        prices_m2: List[float] = []
        for c in comparables:
            if c.get("area_m2") and c["area_m2"] > 0:
                prices_m2.append(c["price"] / c["area_m2"])

        prices = sorted([c["price"] for c in comparables])
        min_val = prices[0]
        max_val = prices[-1]
        median_val = prices[len(prices) // 2]

        now = datetime.now(timezone.utc).isoformat()
        rec_price = recommended_price or median_val

        db.update("deals", deal_id, {
            "cma_min_value": min_val,
            "cma_max_value": max_val,
            "cma_estimated_value": median_val,
            "cma_recommended_price": rec_price,
            "cma_date": now,
        })

        logger.info(
            f"CMA gerado para deal {deal_id}: {min_val}-{max_val}, mediana {median_val}"
        )
        return {
            "deal_id": deal_id,
            "min_value": min_val,
            "max_value": max_val,
            "estimated_value": median_val,
            "recommended_price": rec_price,
            "comparables_count": len(comparables),
            "price_per_m2": (
                round(sum(prices_m2) / len(prices_m2), 2) if prices_m2 else None
            ),
            "cma_date": now,
        }

    def register_visit(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Regista uma visita ao imovel."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        visit = db.insert("deal_visits", {
            "id": db.new_id(),
            "tenant_id": deal["tenant_id"],
            "deal_id": deal_id,
            "visitor_name": data["visitor_name"],
            "visitor_phone": data.get("visitor_phone"),
            "visitor_email": data.get("visitor_email"),
            "visit_date": data["visit_date"],
            "visit_type": data.get("visit_type", "presencial"),
            "duration_minutes": data.get("duration_minutes"),
            "accompanied_by": data.get("accompanied_by"),
        })

        logger.info(f"Visita registada: {data['visitor_name']} ao deal {deal_id}")
        return _visit_to_dict(visit)

    def update_visit(
        self, visit_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualiza feedback de uma visita."""
        visit = db.get_by_id("deal_visits", visit_id)
        if not visit:
            raise ValueError(f"Visita nao encontrada: {visit_id}")

        update_data = {k: v for k, v in data.items() if v is not None}
        if update_data:
            visit = db.update("deal_visits", visit_id, update_data)

        return _visit_to_dict(visit)

    def list_visits(self, deal_id: str) -> List[Dict[str, Any]]:
        """Lista visitas de um deal."""
        items = db.list_rows(
            "deal_visits",
            filters=f"deal_id=eq.{deal_id}",
            order="visit_date.desc",
        )
        return [_visit_to_dict(v) for v in items]

    def calculate_commission(
        self, deal_id: str, sale_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calcula comissao baseada no preco e condicoes do deal."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        price = (
            sale_price
            or deal.get("actual_sale_price")
            or deal.get("target_sale_price")
            or deal.get("purchase_price")
            or 0
        )
        pct = deal.get("commission_pct") or 5.0
        gross = price * pct / 100
        vat_pct = 23.0
        if deal.get("commission_vat_included"):
            commission_with_vat = gross
            commission_net = gross / (1 + vat_pct / 100)
        else:
            commission_net = gross
            commission_with_vat = gross * (1 + vat_pct / 100)

        split_pct = deal.get("commission_split_pct")
        is_shared = bool(split_pct and split_pct < 100)
        share_pct = split_pct or 100.0
        my_commission = commission_with_vat * share_pct / 100
        other_commission = commission_with_vat - my_commission if is_shared else 0

        return {
            "deal_id": deal["id"],
            "sale_price": price,
            "commission_pct": pct,
            "commission_gross": round(gross, 2),
            "vat_pct": vat_pct,
            "commission_with_vat": round(commission_with_vat, 2),
            "commission_net": round(commission_net, 2),
            "is_shared": is_shared,
            "share_pct": share_pct,
            "my_commission": round(my_commission, 2),
            "other_agent_name": deal.get("commission_split_agent"),
            "other_agent_commission": round(other_commission, 2),
        }

    def create_commission_record(
        self, deal_id: str, sale_price: float
    ) -> Dict[str, Any]:
        """Cria registo de comissao com calculo completo."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        pct = deal.get("commission_pct") or 5.0
        gross = sale_price * pct / 100
        vat_pct = 23.0
        if deal.get("commission_vat_included"):
            with_vat = gross
        else:
            with_vat = gross * (1 + vat_pct / 100)

        split_pct = deal.get("commission_split_pct")
        is_shared = bool(split_pct and split_pct < 100)
        share_pct = split_pct or 100.0
        my_part = with_vat * share_pct / 100
        other_part = with_vat - my_part if is_shared else 0

        commission = db.insert("deal_commissions", {
            "id": db.new_id(),
            "tenant_id": deal["tenant_id"],
            "deal_id": deal_id,
            "sale_price": sale_price,
            "commission_pct": pct,
            "commission_gross": round(gross, 2),
            "vat_pct": vat_pct,
            "commission_with_vat": round(with_vat, 2),
            "is_shared": is_shared,
            "share_pct": share_pct,
            "my_commission": round(my_part, 2),
            "other_agent_name": deal.get("commission_split_agent"),
            "other_agent_agency": deal.get("commission_split_agency"),
            "other_agent_commission": round(other_part, 2),
        })

        # Actualizar commission_amount no deal
        db.update("deals", deal_id, {"commission_amount": round(my_part, 2)})

        return _commission_to_dict(commission)

    def invoice_commission(
        self, commission_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Regista factura numa comissao."""
        commission = db.get_by_id("deal_commissions", commission_id)
        if not commission:
            raise ValueError(f"Comissao nao encontrada: {commission_id}")

        update_data: Dict[str, Any] = {
            "invoice_number": data.get("invoice_number"),
            "invoice_url": data.get("invoice_url"),
            "payment_status": "facturado",
        }
        if data.get("paid_amount"):
            update_data["paid_amount"] = data["paid_amount"]
        if data.get("paid_date"):
            update_data["paid_date"] = data["paid_date"]

        # Verificar se esta pago
        paid_amount = data.get("paid_amount") or commission.get("paid_amount") or 0
        my_commission = commission.get("my_commission") or 0
        if paid_amount and paid_amount >= my_commission:
            update_data["payment_status"] = "pago"

        updated = db.update("deal_commissions", commission_id, update_data)
        return _commission_to_dict(updated)

    def get_mediation_stats(self) -> Dict[str, Any]:
        """Stats especificas de mediacao."""
        deals = db.list_rows(
            "deals",
            filters="role=eq.mediador",
            limit=1000,
        )

        active = [
            d for d in deals if d.get("status") not in ("concluido", "descartado")
        ]
        completed = [d for d in deals if d.get("status") == "concluido"]

        total_portfolio = sum(
            d.get("target_sale_price") or d.get("purchase_price") or 0
            for d in active
        )
        potential_commission = sum(
            (d.get("target_sale_price") or d.get("purchase_price") or 0)
            * (d.get("commission_pct") or 5.0)
            / 100
            for d in active
        )
        realized_commission = sum(d.get("commission_amount") or 0 for d in completed)

        total_angariados = len(deals)
        conversion = (
            (len(completed) / total_angariados * 100) if total_angariados else 0
        )

        # Contar visitas dos deals de mediacao
        visit_count = 0
        if deals:
            deal_ids = [d["id"] for d in deals]
            # Buscar visitas de cada deal (PostgREST in filter)
            ids_str = ",".join(deal_ids)
            visit_count = db._count("deal_visits", f"deal_id=in.({ids_str})")

        return {
            "active_mediations": len(active),
            "completed_mediations": len(completed),
            "total_portfolio_value": round(total_portfolio, 2),
            "potential_commission": round(potential_commission, 2),
            "realized_commission": round(realized_commission, 2),
            "conversion_rate_pct": round(conversion, 1),
            "total_visits": visit_count,
            "visits_per_deal": (
                round(visit_count / len(active), 1) if active else 0
            ),
        }
