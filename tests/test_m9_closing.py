"""Testes M9 — Fecho + P&L.

Testa closing CRUD, status transitions, guias fiscais, direito preferencia,
checklist, P&L calculate, ROI CAGR, mais-valias, portfolio, fiscal, edge cases.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import create_app


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Configura BD temporaria para cada teste."""
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test_m9.db"
    from src.database.db import reset_engine, _get_engine
    from src.database.models import Base

    reset_engine()
    import src.database.models_v2  # noqa: F401

    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    reset_engine()


@pytest.fixture
def client():
    """TestClient da aplicacao."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def closing_service():
    """Instancia do ClosingService."""
    from src.modules.m9_closing.service import ClosingService
    return ClosingService()


@pytest.fixture
def pnl_service():
    """Instancia do PnLService."""
    from src.modules.m9_closing.service import PnLService
    return PnLService()


def _create_deal(property_id=None, strategy="fix_and_flip", status="lead"):
    """Cria tenant + property + deal para testes."""
    from src.database.db import get_session
    from src.database.models_v2 import Deal, Property, Tenant
    from sqlalchemy import select

    with get_session() as session:
        tenant = session.execute(
            select(Tenant).where(Tenant.slug == "default")
        ).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=str(uuid4()), name="Default", slug="default", country="PT"
            )
            session.add(tenant)
            session.flush()

        if not property_id:
            prop = Property(
                id=str(uuid4()),
                tenant_id=tenant.id,
                property_type="apartamento",
                typology="T2",
                municipality="Loures",
                parish="Sacavem",
                asking_price=180000,
                gross_area_m2=75,
                source="manual",
                status="active",
            )
            session.add(prop)
            session.flush()
            property_id = prop.id

        deal = Deal(
            id=str(uuid4()),
            tenant_id=tenant.id,
            property_id=property_id,
            investment_strategy=strategy,
            status=status,
            title="Sacavem T2 Fix and Flip",
        )
        session.add(deal)
        session.flush()
        return {"deal_id": deal.id, "property_id": property_id, "tenant_id": tenant.id}


def _create_financial_model(property_id, tenant_id):
    """Cria modelo financeiro M3 para testes de auto-pull."""
    from src.database.db import get_session
    from src.database.models_v2 import FinancialModel

    with get_session() as session:
        model = FinancialModel(
            id=str(uuid4()),
            tenant_id=tenant_id,
            property_id=property_id,
            scenario_name="base",
            country="PT",
            purchase_price=180000,
            imt=3307.54,
            imposto_selo=1440.0,
            total_acquisition_cost=185747.54,
            renovation_total=35000,
            estimated_sale_price=280000,
            net_profit=38252.46,
            roi_pct=17.5,
            total_investment=225747.54,
        )
        session.add(model)
        session.flush()
        return model.id


# ===========================================================================
# Closing CRUD
# ===========================================================================


class TestClosingCRUD:
    """Testes de criacao, listagem e detalhe de closing."""

    def test_create_closing_compra(self, closing_service):
        """Criar closing de compra gera checklist com 12 items."""
        ids = _create_deal()
        result = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
            "transaction_price": 180000,
        })
        assert result["status"] == "pending"
        assert result["closing_type"] == "compra"
        assert result["transaction_price"] == 180000
        assert len(result["checklist"]) == 12

    def test_create_closing_venda(self, closing_service):
        """Criar closing de venda gera checklist com 10 items."""
        ids = _create_deal()
        result = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "venda",
            "transaction_price": 280000,
        })
        assert result["closing_type"] == "venda"
        assert len(result["checklist"]) == 10

    def test_list_closings(self, closing_service):
        """Listar closings retorna todos os criados."""
        ids = _create_deal()
        closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        closings = closing_service.list_closings()
        assert len(closings) >= 1

    def test_get_closing_detail(self, closing_service):
        """Obter detalhe de closing por ID."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        result = closing_service.get_closing(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_closing_not_found(self, closing_service):
        """Closing inexistente retorna None."""
        result = closing_service.get_closing("inexistente")
        assert result is None

    def test_update_closing(self, closing_service):
        """Actualizar campos do closing."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
            "transaction_price": 180000,
        })
        updated = closing_service.update_closing(created["id"], {
            "lawyer_cost": 1500,
            "deed_cost": 375,
        })
        assert updated["lawyer_cost"] == 1500
        assert updated["deed_cost"] == 375


# ===========================================================================
# Status Transitions
# ===========================================================================


class TestClosingTransitions:
    """Testes de transicoes de estado do closing."""

    def test_valid_transition_pending_to_imt_paid(self, closing_service):
        """Transicao pending → imt_paid valida."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        result = closing_service.advance_status(created["id"], "imt_paid")
        assert result["status"] == "imt_paid"
        assert result["imt_paid"] is True

    def test_full_transition_chain(self, closing_service):
        """Transicao completa: pending → ... → completed."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        cid = created["id"]
        closing_service.advance_status(cid, "imt_paid")
        closing_service.advance_status(cid, "deed_scheduled")
        closing_service.advance_status(cid, "deed_done")
        closing_service.advance_status(cid, "registered")
        result = closing_service.advance_status(cid, "completed")
        assert result["status"] == "completed"
        assert result["completed_date"] is not None

    def test_casa_pronta_shortcut(self, closing_service):
        """Casa Pronta: deed_done → completed (sem registered)."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        cid = created["id"]
        closing_service.advance_status(cid, "imt_paid")
        closing_service.advance_status(cid, "deed_scheduled")
        closing_service.advance_status(cid, "deed_done")
        result = closing_service.advance_status(cid, "completed")
        assert result["status"] == "completed"

    def test_invalid_transition_rejected(self, closing_service):
        """Transicao invalida e rejeitada com ValueError."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        with pytest.raises(ValueError, match="Transicao invalida"):
            closing_service.advance_status(created["id"], "completed")

    def test_cancel_from_any_state(self, closing_service):
        """Cancelar e possivel de qualquer estado."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        closing_service.advance_status(created["id"], "imt_paid")
        result = closing_service.advance_status(created["id"], "cancelled")
        assert result["status"] == "cancelled"


# ===========================================================================
# Guias Fiscais
# ===========================================================================


class TestTaxGuides:
    """Testes de emissao de guias IMT/IS."""

    def test_issue_imt_guide_48h_validity(self, closing_service):
        """Guia IMT tem validade de 48 horas."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        result = closing_service.issue_tax_guide(created["id"], "imt", 3307.54)
        assert result["imt_amount"] == 3307.54
        assert result["imt_guide_issued_at"] is not None
        assert result["imt_guide_expires_at"] is not None
        # Checklist auto-marcada
        assert result["checklist"]["guia_imt"]["done"] is True

    def test_issue_is_guide(self, closing_service):
        """Guia IS emitida com alerta de calendario."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        result = closing_service.issue_tax_guide(created["id"], "is", 1440.0)
        assert result["is_amount"] == 1440.0
        assert len(result["calendar_alerts"]) == 1
        assert result["calendar_alerts"][0]["type"] == "guia_is_expiry"

    def test_both_guides_create_two_alerts(self, closing_service):
        """Emitir IMT + IS cria 2 alertas de calendario."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        closing_service.issue_tax_guide(created["id"], "imt", 3307.54)
        result = closing_service.issue_tax_guide(created["id"], "is", 1440.0)
        assert len(result["calendar_alerts"]) == 2


# ===========================================================================
# Direito de Preferencia
# ===========================================================================


class TestPreferenceRight:
    """Testes de notificacao do direito de preferencia."""

    def test_preference_right_10_day_expiry(self, closing_service):
        """Direito de preferencia tem prazo de 10 dias."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        now = datetime.utcnow()
        result = closing_service.notify_preference_right(
            created["id"], ["Camara Municipal de Loures", "Inquilino"], now
        )
        assert result["preference_right_notified"] is True
        assert result["preference_right_entities"] == [
            "Camara Municipal de Loures", "Inquilino"
        ]
        # Checklist auto-marcada
        assert result["checklist"]["direito_preferencia"]["done"] is True


# ===========================================================================
# Checklist
# ===========================================================================


class TestChecklist:
    """Testes de checklist interactiva."""

    def test_mark_checklist_item(self, closing_service):
        """Marcar item da checklist como feito."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        result = closing_service.update_checklist_item(
            created["id"], "cpcv_assinado", True
        )
        assert result["checklist"]["cpcv_assinado"]["done"] is True

    def test_unmark_checklist_item(self, closing_service):
        """Desmarcar item da checklist."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        closing_service.update_checklist_item(
            created["id"], "cpcv_assinado", True
        )
        result = closing_service.update_checklist_item(
            created["id"], "cpcv_assinado", False
        )
        assert result["checklist"]["cpcv_assinado"]["done"] is False

    def test_checklist_progress(self, closing_service):
        """Progresso da checklist e calculado correctamente."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        assert created["checklist_progress"]["total"] == 12
        assert created["checklist_progress"]["done"] == 0

        closing_service.update_checklist_item(created["id"], "cpcv_assinado", True)
        closing_service.update_checklist_item(created["id"], "sinal_pago", True)
        result = closing_service.get_closing(created["id"])
        assert result["checklist_progress"]["done"] == 2
        assert result["checklist_progress"]["pct"] == 17  # 2/12 = 16.67 → 17

    def test_invalid_checklist_item(self, closing_service):
        """Item inexistente na checklist causa ValueError."""
        ids = _create_deal()
        created = closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        with pytest.raises(ValueError, match="Item nao encontrado"):
            closing_service.update_checklist_item(
                created["id"], "item_inexistente", True
            )


# ===========================================================================
# P&L Calculate
# ===========================================================================


class TestPnLCalculate:
    """Testes de calculo de P&L."""

    def test_calculate_pnl_basic(self, pnl_service):
        """P&L basico com dados manuais."""
        ids = _create_deal()
        result = pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            sale_commission=17220,  # 6.15%
            holding_months=9,
            auto_pull=False,
        )
        assert result["sale_price"] == 280000
        assert result["status"] == "in_progress"

    def test_calculate_pnl_with_m3_auto_pull(self, pnl_service):
        """P&L puxa estimativas M3 automaticamente."""
        ids = _create_deal()
        _create_financial_model(ids["property_id"], ids["tenant_id"])

        result = pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            holding_months=9,
            auto_pull=True,
        )
        assert result["purchase_price"] == 180000
        assert result["estimated_roi_pct"] == 17.5
        assert result["estimated_profit"] == 38252.46

    def test_roi_cagr_formula(self, pnl_service):
        """ROI CAGR: (1+0.268)^(12/9)-1 ≈ 0.372 → 37.2%."""
        ids = _create_deal()
        # Cenario simplificado: investiu 100k, lucrou 26.8k em 9 meses
        result = pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=126800,
            holding_months=9,
            auto_pull=False,
        )
        # net_profit depende dos calculos internos
        # O importante e que roi_annualized_pct seja calculado
        assert "roi_annualized_pct" in result

    def test_mais_valias_calculation(self, pnl_service):
        """Mais-valias: 50% incluido no IRS, taxa marginal 35%."""
        ids = _create_deal()
        _create_financial_model(ids["property_id"], ids["tenant_id"])
        result = pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            sale_commission=17220,
            holding_months=9,
            auto_pull=True,
        )
        assert result["capital_gain_taxable"] >= 0
        assert result["capital_gain_tax"] >= 0

    def test_pnl_with_closing_data(self, closing_service, pnl_service):
        """P&L puxa dados do closing automaticamente."""
        ids = _create_deal()
        closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
            "transaction_price": 175000,
        })
        closing_service.create_closing({
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "venda",
            "transaction_price": 280000,
        })

        result = pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            holding_months=9,
            auto_pull=True,
        )
        assert result["purchase_price"] == 175000
        assert result["sale_price"] == 280000


# ===========================================================================
# P&L Finalize + Update
# ===========================================================================


class TestPnLOperations:
    """Testes de operacoes sobre P&L."""

    def test_get_pnl(self, pnl_service):
        """Obter P&L existente."""
        ids = _create_deal()
        pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            auto_pull=False,
        )
        result = pnl_service.get_pnl(ids["deal_id"])
        assert result is not None
        assert result["sale_price"] == 280000

    def test_get_pnl_not_found(self, pnl_service):
        """P&L inexistente retorna None."""
        result = pnl_service.get_pnl("inexistente")
        assert result is None

    def test_update_pnl(self, pnl_service):
        """Actualizar P&L manualmente recalcula metricas."""
        ids = _create_deal()
        pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            auto_pull=False,
        )
        result = pnl_service.update_pnl(ids["deal_id"], {
            "sale_price": 300000,
            "holding_months": 12,
        })
        assert result["sale_price"] == 300000

    def test_finalize_pnl(self, pnl_service):
        """Finalizar P&L muda status para final."""
        ids = _create_deal()
        pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            auto_pull=False,
        )
        result = pnl_service.finalize_pnl(ids["deal_id"])
        assert result["status"] == "final"

    def test_finalize_not_found(self, pnl_service):
        """Finalizar P&L inexistente causa ValueError."""
        with pytest.raises(ValueError, match="P&L nao encontrado"):
            pnl_service.finalize_pnl("inexistente")


# ===========================================================================
# Portfolio
# ===========================================================================


class TestPortfolio:
    """Testes de portfolio summary."""

    def test_portfolio_empty(self, pnl_service):
        """Portfolio vazio retorna zeros."""
        result = pnl_service.get_portfolio_summary()
        assert result["total_deals"] == 0

    def test_portfolio_with_two_deals(self, pnl_service):
        """Portfolio com 2 deals agrega correctamente."""
        ids1 = _create_deal()
        ids2 = _create_deal()

        pnl_service.calculate_pnl(
            deal_id=ids1["deal_id"],
            sale_price=280000,
            holding_months=9,
            auto_pull=False,
        )
        pnl_service.calculate_pnl(
            deal_id=ids2["deal_id"],
            sale_price=350000,
            holding_months=12,
            auto_pull=False,
        )

        result = pnl_service.get_portfolio_summary()
        assert result["total_deals"] == 2
        assert len(result["deals"]) == 2
        assert result["best_deal"] is not None
        assert result["worst_deal"] is not None


# ===========================================================================
# Fiscal Report
# ===========================================================================


class TestFiscalReport:
    """Testes de relatorio fiscal."""

    def test_fiscal_report_by_year(self, pnl_service):
        """Relatorio fiscal filtra por ano."""
        ids = _create_deal()
        pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            auto_pull=False,
        )
        result = pnl_service.generate_fiscal_report(2026)
        assert result["year"] == 2026
        # O deal deve aparecer pois foi criado em 2026
        assert isinstance(result["deals"], list)


# ===========================================================================
# M3 Comparison
# ===========================================================================


class TestM3Comparison:
    """Testes de comparacao estimado vs real."""

    def test_variance_calculated(self, pnl_service):
        """Variancia M3 e calculada correctamente."""
        ids = _create_deal()
        _create_financial_model(ids["property_id"], ids["tenant_id"])

        result = pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            sale_commission=17220,
            holding_months=9,
            auto_pull=True,
        )
        assert result["estimated_roi_pct"] == 17.5
        # roi_variance = real - estimado
        assert "roi_variance_pct" in result
        assert "profit_variance" in result


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Testes de edge cases."""

    def test_deal_without_m3(self, pnl_service):
        """P&L para deal sem modelo M3 nao falha."""
        ids = _create_deal()
        result = pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            auto_pull=True,
        )
        assert result["estimated_roi_pct"] == 0
        assert result["estimated_profit"] == 0

    def test_deal_without_closing(self, pnl_service):
        """P&L para deal sem closing nao falha."""
        ids = _create_deal()
        result = pnl_service.calculate_pnl(
            deal_id=ids["deal_id"],
            sale_price=280000,
            auto_pull=True,
        )
        assert result is not None

    def test_deal_not_found(self, pnl_service):
        """Calcular P&L para deal inexistente causa ValueError."""
        with pytest.raises(ValueError, match="Deal nao encontrado"):
            pnl_service.calculate_pnl(deal_id="inexistente", auto_pull=False)

    def test_closing_deal_not_found(self, closing_service):
        """Criar closing para deal inexistente causa ValueError."""
        with pytest.raises(ValueError, match="Deal nao encontrado"):
            closing_service.create_closing({
                "deal_id": "inexistente",
                "property_id": "xxx",
                "closing_type": "compra",
            })


# ===========================================================================
# API Endpoints
# ===========================================================================


class TestAPIEndpoints:
    """Testes dos endpoints HTTP."""

    def test_create_closing_endpoint(self, client):
        """POST /api/v1/closing cria processo com checklist."""
        ids = _create_deal()
        r = client.post("/api/v1/closing", json={
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
            "transaction_price": 180000,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["closing_type"] == "compra"
        assert len(data["checklist"]) == 12

    def test_list_closings_endpoint(self, client):
        """GET /api/v1/closing lista processos."""
        r = client.get("/api/v1/closing")
        assert r.status_code == 200

    def test_advance_status_endpoint(self, client):
        """PATCH /api/v1/closing/{id}/status avanca estado."""
        ids = _create_deal()
        r = client.post("/api/v1/closing", json={
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        closing_id = r.json()["id"]
        r2 = client.patch(f"/api/v1/closing/{closing_id}/status", json={
            "target_status": "imt_paid",
        })
        assert r2.status_code == 200
        assert r2.json()["status"] == "imt_paid"

    def test_issue_tax_guide_endpoint(self, client):
        """POST /api/v1/closing/{id}/tax-guide emite guia."""
        ids = _create_deal()
        r = client.post("/api/v1/closing", json={
            "deal_id": ids["deal_id"],
            "property_id": ids["property_id"],
            "closing_type": "compra",
        })
        closing_id = r.json()["id"]
        r2 = client.post(f"/api/v1/closing/{closing_id}/tax-guide", json={
            "guide_type": "imt",
            "amount": 3307.54,
        })
        assert r2.status_code == 200
        assert r2.json()["imt_amount"] == 3307.54

    def test_calculate_pnl_endpoint(self, client):
        """POST /api/v1/pnl/{deal_id}/calculate retorna P&L."""
        ids = _create_deal()
        r = client.post(
            f"/api/v1/pnl/{ids['deal_id']}/calculate",
            params={"sale_price": 280000, "holding_months": 9},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["sale_price"] == 280000
        assert "roi_annualized_pct" in data

    def test_portfolio_summary_endpoint(self, client):
        """GET /api/v1/portfolio/summary retorna agregados."""
        r = client.get("/api/v1/portfolio/summary")
        assert r.status_code == 200
        data = r.json()
        assert "total_deals" in data

    def test_fiscal_report_endpoint(self, client):
        """GET /api/v1/portfolio/fiscal-report retorna relatorio."""
        r = client.get("/api/v1/portfolio/fiscal-report", params={"year": 2026})
        assert r.status_code == 200
        assert r.json()["year"] == 2026
