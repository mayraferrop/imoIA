"""Servicos M9 — Fecho + P&L.

ClosingService: workflow administrativo de fecho (CPCV → escritura → registo).
PnLService: calculo de P&L real vs estimado, portfolio e relatorio fiscal.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import select, func as sql_func

from src.database.db import get_session
from src.database.models_v2 import (
    ClosingProcess,
    Deal,
    DealPnL,
    FinancialModel,
    Property,
    Tenant,
)
from src.modules.m9_closing.schemas import CLOSING_TRANSITIONS

_DEFAULT_TENANT_SLUG = "default"

# ---------------------------------------------------------------------------
# Checklists padrao por tipo de fecho
# ---------------------------------------------------------------------------

CHECKLIST_COMPRA: Dict[str, Dict[str, Any]] = {
    "cpcv_assinado": {"label": "CPCV assinado", "done": False, "order": 1},
    "sinal_pago": {"label": "Sinal pago", "done": False, "order": 2},
    "aprovacao_bancaria": {"label": "Aprovacao bancaria", "done": False, "order": 3},
    "dd_completa": {"label": "Due diligence completa", "done": False, "order": 4},
    "guia_imt": {"label": "Guia IMT emitida", "done": False, "order": 5},
    "guia_is": {"label": "Guia IS emitida", "done": False, "order": 6},
    "imt_pago": {"label": "IMT pago", "done": False, "order": 7},
    "is_pago": {"label": "IS pago", "done": False, "order": 8},
    "direito_preferencia": {
        "label": "Direito de preferencia notificado",
        "done": False,
        "order": 9,
    },
    "escritura_agendada": {
        "label": "Escritura agendada",
        "done": False,
        "order": 10,
    },
    "escritura_realizada": {
        "label": "Escritura realizada",
        "done": False,
        "order": 11,
    },
    "registo_predial": {"label": "Registo predial", "done": False, "order": 12},
}

CHECKLIST_VENDA: Dict[str, Dict[str, Any]] = {
    "anuncio_publicado": {"label": "Anuncio publicado", "done": False, "order": 1},
    "proposta_aceite": {"label": "Proposta aceite", "done": False, "order": 2},
    "cpcv_venda": {"label": "CPCV venda assinado", "done": False, "order": 3},
    "sinal_recebido": {"label": "Sinal recebido", "done": False, "order": 4},
    "aprovacao_bancaria_comprador": {
        "label": "Aprovacao bancaria do comprador",
        "done": False,
        "order": 5,
    },
    "direito_preferencia": {
        "label": "Direito de preferencia notificado",
        "done": False,
        "order": 6,
    },
    "escritura_agendada": {
        "label": "Escritura agendada",
        "done": False,
        "order": 7,
    },
    "escritura_realizada": {
        "label": "Escritura realizada",
        "done": False,
        "order": 8,
    },
    "pagamento_recebido": {
        "label": "Pagamento recebido",
        "done": False,
        "order": 9,
    },
    "chaves_entregues": {"label": "Chaves entregues", "done": False, "order": 10},
}


def _ensure_default_tenant(session: Any) -> str:
    """Garante que o tenant default existe e retorna o id."""
    tenant = session.execute(
        select(Tenant).where(Tenant.slug == _DEFAULT_TENANT_SLUG)
    ).scalar_one_or_none()

    if tenant is None:
        tenant = Tenant(
            id=str(uuid4()),
            name="Default",
            slug=_DEFAULT_TENANT_SLUG,
            country="PT",
        )
        session.add(tenant)
        session.flush()
        logger.info("Tenant default criado (m9_closing)")

    return tenant.id


def _closing_to_dict(c: ClosingProcess) -> Dict[str, Any]:
    """Converte ClosingProcess ORM para dicionario."""
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "deal_id": c.deal_id,
        "property_id": c.property_id,
        "closing_type": c.closing_type,
        "status": c.status,
        "cpcv_date": c.cpcv_date.isoformat() if c.cpcv_date else None,
        "deed_scheduled_date": (
            c.deed_scheduled_date.isoformat() if c.deed_scheduled_date else None
        ),
        "deed_actual_date": (
            c.deed_actual_date.isoformat() if c.deed_actual_date else None
        ),
        "registration_date": (
            c.registration_date.isoformat() if c.registration_date else None
        ),
        "completed_date": (
            c.completed_date.isoformat() if c.completed_date else None
        ),
        "transaction_price": c.transaction_price,
        "deposit_amount": c.deposit_amount,
        "imt_amount": c.imt_amount,
        "imt_guide_issued_at": (
            c.imt_guide_issued_at.isoformat() if c.imt_guide_issued_at else None
        ),
        "imt_guide_expires_at": (
            c.imt_guide_expires_at.isoformat() if c.imt_guide_expires_at else None
        ),
        "imt_paid": c.imt_paid,
        "is_amount": c.is_amount,
        "is_guide_issued_at": (
            c.is_guide_issued_at.isoformat() if c.is_guide_issued_at else None
        ),
        "is_guide_expires_at": (
            c.is_guide_expires_at.isoformat() if c.is_guide_expires_at else None
        ),
        "is_paid": c.is_paid,
        "preference_right_notified": c.preference_right_notified,
        "preference_right_date": (
            c.preference_right_date.isoformat() if c.preference_right_date else None
        ),
        "preference_right_expires": (
            c.preference_right_expires.isoformat()
            if c.preference_right_expires
            else None
        ),
        "preference_right_entities": c.preference_right_entities,
        "deed_cost": c.deed_cost,
        "registration_cost": c.registration_cost,
        "lawyer_cost": c.lawyer_cost,
        "commission_cost": c.commission_cost,
        "other_costs": c.other_costs,
        "checklist": c.checklist,
        "calendar_alerts": c.calendar_alerts,
        "notes": c.notes,
        "checklist_progress": _checklist_progress(c.checklist),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _checklist_progress(checklist: Optional[Dict]) -> Dict[str, Any]:
    """Calcula progresso da checklist."""
    if not checklist:
        return {"total": 0, "done": 0, "pct": 0}
    total = len(checklist)
    done = sum(1 for item in checklist.values() if isinstance(item, dict) and item.get("done"))
    return {
        "total": total,
        "done": done,
        "pct": round(done / total * 100) if total > 0 else 0,
    }


def _pnl_to_dict(p: DealPnL) -> Dict[str, Any]:
    """Converte DealPnL ORM para dicionario."""
    return {
        "id": p.id,
        "tenant_id": p.tenant_id,
        "deal_id": p.deal_id,
        "property_id": p.property_id,
        "status": p.status,
        # Compra
        "purchase_price": p.purchase_price,
        "imt_cost": p.imt_cost,
        "is_cost": p.is_cost,
        "notary_cost": p.notary_cost,
        "lawyer_cost": p.lawyer_cost,
        "purchase_commission": p.purchase_commission,
        "total_acquisition": p.total_acquisition,
        # Financiamento
        "loan_amount": p.loan_amount,
        "interest_rate_pct": p.interest_rate_pct,
        "loan_setup_costs": p.loan_setup_costs,
        "total_interest_paid": p.total_interest_paid,
        "financing_months": p.financing_months,
        # Obra
        "renovation_budget": p.renovation_budget,
        "renovation_actual": p.renovation_actual,
        "renovation_variance": p.renovation_variance,
        "renovation_variance_pct": p.renovation_variance_pct,
        "renovation_deductible": p.renovation_deductible,
        # Holding
        "holding_months": p.holding_months,
        "holding_costs": p.holding_costs,
        # Venda
        "sale_price": p.sale_price,
        "sale_commission": p.sale_commission,
        "sale_costs": p.sale_costs,
        "net_proceeds": p.net_proceeds,
        # P&L
        "total_invested": p.total_invested,
        "gross_profit": p.gross_profit,
        "capital_gain_taxable": p.capital_gain_taxable,
        "capital_gain_tax": p.capital_gain_tax,
        "net_profit": p.net_profit,
        # Metricas
        "roi_simple_pct": p.roi_simple_pct,
        "roi_annualized_pct": p.roi_annualized_pct,
        "moic": p.moic,
        "profit_margin_pct": p.profit_margin_pct,
        # Comparacao M3
        "estimated_roi_pct": p.estimated_roi_pct,
        "estimated_profit": p.estimated_profit,
        "roi_variance_pct": p.roi_variance_pct,
        "profit_variance": p.profit_variance,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ===========================================================================
# ClosingService
# ===========================================================================


class ClosingService:
    """Servico de fecho — workflow administrativo CPCV → escritura → registo."""

    def create_closing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria processo de fecho com checklist auto-gerada."""
        with get_session() as session:
            tenant_id = _ensure_default_tenant(session)

            deal = session.get(Deal, data["deal_id"])
            if not deal:
                raise ValueError(f"Deal nao encontrado: {data['deal_id']}")

            closing_type = data["closing_type"]
            checklist = (
                {k: dict(v) for k, v in CHECKLIST_COMPRA.items()}
                if closing_type == "compra"
                else {k: dict(v) for k, v in CHECKLIST_VENDA.items()}
            )

            closing = ClosingProcess(
                id=str(uuid4()),
                tenant_id=tenant_id,
                deal_id=data["deal_id"],
                property_id=data.get("property_id", deal.property_id),
                closing_type=closing_type,
                status="pending",
                transaction_price=data.get("transaction_price"),
                deposit_amount=data.get("deposit_amount"),
                cpcv_date=data.get("cpcv_date"),
                notes=data.get("notes"),
                checklist=checklist,
                calendar_alerts=[],
            )
            session.add(closing)
            session.flush()

            logger.info(
                f"Closing criado: {closing.id} ({closing_type}) "
                f"para deal {data['deal_id']}"
            )
            return _closing_to_dict(closing)

    def get_closing(self, closing_id: str) -> Optional[Dict[str, Any]]:
        """Retorna processo de fecho por ID."""
        with get_session() as session:
            closing = session.get(ClosingProcess, closing_id)
            if not closing:
                return None
            return _closing_to_dict(closing)

    def list_closings(
        self,
        deal_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista processos de fecho com filtros opcionais."""
        with get_session() as session:
            query = select(ClosingProcess).order_by(
                ClosingProcess.created_at.desc()
            )
            if deal_id:
                query = query.where(ClosingProcess.deal_id == deal_id)
            if status:
                query = query.where(ClosingProcess.status == status)

            closings = session.execute(query).scalars().all()
            return [_closing_to_dict(c) for c in closings]

    def update_closing(
        self, closing_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualiza campos do processo de fecho."""
        with get_session() as session:
            closing = session.get(ClosingProcess, closing_id)
            if not closing:
                raise ValueError(f"Closing nao encontrado: {closing_id}")

            updatable = {
                "transaction_price", "deposit_amount", "cpcv_date",
                "deed_scheduled_date", "deed_cost", "registration_cost",
                "lawyer_cost", "commission_cost", "other_costs", "notes",
            }
            for key, value in data.items():
                if key in updatable and value is not None:
                    setattr(closing, key, value)

            session.flush()
            return _closing_to_dict(closing)

    def advance_status(
        self, closing_id: str, target_status: str, notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Avanca o status do closing com validacao de transicao."""
        with get_session() as session:
            closing = session.get(ClosingProcess, closing_id)
            if not closing:
                raise ValueError(f"Closing nao encontrado: {closing_id}")

            current = closing.status
            allowed = CLOSING_TRANSITIONS.get(current, [])

            if target_status not in allowed:
                raise ValueError(
                    f"Transicao invalida: {current} -> {target_status}. "
                    f"Permitidas: {allowed}"
                )

            old_status = closing.status
            closing.status = target_status
            now = datetime.utcnow()

            # Auto-actions por estado
            if target_status == "imt_paid":
                closing.imt_paid = True
                closing.is_paid = True
            elif target_status == "deed_scheduled":
                if not closing.deed_scheduled_date:
                    closing.deed_scheduled_date = now
            elif target_status == "deed_done":
                closing.deed_actual_date = now
            elif target_status == "registered":
                closing.registration_date = now
            elif target_status == "completed":
                closing.completed_date = now

            if notes:
                closing.notes = (
                    f"{closing.notes}\n{notes}" if closing.notes else notes
                )

            session.flush()
            logger.info(
                f"Closing {closing_id}: {old_status} -> {target_status}"
            )
            return _closing_to_dict(closing)

    def issue_tax_guide(
        self, closing_id: str, guide_type: str, amount: float
    ) -> Dict[str, Any]:
        """Emite guia fiscal (IMT ou IS) com validade de 48 horas."""
        with get_session() as session:
            closing = session.get(ClosingProcess, closing_id)
            if not closing:
                raise ValueError(f"Closing nao encontrado: {closing_id}")

            now = datetime.utcnow()
            expires = now + timedelta(hours=48)

            if guide_type == "imt":
                closing.imt_amount = amount
                closing.imt_guide_issued_at = now
                closing.imt_guide_expires_at = expires
                # Auto-marcar checklist
                if closing.checklist and "guia_imt" in closing.checklist:
                    closing.checklist["guia_imt"]["done"] = True
            elif guide_type == "is":
                closing.is_amount = amount
                closing.is_guide_issued_at = now
                closing.is_guide_expires_at = expires
                if closing.checklist and "guia_is" in closing.checklist:
                    closing.checklist["guia_is"]["done"] = True

            # Alerta de calendario (48h)
            alert = {
                "type": f"guia_{guide_type}_expiry",
                "date": expires.isoformat(),
                "description": f"Guia {guide_type.upper()} expira — {amount:.2f} EUR",
            }
            if closing.calendar_alerts is None:
                closing.calendar_alerts = []
            closing.calendar_alerts = [*closing.calendar_alerts, alert]

            # Forcar update do JSON (SQLite)
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(closing, "checklist")
            flag_modified(closing, "calendar_alerts")

            session.flush()
            logger.info(
                f"Guia {guide_type.upper()} emitida: {amount:.2f} EUR, "
                f"expira {expires.isoformat()}"
            )
            return _closing_to_dict(closing)

    def notify_preference_right(
        self,
        closing_id: str,
        entities: List[str],
        notification_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Regista notificacao do direito de preferencia (prazo 10 dias)."""
        with get_session() as session:
            closing = session.get(ClosingProcess, closing_id)
            if not closing:
                raise ValueError(f"Closing nao encontrado: {closing_id}")

            now = notification_date or datetime.utcnow()
            expires = now + timedelta(days=10)

            closing.preference_right_notified = True
            closing.preference_right_date = now
            closing.preference_right_expires = expires
            closing.preference_right_entities = entities

            # Auto-marcar checklist
            if closing.checklist and "direito_preferencia" in closing.checklist:
                closing.checklist["direito_preferencia"]["done"] = True
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(closing, "checklist")

            # Alerta de calendario
            alert = {
                "type": "preference_right_expiry",
                "date": expires.isoformat(),
                "description": (
                    f"Prazo direito preferencia expira — "
                    f"entidades: {', '.join(entities)}"
                ),
            }
            if closing.calendar_alerts is None:
                closing.calendar_alerts = []
            closing.calendar_alerts = [*closing.calendar_alerts, alert]
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(closing, "calendar_alerts")

            session.flush()
            logger.info(
                f"Direito preferencia notificado: {entities}, expira {expires}"
            )
            return _closing_to_dict(closing)

    def update_checklist_item(
        self, closing_id: str, item_key: str, done: bool = True
    ) -> Dict[str, Any]:
        """Marca/desmarca item da checklist."""
        with get_session() as session:
            closing = session.get(ClosingProcess, closing_id)
            if not closing:
                raise ValueError(f"Closing nao encontrado: {closing_id}")

            if not closing.checklist or item_key not in closing.checklist:
                raise ValueError(f"Item nao encontrado na checklist: {item_key}")

            closing.checklist[item_key]["done"] = done

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(closing, "checklist")

            session.flush()
            return _closing_to_dict(closing)

    def get_closings_for_deal(self, deal_id: str) -> List[Dict[str, Any]]:
        """Retorna todos os processos de fecho de um deal."""
        return self.list_closings(deal_id=deal_id)


# ===========================================================================
# PnLService
# ===========================================================================


class PnLService:
    """Servico de P&L — calculo real vs estimado, portfolio e fiscal."""

    def calculate_pnl(
        self,
        deal_id: str,
        sale_price: float = 0,
        sale_commission: float = 0,
        sale_costs: float = 0,
        holding_months: int = 0,
        holding_costs: float = 0,
        auto_pull: bool = True,
    ) -> Dict[str, Any]:
        """Calcula P&L real, puxando dados de M3, M6 e closing se auto_pull=True."""
        with get_session() as session:
            tenant_id = _ensure_default_tenant(session)

            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            # Buscar ou criar PnL
            pnl = session.execute(
                select(DealPnL).where(DealPnL.deal_id == deal_id)
            ).scalar_one_or_none()

            if not pnl:
                pnl = DealPnL(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    deal_id=deal_id,
                    property_id=deal.property_id,
                    status="in_progress",
                )
                session.add(pnl)

            # Valores fornecidos manualmente
            if sale_price:
                pnl.sale_price = sale_price
            if sale_commission:
                pnl.sale_commission = sale_commission
            if sale_costs:
                pnl.sale_costs = sale_costs
            if holding_months:
                pnl.holding_months = holding_months
            if holding_costs:
                pnl.holding_costs = holding_costs

            if auto_pull:
                self._pull_from_closing(session, deal_id, pnl)
                self._pull_from_m3(session, deal.property_id, pnl)
                self._pull_from_m6(session, deal_id, pnl)

            # Recalcular
            self._recalculate(pnl)

            pnl.status = "in_progress"
            session.flush()
            logger.info(f"P&L calculado para deal {deal_id}: ROI {pnl.roi_annualized_pct:.1f}%")
            return _pnl_to_dict(pnl)

    def get_pnl(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Retorna P&L de um deal."""
        with get_session() as session:
            pnl = session.execute(
                select(DealPnL).where(DealPnL.deal_id == deal_id)
            ).scalar_one_or_none()
            if not pnl:
                return None
            return _pnl_to_dict(pnl)

    def update_pnl(self, deal_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza P&L manualmente e recalcula."""
        with get_session() as session:
            pnl = session.execute(
                select(DealPnL).where(DealPnL.deal_id == deal_id)
            ).scalar_one_or_none()
            if not pnl:
                raise ValueError(f"P&L nao encontrado para deal: {deal_id}")

            updatable = {
                "purchase_price", "sale_price", "sale_commission", "sale_costs",
                "holding_months", "holding_costs", "loan_amount",
                "interest_rate_pct", "loan_setup_costs", "total_interest_paid",
                "financing_months",
            }
            for key, value in data.items():
                if key in updatable and value is not None:
                    setattr(pnl, key, value)

            self._recalculate(pnl)
            session.flush()
            return _pnl_to_dict(pnl)

    def finalize_pnl(self, deal_id: str) -> Dict[str, Any]:
        """Marca P&L como final (imutavel)."""
        with get_session() as session:
            pnl = session.execute(
                select(DealPnL).where(DealPnL.deal_id == deal_id)
            ).scalar_one_or_none()
            if not pnl:
                raise ValueError(f"P&L nao encontrado para deal: {deal_id}")
            pnl.status = "final"
            session.flush()
            logger.info(f"P&L finalizado para deal {deal_id}")
            return _pnl_to_dict(pnl)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Resumo agregado de todos os deals com P&L final ou in_progress."""
        with get_session() as session:
            pnls = session.execute(
                select(DealPnL).where(
                    DealPnL.status.in_(["in_progress", "final"])
                )
            ).scalars().all()

            if not pnls:
                return {
                    "total_deals": 0,
                    "total_invested": 0,
                    "total_profit": 0,
                    "total_revenue": 0,
                    "avg_roi_pct": 0,
                    "avg_holding_months": 0,
                    "best_deal": None,
                    "worst_deal": None,
                    "deals": [],
                }

            deals_data = []
            for p in pnls:
                prop = session.get(Property, p.property_id)
                deals_data.append({
                    "deal_id": p.deal_id,
                    "property_id": p.property_id,
                    "property_name": (
                        f"{prop.property_type or ''} {prop.typology or ''} {prop.municipality or ''}"
                        .strip() if prop else "N/A"
                    ),
                    "purchase_price": p.purchase_price,
                    "sale_price": p.sale_price,
                    "net_profit": p.net_profit,
                    "roi_annualized_pct": p.roi_annualized_pct,
                    "moic": p.moic,
                    "holding_months": p.holding_months,
                    "status": p.status,
                })

            total_invested = sum(p.total_invested for p in pnls)
            total_profit = sum(p.net_profit for p in pnls)
            total_revenue = sum(p.sale_price for p in pnls)
            rois = [p.roi_annualized_pct for p in pnls if p.roi_annualized_pct]
            holdings = [p.holding_months for p in pnls if p.holding_months > 0]

            best = max(deals_data, key=lambda d: d["net_profit"]) if deals_data else None
            worst = min(deals_data, key=lambda d: d["net_profit"]) if deals_data else None

            return {
                "total_deals": len(pnls),
                "total_invested": round(total_invested, 2),
                "total_profit": round(total_profit, 2),
                "total_revenue": round(total_revenue, 2),
                "avg_roi_pct": round(sum(rois) / len(rois), 2) if rois else 0,
                "avg_holding_months": (
                    round(sum(holdings) / len(holdings), 1) if holdings else 0
                ),
                "best_deal": best,
                "worst_deal": worst,
                "deals": deals_data,
            }

    def generate_fiscal_report(self, year: int) -> Dict[str, Any]:
        """Gera relatorio fiscal anual — mais-valias, dedutiveis, imposto estimado."""
        with get_session() as session:
            pnls = session.execute(
                select(DealPnL).where(
                    DealPnL.status.in_(["in_progress", "final"])
                )
            ).scalars().all()

            # Filtrar por ano (via data de criacao ou closing)
            year_pnls = []
            for p in pnls:
                if p.created_at and p.created_at.year == year:
                    year_pnls.append(p)

            deals_fiscal = []
            total_gains = 0.0
            total_deductible = 0.0
            total_tax = 0.0

            for p in year_pnls:
                deals_fiscal.append({
                    "deal_id": p.deal_id,
                    "property_id": p.property_id,
                    "capital_gain_taxable": p.capital_gain_taxable,
                    "capital_gain_tax": p.capital_gain_tax,
                    "renovation_deductible": p.renovation_deductible,
                    "net_profit": p.net_profit,
                })
                total_gains += p.capital_gain_taxable
                total_deductible += p.renovation_deductible
                total_tax += p.capital_gain_tax

            taxable = total_gains - total_deductible
            # Mais-valias PT: 50% incluido no IRS
            taxable_50pct = taxable * 0.5 if taxable > 0 else 0

            return {
                "year": year,
                "total_capital_gains": round(total_gains, 2),
                "total_deductible_expenses": round(total_deductible, 2),
                "taxable_amount": round(taxable_50pct, 2),
                "estimated_tax": round(total_tax, 2),
                "deals": deals_fiscal,
            }

    # -----------------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------------

    def _pull_from_closing(
        self, session: Any, deal_id: str, pnl: DealPnL
    ) -> None:
        """Puxa dados reais dos processos de fecho."""
        closings = session.execute(
            select(ClosingProcess).where(ClosingProcess.deal_id == deal_id)
        ).scalars().all()

        for closing in closings:
            if closing.closing_type == "compra":
                if closing.transaction_price:
                    pnl.purchase_price = closing.transaction_price
                if closing.imt_amount:
                    pnl.imt_cost = closing.imt_amount
                if closing.is_amount:
                    pnl.is_cost = closing.is_amount
                if closing.deed_cost:
                    pnl.notary_cost = closing.deed_cost
                if closing.lawyer_cost:
                    pnl.lawyer_cost = closing.lawyer_cost
                if closing.commission_cost:
                    pnl.purchase_commission = closing.commission_cost
            elif closing.closing_type == "venda":
                if closing.transaction_price and not pnl.sale_price:
                    pnl.sale_price = closing.transaction_price
                if closing.commission_cost:
                    pnl.sale_commission = closing.commission_cost
                if closing.deed_cost:
                    pnl.sale_costs = (pnl.sale_costs or 0) + closing.deed_cost

    def _pull_from_m3(
        self, session: Any, property_id: str, pnl: DealPnL
    ) -> None:
        """Puxa estimativas do modelo financeiro M3."""
        model = session.execute(
            select(FinancialModel)
            .where(FinancialModel.property_id == property_id)
            .order_by(FinancialModel.created_at.desc())
        ).scalar_one_or_none()

        if model:
            pnl.estimated_roi_pct = model.roi_pct or 0
            pnl.estimated_profit = model.net_profit or 0

            # Preencher campos se nao tiverem dados do closing
            if not pnl.purchase_price and model.purchase_price:
                pnl.purchase_price = model.purchase_price
            if not pnl.imt_cost and model.imt:
                pnl.imt_cost = model.imt
            if not pnl.is_cost and model.imposto_selo:
                pnl.is_cost = model.imposto_selo
            if not pnl.renovation_budget and model.renovation_total:
                pnl.renovation_budget = model.renovation_total
            if not pnl.loan_amount and model.loan_amount:
                pnl.loan_amount = model.loan_amount
            if model.holding_months:
                pnl.holding_months = pnl.holding_months or model.holding_months

    def _pull_from_m6(
        self, session: Any, deal_id: str, pnl: DealPnL
    ) -> None:
        """Puxa dados reais de obra do M6.

        Usa total_spent das expenses se existirem.
        Caso contrario, usa current_budget ou initial_budget como custo real.
        """
        try:
            from src.modules.m6_renovation.service import RenovationService
            reno_service = RenovationService()
            reno_data = reno_service.get_renovation(deal_id)
            if reno_data:
                reno = reno_data.get("renovation", {})
                summary = reno_data.get("expense_summary", {})

                total_spent = summary.get("total_spent", 0)
                total_deductible = summary.get("total_deductible", 0)
                initial_budget = reno.get("initial_budget", 0)
                current_budget = reno.get("current_budget") or initial_budget

                # Budget original
                if initial_budget:
                    pnl.renovation_budget = initial_budget

                # Custo real: usar expenses se existirem, senao current_budget
                if total_spent > 0:
                    pnl.renovation_actual = total_spent
                    pnl.renovation_deductible = total_deductible
                elif current_budget > 0:
                    # Sem expenses registadas — usar budget como custo real
                    pnl.renovation_actual = current_budget
                    # Assumir 100% dedutivel se nao ha detalhe
                    pnl.renovation_deductible = current_budget

                logger.info(
                    f"M6 pull: budget={initial_budget}, "
                    f"actual={pnl.renovation_actual}, "
                    f"deductible={pnl.renovation_deductible}"
                )
        except Exception as e:
            logger.warning(f"Erro ao puxar dados M6: {e}")

    def _recalculate(self, pnl: DealPnL) -> None:
        """Recalcula todos os campos derivados do P&L."""
        # Helper para evitar None em somas
        def v(x: Any) -> float:
            return x if x is not None else 0.0

        def vi(x: Any) -> int:
            return x if x is not None else 0

        # Total aquisicao
        pnl.total_acquisition = (
            v(pnl.purchase_price) + v(pnl.imt_cost) + v(pnl.is_cost)
            + v(pnl.notary_cost) + v(pnl.lawyer_cost) + v(pnl.purchase_commission)
        )

        # Variancia obra
        if v(pnl.renovation_budget) > 0:
            pnl.renovation_variance = v(pnl.renovation_actual) - v(pnl.renovation_budget)
            pnl.renovation_variance_pct = round(
                pnl.renovation_variance / v(pnl.renovation_budget) * 100, 2
            )
        else:
            pnl.renovation_variance = 0
            pnl.renovation_variance_pct = 0

        # Net proceeds
        pnl.net_proceeds = v(pnl.sale_price) - v(pnl.sale_commission) - v(pnl.sale_costs)

        # Custo de obra: usar actual se > 0, senao budget
        renovation_cost = (
            v(pnl.renovation_actual) if v(pnl.renovation_actual) > 0
            else v(pnl.renovation_budget)
        )

        # Total investido (cash out)
        pnl.total_invested = (
            v(pnl.total_acquisition)
            + renovation_cost
            + v(pnl.loan_setup_costs)
            + v(pnl.total_interest_paid)
            + v(pnl.holding_costs)
        )

        # Gross profit
        pnl.gross_profit = v(pnl.net_proceeds) - v(pnl.total_invested)

        # Mais-valias (PT)
        pnl.capital_gain_taxable = max(
            v(pnl.sale_price)
            - v(pnl.sale_commission)
            - v(pnl.sale_costs)
            - v(pnl.purchase_price)
            - v(pnl.imt_cost)
            - v(pnl.is_cost)
            - v(pnl.notary_cost)
            - v(pnl.renovation_deductible),
            0,
        )
        # 50% incluido no IRS, taxa marginal estimada 35%
        marginal_rate = 0.35
        pnl.capital_gain_tax = round(
            v(pnl.capital_gain_taxable) * 0.5 * marginal_rate, 2
        )

        # Net profit
        pnl.net_profit = round(v(pnl.gross_profit) - v(pnl.capital_gain_tax), 2)

        # Metricas
        if v(pnl.total_invested) > 0:
            pnl.roi_simple_pct = round(
                v(pnl.net_profit) / v(pnl.total_invested) * 100, 2
            )

            # CAGR: (1 + net_profit/total_invested)^(12/holding_months) - 1
            months = vi(pnl.holding_months) if vi(pnl.holding_months) > 0 else 12
            ratio = 1 + v(pnl.net_profit) / v(pnl.total_invested)
            if ratio > 0:
                pnl.roi_annualized_pct = round(
                    (ratio ** (12 / months) - 1) * 100, 2
                )
            else:
                pnl.roi_annualized_pct = round(
                    -(abs(ratio) ** (12 / months) - 1) * 100, 2
                )

            # MOIC = net_proceeds / total_invested
            pnl.moic = round(
                v(pnl.net_proceeds) / v(pnl.total_invested), 2
            )
        else:
            pnl.roi_simple_pct = 0
            pnl.roi_annualized_pct = 0
            pnl.moic = 0

        if v(pnl.sale_price) > 0:
            pnl.profit_margin_pct = round(
                v(pnl.net_profit) / v(pnl.sale_price) * 100, 2
            )
        else:
            pnl.profit_margin_pct = 0

        # Variancia M3
        if v(pnl.estimated_roi_pct):
            pnl.roi_variance_pct = round(
                v(pnl.roi_annualized_pct) - v(pnl.estimated_roi_pct), 2
            )
        if v(pnl.estimated_profit):
            pnl.profit_variance = round(
                v(pnl.net_profit) - v(pnl.estimated_profit), 2
            )
