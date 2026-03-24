"""Sincronizacao de despesas com o Cash Flow Pro (Supabase externo).

O ImoIA apenas LE do Cash Flow Pro — nunca escreve.
As despesas sao importadas como RenovationExpense com external_id para evitar duplicados.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.database.db import get_session
from src.database.models_v2 import Renovation, RenovationExpense, RenovationMilestone

# Mapeamento de categorias CFP → M6
_CATEGORY_MAP = {
    "materiais": "material",
    "material": "material",
    "mão de obra": "mao_de_obra",
    "mao de obra": "mao_de_obra",
    "servicos": "mao_de_obra",
    "equipamento": "equipamento",
    "licencas": "licenca",
    "projeto": "projecto",
    "transporte": "transporte",
}

# Mapeamento de metodos de pagamento CFP → M6
_PAYMENT_METHOD_MAP = {
    "transferencia": "transferencia",
    "transfer": "transferencia",
    "bank_transfer": "transferencia",
    "cartao": "cartao",
    "card": "cartao",
    "credit_card": "cartao",
    "debit_card": "cartao",
    "mbway": "mbway",
    "mb_way": "mbway",
    "cheque": "cheque",
    "cash": "numerario",
    "numerario": "numerario",
    "dinheiro": "numerario",
}

# Mapeamento de status CFP → M6
_STATUS_MAP = {
    "confirmado": "pago",
    "confirmed": "pago",
    "pago": "pago",
    "paid": "pago",
    "previsao": "pendente",
    "forecast": "pendente",
    "pendente": "pendente",
    "pending": "pendente",
    "agendado": "pendente",
    "scheduled": "pendente",
}

_DEDUCTIBLE_METHODS = {"transferencia", "cartao", "mbway"}


def _get_supabase_client():
    """Cria cliente Supabase para o Cash Flow Pro."""
    settings = get_settings()
    if not settings.cashflow_supabase_url or not settings.cashflow_supabase_key:
        raise ValueError(
            "CASHFLOW_SUPABASE_URL e CASHFLOW_SUPABASE_KEY nao configurados"
        )
    try:
        from supabase import create_client
    except ImportError:
        raise ValueError(
            "Pacote 'supabase' nao instalado. Instalar com: pip install supabase"
        )
    return create_client(settings.cashflow_supabase_url, settings.cashflow_supabase_key)


def _map_category(main_cat: str, sub_cat: str = "") -> str:
    """Mapeia categorias do CFP para categorias do M6."""
    for key, val in _CATEGORY_MAP.items():
        if key in (main_cat or "").lower() or key in (sub_cat or "").lower():
            return val
    return "outro"


def _map_payment_method(method: str) -> Optional[str]:
    """Mapeia metodo de pagamento do CFP para M6."""
    if not method:
        return None
    return _PAYMENT_METHOD_MAP.get(method.lower().strip(), None)


def _map_status(status: str) -> str:
    """Mapeia status de pagamento do CFP para M6."""
    return _STATUS_MAP.get((status or "").lower().strip(), "pendente")


class CashFlowSyncService:
    """Sincroniza despesas do Cash Flow Pro (Supabase externo) para o M6."""

    def list_cashflow_projects(self) -> List[Dict[str, Any]]:
        """Lista projectos activos do Cash Flow Pro."""
        client = _get_supabase_client()
        result = (
            client.table("projects")
            .select("id, name, status, budget")
            .eq("status", "active")
            .order("name")
            .execute()
        )
        return [
            {
                "id": str(p["id"]),
                "name": p.get("name", ""),
                "status": p.get("status", ""),
                "budget": p.get("budget"),
            }
            for p in (result.data or [])
        ]

    def link_project(
        self,
        renovation_id: str,
        cashflow_project_id: str,
        cashflow_project_name: str,
    ) -> Dict[str, Any]:
        """Liga um projecto do CFP a uma Renovation."""
        with get_session() as session:
            renovation = session.get(Renovation, renovation_id)
            if not renovation:
                raise ValueError(f"Renovacao nao encontrada: {renovation_id}")

            renovation.cashflow_project_id = cashflow_project_id
            renovation.cashflow_project_name = cashflow_project_name
            session.flush()

            logger.info(
                f"Renovacao {renovation_id} ligada ao CFP projecto "
                f"{cashflow_project_name} ({cashflow_project_id})"
            )
            return {
                "renovation_id": renovation_id,
                "cashflow_project_id": cashflow_project_id,
                "cashflow_project_name": cashflow_project_name,
            }

    def sync_expenses(self, renovation_id: str) -> Dict[str, Any]:
        """Puxa despesas do Cash Flow Pro e sincroniza com o M6."""
        with get_session() as session:
            renovation = session.get(Renovation, renovation_id)
            if not renovation:
                raise ValueError(f"Renovacao nao encontrada: {renovation_id}")
            if not renovation.cashflow_project_id:
                raise ValueError(
                    "Renovacao nao esta ligada a um projecto do Cash Flow Pro"
                )

            # Buscar entradas do CFP
            client = _get_supabase_client()
            result = (
                client.table("cash_flow_entries")
                .select("*")
                .eq("project_id", renovation.cashflow_project_id)
                .eq("entry_type", "expense")
                .eq("is_simulation", False)
                .order("entry_date")
                .execute()
            )
            entries = result.data or []

            # Buscar expenses existentes com external_id
            existing_stmt = select(RenovationExpense).where(
                RenovationExpense.renovation_id == renovation_id,
                RenovationExpense.external_source == "cash_flow_pro",
            )
            existing = session.execute(existing_stmt).scalars().all()
            existing_map = {e.external_id: e for e in existing if e.external_id}

            created = 0
            updated = 0
            unchanged = 0
            total_amount = 0.0
            deductible_amount = 0.0

            for entry in entries:
                ext_id = str(entry["id"])
                amount = float(entry.get("amount", 0))
                total_amount += amount

                # Mapear campos
                main_cat = entry.get("main_category", "")
                sub_cat = entry.get("subcategory", "")
                category = _map_category(main_cat, sub_cat)
                pay_method = _map_payment_method(
                    entry.get("payment_method", "")
                )
                has_invoice = bool(entry.get("invoice_number"))
                is_deductible = has_invoice and pay_method in _DEDUCTIBLE_METHODS
                pay_status = _map_status(entry.get("status", "pendente"))

                if is_deductible:
                    deductible_amount += amount

                # Parse datas
                expense_date = entry.get("entry_date") or entry.get("due_date")
                if isinstance(expense_date, str):
                    try:
                        expense_date = datetime.fromisoformat(
                            expense_date.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        expense_date = datetime.now(timezone.utc)

                paid_date = entry.get("payment_date")
                if isinstance(paid_date, str):
                    try:
                        paid_date = datetime.fromisoformat(
                            paid_date.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        paid_date = None

                if ext_id in existing_map:
                    # Actualizar se mudou
                    exp = existing_map[ext_id]
                    changed = False
                    if exp.amount != amount:
                        exp.amount = amount
                        changed = True
                    if exp.payment_status != pay_status:
                        exp.payment_status = pay_status
                        changed = True
                    if pay_status == "pago" and exp.paid_amount != amount:
                        exp.paid_amount = amount
                        exp.paid_date = paid_date
                        changed = True
                    if changed:
                        updated += 1
                    else:
                        unchanged += 1
                else:
                    # Criar nova despesa
                    exp = RenovationExpense(
                        id=str(uuid4()),
                        renovation_id=renovation_id,
                        description=entry.get("description", "Despesa CFP"),
                        amount=amount,
                        expense_date=expense_date,
                        category=category,
                        supplier_name=entry.get("business_partner"),
                        invoice_number=entry.get("invoice_number"),
                        has_valid_invoice=has_invoice,
                        payment_method=pay_method,
                        is_tax_deductible=is_deductible,
                        payment_status=pay_status,
                        paid_amount=amount if pay_status == "pago" else 0,
                        paid_date=paid_date if pay_status == "pago" else None,
                        external_id=ext_id,
                        external_source="cash_flow_pro",
                    )
                    session.add(exp)
                    created += 1

            # Recalcular totais
            all_expenses = session.execute(
                select(RenovationExpense).where(
                    RenovationExpense.renovation_id == renovation_id
                )
            ).scalars().all()
            renovation.total_spent = sum(e.amount for e in all_expenses)
            budget = renovation.current_budget or renovation.initial_budget
            if budget and budget > 0:
                renovation.budget_variance_pct = round(
                    (renovation.total_spent / budget) * 100, 2
                )
            renovation.last_synced_at = datetime.now(timezone.utc)

            session.flush()

            logger.info(
                f"Sync CFP → M6: {created} criadas, {updated} actualizadas, "
                f"{unchanged} sem alteracao (renovacao {renovation_id})"
            )

            return {
                "synced": len(entries),
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
                "total_amount": round(total_amount, 2),
                "deductible_amount": round(deductible_amount, 2),
                "last_synced_at": renovation.last_synced_at.isoformat(),
            }

    def auto_assign_milestones(self, renovation_id: str) -> Dict[str, Any]:
        """Tenta associar despesas sem milestone a milestones por heuristica."""
        with get_session() as session:
            # Despesas sem milestone
            unassigned_stmt = select(RenovationExpense).where(
                RenovationExpense.renovation_id == renovation_id,
                RenovationExpense.milestone_id.is_(None),
            )
            unassigned = session.execute(unassigned_stmt).scalars().all()

            # Milestones disponiveis
            milestones_stmt = select(RenovationMilestone).where(
                RenovationMilestone.renovation_id == renovation_id
            )
            milestones = session.execute(milestones_stmt).scalars().all()

            # Mapa de keywords → milestone
            keyword_map: Dict[str, str] = {}
            for m in milestones:
                name_lower = m.name.lower()
                keyword_map[name_lower] = m.id
                # Extrair keywords do nome
                for word in name_lower.split():
                    if len(word) > 3:
                        keyword_map[word] = m.id

            assigned = 0
            for exp in unassigned:
                desc_lower = (exp.description or "").lower()
                cat = (exp.category or "").lower()
                supplier = (exp.supplier_name or "").lower()
                search_text = f"{desc_lower} {cat} {supplier}"

                best_match = None
                for keyword, milestone_id in keyword_map.items():
                    if keyword in search_text:
                        best_match = milestone_id
                        break

                if best_match:
                    exp.milestone_id = best_match
                    assigned += 1

            # Recalcular spent nos milestones
            for m in milestones:
                m_expenses = session.execute(
                    select(RenovationExpense).where(
                        RenovationExpense.milestone_id == m.id
                    )
                ).scalars().all()
                m.spent = sum(e.amount for e in m_expenses)

            session.flush()

            logger.info(
                f"Auto-assign: {assigned}/{len(unassigned)} despesas "
                f"atribuidas a milestones (renovacao {renovation_id})"
            )
            return {
                "assigned": assigned,
                "unassigned": len(unassigned) - assigned,
            }
