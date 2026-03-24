"""Servico M6 — Gestao de Obra.

Logica de negocio para gestao de obras/renovacoes, milestones, despesas e fotos
associadas a deals imobiliarios fix and flip.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.db import get_session
from src.database.models_v2 import (
    Deal,
    Property,
    Renovation,
    RenovationExpense,
    RenovationMilestone,
    RenovationPhoto,
    Tenant,
)
from src.modules.m6_renovation.templates import get_milestone_template
from src.shared.document_storage import DocumentStorageService

_DEFAULT_TENANT_SLUG = "default"

# Metodos de pagamento que permitem dedutibilidade fiscal
_TAX_DEDUCTIBLE_PAYMENT_METHODS = ("transferencia", "cartao", "mbway")


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


def _renovation_to_dict(r: Renovation) -> Dict[str, Any]:
    """Serializa Renovation para dict."""
    return {
        "id": r.id,
        "tenant_id": r.tenant_id,
        "deal_id": r.deal_id,
        "initial_budget": r.initial_budget,
        "current_budget": r.current_budget,
        "total_spent": r.total_spent,
        "total_committed": r.total_committed,
        "budget_variance_pct": r.budget_variance_pct,
        "contingency_pct": r.contingency_pct,
        "contingency_amount": r.contingency_amount,
        "planned_start": r.planned_start.isoformat() if r.planned_start else None,
        "actual_start": r.actual_start.isoformat() if r.actual_start else None,
        "planned_end": r.planned_end.isoformat() if r.planned_end else None,
        "estimated_end": r.estimated_end.isoformat() if r.estimated_end else None,
        "actual_end": r.actual_end.isoformat() if r.actual_end else None,
        "planned_duration_days": r.planned_duration_days,
        "delay_days": r.delay_days,
        "delay_reason": r.delay_reason,
        "contractor_name": r.contractor_name,
        "contractor_phone": r.contractor_phone,
        "contractor_email": r.contractor_email,
        "contractor_nif": r.contractor_nif,
        "license_type": r.license_type,
        "license_status": r.license_status,
        "license_number": r.license_number,
        "is_aru": r.is_aru,
        "status": r.status,
        "progress_pct": r.progress_pct,
        "scope_description": r.scope_description,
        "notes": r.notes,
        "cashflow_project_id": r.cashflow_project_id,
        "cashflow_project_name": r.cashflow_project_name,
        "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _milestone_to_dict(m: RenovationMilestone) -> Dict[str, Any]:
    """Serializa RenovationMilestone para dict."""
    return {
        "id": m.id,
        "renovation_id": m.renovation_id,
        "name": m.name,
        "category": m.category,
        "description": m.description,
        "sort_order": m.sort_order,
        "budget": m.budget,
        "spent": m.spent,
        "variance_pct": m.variance_pct,
        "planned_start": m.planned_start.isoformat() if m.planned_start else None,
        "planned_end": m.planned_end.isoformat() if m.planned_end else None,
        "actual_start": m.actual_start.isoformat() if m.actual_start else None,
        "actual_end": m.actual_end.isoformat() if m.actual_end else None,
        "duration_days": m.duration_days,
        "status": m.status,
        "completion_pct": m.completion_pct,
        "depends_on_id": m.depends_on_id,
        "supplier_name": m.supplier_name,
        "supplier_phone": m.supplier_phone,
        "supplier_nif": m.supplier_nif,
        "notes": m.notes,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _expense_to_dict(e: RenovationExpense) -> Dict[str, Any]:
    """Serializa RenovationExpense para dict."""
    return {
        "id": e.id,
        "renovation_id": e.renovation_id,
        "milestone_id": e.milestone_id,
        "description": e.description,
        "category": e.category,
        "amount": e.amount,
        "currency": e.currency,
        "supplier_name": e.supplier_name,
        "supplier_nif": e.supplier_nif,
        "invoice_number": e.invoice_number,
        "invoice_date": e.invoice_date.isoformat() if e.invoice_date else None,
        "invoice_document_id": e.invoice_document_id,
        "has_valid_invoice": e.has_valid_invoice,
        "payment_method": e.payment_method,
        "is_tax_deductible": e.is_tax_deductible,
        "payment_status": e.payment_status,
        "paid_amount": e.paid_amount,
        "paid_date": e.paid_date.isoformat() if e.paid_date else None,
        "expense_date": e.expense_date.isoformat() if e.expense_date else None,
        "external_id": e.external_id,
        "external_source": e.external_source,
        "notes": e.notes,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _photo_to_dict(p: RenovationPhoto) -> Dict[str, Any]:
    """Serializa RenovationPhoto para dict."""
    return {
        "id": p.id,
        "renovation_id": p.renovation_id,
        "milestone_id": p.milestone_id,
        "document_id": p.document_id,
        "photo_type": p.photo_type,
        "caption": p.caption,
        "taken_at": p.taken_at.isoformat() if p.taken_at else None,
        "taken_by": p.taken_by,
        "room_area": p.room_area,
        "sort_order": p.sort_order,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _recalc_totals(session: Session, renovation_id: str) -> None:
    """Recalcula total_spent, budget_variance_pct e progress_pct da renovacao.

    Agrega todas as despesas pagas ou pendentes, recalcula a variacao orcamental
    e actualiza o progresso ponderado com base nos milestones.
    """
    renovation = session.get(Renovation, renovation_id)
    if not renovation:
        return

    # Recalcular total_spent a partir das despesas
    expenses_stmt = select(RenovationExpense).where(
        RenovationExpense.renovation_id == renovation_id
    )
    expenses = session.execute(expenses_stmt).scalars().all()
    total_spent = sum(e.amount for e in expenses)
    renovation.total_spent = total_spent

    # Recalcular variacao orcamental
    current_budget = renovation.current_budget or renovation.initial_budget
    if current_budget and current_budget > 0:
        renovation.budget_variance_pct = round(
            (total_spent / current_budget) * 100, 2
        )
    else:
        renovation.budget_variance_pct = 0.0

    # Recalcular progress_pct como media ponderada por orcamento dos milestones
    milestones_stmt = select(RenovationMilestone).where(
        RenovationMilestone.renovation_id == renovation_id
    )
    milestones = session.execute(milestones_stmt).scalars().all()

    if milestones:
        total_budget_weight = sum(m.budget for m in milestones)
        if total_budget_weight > 0:
            weighted_sum = sum(
                m.completion_pct * m.budget for m in milestones
            )
            renovation.progress_pct = round(
                weighted_sum / total_budget_weight, 1
            )
        else:
            # Sem pesos, usar media simples
            renovation.progress_pct = round(
                sum(m.completion_pct for m in milestones) / len(milestones), 1
            )
    else:
        renovation.progress_pct = 0.0

    session.flush()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RenovationService:
    """Logica de negocio do M6 — Gestao de Obra."""

    # --- Renovacao ---

    def create_renovation(
        self, deal_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria uma renovacao para um deal.

        Calcula o orcamento de contingencia e, se auto_milestones=True (default),
        gera automaticamente os milestones a partir do template adequado ao
        tipo de imovel.
        """
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            tenant_id = deal.tenant_id

            # Verificar se ja existe renovacao para este deal
            existing = session.execute(
                select(Renovation).where(Renovation.deal_id == deal_id)
            ).scalar_one_or_none()
            if existing:
                raise ValueError(
                    f"Renovacao ja existe para o deal {deal_id}: {existing.id}"
                )

            initial_budget = float(data.get("initial_budget", 50000))
            contingency_pct = float(data.get("contingency_pct", 15))
            contingency_amount = round(initial_budget * contingency_pct / 100, 2)

            renovation = Renovation(
                id=str(uuid4()),
                tenant_id=tenant_id,
                deal_id=deal_id,
                initial_budget=initial_budget,
                current_budget=initial_budget,
                contingency_pct=contingency_pct,
                contingency_amount=contingency_amount,
                planned_start=data.get("planned_start"),
                planned_end=data.get("planned_end"),
                planned_duration_days=data.get("planned_duration_days"),
                contractor_name=data.get("contractor_name"),
                contractor_phone=data.get("contractor_phone"),
                contractor_email=data.get("contractor_email"),
                contractor_nif=data.get("contractor_nif"),
                license_type=data.get("license_type", "isento"),
                license_status=data.get("license_status", "na"),
                license_number=data.get("license_number"),
                is_aru=data.get("is_aru", False),
                scope_description=data.get("scope_description"),
                notes=data.get("notes"),
                status="planeamento",
            )
            session.add(renovation)
            session.flush()

            # Gerar milestones automaticos a partir do template
            milestone_count = 0
            auto_milestones = data.get("auto_milestones", True)
            if auto_milestones:
                prop = session.get(Property, deal.property_id)
                property_type = (prop.property_type if prop else None) or "apartamento"
                strategy = deal.investment_strategy

                template_items = get_milestone_template(property_type, strategy)

                # Primeira passagem: criar todos os milestones (sem dependencias)
                created_milestones: Dict[str, RenovationMilestone] = {}
                for idx, tmpl in enumerate(template_items):
                    budget_pct = float(tmpl.get("budget_pct", 0))
                    milestone_budget = round(initial_budget * budget_pct / 100, 2)

                    milestone = RenovationMilestone(
                        id=str(uuid4()),
                        renovation_id=renovation.id,
                        name=tmpl.get("name", f"Fase {idx + 1}"),
                        category=tmpl.get("category", "geral"),
                        description=tmpl.get("description"),
                        sort_order=tmpl.get("sort_order", idx),
                        budget=milestone_budget,
                        duration_days=tmpl.get("duration_days"),
                        status="pendente",
                        completion_pct=0,
                    )
                    session.add(milestone)
                    session.flush()
                    created_milestones[tmpl.get("name", "")] = milestone
                    milestone_count += 1

                # Segunda passagem: resolver dependencias por nome
                for tmpl in template_items:
                    depends_on_name = tmpl.get("depends_on")
                    if depends_on_name and depends_on_name in created_milestones:
                        current = created_milestones.get(tmpl.get("name", ""))
                        dep = created_milestones[depends_on_name]
                        if current:
                            current.depends_on_id = dep.id

                session.flush()

            logger.info(
                f"Renovacao {renovation.id} criada para deal {deal_id} "
                f"(orcamento: {initial_budget}EUR, {milestone_count} milestones)"
            )

            result = _renovation_to_dict(renovation)
            result["milestone_count"] = milestone_count
            return result

    def create_renovation_in_session(
        self, session: Session, deal: Deal
    ) -> Dict[str, Any]:
        """Cria renovacao usando sessao existente (chamado pelo M4 advance_deal).

        Usa deal.renovation_budget como orcamento inicial (50000 se None).
        Obtém o property_type da propriedade associada ao deal.
        """
        # Verificar se ja existe renovacao para este deal
        existing = session.execute(
            select(Renovation).where(Renovation.deal_id == deal.id)
        ).scalar_one_or_none()
        if existing:
            logger.warning(
                f"Renovacao ja existe para deal {deal.id}: {existing.id}"
            )
            return _renovation_to_dict(existing)

        initial_budget = float(deal.renovation_budget or 50000)
        contingency_pct = 15.0
        contingency_amount = round(initial_budget * contingency_pct / 100, 2)

        renovation = Renovation(
            id=str(uuid4()),
            tenant_id=deal.tenant_id,
            deal_id=deal.id,
            initial_budget=initial_budget,
            current_budget=initial_budget,
            contingency_pct=contingency_pct,
            contingency_amount=contingency_amount,
            status="planeamento",
        )
        session.add(renovation)
        session.flush()

        # Milestones automaticos
        prop = session.get(Property, deal.property_id)
        property_type = (prop.property_type if prop else None) or "apartamento"
        strategy = deal.investment_strategy
        template_items = get_milestone_template(property_type, strategy)

        created_milestones: Dict[str, RenovationMilestone] = {}
        for idx, tmpl in enumerate(template_items):
            budget_pct = float(tmpl.get("budget_pct", 0))
            milestone_budget = round(initial_budget * budget_pct / 100, 2)

            milestone = RenovationMilestone(
                id=str(uuid4()),
                renovation_id=renovation.id,
                name=tmpl.get("name", f"Fase {idx + 1}"),
                category=tmpl.get("category", "geral"),
                description=tmpl.get("description"),
                sort_order=tmpl.get("sort_order", idx),
                budget=milestone_budget,
                duration_days=tmpl.get("duration_days"),
                status="pendente",
                completion_pct=0,
            )
            session.add(milestone)
            session.flush()
            created_milestones[tmpl.get("name", "")] = milestone

        # Resolver dependencias por nome
        for tmpl in template_items:
            depends_on_name = tmpl.get("depends_on")
            if depends_on_name and depends_on_name in created_milestones:
                current = created_milestones.get(tmpl.get("name", ""))
                dep = created_milestones[depends_on_name]
                if current:
                    current.depends_on_id = dep.id

        session.flush()
        logger.info(
            f"Renovacao {renovation.id} criada em sessao para deal {deal.id} "
            f"({len(created_milestones)} milestones)"
        )
        result = _renovation_to_dict(renovation)
        result["milestone_count"] = len(created_milestones)
        return result

    def get_renovation(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Retorna renovacao completa com milestones, resumo de despesas e saude orcamental."""
        with get_session() as session:
            renovation = session.execute(
                select(Renovation).where(Renovation.deal_id == deal_id)
            ).scalar_one_or_none()

            if not renovation:
                return None

            # Milestones ordenados
            milestones_stmt = (
                select(RenovationMilestone)
                .where(RenovationMilestone.renovation_id == renovation.id)
                .order_by(RenovationMilestone.sort_order)
            )
            milestones = session.execute(milestones_stmt).scalars().all()

            # Resumo de despesas
            expense_summary = self._build_expense_summary(session, renovation.id)

            # Saude orcamental
            variance_pct = renovation.budget_variance_pct
            if variance_pct > 100:
                budget_health = "over_budget"
            elif variance_pct >= 80:
                budget_health = "warning"
            else:
                budget_health = "on_track"

            return {
                "renovation": _renovation_to_dict(renovation),
                "milestones": [_milestone_to_dict(m) for m in milestones],
                "expense_summary": expense_summary,
                "budget_health": budget_health,
            }

    def update_renovation(
        self, renovation_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualiza campos de uma renovacao."""
        with get_session() as session:
            renovation = session.get(Renovation, renovation_id)
            if not renovation:
                raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

            updatable_fields = (
                "current_budget",
                "contingency_pct",
                "contingency_amount",
                "planned_start",
                "planned_end",
                "planned_duration_days",
                "estimated_end",
                "delay_days",
                "delay_reason",
                "contractor_name",
                "contractor_phone",
                "contractor_email",
                "contractor_nif",
                "license_type",
                "license_status",
                "license_number",
                "is_aru",
                "scope_description",
                "notes",
                "status",
            )
            for field in updatable_fields:
                if field in data:
                    setattr(renovation, field, data[field])

            # Recalcular contingencia se current_budget alterado
            if "current_budget" in data and data["current_budget"]:
                new_budget = float(data["current_budget"])
                contingency_pct = renovation.contingency_pct or 15.0
                renovation.contingency_amount = round(
                    new_budget * contingency_pct / 100, 2
                )

            session.flush()
            logger.info(f"Renovacao {renovation_id} actualizada: {list(data.keys())}")
            return _renovation_to_dict(renovation)

    # --- Milestones ---

    def get_milestones(self, renovation_id: str) -> List[Dict[str, Any]]:
        """Lista milestones de uma renovacao ordenados por sort_order."""
        with get_session() as session:
            stmt = (
                select(RenovationMilestone)
                .where(RenovationMilestone.renovation_id == renovation_id)
                .order_by(RenovationMilestone.sort_order)
            )
            items = session.execute(stmt).scalars().all()
            return [_milestone_to_dict(m) for m in items]

    def add_milestone(
        self, renovation_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adiciona um milestone a uma renovacao."""
        with get_session() as session:
            renovation = session.get(Renovation, renovation_id)
            if not renovation:
                raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

            milestone = RenovationMilestone(
                id=str(uuid4()),
                renovation_id=renovation_id,
                name=data["name"],
                category=data.get("category", "geral"),
                description=data.get("description"),
                sort_order=data.get("sort_order", 999),
                budget=float(data.get("budget", 0)),
                planned_start=data.get("planned_start"),
                planned_end=data.get("planned_end"),
                duration_days=data.get("duration_days"),
                depends_on_id=data.get("depends_on_id"),
                supplier_name=data.get("supplier_name"),
                supplier_phone=data.get("supplier_phone"),
                supplier_nif=data.get("supplier_nif"),
                notes=data.get("notes"),
                status="pendente",
                completion_pct=0,
            )
            session.add(milestone)
            session.flush()
            logger.info(
                f"Milestone '{milestone.name}' adicionado a renovacao {renovation_id}"
            )
            return _milestone_to_dict(milestone)

    def update_milestone(
        self, milestone_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualiza um milestone.

        Se completion_pct atingir 100, define status='concluido' e actual_end=now.
        Recalcula o progresso global da renovacao.
        """
        with get_session() as session:
            milestone = session.get(RenovationMilestone, milestone_id)
            if not milestone:
                raise ValueError(f"Milestone nao encontrado: {milestone_id}")

            updatable_fields = (
                "name",
                "category",
                "description",
                "sort_order",
                "budget",
                "planned_start",
                "planned_end",
                "actual_start",
                "actual_end",
                "duration_days",
                "completion_pct",
                "depends_on_id",
                "supplier_name",
                "supplier_phone",
                "supplier_nif",
                "notes",
                "status",
            )
            for field in updatable_fields:
                if field in data:
                    setattr(milestone, field, data[field])

            # Auto-completar se completion_pct = 100
            if data.get("completion_pct") == 100:
                milestone.status = "concluido"
                if not milestone.actual_end:
                    milestone.actual_end = datetime.now(timezone.utc)

            session.flush()

            # Recalcular progresso da renovacao
            _recalc_totals(session, milestone.renovation_id)

            logger.info(f"Milestone {milestone_id} actualizado: {list(data.keys())}")
            return _milestone_to_dict(milestone)

    def start_milestone(self, milestone_id: str) -> Dict[str, Any]:
        """Inicia um milestone.

        Verifica se o milestone de dependencia esta concluido antes de arrancar.
        Se for o primeiro milestone iniciado, define actual_start da renovacao.
        """
        with get_session() as session:
            milestone = session.get(RenovationMilestone, milestone_id)
            if not milestone:
                raise ValueError(f"Milestone nao encontrado: {milestone_id}")

            # Verificar dependencia
            if milestone.depends_on_id:
                dep = session.get(RenovationMilestone, milestone.depends_on_id)
                if dep and dep.status != "concluido":
                    raise ValueError(
                        f"O milestone '{dep.name}' (dependencia) ainda nao esta concluido"
                    )

            now = datetime.now(timezone.utc)
            milestone.status = "em_curso"
            milestone.actual_start = now

            # Se for o primeiro milestone iniciado, actualizar renovacao
            renovation = session.get(Renovation, milestone.renovation_id)
            if renovation and not renovation.actual_start:
                renovation.actual_start = now
                renovation.status = "em_curso"

            session.flush()
            logger.info(
                f"Milestone '{milestone.name}' iniciado "
                f"(renovacao {milestone.renovation_id})"
            )
            return _milestone_to_dict(milestone)

    def complete_milestone(self, milestone_id: str) -> Dict[str, Any]:
        """Conclui um milestone e recalcula o progresso da renovacao."""
        with get_session() as session:
            milestone = session.get(RenovationMilestone, milestone_id)
            if not milestone:
                raise ValueError(f"Milestone nao encontrado: {milestone_id}")

            now = datetime.now(timezone.utc)
            milestone.status = "concluido"
            milestone.completion_pct = 100
            milestone.actual_end = now

            session.flush()

            # Recalcular progresso global
            _recalc_totals(session, milestone.renovation_id)

            logger.info(
                f"Milestone '{milestone.name}' concluido "
                f"(renovacao {milestone.renovation_id})"
            )
            return _milestone_to_dict(milestone)

    def delete_milestone(self, milestone_id: str) -> bool:
        """Remove um milestone e recalcula totais da renovacao."""
        with get_session() as session:
            milestone = session.get(RenovationMilestone, milestone_id)
            if not milestone:
                raise ValueError(f"Milestone nao encontrado: {milestone_id}")

            reno_id = milestone.renovation_id

            # Remover despesas associadas
            expenses = session.execute(
                select(RenovationExpense).where(
                    RenovationExpense.milestone_id == milestone_id
                )
            ).scalars().all()
            for exp in expenses:
                session.delete(exp)

            # Remover fotos associadas
            photos = session.execute(
                select(RenovationPhoto).where(
                    RenovationPhoto.milestone_id == milestone_id
                )
            ).scalars().all()
            for photo in photos:
                session.delete(photo)

            # Limpar dependencias que apontam para este milestone
            dependents = session.execute(
                select(RenovationMilestone).where(
                    RenovationMilestone.depends_on_id == milestone_id
                )
            ).scalars().all()
            for dep in dependents:
                dep.depends_on_id = None

            session.delete(milestone)
            session.flush()

            self._recalc_totals(session, reno_id)
            session.flush()

            logger.info(f"Milestone {milestone_id} removido")
            return True

    # --- Despesas ---

    def add_expense(
        self, renovation_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Regista uma despesa numa renovacao.

        Calcula automaticamente is_tax_deductible com base na presenca de
        factura valida e no metodo de pagamento.
        Actualiza os totais do milestone associado (se indicado) e da renovacao.
        """
        with get_session() as session:
            renovation = session.get(Renovation, renovation_id)
            if not renovation:
                raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

            has_valid_invoice = bool(data.get("has_valid_invoice", False))
            payment_method = data.get("payment_method")
            is_tax_deductible = (
                has_valid_invoice
                and payment_method in _TAX_DEDUCTIBLE_PAYMENT_METHODS
            )

            expense_date = data.get("expense_date") or datetime.now(timezone.utc)

            expense = RenovationExpense(
                id=str(uuid4()),
                renovation_id=renovation_id,
                milestone_id=data.get("milestone_id"),
                description=data["description"],
                category=data.get("category"),
                amount=float(data["amount"]),
                currency=data.get("currency", "EUR"),
                supplier_name=data.get("supplier_name"),
                supplier_nif=data.get("supplier_nif"),
                invoice_number=data.get("invoice_number"),
                invoice_date=data.get("invoice_date"),
                invoice_document_id=data.get("invoice_document_id"),
                has_valid_invoice=has_valid_invoice,
                payment_method=payment_method,
                is_tax_deductible=is_tax_deductible,
                payment_status=data.get("payment_status", "pendente"),
                expense_date=expense_date,
                notes=data.get("notes"),
            )
            session.add(expense)
            session.flush()

            # Actualizar totais do milestone (se indicado)
            if expense.milestone_id:
                milestone = session.get(RenovationMilestone, expense.milestone_id)
                if milestone:
                    milestone.spent = (milestone.spent or 0) + expense.amount
                    if milestone.budget and milestone.budget > 0:
                        milestone.variance_pct = round(
                            milestone.spent / milestone.budget * 100, 2
                        )
                    session.flush()

            # Recalcular totais da renovacao
            _recalc_totals(session, renovation_id)

            logger.info(
                f"Despesa {expense.id} adicionada a renovacao {renovation_id}: "
                f"{expense.description} — {expense.amount}EUR"
            )
            return _expense_to_dict(expense)

    def mark_expense_paid(self, expense_id: str) -> Dict[str, Any]:
        """Marca uma despesa como paga."""
        with get_session() as session:
            expense = session.get(RenovationExpense, expense_id)
            if not expense:
                raise ValueError(f"Despesa nao encontrada: {expense_id}")

            expense.payment_status = "pago"
            expense.paid_amount = expense.amount
            expense.paid_date = datetime.now(timezone.utc)

            session.flush()
            logger.info(f"Despesa {expense_id} marcada como paga: {expense.amount}EUR")
            return _expense_to_dict(expense)

    def delete_expense(self, expense_id: str) -> bool:
        """Remove uma despesa e recalcula os totais."""
        with get_session() as session:
            expense = session.get(RenovationExpense, expense_id)
            if not expense:
                return False

            renovation_id = expense.renovation_id
            milestone_id = expense.milestone_id
            amount = expense.amount

            # Reverter total do milestone
            if milestone_id:
                milestone = session.get(RenovationMilestone, milestone_id)
                if milestone:
                    milestone.spent = max(0, (milestone.spent or 0) - amount)
                    if milestone.budget and milestone.budget > 0:
                        milestone.variance_pct = round(
                            milestone.spent / milestone.budget * 100, 2
                        )

            session.delete(expense)
            session.flush()

            # Recalcular totais da renovacao
            _recalc_totals(session, renovation_id)

            logger.info(f"Despesa {expense_id} eliminada da renovacao {renovation_id}")
            return True

    def list_expenses(
        self,
        renovation_id: str,
        milestone_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista despesas de uma renovacao com filtros opcionais."""
        with get_session() as session:
            stmt = (
                select(RenovationExpense)
                .where(RenovationExpense.renovation_id == renovation_id)
            )
            if milestone_id:
                stmt = stmt.where(RenovationExpense.milestone_id == milestone_id)
            if category:
                stmt = stmt.where(RenovationExpense.category == category)

            stmt = stmt.order_by(RenovationExpense.expense_date.desc())
            expenses = session.execute(stmt).scalars().all()
            return [_expense_to_dict(e) for e in expenses]

    def get_expense_summary(self, renovation_id: str) -> Dict[str, Any]:
        """Retorna resumo financeiro completo da renovacao.

        Inclui totais por categoria, por milestone, dedutiveis fiscais e alertas.
        """
        with get_session() as session:
            renovation = session.get(Renovation, renovation_id)
            if not renovation:
                raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

            return self._build_expense_summary(session, renovation_id)

    def _build_expense_summary(
        self, session: Session, renovation_id: str
    ) -> Dict[str, Any]:
        """Helper interno que constroi o resumo de despesas usando sessao existente."""
        renovation = session.get(Renovation, renovation_id)
        if not renovation:
            return {}

        expenses_stmt = select(RenovationExpense).where(
            RenovationExpense.renovation_id == renovation_id
        )
        expenses = session.execute(expenses_stmt).scalars().all()

        total_budget = renovation.current_budget or renovation.initial_budget
        total_spent = sum(e.amount for e in expenses)
        total_pending = sum(
            e.amount for e in expenses if e.payment_status == "pendente"
        )
        variance_pct = (
            round(total_spent / total_budget * 100, 2)
            if total_budget and total_budget > 0
            else 0.0
        )
        budget_remaining = (total_budget or 0) - total_spent

        total_deductible = sum(
            e.amount for e in expenses if e.is_tax_deductible
        )
        total_non_deductible = total_spent - total_deductible

        # Agrupamento por categoria
        by_category: Dict[str, float] = {}
        for e in expenses:
            cat = e.category or "outros"
            by_category[cat] = by_category.get(cat, 0) + e.amount

        # Agrupamento por milestone
        milestones_stmt = select(RenovationMilestone).where(
            RenovationMilestone.renovation_id == renovation_id
        )
        milestones = session.execute(milestones_stmt).scalars().all()
        milestone_names: Dict[str, str] = {m.id: m.name for m in milestones}

        by_milestone: Dict[str, Dict[str, Any]] = {}
        for e in expenses:
            mid = e.milestone_id or "sem_milestone"
            name = milestone_names.get(mid, "Sem milestone") if mid != "sem_milestone" else "Sem milestone"
            if mid not in by_milestone:
                by_milestone[mid] = {"name": name, "total": 0}
            by_milestone[mid]["total"] += e.amount

        # Alertas
        alerts: List[str] = []
        if variance_pct >= 100:
            alerts.append(
                f"Orcamento ultrapassado: {variance_pct:.1f}% do orcamento gasto"
            )
        elif variance_pct >= 80:
            alerts.append(
                f"Atencao: {variance_pct:.1f}% do orcamento ja utilizado"
            )
        if total_pending > 0:
            alerts.append(
                f"{total_pending:.0f}EUR em despesas pendentes de pagamento"
            )
        if total_non_deductible > total_spent * 0.3 and total_spent > 0:
            pct_nd = round(total_non_deductible / total_spent * 100, 1)
            alerts.append(
                f"{pct_nd}% das despesas nao sao dedutiveis fiscalmente"
            )

        return {
            "total_budget": total_budget,
            "total_spent": total_spent,
            "total_pending": total_pending,
            "variance_pct": variance_pct,
            "budget_remaining": budget_remaining,
            "total_deductible": total_deductible,
            "total_non_deductible": total_non_deductible,
            "by_category": by_category,
            "by_milestone": by_milestone,
            "alerts": alerts,
        }

    # --- Fotos ---

    def upload_photo(
        self,
        renovation_id: str,
        file_content: bytes,
        filename: str,
        data: Dict[str, Any],
        storage_base: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Faz upload de uma foto de progresso da obra.

        Usa DocumentStorageService para guardar o ficheiro e cria o registo
        RenovationPhoto associado.
        """
        with get_session() as session:
            renovation = session.get(Renovation, renovation_id)
            if not renovation:
                raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

            storage = DocumentStorageService(session, base_path=storage_base)
            doc = storage.upload_document(
                file_content=file_content,
                filename=filename,
                tenant_id=renovation.tenant_id,
                deal_id=renovation.deal_id,
                document_type="foto_obra",
                title=data.get("caption") or filename,
                uploaded_by=data.get("taken_by", "system"),
            )

            photo = RenovationPhoto(
                id=str(uuid4()),
                renovation_id=renovation_id,
                milestone_id=data.get("milestone_id"),
                document_id=doc["id"],
                photo_type=data.get("photo_type", "progresso"),
                caption=data.get("caption"),
                taken_at=data.get("taken_at") or datetime.now(timezone.utc),
                taken_by=data.get("taken_by"),
                room_area=data.get("room_area"),
                sort_order=data.get("sort_order", 0),
            )
            session.add(photo)
            session.flush()

            logger.info(
                f"Foto '{filename}' adicionada a renovacao {renovation_id} "
                f"(tipo: {photo.photo_type})"
            )
            return _photo_to_dict(photo)

    def list_photos(
        self,
        renovation_id: str,
        photo_type: Optional[str] = None,
        milestone_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista fotos de uma renovacao com filtros opcionais."""
        with get_session() as session:
            stmt = (
                select(RenovationPhoto)
                .where(RenovationPhoto.renovation_id == renovation_id)
            )
            if photo_type:
                stmt = stmt.where(RenovationPhoto.photo_type == photo_type)
            if milestone_id:
                stmt = stmt.where(RenovationPhoto.milestone_id == milestone_id)

            stmt = stmt.order_by(
                RenovationPhoto.sort_order.asc(),
                RenovationPhoto.taken_at.desc().nullslast(),
            )
            photos = session.execute(stmt).scalars().all()
            return [_photo_to_dict(p) for p in photos]

    # --- Alertas ---

    def get_budget_alerts(self, renovation_id: str) -> List[Dict[str, Any]]:
        """Retorna alertas orcamentais da renovacao com severidade.

        Avalia o estado do orcamento, milestones atrasados e despesas pendentes.
        """
        with get_session() as session:
            renovation = session.get(Renovation, renovation_id)
            if not renovation:
                raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

            alerts: List[Dict[str, Any]] = []
            variance_pct = renovation.budget_variance_pct
            current_budget = renovation.current_budget or renovation.initial_budget

            # Alertas de orcamento
            if variance_pct >= 100:
                alerts.append({
                    "severity": "critical",
                    "message": (
                        f"Orcamento ultrapassado: {variance_pct:.1f}% gasto "
                        f"({renovation.total_spent:.0f} / {current_budget:.0f} EUR)"
                    ),
                })
            elif variance_pct >= 90:
                alerts.append({
                    "severity": "high",
                    "message": (
                        f"Orcamento quase esgotado: {variance_pct:.1f}% utilizado"
                    ),
                })
            elif variance_pct >= 80:
                alerts.append({
                    "severity": "medium",
                    "message": (
                        f"80%+ do orcamento consumido: {variance_pct:.1f}%"
                    ),
                })

            # Milestones em atraso (planned_end no passado, nao concluidos)
            now = datetime.now(timezone.utc)
            milestones_stmt = select(RenovationMilestone).where(
                RenovationMilestone.renovation_id == renovation_id,
                RenovationMilestone.status.notin_(["concluido"]),
                RenovationMilestone.planned_end.isnot(None),
            )
            milestones = session.execute(milestones_stmt).scalars().all()
            for m in milestones:
                if m.planned_end:
                    planned_end = m.planned_end.replace(tzinfo=timezone.utc) if m.planned_end.tzinfo is None else m.planned_end
                    if planned_end < now:
                        delay_days = (now - planned_end).days
                        alerts.append({
                            "severity": "high" if delay_days > 14 else "medium",
                            "message": (
                                f"Milestone '{m.name}' em atraso: "
                                f"{delay_days} dia(s) alem do planeado"
                            ),
                        })

            # Despesas pendentes de pagamento
            expenses_stmt = select(RenovationExpense).where(
                RenovationExpense.renovation_id == renovation_id,
                RenovationExpense.payment_status == "pendente",
            )
            pending_expenses = session.execute(expenses_stmt).scalars().all()
            if pending_expenses:
                total_pending = sum(e.amount for e in pending_expenses)
                alerts.append({
                    "severity": "low",
                    "message": (
                        f"{len(pending_expenses)} despesa(s) pendente(s) de pagamento: "
                        f"{total_pending:.0f}EUR"
                    ),
                })

            return alerts

    # --- Conclusao ---

    def complete_renovation(self, renovation_id: str) -> Dict[str, Any]:
        """Conclui uma renovacao e actualiza o custo real no deal."""
        with get_session() as session:
            renovation = session.get(Renovation, renovation_id)
            if not renovation:
                raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

            now = datetime.now(timezone.utc)
            renovation.status = "concluida"
            renovation.actual_end = now
            renovation.progress_pct = 100.0

            # Actualizar custo real da obra no deal
            deal = session.get(Deal, renovation.deal_id)
            if deal:
                deal.actual_renovation_cost = renovation.total_spent

            session.flush()
            logger.info(
                f"Renovacao {renovation_id} concluida. "
                f"Custo total: {renovation.total_spent}EUR"
            )
            return _renovation_to_dict(renovation)

    # --- Estatisticas globais ---

    def get_renovation_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas globais de todas as renovacoes."""
        with get_session() as session:
            all_renovations = session.execute(select(Renovation)).scalars().all()

            active = [
                r for r in all_renovations
                if r.status in ("planeamento", "em_curso")
            ]

            total_budget = sum(
                r.current_budget or r.initial_budget for r in active
            )
            total_spent = sum(r.total_spent for r in active)
            avg_progress = (
                round(
                    sum(r.progress_pct for r in active) / len(active), 1
                )
                if active
                else 0.0
            )

            # Total de despesas dedutiveis (todas as renovacoes activas)
            if active:
                renovation_ids = [r.id for r in active]
                expenses_stmt = select(RenovationExpense).where(
                    RenovationExpense.renovation_id.in_(renovation_ids),
                    RenovationExpense.is_tax_deductible == True,  # noqa: E712
                )
                deductible_expenses = session.execute(expenses_stmt).scalars().all()
                total_deductible = sum(e.amount for e in deductible_expenses)
            else:
                total_deductible = 0.0

            return {
                "active_count": len(active),
                "total_budget": total_budget,
                "total_spent": total_spent,
                "avg_progress_pct": avg_progress,
                "total_deductible": total_deductible,
            }
