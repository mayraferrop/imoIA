"""Servicos M9 — Fecho + P&L.

ClosingService: workflow administrativo de fecho (CPCV -> escritura -> registo).
PnLService: calculo de P&L real vs estimado, portfolio e relatorio fiscal.

Persistencia via Supabase REST (sem SQLAlchemy).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger

# FIXME(jwt-refactor): migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'
from src.database import supabase_rest as db
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


def _closing_to_dict(c: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza dict de ClosingProcess vindo do Supabase."""
    checklist = c.get("checklist")
    return {
        "id": c.get("id"),
        "tenant_id": c.get("tenant_id"),
        "deal_id": c.get("deal_id"),
        "property_id": c.get("property_id"),
        "closing_type": c.get("closing_type"),
        "status": c.get("status"),
        "cpcv_date": c.get("cpcv_date"),
        "deed_scheduled_date": c.get("deed_scheduled_date"),
        "deed_actual_date": c.get("deed_actual_date"),
        "registration_date": c.get("registration_date"),
        "completed_date": c.get("completed_date"),
        "transaction_price": c.get("transaction_price"),
        "deposit_amount": c.get("deposit_amount"),
        "imt_amount": c.get("imt_amount"),
        "imt_guide_issued_at": c.get("imt_guide_issued_at"),
        "imt_guide_expires_at": c.get("imt_guide_expires_at"),
        "imt_paid": c.get("imt_paid"),
        "is_amount": c.get("is_amount"),
        "is_guide_issued_at": c.get("is_guide_issued_at"),
        "is_guide_expires_at": c.get("is_guide_expires_at"),
        "is_paid": c.get("is_paid"),
        "preference_right_notified": c.get("preference_right_notified"),
        "preference_right_date": c.get("preference_right_date"),
        "preference_right_expires": c.get("preference_right_expires"),
        "preference_right_entities": c.get("preference_right_entities"),
        "deed_cost": c.get("deed_cost"),
        "registration_cost": c.get("registration_cost"),
        "lawyer_cost": c.get("lawyer_cost"),
        "commission_cost": c.get("commission_cost"),
        "other_costs": c.get("other_costs"),
        "checklist": checklist,
        "calendar_alerts": c.get("calendar_alerts"),
        "notes": c.get("notes"),
        "checklist_progress": _checklist_progress(checklist),
        "created_at": c.get("created_at"),
        "updated_at": c.get("updated_at"),
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


def _pnl_to_dict(p: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza dict de DealPnL vindo do Supabase."""
    return {
        "id": p.get("id"),
        "tenant_id": p.get("tenant_id"),
        "deal_id": p.get("deal_id"),
        "property_id": p.get("property_id"),
        "status": p.get("status"),
        # Compra
        "purchase_price": p.get("purchase_price"),
        "imt_cost": p.get("imt_cost"),
        "is_cost": p.get("is_cost"),
        "notary_cost": p.get("notary_cost"),
        "lawyer_cost": p.get("lawyer_cost"),
        "purchase_commission": p.get("purchase_commission"),
        "total_acquisition": p.get("total_acquisition"),
        # Financiamento
        "loan_amount": p.get("loan_amount"),
        "interest_rate_pct": p.get("interest_rate_pct"),
        "loan_setup_costs": p.get("loan_setup_costs"),
        "total_interest_paid": p.get("total_interest_paid"),
        "financing_months": p.get("financing_months"),
        # Obra
        "renovation_budget": p.get("renovation_budget"),
        "renovation_actual": p.get("renovation_actual"),
        "renovation_variance": p.get("renovation_variance"),
        "renovation_variance_pct": p.get("renovation_variance_pct"),
        "renovation_deductible": p.get("renovation_deductible"),
        # Holding
        "holding_months": p.get("holding_months"),
        "holding_costs": p.get("holding_costs"),
        # Venda
        "sale_price": p.get("sale_price"),
        "sale_commission": p.get("sale_commission"),
        "sale_costs": p.get("sale_costs"),
        "net_proceeds": p.get("net_proceeds"),
        # P&L
        "total_invested": p.get("total_invested"),
        "gross_profit": p.get("gross_profit"),
        "capital_gain_taxable": p.get("capital_gain_taxable"),
        "capital_gain_tax": p.get("capital_gain_tax"),
        "net_profit": p.get("net_profit"),
        # Metricas
        "roi_simple_pct": p.get("roi_simple_pct"),
        "roi_annualized_pct": p.get("roi_annualized_pct"),
        "moic": p.get("moic"),
        "profit_margin_pct": p.get("profit_margin_pct"),
        # Comparacao M3
        "estimated_roi_pct": p.get("estimated_roi_pct"),
        "estimated_profit": p.get("estimated_profit"),
        "roi_variance_pct": p.get("roi_variance_pct"),
        "profit_variance": p.get("profit_variance"),
        "created_at": p.get("created_at"),
        "updated_at": p.get("updated_at"),
    }


# ===========================================================================
# ClosingService
# ===========================================================================


class ClosingService:
    """Servico de fecho — workflow administrativo CPCV -> escritura -> registo."""

    def create_closing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria processo de fecho com checklist auto-gerada."""
        tenant_id = db.ensure_tenant()

        deal = db.get_by_id("deals", data["deal_id"])
        if not deal:
            raise ValueError(f"Deal nao encontrado: {data['deal_id']}")

        closing_type = data["closing_type"]
        checklist = (
            {k: dict(v) for k, v in CHECKLIST_COMPRA.items()}
            if closing_type == "compra"
            else {k: dict(v) for k, v in CHECKLIST_VENDA.items()}
        )

        closing = db.insert("closing_processes", {
            "id": db.new_id(),
            "tenant_id": tenant_id,
            "deal_id": data["deal_id"],
            "property_id": data.get("property_id", deal.get("property_id")),
            "closing_type": closing_type,
            "status": "pending",
            "transaction_price": data.get("transaction_price"),
            "deposit_amount": data.get("deposit_amount"),
            "cpcv_date": data.get("cpcv_date"),
            "imt_paid": False,
            "is_paid": False,
            "preference_right_notified": False,
            "notes": data.get("notes"),
            "checklist": checklist,
            "calendar_alerts": [],
        })

        logger.info(
            f"Closing criado: {closing['id']} ({closing_type}) "
            f"para deal {data['deal_id']}"
        )
        return _closing_to_dict(closing)

    def get_closing(self, closing_id: str) -> Optional[Dict[str, Any]]:
        """Retorna processo de fecho por ID."""
        closing = db.get_by_id("closing_processes", closing_id)
        if not closing:
            return None
        return _closing_to_dict(closing)

    def list_closings(
        self,
        deal_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista processos de fecho com filtros opcionais."""
        filter_parts = []
        if deal_id:
            filter_parts.append(f"deal_id=eq.{deal_id}")
        if status:
            filter_parts.append(f"status=eq.{status}")
        filters = "&".join(filter_parts)

        closings = db.list_rows(
            "closing_processes",
            filters=filters,
            order="created_at.desc",
            limit=200,
        )
        return [_closing_to_dict(c) for c in closings]

    def update_closing(
        self, closing_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualiza campos do processo de fecho."""
        closing = db.get_by_id("closing_processes", closing_id)
        if not closing:
            raise ValueError(f"Closing nao encontrado: {closing_id}")

        updatable = {
            "transaction_price", "deposit_amount", "cpcv_date",
            "deed_scheduled_date", "deed_cost", "registration_cost",
            "lawyer_cost", "commission_cost", "other_costs", "notes",
        }
        update_data = {}
        for key, value in data.items():
            if key in updatable and value is not None:
                update_data[key] = value

        if update_data:
            closing = db.update("closing_processes", closing_id, update_data)

        return _closing_to_dict(closing)

    def advance_status(
        self, closing_id: str, target_status: str, notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Avanca o status do closing com validacao de transicao."""
        closing = db.get_by_id("closing_processes", closing_id)
        if not closing:
            raise ValueError(f"Closing nao encontrado: {closing_id}")

        current = closing.get("status")
        allowed = CLOSING_TRANSITIONS.get(current, [])

        if target_status not in allowed:
            raise ValueError(
                f"Transicao invalida: {current} -> {target_status}. "
                f"Permitidas: {allowed}"
            )

        now = datetime.utcnow().isoformat()
        update_data: Dict[str, Any] = {"status": target_status}

        # Auto-actions por estado
        if target_status == "imt_paid":
            update_data["imt_paid"] = True
            update_data["is_paid"] = True
        elif target_status == "deed_scheduled":
            if not closing.get("deed_scheduled_date"):
                update_data["deed_scheduled_date"] = now
        elif target_status == "deed_done":
            update_data["deed_actual_date"] = now
        elif target_status == "registered":
            update_data["registration_date"] = now
        elif target_status == "completed":
            update_data["completed_date"] = now

        if notes:
            existing_notes = closing.get("notes") or ""
            update_data["notes"] = (
                f"{existing_notes}\n{notes}" if existing_notes else notes
            )

        closing = db.update("closing_processes", closing_id, update_data)
        logger.info(
            f"Closing {closing_id}: {current} -> {target_status}"
        )
        return _closing_to_dict(closing)

    def issue_tax_guide(
        self, closing_id: str, guide_type: str, amount: float
    ) -> Dict[str, Any]:
        """Emite guia fiscal (IMT ou IS) com validade de 48 horas."""
        closing = db.get_by_id("closing_processes", closing_id)
        if not closing:
            raise ValueError(f"Closing nao encontrado: {closing_id}")

        now = datetime.utcnow()
        expires = now + timedelta(hours=48)

        update_data: Dict[str, Any] = {}
        checklist = dict(closing.get("checklist") or {})

        if guide_type == "imt":
            update_data["imt_amount"] = amount
            update_data["imt_guide_issued_at"] = now.isoformat()
            update_data["imt_guide_expires_at"] = expires.isoformat()
            # Auto-marcar checklist
            if "guia_imt" in checklist:
                checklist["guia_imt"]["done"] = True
        elif guide_type == "is":
            update_data["is_amount"] = amount
            update_data["is_guide_issued_at"] = now.isoformat()
            update_data["is_guide_expires_at"] = expires.isoformat()
            if "guia_is" in checklist:
                checklist["guia_is"]["done"] = True

        update_data["checklist"] = checklist

        # Alerta de calendario (48h)
        alert = {
            "type": f"guia_{guide_type}_expiry",
            "date": expires.isoformat(),
            "description": f"Guia {guide_type.upper()} expira — {amount:.2f} EUR",
        }
        calendar_alerts = list(closing.get("calendar_alerts") or [])
        calendar_alerts.append(alert)
        update_data["calendar_alerts"] = calendar_alerts

        closing = db.update("closing_processes", closing_id, update_data)

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
        closing = db.get_by_id("closing_processes", closing_id)
        if not closing:
            raise ValueError(f"Closing nao encontrado: {closing_id}")

        now = notification_date or datetime.utcnow()
        expires = now + timedelta(days=10)

        update_data: Dict[str, Any] = {
            "preference_right_notified": True,
            "preference_right_date": now.isoformat(),
            "preference_right_expires": expires.isoformat(),
            "preference_right_entities": entities,
        }

        # Auto-marcar checklist
        checklist = dict(closing.get("checklist") or {})
        if "direito_preferencia" in checklist:
            checklist["direito_preferencia"]["done"] = True
            update_data["checklist"] = checklist

        # Alerta de calendario
        alert = {
            "type": "preference_right_expiry",
            "date": expires.isoformat(),
            "description": (
                f"Prazo direito preferencia expira — "
                f"entidades: {', '.join(entities)}"
            ),
        }
        calendar_alerts = list(closing.get("calendar_alerts") or [])
        calendar_alerts.append(alert)
        update_data["calendar_alerts"] = calendar_alerts

        closing = db.update("closing_processes", closing_id, update_data)

        logger.info(
            f"Direito preferencia notificado: {entities}, expira {expires}"
        )
        return _closing_to_dict(closing)

    def update_checklist_item(
        self, closing_id: str, item_key: str, done: bool = True
    ) -> Dict[str, Any]:
        """Marca/desmarca item da checklist."""
        closing = db.get_by_id("closing_processes", closing_id)
        if not closing:
            raise ValueError(f"Closing nao encontrado: {closing_id}")

        checklist = closing.get("checklist") or {}
        if item_key not in checklist:
            raise ValueError(f"Item nao encontrado na checklist: {item_key}")

        checklist[item_key]["done"] = done
        closing = db.update("closing_processes", closing_id, {"checklist": checklist})
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
        tenant_id = db.ensure_tenant()

        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        # Buscar ou criar PnL
        pnl_rows = db.list_rows(
            "deal_pnl",
            filters=f"deal_id=eq.{deal_id}",
            limit=1,
        )

        if pnl_rows:
            pnl = pnl_rows[0]
        else:
            pnl = db.insert("deal_pnl", {
                "id": db.new_id(),
                "tenant_id": tenant_id,
                "deal_id": deal_id,
                "property_id": deal.get("property_id"),
                "status": "in_progress",
            })

        # Valores fornecidos manualmente
        manual_updates: Dict[str, Any] = {}
        if sale_price:
            manual_updates["sale_price"] = sale_price
        if sale_commission:
            manual_updates["sale_commission"] = sale_commission
        if sale_costs:
            manual_updates["sale_costs"] = sale_costs
        if holding_months:
            manual_updates["holding_months"] = holding_months
        if holding_costs:
            manual_updates["holding_costs"] = holding_costs

        if manual_updates:
            pnl.update(manual_updates)

        if auto_pull:
            self._pull_from_closing(deal_id, pnl)
            self._pull_from_m3(deal.get("property_id"), pnl)
            self._pull_from_m6(deal_id, pnl)

        # Recalcular
        self._recalculate(pnl)

        pnl["status"] = "in_progress"

        # Persistir todas as alteracoes
        pnl_id = pnl["id"]
        save_data = {k: v for k, v in pnl.items() if k != "id"}
        pnl = db.update("deal_pnl", pnl_id, save_data)

        roi = pnl.get("roi_annualized_pct") or 0
        logger.info(f"P&L calculado para deal {deal_id}: ROI {roi:.1f}%")
        return _pnl_to_dict(pnl)

    def get_pnl(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Retorna P&L de um deal."""
        rows = db.list_rows(
            "deal_pnl",
            filters=f"deal_id=eq.{deal_id}",
            limit=1,
        )
        if not rows:
            return None
        return _pnl_to_dict(rows[0])

    def update_pnl(self, deal_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza P&L manualmente e recalcula."""
        rows = db.list_rows(
            "deal_pnl",
            filters=f"deal_id=eq.{deal_id}",
            limit=1,
        )
        if not rows:
            raise ValueError(f"P&L nao encontrado para deal: {deal_id}")

        pnl = rows[0]

        updatable = {
            "purchase_price", "sale_price", "sale_commission", "sale_costs",
            "holding_months", "holding_costs", "loan_amount",
            "interest_rate_pct", "loan_setup_costs", "total_interest_paid",
            "financing_months",
        }
        for key, value in data.items():
            if key in updatable and value is not None:
                pnl[key] = value

        self._recalculate(pnl)

        save_data = {k: v for k, v in pnl.items() if k != "id"}
        pnl = db.update("deal_pnl", pnl["id"], save_data)
        return _pnl_to_dict(pnl)

    def finalize_pnl(self, deal_id: str) -> Dict[str, Any]:
        """Marca P&L como final (imutavel)."""
        rows = db.list_rows(
            "deal_pnl",
            filters=f"deal_id=eq.{deal_id}",
            limit=1,
        )
        if not rows:
            raise ValueError(f"P&L nao encontrado para deal: {deal_id}")
        pnl = db.update("deal_pnl", rows[0]["id"], {"status": "final"})
        logger.info(f"P&L finalizado para deal {deal_id}")
        return _pnl_to_dict(pnl)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Resumo agregado de todos os deals com P&L final ou in_progress."""
        pnls = db.list_rows(
            "deal_pnl",
            filters="status=in.(in_progress,final)",
            limit=1000,
        )

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
            prop_id = p.get("property_id")
            prop = db.get_by_id("properties", prop_id) if prop_id else None

            deals_data.append({
                "deal_id": p.get("deal_id"),
                "property_id": prop_id,
                "property_name": (
                    f"{prop.get('property_type', '')} {prop.get('typology', '')} {prop.get('municipality', '')}"
                    .strip() if prop else "N/A"
                ),
                "purchase_price": p.get("purchase_price"),
                "sale_price": p.get("sale_price"),
                "net_profit": p.get("net_profit"),
                "roi_annualized_pct": p.get("roi_annualized_pct"),
                "moic": p.get("moic"),
                "holding_months": p.get("holding_months"),
                "status": p.get("status"),
            })

        total_invested = sum(p.get("total_invested", 0) or 0 for p in pnls)
        total_profit = sum(p.get("net_profit", 0) or 0 for p in pnls)
        total_revenue = sum(p.get("sale_price", 0) or 0 for p in pnls)
        rois = [p.get("roi_annualized_pct") for p in pnls if p.get("roi_annualized_pct")]
        holdings = [p.get("holding_months") for p in pnls if (p.get("holding_months") or 0) > 0]

        best = max(deals_data, key=lambda d: d.get("net_profit") or 0) if deals_data else None
        worst = min(deals_data, key=lambda d: d.get("net_profit") or 0) if deals_data else None

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
        pnls = db.list_rows(
            "deal_pnl",
            filters="status=in.(in_progress,final)",
            limit=1000,
        )

        # Filtrar por ano (via data de criacao)
        year_pnls = []
        for p in pnls:
            created = p.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(
                        created.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    if created_dt.year == year:
                        year_pnls.append(p)
                except (ValueError, TypeError):
                    pass

        deals_fiscal = []
        total_gains = 0.0
        total_deductible = 0.0
        total_tax = 0.0

        for p in year_pnls:
            cgt = p.get("capital_gain_taxable", 0) or 0
            cgx = p.get("capital_gain_tax", 0) or 0
            rd = p.get("renovation_deductible", 0) or 0
            np_ = p.get("net_profit", 0) or 0

            deals_fiscal.append({
                "deal_id": p.get("deal_id"),
                "property_id": p.get("property_id"),
                "capital_gain_taxable": cgt,
                "capital_gain_tax": cgx,
                "renovation_deductible": rd,
                "net_profit": np_,
            })
            total_gains += cgt
            total_deductible += rd
            total_tax += cgx

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
        self, deal_id: str, pnl: Dict[str, Any]
    ) -> None:
        """Puxa dados reais dos processos de fecho."""
        closings = db.list_rows(
            "closing_processes",
            filters=f"deal_id=eq.{deal_id}",
            limit=50,
        )

        for closing in closings:
            if closing.get("closing_type") == "compra":
                if closing.get("transaction_price"):
                    pnl["purchase_price"] = closing["transaction_price"]
                if closing.get("imt_amount"):
                    pnl["imt_cost"] = closing["imt_amount"]
                if closing.get("is_amount"):
                    pnl["is_cost"] = closing["is_amount"]
                if closing.get("deed_cost"):
                    pnl["notary_cost"] = closing["deed_cost"]
                if closing.get("lawyer_cost"):
                    pnl["lawyer_cost"] = closing["lawyer_cost"]
                if closing.get("commission_cost"):
                    pnl["purchase_commission"] = closing["commission_cost"]
            elif closing.get("closing_type") == "venda":
                if closing.get("transaction_price") and not pnl.get("sale_price"):
                    pnl["sale_price"] = closing["transaction_price"]
                if closing.get("commission_cost"):
                    pnl["sale_commission"] = closing["commission_cost"]
                if closing.get("deed_cost"):
                    pnl["sale_costs"] = (pnl.get("sale_costs") or 0) + closing["deed_cost"]

    def _pull_from_m3(
        self, property_id: Optional[str], pnl: Dict[str, Any]
    ) -> None:
        """Puxa estimativas do modelo financeiro M3."""
        if not property_id:
            return

        models = db.list_rows(
            "financial_models",
            filters=f"property_id=eq.{property_id}",
            order="created_at.desc",
            limit=1,
        )

        if not models:
            return

        model = models[0]
        pnl["estimated_roi_pct"] = model.get("roi_pct") or 0
        pnl["estimated_profit"] = model.get("net_profit") or 0

        # Preencher campos se nao tiverem dados do closing
        if not pnl.get("purchase_price") and model.get("purchase_price"):
            pnl["purchase_price"] = model["purchase_price"]
        if not pnl.get("imt_cost") and model.get("imt"):
            pnl["imt_cost"] = model["imt"]
        if not pnl.get("is_cost") and model.get("imposto_selo"):
            pnl["is_cost"] = model["imposto_selo"]
        if not pnl.get("renovation_budget") and model.get("renovation_total"):
            pnl["renovation_budget"] = model["renovation_total"]
        if not pnl.get("loan_amount") and model.get("loan_amount"):
            pnl["loan_amount"] = model["loan_amount"]
        if model.get("holding_months"):
            pnl["holding_months"] = pnl.get("holding_months") or model["holding_months"]

    def _pull_from_m6(
        self, deal_id: str, pnl: Dict[str, Any]
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
                    pnl["renovation_budget"] = initial_budget

                # Custo real: usar expenses se existirem, senao current_budget
                if total_spent > 0:
                    pnl["renovation_actual"] = total_spent
                    pnl["renovation_deductible"] = total_deductible
                elif current_budget > 0:
                    # Sem expenses registadas — usar budget como custo real
                    pnl["renovation_actual"] = current_budget
                    # Assumir 100% dedutivel se nao ha detalhe
                    pnl["renovation_deductible"] = current_budget

                logger.info(
                    f"M6 pull: budget={initial_budget}, "
                    f"actual={pnl.get('renovation_actual')}, "
                    f"deductible={pnl.get('renovation_deductible')}"
                )
        except Exception as e:
            logger.warning(f"Erro ao puxar dados M6: {e}")

    def _recalculate(self, pnl: Dict[str, Any]) -> None:
        """Recalcula todos os campos derivados do P&L."""
        # Helper para evitar None em somas
        def v(x: Any) -> float:
            return float(x) if x is not None else 0.0

        def vi(x: Any) -> int:
            return int(x) if x is not None else 0

        # Total aquisicao
        pnl["total_acquisition"] = (
            v(pnl.get("purchase_price")) + v(pnl.get("imt_cost")) + v(pnl.get("is_cost"))
            + v(pnl.get("notary_cost")) + v(pnl.get("lawyer_cost")) + v(pnl.get("purchase_commission"))
        )

        # Variancia obra
        if v(pnl.get("renovation_budget")) > 0:
            pnl["renovation_variance"] = v(pnl.get("renovation_actual")) - v(pnl.get("renovation_budget"))
            pnl["renovation_variance_pct"] = round(
                pnl["renovation_variance"] / v(pnl.get("renovation_budget")) * 100, 2
            )
        else:
            pnl["renovation_variance"] = 0
            pnl["renovation_variance_pct"] = 0

        # Net proceeds
        pnl["net_proceeds"] = v(pnl.get("sale_price")) - v(pnl.get("sale_commission")) - v(pnl.get("sale_costs"))

        # Custo de obra: usar actual se > 0, senao budget
        renovation_cost = (
            v(pnl.get("renovation_actual")) if v(pnl.get("renovation_actual")) > 0
            else v(pnl.get("renovation_budget"))
        )

        # Total investido (cash out)
        pnl["total_invested"] = (
            v(pnl.get("total_acquisition"))
            + renovation_cost
            + v(pnl.get("loan_setup_costs"))
            + v(pnl.get("total_interest_paid"))
            + v(pnl.get("holding_costs"))
        )

        # Gross profit
        pnl["gross_profit"] = v(pnl.get("net_proceeds")) - v(pnl.get("total_invested"))

        # Mais-valias (PT)
        pnl["capital_gain_taxable"] = max(
            v(pnl.get("sale_price"))
            - v(pnl.get("sale_commission"))
            - v(pnl.get("sale_costs"))
            - v(pnl.get("purchase_price"))
            - v(pnl.get("imt_cost"))
            - v(pnl.get("is_cost"))
            - v(pnl.get("notary_cost"))
            - v(pnl.get("renovation_deductible")),
            0,
        )
        # 50% incluido no IRS, taxa marginal estimada 35%
        marginal_rate = 0.35
        pnl["capital_gain_tax"] = round(
            v(pnl.get("capital_gain_taxable")) * 0.5 * marginal_rate, 2
        )

        # Net profit
        pnl["net_profit"] = round(v(pnl.get("gross_profit")) - v(pnl.get("capital_gain_tax")), 2)

        # Metricas
        if v(pnl.get("total_invested")) > 0:
            pnl["roi_simple_pct"] = round(
                v(pnl.get("net_profit")) / v(pnl.get("total_invested")) * 100, 2
            )

            # CAGR: (1 + net_profit/total_invested)^(12/holding_months) - 1
            months = vi(pnl.get("holding_months")) if vi(pnl.get("holding_months")) > 0 else 12
            ratio = 1 + v(pnl.get("net_profit")) / v(pnl.get("total_invested"))
            if ratio > 0:
                pnl["roi_annualized_pct"] = round(
                    (ratio ** (12 / months) - 1) * 100, 2
                )
            else:
                pnl["roi_annualized_pct"] = round(
                    -(abs(ratio) ** (12 / months) - 1) * 100, 2
                )

            # MOIC = net_proceeds / total_invested
            pnl["moic"] = round(
                v(pnl.get("net_proceeds")) / v(pnl.get("total_invested")), 2
            )
        else:
            pnl["roi_simple_pct"] = 0
            pnl["roi_annualized_pct"] = 0
            pnl["moic"] = 0

        if v(pnl.get("sale_price")) > 0:
            pnl["profit_margin_pct"] = round(
                v(pnl.get("net_profit")) / v(pnl.get("sale_price")) * 100, 2
            )
        else:
            pnl["profit_margin_pct"] = 0

        # Variancia M3
        if v(pnl.get("estimated_roi_pct")):
            pnl["roi_variance_pct"] = round(
                v(pnl.get("roi_annualized_pct")) - v(pnl.get("estimated_roi_pct")), 2
            )
        if v(pnl.get("estimated_profit")):
            pnl["profit_variance"] = round(
                v(pnl.get("net_profit")) - v(pnl.get("estimated_profit")), 2
            )
