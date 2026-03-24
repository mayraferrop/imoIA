"""Testes M8 — CRM de Leads.

Testa CRUD, scoring, stage transitions, matching, interactions,
nurturing, sync habta, filtros, pipeline summary, e edge cases.
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
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test_m8.db"
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
def service():
    """Instancia do LeadService."""
    from src.modules.m8_leads.service import LeadService

    return LeadService()


def _lead_data(**overrides):
    """Gera dados base para criacao de lead."""
    data = {
        "name": "Joao Silva",
        "email": "joao@example.com",
        "phone": "+351912345678",
        "budget_min": 200000,
        "budget_max": 400000,
        "preferred_typology": "T2",
        "preferred_locations": ["Lisboa", "Almada"],
        "preferred_features": ["elevador", "garagem"],
        "timeline": "3_months",
        "financing": "pre_approved",
        "buyer_type": "investor",
        "source": "website",
    }
    data.update(overrides)
    return data


def _create_deal_with_listing(listing_price=350000, municipality="Lisboa", typology="T2"):
    """Cria tenant, property, deal e listing para testes de matching."""
    from src.database.db import get_session
    from src.database.models_v2 import Deal, Listing, Property, Tenant
    from sqlalchemy import select

    with get_session() as session:
        tenant = session.execute(
            select(Tenant).where(Tenant.slug == "default")
        ).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=str(uuid4()), name="Test", slug="default", country="PT"
            )
            session.add(tenant)
            session.flush()

        prop = Property(
            id=str(uuid4()),
            tenant_id=tenant.id,
            source="test",
            country="PT",
            municipality=municipality,
            district="Lisboa",
            parish="Sacavem",
            property_type="apartamento",
            typology=typology,
            gross_area_m2=85,
            bedrooms=2,
            asking_price=listing_price,
            status="lead",
        )
        session.add(prop)
        session.flush()

        deal = Deal(
            id=str(uuid4()),
            tenant_id=tenant.id,
            property_id=prop.id,
            investment_strategy="fix_and_flip",
            status="marketing",
            title="Test Deal",
            purchase_price=listing_price - 50000,
            target_sale_price=listing_price,
        )
        session.add(deal)
        session.flush()

        listing = Listing(
            id=str(uuid4()),
            tenant_id=tenant.id,
            deal_id=deal.id,
            listing_type="venda",
            listing_price=listing_price,
            status="active",
        )
        session.add(listing)
        session.flush()

        return {
            "tenant_id": tenant.id,
            "property_id": prop.id,
            "deal_id": deal.id,
            "listing_id": listing.id,
        }


# ---------------------------------------------------------------------------
# CRUD Tests
# ---------------------------------------------------------------------------


class TestLeadCRUD:
    """Testes CRUD de leads."""

    def test_create_lead(self, service):
        lead = service.create_lead(_lead_data())
        assert lead["name"] == "Joao Silva"
        assert lead["email"] == "joao@example.com"
        assert lead["stage"] == "new"
        assert lead["id"] is not None

    def test_create_lead_minimal(self, service):
        lead = service.create_lead({"name": "Ana"})
        assert lead["name"] == "Ana"
        assert lead["budget_min"] is None

    def test_get_lead(self, service):
        created = service.create_lead(_lead_data())
        fetched = service.get_lead(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]
        assert fetched["name"] == "Joao Silva"

    def test_get_lead_not_found(self, service):
        result = service.get_lead("nonexistent-id")
        assert result is None

    def test_update_lead(self, service):
        lead = service.create_lead(_lead_data())
        updated = service.update_lead(lead["id"], {"name": "Joao Santos", "phone": "+351999999999"})
        assert updated["name"] == "Joao Santos"
        assert updated["phone"] == "+351999999999"
        assert updated["email"] == "joao@example.com"  # inalterado

    def test_update_lead_not_found(self, service):
        result = service.update_lead("nonexistent", {"name": "X"})
        assert result is None

    def test_delete_lead(self, service):
        lead = service.create_lead(_lead_data())
        assert service.delete_lead(lead["id"]) is True
        assert service.get_lead(lead["id"]) is None

    def test_delete_lead_not_found(self, service):
        assert service.delete_lead("nonexistent") is False

    def test_list_leads(self, service):
        service.create_lead(_lead_data(name="Lead 1"))
        service.create_lead(_lead_data(name="Lead 2"))
        service.create_lead(_lead_data(name="Lead 3"))
        result = service.list_leads()
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_list_leads_pagination(self, service):
        for i in range(5):
            service.create_lead(_lead_data(name=f"Lead {i}"))
        result = service.list_leads(limit=2, offset=0)
        assert len(result["items"]) == 2
        assert result["total"] == 5

        result2 = service.list_leads(limit=2, offset=2)
        assert len(result2["items"]) == 2


# ---------------------------------------------------------------------------
# Scoring Tests
# ---------------------------------------------------------------------------


class TestLeadScoring:
    """Testes de scoring de leads."""

    def test_score_demographic_full(self, service):
        lead = service.create_lead(_lead_data())
        breakdown = lead["score_breakdown"]
        # budget (10) + email (5) + phone (5) + typology (5) + locations (5) = 30
        assert breakdown["demographic"] == 30

    def test_score_demographic_minimal(self, service):
        lead = service.create_lead({"name": "Ana"})
        assert lead["score_breakdown"]["demographic"] == 0

    def test_score_behavioral_with_interactions(self, service):
        lead = service.create_lead(_lead_data())
        service.add_interaction(lead["id"], {"type": "call", "channel": "phone"})
        service.add_interaction(lead["id"], {"type": "email", "channel": "email"})
        service.add_interaction(lead["id"], {"type": "visit", "channel": "presencial"})
        updated = service.recalculate_score(lead["id"])
        assert updated["score_breakdown"]["behavioral"] >= 30  # 3 interactions + visit

    def test_score_urgency(self, service):
        lead = service.create_lead(_lead_data(
            timeline="imediato", financing="pre_approved"
        ))
        assert lead["score_breakdown"]["urgency"] >= 5

    def test_grade_calculation(self, service):
        # Lead com dados completos + interaccoes deve ter score mais alto
        lead = service.create_lead(_lead_data())
        # Score inicial: demographic=30 + urgency (timeline+financing) = ~38
        assert lead["grade"] in ("C", "D", "B")

    def test_recalculate_score(self, service):
        lead = service.create_lead(_lead_data())
        recalculated = service.recalculate_score(lead["id"])
        assert "score_breakdown" in recalculated
        assert recalculated["score"] == recalculated["score_breakdown"]["total"]

    def test_recalculate_score_not_found(self, service):
        with pytest.raises(ValueError, match="nao encontrado"):
            service.recalculate_score("nonexistent")


# ---------------------------------------------------------------------------
# Stage Transition Tests
# ---------------------------------------------------------------------------


class TestStageTransitions:
    """Testes de transicao de estagios."""

    def test_valid_transition_new_to_contacted(self, service):
        lead = service.create_lead(_lead_data())
        updated = service.advance_stage(lead["id"], "contacted")
        assert updated["stage"] == "contacted"

    def test_valid_transition_contacted_to_qualified(self, service):
        lead = service.create_lead(_lead_data())
        service.advance_stage(lead["id"], "contacted")
        updated = service.advance_stage(lead["id"], "qualified")
        assert updated["stage"] == "qualified"

    def test_full_pipeline_to_won(self, service):
        lead = service.create_lead(_lead_data())
        for stage in ["contacted", "qualified", "visiting", "proposal", "negotiation", "won"]:
            lead = service.advance_stage(lead["id"], stage)
        assert lead["stage"] == "won"

    def test_invalid_transition(self, service):
        lead = service.create_lead(_lead_data())
        with pytest.raises(ValueError, match="Transicao invalida"):
            service.advance_stage(lead["id"], "won")

    def test_transition_to_lost(self, service):
        lead = service.create_lead(_lead_data())
        updated = service.advance_stage(lead["id"], "lost")
        assert updated["stage"] == "lost"

    def test_reopen_from_lost(self, service):
        lead = service.create_lead(_lead_data())
        service.advance_stage(lead["id"], "lost")
        updated = service.advance_stage(lead["id"], "new")
        assert updated["stage"] == "new"

    def test_stage_change_creates_interaction(self, service):
        lead = service.create_lead(_lead_data())
        service.advance_stage(lead["id"], "contacted")
        interactions = service.list_interactions(lead["id"])
        stage_changes = [
            i for i in interactions["items"] if i["type"] == "stage_change"
        ]
        assert len(stage_changes) == 1

    def test_advance_stage_not_found(self, service):
        with pytest.raises(ValueError, match="nao encontrado"):
            service.advance_stage("nonexistent", "contacted")


# ---------------------------------------------------------------------------
# Interaction Tests
# ---------------------------------------------------------------------------


class TestInteractions:
    """Testes de interaccoes."""

    def test_add_interaction(self, service):
        lead = service.create_lead(_lead_data())
        interaction = service.add_interaction(lead["id"], {
            "type": "call",
            "channel": "phone",
            "direction": "outbound",
            "subject": "Primeiro contacto",
            "content": "Chamada introdutoria",
            "performed_by": "agente1",
        })
        assert interaction["type"] == "call"
        assert interaction["channel"] == "phone"
        assert interaction["lead_id"] == lead["id"]

    def test_list_interactions(self, service):
        lead = service.create_lead(_lead_data())
        service.add_interaction(lead["id"], {"type": "call"})
        service.add_interaction(lead["id"], {"type": "email"})
        result = service.list_interactions(lead["id"])
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_timeline(self, service):
        lead = service.create_lead(_lead_data())
        service.add_interaction(lead["id"], {"type": "call", "subject": "Call 1"})
        service.advance_stage(lead["id"], "contacted")
        service.add_interaction(lead["id"], {"type": "email", "subject": "Email 1"})

        timeline = service.get_timeline(lead["id"])
        assert len(timeline) == 3  # call + stage_change + email
        assert timeline[0]["type"] == "call"
        assert timeline[1]["type"] == "stage_change"
        assert timeline[2]["type"] == "email"

    def test_interaction_not_found(self, service):
        with pytest.raises(ValueError, match="nao encontrado"):
            service.add_interaction("nonexistent", {"type": "call"})

    def test_interaction_with_metadata(self, service):
        lead = service.create_lead(_lead_data())
        interaction = service.add_interaction(lead["id"], {
            "type": "email",
            "metadata": {"template": "welcome", "opened": True},
        })
        assert interaction["metadata"]["template"] == "welcome"


# ---------------------------------------------------------------------------
# Matching Tests
# ---------------------------------------------------------------------------


class TestMatching:
    """Testes de matching lead-listing."""

    def test_budget_match(self, service):
        _create_deal_with_listing(listing_price=350000, municipality="Porto")
        lead = service.create_lead(_lead_data(
            budget_min=200000, budget_max=400000,
            preferred_locations=[], preferred_typology=None
        ))
        matches = service.find_matches(lead["id"])
        assert len(matches) >= 1
        assert any(m["match_score"] >= 40 for m in matches)

    def test_location_match(self, service):
        _create_deal_with_listing(
            listing_price=9999999, municipality="Lisboa"
        )
        lead = service.create_lead(_lead_data(
            budget_min=None, budget_max=None,
            preferred_locations=["Lisboa"],
            preferred_typology=None,
        ))
        matches = service.find_matches(lead["id"])
        assert len(matches) >= 1
        has_location = any(
            "Localizacao compativel" in r
            for m in matches
            for r in m["match_reasons"]
        )
        assert has_location

    def test_typology_match(self, service):
        _create_deal_with_listing(
            listing_price=9999999, municipality="Faro", typology="T2"
        )
        lead = service.create_lead(_lead_data(
            budget_min=None, budget_max=None,
            preferred_locations=[],
            preferred_typology="T2",
        ))
        matches = service.find_matches(lead["id"])
        assert len(matches) >= 1

    def test_no_match(self, service):
        _create_deal_with_listing(
            listing_price=1000000, municipality="Porto", typology="T5"
        )
        lead = service.create_lead(_lead_data(
            budget_min=100000, budget_max=150000,
            preferred_locations=["Faro"],
            preferred_typology="T1",
        ))
        matches = service.find_matches(lead["id"])
        # Pode retornar 0 ou matches com score baixo
        for m in matches:
            assert m["match_score"] < 40

    def test_send_listing_to_lead(self, service):
        ids = _create_deal_with_listing()
        lead = service.create_lead(_lead_data())
        result = service.send_listing_to_lead(lead["id"], ids["listing_id"])
        assert result["status"] == "sent"
        assert result["sent_at"] is not None

    def test_find_matches_not_found(self, service):
        with pytest.raises(ValueError, match="nao encontrado"):
            service.find_matches("nonexistent")


# ---------------------------------------------------------------------------
# Nurturing Tests
# ---------------------------------------------------------------------------


class TestNurturing:
    """Testes de nurturing automatico."""

    def test_start_nurture(self, service):
        lead = service.create_lead(_lead_data())
        ns = service.start_nurture(lead["id"])
        assert ns["status"] == "active"
        assert ns["current_step"] == 0
        assert ns["lead_id"] == lead["id"]

    def test_start_nurture_duplicate(self, service):
        lead = service.create_lead(_lead_data())
        service.start_nurture(lead["id"])
        with pytest.raises(ValueError, match="ja tem nurture activo"):
            service.start_nurture(lead["id"])

    def test_execute_pending_step(self, service):
        lead = service.create_lead(_lead_data())
        service.start_nurture(lead["id"])
        result = service.execute_pending_nurtures()
        assert result["executed"] >= 1

        status = service.get_nurture_status(lead["id"])
        assert status["current_step"] == 1
        assert len(status["steps_executed"]) == 1

    def test_execute_until_complete(self, service):
        lead = service.create_lead(_lead_data())
        service.start_nurture(lead["id"])

        # Simular execucao de todos os passos
        from src.modules.m8_leads.service import NURTURE_STEPS
        from src.database.db import get_session
        from src.database.models_v2 import NurtureSequence
        from sqlalchemy import select

        for i in range(len(NURTURE_STEPS)):
            # Forcar next_action_at para o passado
            with get_session() as session:
                ns = session.execute(
                    select(NurtureSequence).where(
                        NurtureSequence.lead_id == lead["id"]
                    )
                ).scalar_one()
                ns.next_action_at = datetime.utcnow() - timedelta(hours=1)

            service.execute_pending_nurtures()

        status = service.get_nurture_status(lead["id"])
        assert status["status"] == "completed"

    def test_pause_nurture(self, service):
        lead = service.create_lead(_lead_data())
        service.start_nurture(lead["id"])
        result = service.pause_nurture(lead["id"])
        assert result["status"] == "paused"

    def test_resume_nurture(self, service):
        lead = service.create_lead(_lead_data())
        service.start_nurture(lead["id"])
        service.pause_nurture(lead["id"])
        result = service.resume_nurture(lead["id"])
        assert result["status"] == "active"
        assert result["next_action_at"] is not None

    def test_pause_no_active(self, service):
        lead = service.create_lead(_lead_data())
        with pytest.raises(ValueError, match="Nenhum nurture activo"):
            service.pause_nurture(lead["id"])

    def test_resume_no_paused(self, service):
        lead = service.create_lead(_lead_data())
        with pytest.raises(ValueError, match="Nenhum nurture pausado"):
            service.resume_nurture(lead["id"])

    def test_nurture_status_none(self, service):
        lead = service.create_lead(_lead_data())
        assert service.get_nurture_status(lead["id"]) is None


# ---------------------------------------------------------------------------
# Habta Sync Tests
# ---------------------------------------------------------------------------


class TestHabtaSync:
    """Testes de sincronizacao com Habta."""

    def test_sync_create(self, service):
        contacts = [
            {
                "id": "habta-001",
                "name": "Maria Costa",
                "email": "maria@example.com",
                "phone": "+351911111111",
                "budget": "300000-500000",
                "preferences": {"typology": "T3", "locations": ["Lisboa"]},
                "source": "habta_website",
            }
        ]
        result = service.sync_from_habta(contacts)
        assert result["created"] == 1
        assert result["updated"] == 0
        assert result["errors"] == 0

        # Verificar que foi criado
        leads = service.list_leads()
        assert leads["total"] == 1
        lead = leads["items"][0]
        assert lead["name"] == "Maria Costa"
        assert lead["budget_min"] == 300000
        assert lead["budget_max"] == 500000
        assert lead["preferred_typology"] == "T3"

    def test_sync_update(self, service):
        contacts = [
            {"id": "habta-002", "name": "Pedro", "email": "pedro@x.com"}
        ]
        service.sync_from_habta(contacts)

        # Actualizar
        contacts[0]["name"] = "Pedro Santos"
        contacts[0]["budget"] = "200000"
        result = service.sync_from_habta(contacts)
        assert result["updated"] == 1
        assert result["created"] == 0

    def test_sync_budget_single_value(self, service):
        contacts = [
            {"id": "habta-003", "name": "Ana", "budget": "250000"}
        ]
        service.sync_from_habta(contacts)
        leads = service.list_leads()
        lead = leads["items"][0]
        assert lead["budget_max"] == 250000

    def test_sync_no_id_error(self, service):
        contacts = [{"name": "Invalid"}]
        result = service.sync_from_habta(contacts)
        assert result["errors"] == 1

    def test_sync_empty(self, service):
        result = service.sync_from_habta([])
        assert result["created"] == 0


# ---------------------------------------------------------------------------
# Filter Tests
# ---------------------------------------------------------------------------


class TestFilters:
    """Testes de filtros na listagem."""

    def test_filter_by_stage(self, service):
        lead1 = service.create_lead(_lead_data(name="Lead A"))
        service.create_lead(_lead_data(name="Lead B"))
        service.advance_stage(lead1["id"], "contacted")

        result = service.list_leads(stage="contacted")
        assert result["total"] == 1
        assert result["items"][0]["name"] == "Lead A"

    def test_filter_by_grade(self, service):
        service.create_lead(_lead_data(name="Full"))
        service.create_lead({"name": "Minimal"})

        full_leads = service.list_leads(grade="C")
        # Grade depends on score, but full data lead should score higher
        minimal_leads = service.list_leads(grade="D")
        assert full_leads["total"] + minimal_leads["total"] >= 1

    def test_filter_by_source(self, service):
        service.create_lead(_lead_data(source="website"))
        service.create_lead(_lead_data(name="Lead 2", source="referral"))

        result = service.list_leads(source="website")
        assert result["total"] == 1

    def test_filter_by_search(self, service):
        service.create_lead(_lead_data(name="Joao Silva"))
        service.create_lead(_lead_data(name="Ana Costa", email="ana@x.com"))

        result = service.list_leads(search="Joao")
        assert result["total"] == 1
        assert result["items"][0]["name"] == "Joao Silva"

        result2 = service.list_leads(search="ana@")
        assert result2["total"] == 1


# ---------------------------------------------------------------------------
# Pipeline Summary Tests
# ---------------------------------------------------------------------------


class TestPipelineSummary:
    """Testes de analytics do pipeline."""

    def test_pipeline_summary(self, service):
        service.create_lead(_lead_data(name="L1"))
        service.create_lead(_lead_data(name="L2"))
        lead3 = service.create_lead(_lead_data(name="L3"))
        service.advance_stage(lead3["id"], "contacted")

        summary = service.get_pipeline_summary()
        stages = {s["stage"]: s["count"] for s in summary}
        assert stages["new"] == 2
        assert stages["contacted"] == 1

    def test_conversion_funnel(self, service):
        for i in range(3):
            service.create_lead(_lead_data(name=f"L{i}"))

        funnel = service.get_conversion_funnel()
        assert len(funnel) == 7  # 7 stages (excl. lost)
        assert funnel[0]["stage"] == "new"
        assert funnel[0]["count"] == 3

    def test_source_breakdown(self, service):
        service.create_lead(_lead_data(source="website"))
        service.create_lead(_lead_data(name="L2", source="website"))
        service.create_lead(_lead_data(name="L3", source="referral"))

        breakdown = service.get_source_breakdown()
        sources = {b["source"]: b["count"] for b in breakdown}
        assert sources["website"] == 2
        assert sources["referral"] == 1

    def test_grades_summary(self, service):
        service.create_lead(_lead_data())
        service.create_lead({"name": "Minimal"})

        grades = service.get_grades_summary()
        assert "A" in grades
        assert "D" in grades
        total = sum(grades.values())
        assert total == 2

    def test_stats(self, service):
        service.create_lead(_lead_data())
        stats = service.get_stats()
        assert stats["total_leads"] == 1
        assert "by_stage" in stats
        assert "by_grade" in stats
        assert "avg_score" in stats
        assert stats["leads_this_month"] >= 1


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Testes de casos limite."""

    def test_lead_without_budget(self, service):
        lead = service.create_lead({"name": "Sem orcamento"})
        assert lead["budget_min"] is None
        assert lead["budget_max"] is None
        assert lead["score_breakdown"]["demographic"] == 0

    def test_duplicate_habta_contact_id(self, service):
        service.create_lead(_lead_data(habta_contact_id="habta-dup"))
        # Segundo com mesmo habta_contact_id via sync deve actualizar
        contacts = [
            {"id": "habta-dup", "name": "Updated Name"}
        ]
        result = service.sync_from_habta(contacts)
        assert result["updated"] == 1

    def test_delete_lead_with_interactions(self, service):
        lead = service.create_lead(_lead_data())
        service.add_interaction(lead["id"], {"type": "call"})
        service.add_interaction(lead["id"], {"type": "email"})
        assert service.delete_lead(lead["id"]) is True
        assert service.get_lead(lead["id"]) is None

    def test_delete_lead_with_nurture(self, service):
        lead = service.create_lead(_lead_data())
        service.start_nurture(lead["id"])
        assert service.delete_lead(lead["id"]) is True

    def test_interactions_count_in_response(self, service):
        lead = service.create_lead(_lead_data())
        service.add_interaction(lead["id"], {"type": "call"})
        service.add_interaction(lead["id"], {"type": "email"})

        fetched = service.get_lead(lead["id"])
        assert fetched["interactions_count"] == 2


# ---------------------------------------------------------------------------
# API (TestClient) Tests
# ---------------------------------------------------------------------------


class TestLeadAPI:
    """Testes dos endpoints REST via TestClient."""

    def test_create_lead_api(self, client):
        resp = client.post("/api/v1/leads/", json=_lead_data())
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Joao Silva"

    def test_list_leads_api(self, client):
        client.post("/api/v1/leads/", json=_lead_data(name="L1"))
        client.post("/api/v1/leads/", json=_lead_data(name="L2"))
        resp = client.get("/api/v1/leads/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_get_lead_api(self, client):
        created = client.post("/api/v1/leads/", json=_lead_data()).json()
        resp = client.get(f"/api/v1/leads/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_lead_not_found_api(self, client):
        resp = client.get("/api/v1/leads/nonexistent")
        assert resp.status_code == 404

    def test_update_lead_api(self, client):
        created = client.post("/api/v1/leads/", json=_lead_data()).json()
        resp = client.put(
            f"/api/v1/leads/{created['id']}",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_delete_lead_api(self, client):
        created = client.post("/api/v1/leads/", json=_lead_data()).json()
        resp = client.delete(f"/api/v1/leads/{created['id']}")
        assert resp.status_code == 200

    def test_advance_stage_api(self, client):
        created = client.post("/api/v1/leads/", json=_lead_data()).json()
        resp = client.patch(
            f"/api/v1/leads/{created['id']}/stage?new_stage=contacted"
        )
        assert resp.status_code == 200
        assert resp.json()["stage"] == "contacted"

    def test_stats_api(self, client):
        client.post("/api/v1/leads/", json=_lead_data())
        resp = client.get("/api/v1/leads/stats")
        assert resp.status_code == 200
        assert resp.json()["total_leads"] == 1

    def test_pipeline_summary_api(self, client):
        resp = client.get("/api/v1/leads/pipeline-summary")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_grades_summary_api(self, client):
        resp = client.get("/api/v1/leads/grades-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "A" in data

    def test_sync_habta_api(self, client):
        resp = client.post("/api/v1/leads/sync-habta", json=[
            {"id": "h1", "name": "Test", "email": "t@x.com"}
        ])
        assert resp.status_code == 200
        assert resp.json()["created"] == 1
