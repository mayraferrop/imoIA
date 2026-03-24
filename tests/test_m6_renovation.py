"""Testes M6 — Gestao de Obra.

Testa templates, milestones, despesas, dedutibilidade, alertas.
"""

from __future__ import annotations

import pytest

from src.modules.m6_renovation.templates import (
    FLIP_STANDARD_MILESTONES,
    BUILDING_MILESTONES,
    AL_MILESTONES,
    get_milestone_template,
)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class TestTemplates:
    def test_flip_has_15_milestones(self) -> None:
        assert len(FLIP_STANDARD_MILESTONES) == 15

    def test_building_has_extras(self) -> None:
        assert len(BUILDING_MILESTONES) == 17
        names = [m["name"] for m in BUILDING_MILESTONES]
        assert any("comuns" in n.lower() for n in names)
        assert any("fachada" in n.lower() for n in names)

    def test_al_has_extras(self) -> None:
        assert len(AL_MILESTONES) == 17
        names = [m["name"] for m in AL_MILESTONES]
        assert any("mobil" in n.lower() for n in names)

    def test_budget_pct_sums_to_100(self) -> None:
        total = sum(m["budget_pct"] for m in FLIP_STANDARD_MILESTONES)
        assert abs(total - 100) < 1  # allow small rounding

    def test_get_template_default(self) -> None:
        tmpl = get_milestone_template("apartamento", "fix_and_flip")
        assert len(tmpl) == 15

    def test_get_template_predio(self) -> None:
        tmpl = get_milestone_template("predio", "fix_and_flip")
        assert len(tmpl) == 17

    def test_get_template_al(self) -> None:
        tmpl = get_milestone_template("apartamento", "alojamento_local")
        assert len(tmpl) == 17


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TestRenovationService:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        import os
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
        from src.database.db import reset_engine, _get_engine
        from src.database.models import Base
        reset_engine()
        import src.database.models_v2  # noqa: F401
        engine = _get_engine()
        Base.metadata.create_all(bind=engine)
        self.service = __import__(
            "src.modules.m6_renovation.service",
            fromlist=["RenovationService"],
        ).RenovationService()
        self.m4_service = __import__(
            "src.modules.m4_deal_pipeline.service",
            fromlist=["DealPipelineService"],
        ).DealPipelineService()
        self.tmp_path = tmp_path
        yield
        from src.database.db import reset_engine as re
        re()

    def _create_deal(self, property_type="apartamento", strategy="fix_and_flip"):
        from uuid import uuid4
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
                property_type=property_type, asking_price=200000, status="lead",
            )
            session.add(prop)
            session.flush()
            prop_id = prop.id
        return self.m4_service.create_deal({
            "property_id": prop_id,
            "investment_strategy": strategy,
            "title": f"Test Reno ({property_type})",
            "purchase_price": 200000,
            "renovation_budget": 98400,
        })

    def _create_renovation(self, deal=None, property_type="apartamento", strategy="fix_and_flip"):
        if not deal:
            deal = self._create_deal(property_type, strategy)
        return self.service.create_renovation(deal["id"], {
            "initial_budget": 98400,
            "contractor_name": "Alector",
            "auto_milestones": True,
        }), deal

    def test_create_renovation_with_auto_milestones(self) -> None:
        reno, deal = self._create_renovation()
        assert reno["initial_budget"] == 98400
        assert reno["milestone_count"] == 15

    def test_budget_distribution(self) -> None:
        reno, deal = self._create_renovation()
        milestones = self.service.get_milestones(reno["id"])
        total_budget = sum(m["budget"] for m in milestones)
        assert abs(total_budget - 98400) < 10  # allow rounding

    def test_template_for_predio(self) -> None:
        reno, _ = self._create_renovation(property_type="predio")
        assert reno["milestone_count"] == 17

    def test_template_for_al(self) -> None:
        reno, _ = self._create_renovation(strategy="alojamento_local")
        assert reno["milestone_count"] == 17

    def test_start_milestone(self) -> None:
        reno, _ = self._create_renovation()
        milestones = self.service.get_milestones(reno["id"])
        first = milestones[0]
        started = self.service.start_milestone(first["id"])
        assert started["status"] == "em_curso"
        assert started["actual_start"] is not None

    def test_milestone_dependencies(self) -> None:
        """Nao pode iniciar milestone se dependencia nao esta concluida."""
        reno, _ = self._create_renovation()
        milestones = self.service.get_milestones(reno["id"])
        # Find one with depends_on
        dependent = next((m for m in milestones if m.get("depends_on_id")), None)
        if dependent:
            with pytest.raises(ValueError, match="[Dd]ependencia|[Dd]epends"):
                self.service.start_milestone(dependent["id"])

    def test_complete_milestone_recalculates_progress(self) -> None:
        reno, _ = self._create_renovation()
        milestones = self.service.get_milestones(reno["id"])
        first = milestones[0]
        self.service.start_milestone(first["id"])
        self.service.complete_milestone(first["id"])
        full = self.service.get_renovation(reno["deal_id"])
        assert full["renovation"]["progress_pct"] > 0

    def test_add_expense_updates_totals(self) -> None:
        reno, _ = self._create_renovation()
        from datetime import datetime, timezone
        self.service.add_expense(reno["id"], {
            "description": "Material electrico",
            "amount": 5000,
            "expense_date": datetime.now(timezone.utc),
            "category": "material",
        })
        full = self.service.get_renovation(reno["deal_id"])
        assert full["renovation"]["total_spent"] == 5000

    def test_expense_deductibility_transfer(self) -> None:
        reno, _ = self._create_renovation()
        from datetime import datetime, timezone
        exp = self.service.add_expense(reno["id"], {
            "description": "Factura electricista",
            "amount": 3000,
            "expense_date": datetime.now(timezone.utc),
            "has_valid_invoice": True,
            "payment_method": "transferencia",
        })
        assert exp["is_tax_deductible"] is True

    def test_expense_deductibility_cash_not_deductible(self) -> None:
        reno, _ = self._create_renovation()
        from datetime import datetime, timezone
        exp = self.service.add_expense(reno["id"], {
            "description": "Material",
            "amount": 500,
            "expense_date": datetime.now(timezone.utc),
            "has_valid_invoice": True,
            "payment_method": "numerario",
        })
        assert exp["is_tax_deductible"] is False

    def test_budget_alert_warning(self) -> None:
        reno, _ = self._create_renovation()
        from datetime import datetime, timezone
        # Spend 85% of budget
        self.service.add_expense(reno["id"], {
            "description": "Obra grande",
            "amount": 83640,  # 85% of 98400
            "expense_date": datetime.now(timezone.utc),
        })
        alerts = self.service.get_budget_alerts(reno["id"])
        assert len(alerts) > 0  # deve haver pelo menos um alerta

    def test_budget_alert_over(self) -> None:
        reno, _ = self._create_renovation()
        from datetime import datetime, timezone
        self.service.add_expense(reno["id"], {
            "description": "Obra cara",
            "amount": 100000,
            "expense_date": datetime.now(timezone.utc),
        })
        alerts = self.service.get_budget_alerts(reno["id"])
        assert any(a["severity"] == "critical" for a in alerts)

    def test_mark_expense_paid(self) -> None:
        reno, _ = self._create_renovation()
        from datetime import datetime, timezone
        exp = self.service.add_expense(reno["id"], {
            "description": "Test",
            "amount": 1000,
            "expense_date": datetime.now(timezone.utc),
        })
        paid = self.service.mark_expense_paid(exp["id"])
        assert paid["payment_status"] == "pago"
        assert paid["paid_amount"] == 1000

    def test_delete_expense_recalculates(self) -> None:
        reno, _ = self._create_renovation()
        from datetime import datetime, timezone
        exp = self.service.add_expense(reno["id"], {
            "description": "To delete",
            "amount": 2000,
            "expense_date": datetime.now(timezone.utc),
        })
        self.service.delete_expense(exp["id"])
        full = self.service.get_renovation(reno["deal_id"])
        assert full["renovation"]["total_spent"] == 0

    def test_expense_summary_by_category(self) -> None:
        reno, _ = self._create_renovation()
        from datetime import datetime, timezone
        self.service.add_expense(reno["id"], {
            "description": "Material", "amount": 1000,
            "expense_date": datetime.now(timezone.utc), "category": "material",
        })
        self.service.add_expense(reno["id"], {
            "description": "Mao de obra", "amount": 2000,
            "expense_date": datetime.now(timezone.utc), "category": "mao_de_obra",
        })
        summary = self.service.get_expense_summary(reno["id"])
        assert summary["by_category"]["material"] == 1000
        assert summary["by_category"]["mao_de_obra"] == 2000

    def test_complete_renovation(self) -> None:
        reno, deal = self._create_renovation()
        result = self.service.complete_renovation(reno["id"])
        assert result["status"] == "concluida"
        assert result["actual_end"] is not None

    def test_auto_create_on_advance(self) -> None:
        deal = self._create_deal()
        for target in ["oportunidade", "analise", "proposta", "negociacao",
                        "cpcv_compra", "due_diligence", "escritura_compra", "obra"]:
            deal = self.m4_service.advance_deal(deal["id"], target)
        reno = self.service.get_renovation(deal["id"])
        assert reno is not None
        assert reno["renovation"]["initial_budget"] > 0

    def test_upload_photo(self) -> None:
        reno, _ = self._create_renovation()
        photo = self.service.upload_photo(
            reno["id"], b"fake image content", "cozinha_antes.jpg",
            {"photo_type": "antes", "room_area": "cozinha", "taken_by": "Mayara"},
            storage_base=str(self.tmp_path / "storage"),
        )
        assert photo["photo_type"] == "antes"
        assert photo["room_area"] == "cozinha"

    def test_list_photos(self) -> None:
        reno, _ = self._create_renovation()
        self.service.upload_photo(
            reno["id"], b"img1", "foto1.jpg", {"photo_type": "antes"},
            storage_base=str(self.tmp_path / "storage"),
        )
        self.service.upload_photo(
            reno["id"], b"img2", "foto2.jpg", {"photo_type": "durante"},
            storage_base=str(self.tmp_path / "storage"),
        )
        all_photos = self.service.list_photos(reno["id"])
        assert len(all_photos) == 2
        antes = self.service.list_photos(reno["id"], photo_type="antes")
        assert len(antes) == 1

    def test_renovation_stats(self) -> None:
        self._create_renovation()
        stats = self.service.get_renovation_stats()
        assert stats["active_count"] >= 1
        assert stats["total_budget"] >= 98400
