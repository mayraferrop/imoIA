"""Servico M6 — Gestao de Obra.

Logica de negocio para gestao de obras/renovacoes, milestones, despesas e fotos
associadas a deals imobiliarios fix and flip.

Persistencia via Supabase REST (sem SQLAlchemy).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

# FIXME(jwt-refactor): migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'
from src.database import supabase_rest as db
from src.modules.m6_renovation.templates import get_milestone_template

# Metodos de pagamento que permitem dedutibilidade fiscal
_TAX_DEDUCTIBLE_PAYMENT_METHODS = ("transferencia", "cartao", "mbway")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _renovation_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um registo de renovations para o formato da API."""
    return {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "deal_id": row.get("deal_id"),
        "initial_budget": row.get("initial_budget"),
        "current_budget": row.get("current_budget"),
        "total_spent": row.get("total_spent"),
        "total_committed": row.get("total_committed"),
        "budget_variance_pct": row.get("budget_variance_pct"),
        "contingency_pct": row.get("contingency_pct"),
        "contingency_amount": row.get("contingency_amount"),
        "planned_start": row.get("planned_start"),
        "actual_start": row.get("actual_start"),
        "planned_end": row.get("planned_end"),
        "estimated_end": row.get("estimated_end"),
        "actual_end": row.get("actual_end"),
        "planned_duration_days": row.get("planned_duration_days"),
        "delay_days": row.get("delay_days"),
        "delay_reason": row.get("delay_reason"),
        "contractor_name": row.get("contractor_name"),
        "contractor_phone": row.get("contractor_phone"),
        "contractor_email": row.get("contractor_email"),
        "contractor_nif": row.get("contractor_nif"),
        "license_type": row.get("license_type"),
        "license_status": row.get("license_status"),
        "license_number": row.get("license_number"),
        "is_aru": row.get("is_aru"),
        "status": row.get("status"),
        "progress_pct": row.get("progress_pct"),
        "scope_description": row.get("scope_description"),
        "notes": row.get("notes"),
        "cashflow_project_id": row.get("cashflow_project_id"),
        "cashflow_project_name": row.get("cashflow_project_name"),
        "last_synced_at": row.get("last_synced_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _milestone_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um registo de renovation_milestones para o formato da API."""
    return {
        "id": row.get("id"),
        "renovation_id": row.get("renovation_id"),
        "name": row.get("name"),
        "category": row.get("category"),
        "description": row.get("description"),
        "sort_order": row.get("sort_order"),
        "budget": row.get("budget"),
        "spent": row.get("spent"),
        "variance_pct": row.get("variance_pct"),
        "planned_start": row.get("planned_start"),
        "planned_end": row.get("planned_end"),
        "actual_start": row.get("actual_start"),
        "actual_end": row.get("actual_end"),
        "duration_days": row.get("duration_days"),
        "status": row.get("status"),
        "completion_pct": row.get("completion_pct"),
        "depends_on_id": row.get("depends_on_id"),
        "supplier_name": row.get("supplier_name"),
        "supplier_phone": row.get("supplier_phone"),
        "supplier_nif": row.get("supplier_nif"),
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _expense_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um registo de renovation_expenses para o formato da API."""
    return {
        "id": row.get("id"),
        "renovation_id": row.get("renovation_id"),
        "milestone_id": row.get("milestone_id"),
        "description": row.get("description"),
        "category": row.get("category"),
        "amount": row.get("amount"),
        "currency": row.get("currency"),
        "supplier_name": row.get("supplier_name"),
        "supplier_nif": row.get("supplier_nif"),
        "invoice_number": row.get("invoice_number"),
        "invoice_date": row.get("invoice_date"),
        "invoice_document_id": row.get("invoice_document_id"),
        "has_valid_invoice": row.get("has_valid_invoice"),
        "payment_method": row.get("payment_method"),
        "is_tax_deductible": row.get("is_tax_deductible"),
        "payment_status": row.get("payment_status"),
        "paid_amount": row.get("paid_amount"),
        "paid_date": row.get("paid_date"),
        "expense_date": row.get("expense_date"),
        "external_id": row.get("external_id"),
        "external_source": row.get("external_source"),
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
    }


def _photo_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um registo de renovation_photos para o formato da API."""
    return {
        "id": row.get("id"),
        "renovation_id": row.get("renovation_id"),
        "milestone_id": row.get("milestone_id"),
        "document_id": row.get("document_id"),
        "photo_type": row.get("photo_type"),
        "caption": row.get("caption"),
        "taken_at": row.get("taken_at"),
        "taken_by": row.get("taken_by"),
        "room_area": row.get("room_area"),
        "sort_order": row.get("sort_order"),
        "created_at": row.get("created_at"),
    }


def _recalc_totals(renovation_id: str) -> None:
    """Recalcula total_spent, budget_variance_pct e progress_pct da renovacao.

    Agrega todas as despesas pagas ou pendentes, recalcula a variacao orcamental
    e actualiza o progresso ponderado com base nos milestones.
    """
    renovation = db.get_by_id("renovations", renovation_id)
    if not renovation:
        return

    # Recalcular total_spent a partir das despesas
    expenses = db.list_rows(
        "renovation_expenses",
        filters=f"renovation_id=eq.{renovation_id}",
    )
    total_spent = sum(e.get("amount", 0) or 0 for e in expenses)

    # Recalcular variacao orcamental
    current_budget = renovation.get("current_budget") or renovation.get("initial_budget")
    if current_budget and current_budget > 0:
        budget_variance_pct = round((total_spent / current_budget) * 100, 2)
    else:
        budget_variance_pct = 0.0

    # Recalcular progress_pct como media ponderada por orcamento dos milestones
    milestones = db.list_rows(
        "renovation_milestones",
        filters=f"renovation_id=eq.{renovation_id}",
    )

    if milestones:
        total_budget_weight = sum(m.get("budget", 0) or 0 for m in milestones)
        if total_budget_weight > 0:
            weighted_sum = sum(
                (m.get("completion_pct", 0) or 0) * (m.get("budget", 0) or 0)
                for m in milestones
            )
            progress_pct = round(weighted_sum / total_budget_weight, 1)
        else:
            # Sem pesos, usar media simples
            progress_pct = round(
                sum(m.get("completion_pct", 0) or 0 for m in milestones) / len(milestones),
                1,
            )
    else:
        progress_pct = 0.0

    db.update("renovations", renovation_id, {
        "total_spent": total_spent,
        "budget_variance_pct": budget_variance_pct,
        "progress_pct": progress_pct,
    })


def _create_milestones_from_template(
    renovation_id: str,
    initial_budget: float,
    property_type: str,
    strategy: Optional[str],
) -> int:
    """Cria milestones a partir do template e resolve dependencias. Retorna contagem."""
    template_items = get_milestone_template(property_type, strategy)

    # Primeira passagem: criar todos os milestones (sem dependencias)
    created_milestones: Dict[str, Dict[str, Any]] = {}
    for idx, tmpl in enumerate(template_items):
        budget_pct = float(tmpl.get("budget_pct", 0))
        milestone_budget = round(initial_budget * budget_pct / 100, 2)

        row = {
            "id": db.new_id(),
            "renovation_id": renovation_id,
            "name": tmpl.get("name", f"Fase {idx + 1}"),
            "category": tmpl.get("category", "geral"),
            "description": tmpl.get("description"),
            "sort_order": tmpl.get("sort_order", idx),
            "budget": milestone_budget,
            "duration_days": tmpl.get("duration_days"),
            "status": "pendente",
            "completion_pct": 0,
        }
        inserted = db.insert("renovation_milestones", row)
        created_milestones[tmpl.get("name", "")] = inserted

    # Segunda passagem: resolver dependencias por nome
    for tmpl in template_items:
        depends_on_name = tmpl.get("depends_on")
        if depends_on_name and depends_on_name in created_milestones:
            current = created_milestones.get(tmpl.get("name", ""))
            dep = created_milestones[depends_on_name]
            if current:
                db.update(
                    "renovation_milestones",
                    current["id"],
                    {"depends_on_id": dep["id"]},
                )

    return len(created_milestones)


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
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        tenant_id = deal["tenant_id"]

        # Verificar se ja existe renovacao para este deal
        existing = db.list_rows(
            "renovations",
            filters=f"deal_id=eq.{deal_id}",
            limit=1,
        )
        if existing:
            raise ValueError(
                f"Renovacao ja existe para o deal {deal_id}: {existing[0]['id']}"
            )

        initial_budget = float(data.get("initial_budget", 50000))
        contingency_pct = float(data.get("contingency_pct", 15))
        contingency_amount = round(initial_budget * contingency_pct / 100, 2)

        row = {
            "id": db.new_id(),
            "tenant_id": tenant_id,
            "deal_id": deal_id,
            "initial_budget": initial_budget,
            "current_budget": initial_budget,
            "total_spent": 0,
            "total_committed": 0,
            "budget_variance_pct": 0,
            "contingency_pct": contingency_pct,
            "contingency_amount": contingency_amount,
            "planned_start": data.get("planned_start"),
            "planned_end": data.get("planned_end"),
            "planned_duration_days": data.get("planned_duration_days"),
            "delay_days": 0,
            "contractor_name": data.get("contractor_name"),
            "contractor_phone": data.get("contractor_phone"),
            "contractor_email": data.get("contractor_email"),
            "contractor_nif": data.get("contractor_nif"),
            "license_type": data.get("license_type", "isento"),
            "license_status": data.get("license_status", "na"),
            "license_number": data.get("license_number"),
            "is_aru": data.get("is_aru", False),
            "status": "planeamento",
            "progress_pct": 0,
            "scope_description": data.get("scope_description"),
            "notes": data.get("notes"),
        }
        renovation = db.insert("renovations", row)

        # Gerar milestones automaticos a partir do template
        milestone_count = 0
        auto_milestones = data.get("auto_milestones", True)
        if auto_milestones:
            prop = (
                db.get_by_id("properties", deal["property_id"])
                if deal.get("property_id")
                else None
            )
            property_type = (prop.get("property_type") if prop else None) or "apartamento"
            strategy = deal.get("investment_strategy")

            milestone_count = _create_milestones_from_template(
                renovation["id"], initial_budget, property_type, strategy
            )

        logger.info(
            f"Renovacao {renovation['id']} criada para deal {deal_id} "
            f"(orcamento: {initial_budget}EUR, {milestone_count} milestones)"
        )

        result = _renovation_to_dict(renovation)
        result["milestone_count"] = milestone_count
        return result

    def create_renovation_in_session(
        self, deal_id: str, deal_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Cria renovacao para um deal (chamado pelo M4 advance_deal).

        Aceita deal_data como dict em vez de objecto ORM.
        Se deal_data nao for fornecido, busca o deal pelo id.
        Usa deal.renovation_budget como orcamento inicial (50000 se None).
        """
        if not deal_data:
            deal_data = db.get_by_id("deals", deal_id)
            if not deal_data:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

        # Verificar se ja existe renovacao para este deal
        existing = db.list_rows(
            "renovations",
            filters=f"deal_id=eq.{deal_id}",
            limit=1,
        )
        if existing:
            logger.warning(
                f"Renovacao ja existe para deal {deal_id}: {existing[0]['id']}"
            )
            return _renovation_to_dict(existing[0])

        initial_budget = float(deal_data.get("renovation_budget") or 50000)
        contingency_pct = 15.0
        contingency_amount = round(initial_budget * contingency_pct / 100, 2)

        row = {
            "id": db.new_id(),
            "tenant_id": deal_data.get("tenant_id"),
            "deal_id": deal_id,
            "initial_budget": initial_budget,
            "current_budget": initial_budget,
            "total_spent": 0,
            "total_committed": 0,
            "budget_variance_pct": 0,
            "contingency_pct": contingency_pct,
            "contingency_amount": contingency_amount,
            "delay_days": 0,
            "is_aru": False,
            "status": "planeamento",
            "progress_pct": 0,
        }
        renovation = db.insert("renovations", row)

        # Milestones automaticos
        prop = (
            db.get_by_id("properties", deal_data["property_id"])
            if deal_data.get("property_id")
            else None
        )
        property_type = (prop.get("property_type") if prop else None) or "apartamento"
        strategy = deal_data.get("investment_strategy")

        milestone_count = _create_milestones_from_template(
            renovation["id"], initial_budget, property_type, strategy
        )

        logger.info(
            f"Renovacao {renovation['id']} criada para deal {deal_id} "
            f"({milestone_count} milestones)"
        )
        result = _renovation_to_dict(renovation)
        result["milestone_count"] = milestone_count
        return result

    def get_renovation(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Retorna renovacao completa com milestones, resumo de despesas e saude orcamental."""
        rows = db.list_rows(
            "renovations",
            filters=f"deal_id=eq.{deal_id}",
            limit=1,
        )
        if not rows:
            return None
        renovation = rows[0]

        # Milestones ordenados
        milestones = db.list_rows(
            "renovation_milestones",
            filters=f"renovation_id=eq.{renovation['id']}",
            order="sort_order.asc",
        )

        # Resumo de despesas
        expense_summary = self._build_expense_summary(renovation["id"])

        # Saude orcamental
        variance_pct = renovation.get("budget_variance_pct", 0) or 0
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
        renovation = db.get_by_id("renovations", renovation_id)
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
        update_data: Dict[str, Any] = {}
        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field]

        # Recalcular contingencia se current_budget alterado
        if "current_budget" in data and data["current_budget"]:
            new_budget = float(data["current_budget"])
            contingency_pct = renovation.get("contingency_pct") or 15.0
            update_data["contingency_amount"] = round(
                new_budget * contingency_pct / 100, 2
            )

        updated = db.update("renovations", renovation_id, update_data)
        logger.info(f"Renovacao {renovation_id} actualizada: {list(data.keys())}")
        return _renovation_to_dict(updated)

    # --- Milestones ---

    def get_milestones(self, renovation_id: str) -> List[Dict[str, Any]]:
        """Lista milestones de uma renovacao ordenados por sort_order."""
        items = db.list_rows(
            "renovation_milestones",
            filters=f"renovation_id=eq.{renovation_id}",
            order="sort_order.asc",
        )
        return [_milestone_to_dict(m) for m in items]

    def add_milestone(
        self, renovation_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adiciona um milestone a uma renovacao."""
        renovation = db.get_by_id("renovations", renovation_id)
        if not renovation:
            raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

        row = {
            "id": db.new_id(),
            "renovation_id": renovation_id,
            "name": data["name"],
            "category": data.get("category", "geral"),
            "description": data.get("description"),
            "sort_order": data.get("sort_order", 999),
            "budget": float(data.get("budget", 0)),
            "planned_start": data.get("planned_start"),
            "planned_end": data.get("planned_end"),
            "duration_days": data.get("duration_days"),
            "depends_on_id": data.get("depends_on_id"),
            "supplier_name": data.get("supplier_name"),
            "supplier_phone": data.get("supplier_phone"),
            "supplier_nif": data.get("supplier_nif"),
            "notes": data.get("notes"),
            "status": "pendente",
            "completion_pct": 0,
        }
        inserted = db.insert("renovation_milestones", row)
        logger.info(
            f"Milestone '{row['name']}' adicionado a renovacao {renovation_id}"
        )
        return _milestone_to_dict(inserted)

    def update_milestone(
        self, milestone_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualiza um milestone.

        Se completion_pct atingir 100, define status='concluido' e actual_end=now.
        Recalcula o progresso global da renovacao.
        """
        milestone = db.get_by_id("renovation_milestones", milestone_id)
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
        update_data: Dict[str, Any] = {}
        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field]

        # Auto-completar se completion_pct = 100
        if data.get("completion_pct") == 100:
            update_data["status"] = "concluido"
            if not milestone.get("actual_end"):
                update_data["actual_end"] = datetime.now(timezone.utc).isoformat()

        updated = db.update("renovation_milestones", milestone_id, update_data)

        # Recalcular progresso da renovacao
        _recalc_totals(milestone["renovation_id"])

        logger.info(f"Milestone {milestone_id} actualizado: {list(data.keys())}")
        return _milestone_to_dict(updated)

    def start_milestone(self, milestone_id: str) -> Dict[str, Any]:
        """Inicia um milestone.

        Verifica se o milestone de dependencia esta concluido antes de arrancar.
        Se for o primeiro milestone iniciado, define actual_start da renovacao.
        """
        milestone = db.get_by_id("renovation_milestones", milestone_id)
        if not milestone:
            raise ValueError(f"Milestone nao encontrado: {milestone_id}")

        # Verificar dependencia
        if milestone.get("depends_on_id"):
            dep = db.get_by_id("renovation_milestones", milestone["depends_on_id"])
            if dep and dep.get("status") != "concluido":
                raise ValueError(
                    f"O milestone '{dep.get('name')}' (dependencia) ainda nao esta concluido"
                )

        now = datetime.now(timezone.utc).isoformat()
        db.update("renovation_milestones", milestone_id, {
            "status": "em_curso",
            "actual_start": now,
        })

        # Se for o primeiro milestone iniciado, actualizar renovacao
        renovation = db.get_by_id("renovations", milestone["renovation_id"])
        if renovation and not renovation.get("actual_start"):
            db.update("renovations", renovation["id"], {
                "actual_start": now,
                "status": "em_curso",
            })

        updated = db.get_by_id("renovation_milestones", milestone_id)
        logger.info(
            f"Milestone '{milestone.get('name')}' iniciado "
            f"(renovacao {milestone['renovation_id']})"
        )
        return _milestone_to_dict(updated)

    def complete_milestone(self, milestone_id: str) -> Dict[str, Any]:
        """Conclui um milestone e recalcula o progresso da renovacao."""
        milestone = db.get_by_id("renovation_milestones", milestone_id)
        if not milestone:
            raise ValueError(f"Milestone nao encontrado: {milestone_id}")

        now = datetime.now(timezone.utc).isoformat()
        updated = db.update("renovation_milestones", milestone_id, {
            "status": "concluido",
            "completion_pct": 100,
            "actual_end": now,
        })

        # Recalcular progresso global
        _recalc_totals(milestone["renovation_id"])

        logger.info(
            f"Milestone '{milestone.get('name')}' concluido "
            f"(renovacao {milestone['renovation_id']})"
        )
        return _milestone_to_dict(updated)

    def delete_milestone(self, milestone_id: str) -> bool:
        """Remove um milestone e recalcula totais da renovacao."""
        milestone = db.get_by_id("renovation_milestones", milestone_id)
        if not milestone:
            raise ValueError(f"Milestone nao encontrado: {milestone_id}")

        reno_id = milestone["renovation_id"]

        # Remover despesas associadas
        db.delete_by_filter(
            "renovation_expenses",
            f"milestone_id=eq.{milestone_id}",
        )

        # Remover fotos associadas
        db.delete_by_filter(
            "renovation_photos",
            f"milestone_id=eq.{milestone_id}",
        )

        # Limpar dependencias que apontam para este milestone
        dependents = db.list_rows(
            "renovation_milestones",
            filters=f"depends_on_id=eq.{milestone_id}",
        )
        for dep in dependents:
            db.update("renovation_milestones", dep["id"], {"depends_on_id": None})

        db.delete_by_id("renovation_milestones", milestone_id)

        _recalc_totals(reno_id)

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
        renovation = db.get_by_id("renovations", renovation_id)
        if not renovation:
            raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

        has_valid_invoice = bool(data.get("has_valid_invoice", False))
        payment_method = data.get("payment_method")
        is_tax_deductible = (
            has_valid_invoice
            and payment_method in _TAX_DEDUCTIBLE_PAYMENT_METHODS
        )

        expense_date = data.get("expense_date") or datetime.now(timezone.utc).isoformat()

        row = {
            "id": db.new_id(),
            "renovation_id": renovation_id,
            "milestone_id": data.get("milestone_id"),
            "description": data["description"],
            "category": data.get("category"),
            "amount": float(data["amount"]),
            "currency": data.get("currency", "EUR"),
            "supplier_name": data.get("supplier_name"),
            "supplier_nif": data.get("supplier_nif"),
            "invoice_number": data.get("invoice_number"),
            "invoice_date": data.get("invoice_date"),
            "invoice_document_id": data.get("invoice_document_id"),
            "has_valid_invoice": has_valid_invoice,
            "payment_method": payment_method,
            "is_tax_deductible": is_tax_deductible,
            "payment_status": data.get("payment_status", "pendente"),
            "expense_date": expense_date,
            "notes": data.get("notes"),
        }
        expense = db.insert("renovation_expenses", row)

        # Actualizar totais do milestone (se indicado)
        milestone_id = data.get("milestone_id")
        if milestone_id:
            milestone = db.get_by_id("renovation_milestones", milestone_id)
            if milestone:
                new_spent = (milestone.get("spent") or 0) + float(data["amount"])
                milestone_update: Dict[str, Any] = {"spent": new_spent}
                budget = milestone.get("budget")
                if budget and budget > 0:
                    milestone_update["variance_pct"] = round(
                        new_spent / budget * 100, 2
                    )
                db.update("renovation_milestones", milestone_id, milestone_update)

        # Recalcular totais da renovacao
        _recalc_totals(renovation_id)

        logger.info(
            f"Despesa {expense['id']} adicionada a renovacao {renovation_id}: "
            f"{expense.get('description')} — {expense.get('amount')}EUR"
        )
        return _expense_to_dict(expense)

    def mark_expense_paid(self, expense_id: str) -> Dict[str, Any]:
        """Marca uma despesa como paga."""
        expense = db.get_by_id("renovation_expenses", expense_id)
        if not expense:
            raise ValueError(f"Despesa nao encontrada: {expense_id}")

        updated = db.update("renovation_expenses", expense_id, {
            "payment_status": "pago",
            "paid_amount": expense.get("amount"),
            "paid_date": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Despesa {expense_id} marcada como paga: {expense.get('amount')}EUR")
        return _expense_to_dict(updated)

    def delete_expense(self, expense_id: str) -> bool:
        """Remove uma despesa e recalcula os totais."""
        expense = db.get_by_id("renovation_expenses", expense_id)
        if not expense:
            return False

        renovation_id = expense["renovation_id"]
        milestone_id = expense.get("milestone_id")
        amount = expense.get("amount", 0) or 0

        # Reverter total do milestone
        if milestone_id:
            milestone = db.get_by_id("renovation_milestones", milestone_id)
            if milestone:
                new_spent = max(0, (milestone.get("spent") or 0) - amount)
                milestone_update: Dict[str, Any] = {"spent": new_spent}
                budget = milestone.get("budget")
                if budget and budget > 0:
                    milestone_update["variance_pct"] = round(
                        new_spent / budget * 100, 2
                    )
                db.update("renovation_milestones", milestone_id, milestone_update)

        db.delete_by_id("renovation_expenses", expense_id)

        # Recalcular totais da renovacao
        _recalc_totals(renovation_id)

        logger.info(f"Despesa {expense_id} eliminada da renovacao {renovation_id}")
        return True

    def list_expenses(
        self,
        renovation_id: str,
        milestone_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista despesas de uma renovacao com filtros opcionais."""
        filters = f"renovation_id=eq.{renovation_id}"
        if milestone_id:
            filters += f"&milestone_id=eq.{milestone_id}"
        if category:
            filters += f"&category=eq.{category}"

        expenses = db.list_rows(
            "renovation_expenses",
            filters=filters,
            order="expense_date.desc",
        )
        return [_expense_to_dict(e) for e in expenses]

    def get_expense_summary(self, renovation_id: str) -> Dict[str, Any]:
        """Retorna resumo financeiro completo da renovacao.

        Inclui totais por categoria, por milestone, dedutiveis fiscais e alertas.
        """
        renovation = db.get_by_id("renovations", renovation_id)
        if not renovation:
            raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

        return self._build_expense_summary(renovation_id)

    def _build_expense_summary(self, renovation_id: str) -> Dict[str, Any]:
        """Helper interno que constroi o resumo de despesas."""
        renovation = db.get_by_id("renovations", renovation_id)
        if not renovation:
            return {}

        expenses = db.list_rows(
            "renovation_expenses",
            filters=f"renovation_id=eq.{renovation_id}",
        )

        total_budget = renovation.get("current_budget") or renovation.get("initial_budget")
        total_spent = sum(e.get("amount", 0) or 0 for e in expenses)
        total_pending = sum(
            e.get("amount", 0) or 0
            for e in expenses
            if e.get("payment_status") == "pendente"
        )
        variance_pct = (
            round(total_spent / total_budget * 100, 2)
            if total_budget and total_budget > 0
            else 0.0
        )
        budget_remaining = (total_budget or 0) - total_spent

        total_deductible = sum(
            e.get("amount", 0) or 0
            for e in expenses
            if e.get("is_tax_deductible")
        )
        total_non_deductible = total_spent - total_deductible

        # Agrupamento por categoria
        by_category: Dict[str, float] = {}
        for e in expenses:
            cat = e.get("category") or "outros"
            by_category[cat] = by_category.get(cat, 0) + (e.get("amount", 0) or 0)

        # Agrupamento por milestone
        milestones = db.list_rows(
            "renovation_milestones",
            filters=f"renovation_id=eq.{renovation_id}",
        )
        milestone_names: Dict[str, str] = {m["id"]: m.get("name", "") for m in milestones}

        by_milestone: Dict[str, Dict[str, Any]] = {}
        for e in expenses:
            mid = e.get("milestone_id") or "sem_milestone"
            name = (
                milestone_names.get(mid, "Sem milestone")
                if mid != "sem_milestone"
                else "Sem milestone"
            )
            if mid not in by_milestone:
                by_milestone[mid] = {"name": name, "total": 0}
            by_milestone[mid]["total"] += e.get("amount", 0) or 0

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
        renovation_photos associado.

        Nota: DocumentStorageService ainda usa sessao SQLAlchemy internamente.
        Quando for migrado, este metodo sera simplificado.
        """
        from src.database.db import get_session
        from src.shared.document_storage import DocumentStorageService

        renovation = db.get_by_id("renovations", renovation_id)
        if not renovation:
            raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

        with get_session() as session:
            storage = DocumentStorageService(session, base_path=storage_base)
            doc = storage.upload_document(
                file_content=file_content,
                filename=filename,
                tenant_id=renovation["tenant_id"],
                deal_id=renovation["deal_id"],
                document_type="foto_obra",
                title=data.get("caption") or filename,
                uploaded_by=data.get("taken_by", "system"),
            )

        photo_row = {
            "id": db.new_id(),
            "renovation_id": renovation_id,
            "milestone_id": data.get("milestone_id"),
            "document_id": doc["id"],
            "photo_type": data.get("photo_type", "progresso"),
            "caption": data.get("caption"),
            "taken_at": data.get("taken_at") or datetime.now(timezone.utc).isoformat(),
            "taken_by": data.get("taken_by"),
            "room_area": data.get("room_area"),
            "sort_order": data.get("sort_order", 0),
        }
        photo = db.insert("renovation_photos", photo_row)

        logger.info(
            f"Foto '{filename}' adicionada a renovacao {renovation_id} "
            f"(tipo: {photo.get('photo_type')})"
        )
        return _photo_to_dict(photo)

    def list_photos(
        self,
        renovation_id: str,
        photo_type: Optional[str] = None,
        milestone_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista fotos de uma renovacao com filtros opcionais."""
        filters = f"renovation_id=eq.{renovation_id}"
        if photo_type:
            filters += f"&photo_type=eq.{photo_type}"
        if milestone_id:
            filters += f"&milestone_id=eq.{milestone_id}"

        photos = db.list_rows(
            "renovation_photos",
            filters=filters,
            order="sort_order.asc,taken_at.desc.nullslast",
        )
        return [_photo_to_dict(p) for p in photos]

    # --- Alertas ---

    def get_budget_alerts(self, renovation_id: str) -> List[Dict[str, Any]]:
        """Retorna alertas orcamentais da renovacao com severidade.

        Avalia o estado do orcamento, milestones atrasados e despesas pendentes.
        """
        renovation = db.get_by_id("renovations", renovation_id)
        if not renovation:
            raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

        alerts: List[Dict[str, Any]] = []
        variance_pct = renovation.get("budget_variance_pct", 0) or 0
        current_budget = renovation.get("current_budget") or renovation.get("initial_budget") or 0
        total_spent = renovation.get("total_spent", 0) or 0

        # Alertas de orcamento
        if variance_pct >= 100:
            alerts.append({
                "severity": "critical",
                "message": (
                    f"Orcamento ultrapassado: {variance_pct:.1f}% gasto "
                    f"({total_spent:.0f} / {current_budget:.0f} EUR)"
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
        milestones = db.list_rows(
            "renovation_milestones",
            filters=(
                f"renovation_id=eq.{renovation_id}"
                f"&status=neq.concluido"
                f"&planned_end=not.is.null"
            ),
        )
        for m in milestones:
            planned_end_str = m.get("planned_end")
            if planned_end_str:
                try:
                    planned_end = datetime.fromisoformat(
                        planned_end_str.replace("Z", "+00:00")
                    )
                    if planned_end.tzinfo is None:
                        planned_end = planned_end.replace(tzinfo=timezone.utc)
                    if planned_end < now:
                        delay_days = (now - planned_end).days
                        alerts.append({
                            "severity": "high" if delay_days > 14 else "medium",
                            "message": (
                                f"Milestone '{m.get('name')}' em atraso: "
                                f"{delay_days} dia(s) alem do planeado"
                            ),
                        })
                except (ValueError, TypeError):
                    pass

        # Despesas pendentes de pagamento
        pending_expenses = db.list_rows(
            "renovation_expenses",
            filters=(
                f"renovation_id=eq.{renovation_id}"
                f"&payment_status=eq.pendente"
            ),
        )
        if pending_expenses:
            total_pending = sum(e.get("amount", 0) or 0 for e in pending_expenses)
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
        renovation = db.get_by_id("renovations", renovation_id)
        if not renovation:
            raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

        now = datetime.now(timezone.utc).isoformat()
        updated = db.update("renovations", renovation_id, {
            "status": "concluida",
            "actual_end": now,
            "progress_pct": 100.0,
        })

        # Actualizar custo real da obra no deal
        deal_id = renovation.get("deal_id")
        if deal_id:
            deal = db.get_by_id("deals", deal_id)
            if deal:
                db.update("deals", deal_id, {
                    "actual_renovation_cost": renovation.get("total_spent"),
                })

        logger.info(
            f"Renovacao {renovation_id} concluida. "
            f"Custo total: {renovation.get('total_spent')}EUR"
        )
        return _renovation_to_dict(updated)

    # --- Estatisticas globais ---

    def get_renovation_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas globais de todas as renovacoes."""
        all_renovations = db.list_rows("renovations")

        active = [
            r for r in all_renovations
            if r.get("status") in ("planeamento", "em_curso")
        ]

        total_budget = sum(
            r.get("current_budget") or r.get("initial_budget") or 0
            for r in active
        )
        total_spent = sum(r.get("total_spent", 0) or 0 for r in active)
        avg_progress = (
            round(
                sum(r.get("progress_pct", 0) or 0 for r in active) / len(active),
                1,
            )
            if active
            else 0.0
        )

        # Total de despesas dedutiveis (todas as renovacoes activas)
        total_deductible = 0.0
        if active:
            renovation_ids = [r["id"] for r in active]
            for rid in renovation_ids:
                deductible = db.list_rows(
                    "renovation_expenses",
                    select="amount",
                    filters=f"renovation_id=eq.{rid}&is_tax_deductible=eq.true",
                )
                total_deductible += sum(
                    e.get("amount", 0) or 0 for e in deductible
                )

        return {
            "active_count": len(active),
            "total_budget": total_budget,
            "total_spent": total_spent,
            "avg_progress_pct": avg_progress,
            "total_deductible": total_deductible,
        }
