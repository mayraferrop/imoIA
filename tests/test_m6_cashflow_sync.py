"""Testes M6 — Cash Flow Pro Sync.

Testa mapeamentos, criacao de despesas, dedup, e auto-assign.
Usa mock do Supabase client para nao depender do servico externo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.m6_renovation.cashflow_sync import (
    CashFlowSyncService,
    _map_category,
    _map_payment_method,
    _map_status,
)


# ---------------------------------------------------------------------------
# Mapeamentos
# ---------------------------------------------------------------------------


class TestMappings:
    def test_category_material(self) -> None:
        assert _map_category("Materiais", "") == "material"
        assert _map_category("", "material de construcao") == "material"

    def test_category_mao_de_obra(self) -> None:
        assert _map_category("Mão de obra", "") == "mao_de_obra"
        assert _map_category("Servicos", "") == "mao_de_obra"

    def test_category_unknown(self) -> None:
        assert _map_category("random", "stuff") == "outro"

    def test_payment_transfer(self) -> None:
        assert _map_payment_method("transferencia") == "transferencia"
        assert _map_payment_method("bank_transfer") == "transferencia"

    def test_payment_card(self) -> None:
        assert _map_payment_method("cartao") == "cartao"
        assert _map_payment_method("credit_card") == "cartao"

    def test_payment_cash(self) -> None:
        assert _map_payment_method("cash") == "numerario"
        assert _map_payment_method("numerario") == "numerario"

    def test_payment_none(self) -> None:
        assert _map_payment_method("") is None
        assert _map_payment_method(None) is None

    def test_status_confirmed(self) -> None:
        assert _map_status("confirmado") == "pago"
        assert _map_status("confirmed") == "pago"

    def test_status_pending(self) -> None:
        assert _map_status("pendente") == "pendente"
        assert _map_status("previsao") == "pendente"
        assert _map_status("agendado") == "pendente"


# ---------------------------------------------------------------------------
# Sync service
# ---------------------------------------------------------------------------


class TestCashFlowSync:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        import os
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
        os.environ["CASHFLOW_SUPABASE_URL"] = "https://fake.supabase.co"
        os.environ["CASHFLOW_SUPABASE_KEY"] = "fake_key"
        from src.database.db import reset_engine, _get_engine
        from src.database.models import Base
        reset_engine()
        import src.database.models_v2  # noqa: F401
        engine = _get_engine()
        Base.metadata.create_all(bind=engine)

        self.m4_service = __import__(
            "src.modules.m4_deal_pipeline.service",
            fromlist=["DealPipelineService"],
        ).DealPipelineService()
        self.reno_service = __import__(
            "src.modules.m6_renovation.service",
            fromlist=["RenovationService"],
        ).RenovationService()
        self.sync_service = CashFlowSyncService()
        yield
        from src.database.db import reset_engine as re
        re()

    def _create_deal_with_reno(self):
        from src.database.db import get_session
        from src.database.models_v2 import Property, Tenant
        from sqlalchemy import select
        with get_session() as session:
            tenant = session.execute(
                select(Tenant).where(Tenant.slug == "default")
            ).scalar_one_or_none()
            if not tenant:
                tenant = Tenant(id=str(uuid4()), name="Test", slug="default", country="PT")
                session.add(tenant)
                session.flush()
            prop = Property(
                id=str(uuid4()), tenant_id=tenant.id, source="test",
                country="PT", municipality="Lisboa",
                property_type="apartamento", asking_price=200000, status="lead",
            )
            session.add(prop)
            session.flush()
            prop_id = prop.id

        deal = self.m4_service.create_deal({
            "property_id": prop_id,
            "investment_strategy": "fix_and_flip",
            "title": "Test CFP Sync",
            "purchase_price": 200000,
            "renovation_budget": 98400,
        })
        reno = self.reno_service.create_renovation(deal["id"], {
            "initial_budget": 98400,
            "auto_milestones": True,
        })
        return deal, reno

    def _mock_cfp_entries(self, n=3):
        entries = []
        for i in range(n):
            entries.append({
                "id": str(uuid4()),
                "project_id": "proj-123",
                "entry_type": "expense",
                "is_simulation": False,
                "description": f"Despesa teste {i+1}",
                "amount": 1000.0 * (i + 1),
                "entry_date": "2026-03-15T00:00:00",
                "main_category": "Materiais" if i % 2 == 0 else "Mão de obra",
                "subcategory": "",
                "business_partner": f"Fornecedor {i+1}",
                "payment_method": "transferencia" if i < 2 else "cash",
                "invoice_number": f"FT-{i+1}" if i < 2 else None,
                "status": "confirmado" if i == 0 else "pendente",
                "payment_date": "2026-03-16T00:00:00" if i == 0 else None,
            })
        return entries

    def test_link_project(self) -> None:
        _, reno = self._create_deal_with_reno()
        result = self.sync_service.link_project(
            reno["id"], "proj-123", "Sacavem T3"
        )
        assert result["cashflow_project_id"] == "proj-123"
        assert result["cashflow_project_name"] == "Sacavem T3"

    @patch("src.modules.m6_renovation.cashflow_sync._get_supabase_client")
    def test_sync_creates_new_expenses(self, mock_client_fn) -> None:
        _, reno = self._create_deal_with_reno()
        self.sync_service.link_project(reno["id"], "proj-123", "Test")

        entries = self._mock_cfp_entries(3)
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=entries)
        mock_client_fn.return_value = mock_client

        result = self.sync_service.sync_expenses(reno["id"])
        assert result["synced"] == 3
        assert result["created"] == 3
        assert result["updated"] == 0
        assert result["total_amount"] == 6000.0

    @patch("src.modules.m6_renovation.cashflow_sync._get_supabase_client")
    def test_sync_no_duplicates(self, mock_client_fn) -> None:
        """Correr sync 2x com mesmos dados = sem duplicados."""
        _, reno = self._create_deal_with_reno()
        self.sync_service.link_project(reno["id"], "proj-123", "Test")

        entries = self._mock_cfp_entries(2)
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=entries)
        mock_client_fn.return_value = mock_client

        r1 = self.sync_service.sync_expenses(reno["id"])
        assert r1["created"] == 2

        r2 = self.sync_service.sync_expenses(reno["id"])
        assert r2["created"] == 0
        assert r2["unchanged"] == 2

    @patch("src.modules.m6_renovation.cashflow_sync._get_supabase_client")
    def test_sync_updates_existing(self, mock_client_fn) -> None:
        """Se amount mudou no CFP, actualiza no M6."""
        _, reno = self._create_deal_with_reno()
        self.sync_service.link_project(reno["id"], "proj-123", "Test")

        entries = self._mock_cfp_entries(1)
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=entries)
        mock_client_fn.return_value = mock_client

        self.sync_service.sync_expenses(reno["id"])

        # Mudar amount
        entries[0]["amount"] = 9999.0
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=entries)

        r2 = self.sync_service.sync_expenses(reno["id"])
        assert r2["updated"] == 1
        assert r2["created"] == 0

    @patch("src.modules.m6_renovation.cashflow_sync._get_supabase_client")
    def test_deductibility_mapping(self, mock_client_fn) -> None:
        """Transferencia + factura = dedutivel. Cash = nao dedutivel."""
        _, reno = self._create_deal_with_reno()
        self.sync_service.link_project(reno["id"], "proj-123", "Test")

        entries = self._mock_cfp_entries(3)
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=entries)
        mock_client_fn.return_value = mock_client

        result = self.sync_service.sync_expenses(reno["id"])
        # entries 0 e 1 tem invoice + transferencia = dedutivel
        # entry 2 tem cash + sem invoice = nao dedutivel
        assert result["deductible_amount"] == 3000.0  # 1000 + 2000

    @patch("src.modules.m6_renovation.cashflow_sync._get_supabase_client")
    def test_payment_status_mapping(self, mock_client_fn) -> None:
        _, reno = self._create_deal_with_reno()
        self.sync_service.link_project(reno["id"], "proj-123", "Test")

        entries = self._mock_cfp_entries(2)
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=entries)
        mock_client_fn.return_value = mock_client

        self.sync_service.sync_expenses(reno["id"])

        expenses = self.reno_service.list_expenses(reno["id"])
        statuses = {e["description"]: e["payment_status"] for e in expenses if e.get("external_source")}
        # Entry 0 = confirmado → pago, Entry 1 = pendente → pendente
        assert any(s == "pago" for s in statuses.values())
        assert any(s == "pendente" for s in statuses.values())
