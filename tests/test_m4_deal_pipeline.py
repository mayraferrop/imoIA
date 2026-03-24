"""Testes M4 — Deal Pipeline.

Testa maquina de estados, transicoes por estrategia, service e API.
"""

from __future__ import annotations

import pytest

from src.modules.m4_deal_pipeline.state_machine import (
    AUTO_TASKS,
    DEAL_STATUSES,
    DEAL_TRANSITIONS,
    INVESTMENT_STRATEGIES,
    STATUS_CONFIG,
    is_mediation_strategy,
    STRATEGY_ROUTES,
    can_transition,
    get_all_strategies,
    get_all_statuses,
    get_next_statuses,
    get_progress_pct,
    get_strategy_info,
)


# ---------------------------------------------------------------------------
# State machine — transicoes
# ---------------------------------------------------------------------------


class TestCanTransition:
    """Testa validacao de transicoes."""

    def test_valid_transitions(self) -> None:
        assert can_transition("lead", "oportunidade") is True
        assert can_transition("oportunidade", "analise") is True
        assert can_transition("analise", "proposta") is True
        assert can_transition("proposta", "negociacao") is True
        assert can_transition("negociacao", "cpcv_compra") is True
        assert can_transition("cpcv_compra", "due_diligence") is True
        assert can_transition("escritura_compra", "obra") is True
        assert can_transition("obra", "em_venda") is True
        assert can_transition("em_venda", "cpcv_venda") is True
        assert can_transition("cpcv_venda", "escritura_venda") is True
        assert can_transition("escritura_venda", "concluido") is True

    def test_invalid_transitions(self) -> None:
        assert can_transition("lead", "concluido") is False
        assert can_transition("analise", "escritura_compra") is False
        assert can_transition("concluido", "em_venda") is False
        assert can_transition("obra", "lead") is False

    def test_discard_from_any_active(self) -> None:
        """Descartado deve ser possivel a partir de estados activos."""
        discardable = [
            "lead", "oportunidade", "analise", "proposta",
            "negociacao", "cpcv_compra", "due_diligence",
            "financiamento", "cessao",
        ]
        for status in discardable:
            assert can_transition(status, "descartado") is True, (
                f"{status} -> descartado deveria ser valido"
            )

    def test_reopen_from_discarded(self) -> None:
        assert can_transition("descartado", "lead") is True

    def test_pause_resume(self) -> None:
        assert can_transition("arrendamento", "em_pausa") is True
        assert can_transition("em_venda", "em_pausa") is True
        assert can_transition("em_pausa", "em_venda") is True
        assert can_transition("em_pausa", "arrendamento") is True

    def test_pivot_flip_to_hold(self) -> None:
        """Flip que nao vendeu -> arrendamento (pivot)."""
        assert can_transition("em_venda", "arrendamento") is True

    def test_pivot_hold_to_sell(self) -> None:
        """Hold que decide vender."""
        assert can_transition("arrendamento", "em_venda") is True


# ---------------------------------------------------------------------------
# State machine — rotas por estrategia
# ---------------------------------------------------------------------------


class TestStrategyRoutes:
    """Testa rotas sugeridas por estrategia."""

    def test_fix_and_flip_full_route(self) -> None:
        """Fix and flip: lead -> ... -> obra -> em_venda -> ... -> concluido."""
        route = STRATEGY_ROUTES["fix_and_flip"]
        assert route[0] == "lead"
        assert route[-1] == "concluido"
        assert "obra" in route
        assert "em_venda" in route
        assert "escritura_venda" in route
        # Nao deve ter arrendamento
        assert "arrendamento" not in route
        assert "refinanciamento" not in route

    def test_buy_and_hold_route(self) -> None:
        """Buy and hold: ... -> escritura_compra -> arrendamento -> concluido."""
        route = STRATEGY_ROUTES["buy_and_hold"]
        assert "arrendamento" in route
        assert "concluido" in route
        # Nao deve ter venda
        assert "em_venda" not in route
        assert "obra" not in route

    def test_brrrr_route(self) -> None:
        """BRRRR: ... -> obra -> arrendamento -> refinanciamento -> concluido."""
        route = STRATEGY_ROUTES["brrrr"]
        assert "obra" in route
        assert "arrendamento" in route
        assert "refinanciamento" in route

    def test_wholesale_route(self) -> None:
        """Wholesale: ... -> cpcv_compra -> cessao -> concluido."""
        route = STRATEGY_ROUTES["wholesale"]
        assert "cpcv_compra" in route
        assert "cessao" in route
        assert "escritura_compra" not in route
        assert "obra" not in route

    def test_all_strategies_have_routes(self) -> None:
        for strategy in INVESTMENT_STRATEGIES:
            assert strategy in STRATEGY_ROUTES, f"Falta rota para {strategy}"
            route = STRATEGY_ROUTES[strategy]
            assert route[0] == "lead"
            assert route[-1] == "concluido"

    def test_ten_strategies(self) -> None:
        assert len(INVESTMENT_STRATEGIES) == 10


# ---------------------------------------------------------------------------
# State machine — next actions filtradas
# ---------------------------------------------------------------------------


class TestNextStatuses:
    """Testa filtragem de proximos estados por estrategia."""

    def test_next_from_escritura_fix_and_flip(self) -> None:
        """Fix and flip apos escritura -> obra (nao arrendamento)."""
        nexts = get_next_statuses("escritura_compra", "fix_and_flip")
        assert "obra" in nexts
        assert "concluido" in nexts
        # Arrendamento nao esta na rota fix_and_flip
        assert "arrendamento" not in nexts

    def test_next_from_escritura_buy_and_hold(self) -> None:
        """Buy and hold apos escritura -> arrendamento (nao obra)."""
        nexts = get_next_statuses("escritura_compra", "buy_and_hold")
        assert "arrendamento" in nexts
        assert "concluido" in nexts
        assert "obra" not in nexts

    def test_next_from_cpcv_wholesale(self) -> None:
        """Wholesale apos CPCV -> cessao."""
        nexts = get_next_statuses("cpcv_compra", "wholesale")
        assert "cessao" in nexts
        assert "descartado" in nexts

    def test_skip_financiamento_cash(self) -> None:
        """Financiamento pode ser saltado (due_diligence -> escritura)."""
        nexts = get_next_statuses("due_diligence")
        assert "escritura_compra" in nexts
        assert "financiamento" in nexts

    def test_no_strategy_returns_all(self) -> None:
        nexts = get_next_statuses("escritura_compra")
        assert "obra" in nexts
        assert "arrendamento" in nexts
        assert "em_venda" in nexts


# ---------------------------------------------------------------------------
# State machine — progresso
# ---------------------------------------------------------------------------


class TestProgress:
    """Testa calculo de progresso."""

    def test_lead_is_zero(self) -> None:
        assert get_progress_pct("lead", "fix_and_flip") == 0.0

    def test_concluido_is_100(self) -> None:
        assert get_progress_pct("concluido", "fix_and_flip") == 100.0

    def test_mid_route(self) -> None:
        pct = get_progress_pct("obra", "fix_and_flip")
        assert 50 < pct < 80

    def test_descartado_is_zero(self) -> None:
        assert get_progress_pct("descartado", "fix_and_flip") == 0.0


# ---------------------------------------------------------------------------
# State machine — helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    """Testa funcoes auxiliares."""

    def test_get_strategy_info(self) -> None:
        info = get_strategy_info("fix_and_flip")
        assert info is not None
        assert info["key"] == "fix_and_flip"
        assert info["label"] == "Fix and Flip"
        assert "route" in info

    def test_get_strategy_info_invalid(self) -> None:
        assert get_strategy_info("invalid") is None

    def test_get_all_strategies(self) -> None:
        strategies = get_all_strategies()
        assert len(strategies) == 10
        keys = [s["key"] for s in strategies]
        assert "fix_and_flip" in keys
        assert "wholesale" in keys
        assert "mediacao_venda" in keys
        assert "mediacao_compra" in keys

    def test_get_strategies_by_role(self) -> None:
        inv = get_all_strategies(role="investidor")
        med = get_all_strategies(role="mediador")
        assert len(inv) == 7
        assert len(med) == 3
        assert all(s.get("role") == "mediador" for s in med)

    def test_get_all_statuses(self) -> None:
        statuses = get_all_statuses()
        assert len(statuses) == len(DEAL_STATUSES)
        keys = [s["key"] for s in statuses]
        assert "lead" in keys
        assert "concluido" in keys

    def test_all_statuses_have_config(self) -> None:
        for status in DEAL_STATUSES:
            assert status in STATUS_CONFIG, f"Falta config para {status}"

    def test_all_statuses_have_transitions(self) -> None:
        """Todos os estados (excepto concluido) devem ter transicoes definidas."""
        for status in DEAL_STATUSES:
            if status == "concluido":
                continue
            assert status in DEAL_TRANSITIONS, (
                f"Falta transicoes para {status}"
            )

    def test_auto_tasks_exist(self) -> None:
        assert "cpcv_compra" in AUTO_TASKS
        assert "obra" in AUTO_TASKS
        assert "em_venda" in AUTO_TASKS
        assert "arrendamento" in AUTO_TASKS


# ---------------------------------------------------------------------------
# Service — CRUD + state machine (requer BD)
# ---------------------------------------------------------------------------


class TestDealPipelineService:
    """Testa o service com BD SQLite em memoria."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Configura BD SQLite em memoria para cada teste."""
        import os
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"

        from src.database.db import reset_engine, _get_engine
        from src.database.models import Base

        reset_engine()

        import src.database.models_v2  # noqa: F401

        engine = _get_engine()
        Base.metadata.create_all(bind=engine)

        self.service = __import__(
            "src.modules.m4_deal_pipeline.service",
            fromlist=["DealPipelineService"],
        ).DealPipelineService()

        yield

        reset_engine()

    def _create_test_deal(
        self, strategy: str = "fix_and_flip"
    ) -> dict:
        """Helper: cria Property + Deal para testes."""
        from uuid import uuid4
        from src.database.db import get_session
        from src.database.models_v2 import Property, Tenant

        with get_session() as session:
            from sqlalchemy import select

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
                municipality="Lisboa",
                asking_price=200000,
                status="lead",
            )
            session.add(prop)
            session.flush()
            prop_id = prop.id

        return self.service.create_deal({
            "property_id": prop_id,
            "investment_strategy": strategy,
            "title": f"Test Deal ({strategy})",
            "purchase_price": 200000,
        })

    def test_create_deal(self) -> None:
        deal = self._create_test_deal()
        assert deal["status"] == "lead"
        assert deal["investment_strategy"] == "fix_and_flip"
        assert deal["progress_pct"] == 0.0

    def test_create_deal_invalid_strategy(self) -> None:
        with pytest.raises(ValueError, match="Estrategia invalida"):
            self.service.create_deal({
                "property_id": "fake",
                "investment_strategy": "invalid",
                "title": "Test",
            })

    def test_advance_fix_and_flip_full_route(self) -> None:
        """Fix and flip: lead -> ... -> concluido."""
        deal = self._create_test_deal("fix_and_flip")
        route = [
            "oportunidade", "analise", "proposta", "negociacao",
            "cpcv_compra", "due_diligence", "financiamento",
            "escritura_compra", "obra", "em_venda", "cpcv_venda",
            "escritura_venda", "concluido",
        ]
        for target in route:
            deal = self.service.advance_deal(deal["id"], target)
            assert deal["status"] == target

        assert deal["progress_pct"] == 100.0

    def test_advance_buy_and_hold_route(self) -> None:
        """Buy and hold: lead -> ... -> arrendamento -> concluido."""
        deal = self._create_test_deal("buy_and_hold")
        route = [
            "oportunidade", "analise", "proposta", "negociacao",
            "cpcv_compra", "due_diligence", "financiamento",
            "escritura_compra", "arrendamento", "concluido",
        ]
        for target in route:
            deal = self.service.advance_deal(deal["id"], target)
        assert deal["status"] == "concluido"

    def test_advance_brrrr_route(self) -> None:
        """BRRRR: ... -> obra -> arrendamento -> refinanciamento -> concluido."""
        deal = self._create_test_deal("brrrr")
        route = [
            "oportunidade", "analise", "proposta", "negociacao",
            "cpcv_compra", "due_diligence", "financiamento",
            "escritura_compra", "obra", "arrendamento",
            "refinanciamento", "concluido",
        ]
        for target in route:
            deal = self.service.advance_deal(deal["id"], target)
        assert deal["status"] == "concluido"

    def test_advance_wholesale_route(self) -> None:
        """Wholesale: ... -> cpcv_compra -> cessao -> concluido."""
        deal = self._create_test_deal("wholesale")
        route = [
            "oportunidade", "analise", "proposta", "negociacao",
            "cpcv_compra", "cessao", "concluido",
        ]
        for target in route:
            deal = self.service.advance_deal(deal["id"], target)
        assert deal["status"] == "concluido"

    def test_invalid_transition(self) -> None:
        deal = self._create_test_deal()
        with pytest.raises(ValueError, match="Transicao invalida"):
            self.service.advance_deal(deal["id"], "concluido")

    def test_pivot_flip_to_hold(self) -> None:
        """Flip que nao vende -> arrendamento."""
        deal = self._create_test_deal("fix_and_flip")
        for target in ["oportunidade", "analise", "proposta", "negociacao",
                        "cpcv_compra", "escritura_compra", "obra", "em_venda"]:
            deal = self.service.advance_deal(deal["id"], target)

        # Pivot: em_venda -> arrendamento
        deal = self.service.advance_deal(deal["id"], "arrendamento")
        assert deal["status"] == "arrendamento"

    def test_skip_financiamento(self) -> None:
        """Compra a cash: salta financiamento."""
        deal = self._create_test_deal()
        for target in ["oportunidade", "analise", "proposta", "negociacao",
                        "cpcv_compra", "due_diligence"]:
            deal = self.service.advance_deal(deal["id"], target)

        # Salta financiamento -> directo para escritura
        deal = self.service.advance_deal(deal["id"], "escritura_compra")
        assert deal["status"] == "escritura_compra"

    def test_deal_history(self) -> None:
        deal = self._create_test_deal()
        self.service.advance_deal(deal["id"], "oportunidade")
        self.service.advance_deal(deal["id"], "analise")

        history = self.service.get_deal_history(deal["id"])
        assert len(history) == 3  # criacao + 2 avancos
        statuses = {h["to_status"] for h in history}
        assert statuses == {"lead", "oportunidade", "analise"}

    def test_proposals(self) -> None:
        deal = self._create_test_deal()
        prop = self.service.create_proposal(deal["id"], {
            "proposal_type": "offer",
            "amount": 180000,
            "deposit_pct": 10,
            "conditions": "Sujeita a financiamento",
            "validity_days": 5,
        })
        assert prop["amount"] == 180000
        assert prop["status"] == "sent"

        # Responder
        prop = self.service.respond_to_proposal(prop["id"], "counter", "285k")
        assert prop["status"] == "counter"

        proposals = self.service.list_proposals(deal["id"])
        assert len(proposals) == 1

    def test_tasks(self) -> None:
        deal = self._create_test_deal()
        task = self.service.create_task(deal["id"], {
            "title": "Visitar imovel",
            "priority": "high",
        })
        assert task["is_completed"] is False

        task = self.service.complete_task(task["id"])
        assert task["is_completed"] is True

    def test_auto_tasks_on_advance(self) -> None:
        """Avancar para cpcv_compra deve criar tasks automaticas."""
        deal = self._create_test_deal()
        for target in ["oportunidade", "analise", "proposta",
                        "negociacao", "cpcv_compra"]:
            deal = self.service.advance_deal(deal["id"], target)

        upcoming = self.service.get_upcoming_tasks(limit=100)
        auto_tasks = [t for t in upcoming if t["deal_id"] == deal["id"]]
        assert len(auto_tasks) >= 3  # cpcv_compra tem 3 auto-tasks

    def test_rental(self) -> None:
        deal = self._create_test_deal("buy_and_hold")
        for target in ["oportunidade", "analise", "proposta", "negociacao",
                        "cpcv_compra", "escritura_compra", "arrendamento"]:
            deal = self.service.advance_deal(deal["id"], target)

        rental = self.service.add_rental(deal["id"], {
            "rental_type": "longa_duracao",
            "monthly_rent": 1500,
            "deposit_months": 2,
            "tenant_name": "Ana Silva",
        })
        assert rental["monthly_rent"] == 1500
        assert rental["tenant_name"] == "Ana Silva"

        # Actualizar
        rental = self.service.update_rental(rental["id"], {"monthly_rent": 1600})
        assert rental["monthly_rent"] == 1600

    def test_kanban(self) -> None:
        self._create_test_deal("fix_and_flip")
        self._create_test_deal("buy_and_hold")

        kanban = self.service.get_kanban_data()
        assert "columns" in kanban
        assert "lead" in kanban["columns"]
        assert len(kanban["columns"]["lead"]) == 2

    def test_stats_include_monthly_rent(self) -> None:
        deal = self._create_test_deal("buy_and_hold")
        for target in ["oportunidade", "analise", "proposta", "negociacao",
                        "cpcv_compra", "escritura_compra", "arrendamento"]:
            deal = self.service.advance_deal(deal["id"], target)

        self.service.add_rental(deal["id"], {
            "monthly_rent": 2000,
        })

        # Re-fetch deal para ter monthly_rent actualizado
        stats = self.service.get_pipeline_stats()
        assert stats["total_monthly_rent"] == 2000
        assert stats["active_deals"] == 1
        assert stats["by_strategy"]["buy_and_hold"] == 1


# ---------------------------------------------------------------------------
# Mediacao — state machine
# ---------------------------------------------------------------------------


class TestMediationStateMachine:
    """Testa estados e transicoes de mediacao."""

    def test_mediation_strategies_exist(self) -> None:
        assert "mediacao_venda" in INVESTMENT_STRATEGIES
        assert "mediacao_arrendamento" in INVESTMENT_STRATEGIES
        assert "mediacao_compra" in INVESTMENT_STRATEGIES

    def test_mediation_role(self) -> None:
        assert is_mediation_strategy("mediacao_venda") is True
        assert is_mediation_strategy("mediacao_arrendamento") is True
        assert is_mediation_strategy("mediacao_compra") is True
        assert is_mediation_strategy("fix_and_flip") is False

    def test_mediation_statuses_exist(self) -> None:
        for s in ["angariacao", "cma", "acordo_mediacao", "marketing_activo",
                   "com_leads", "visitas_agendadas", "proposta_recebida", "em_partilha"]:
            assert s in DEAL_STATUSES
            assert s in STATUS_CONFIG

    def test_mediation_transitions(self) -> None:
        assert can_transition("lead", "angariacao")
        assert can_transition("angariacao", "cma")
        assert can_transition("cma", "acordo_mediacao")
        assert can_transition("acordo_mediacao", "marketing_activo")
        assert can_transition("marketing_activo", "com_leads")
        assert can_transition("com_leads", "visitas_agendadas")
        assert can_transition("visitas_agendadas", "proposta_recebida")
        assert can_transition("proposta_recebida", "negociacao")

    def test_mediacao_venda_route(self) -> None:
        route = STRATEGY_ROUTES["mediacao_venda"]
        assert route[0] == "lead"
        assert route[-1] == "concluido"
        assert "angariacao" in route
        assert "marketing_activo" in route
        assert "proposta_recebida" in route

    def test_mediacao_compra_route(self) -> None:
        route = STRATEGY_ROUTES["mediacao_compra"]
        assert "visitas_agendadas" in route
        assert "proposta" in route
        assert "escritura_compra" in route

    def test_mediation_auto_tasks(self) -> None:
        assert "angariacao" in AUTO_TASKS
        assert "cma" in AUTO_TASKS
        assert "acordo_mediacao" in AUTO_TASKS
        assert "marketing_activo" in AUTO_TASKS


# ---------------------------------------------------------------------------
# Mediacao — service
# ---------------------------------------------------------------------------


class TestMediationService:
    """Testa o service de mediacao com BD SQLite em memoria."""

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
            "src.modules.m4_deal_pipeline.service",
            fromlist=["DealPipelineService"],
        ).DealPipelineService()
        yield
        reset_engine()

    def _create_test_property(self) -> str:
        from uuid import uuid4
        from src.database.db import get_session
        from src.database.models_v2 import Property, Tenant
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
                id=str(uuid4()), tenant_id=tenant.id, source="test",
                country="PT", municipality="Oeiras", asking_price=380000,
                status="lead",
            )
            session.add(prop)
            session.flush()
            return prop.id

    def _create_mediation_deal(self) -> dict:
        prop_id = self._create_test_property()
        return self.service.create_mediation_deal({
            "property_id": prop_id,
            "investment_strategy": "mediacao_venda",
            "title": "T3 Oeiras — Mediacao venda",
            "owner_name": "Sr. Silva",
            "owner_phone": "+351912345678",
            "commission_pct": 5.0,
            "mediation_contract_type": "exclusivo",
        })

    def test_create_mediation_deal(self) -> None:
        deal = self._create_mediation_deal()
        assert deal["role"] == "mediador"
        assert deal["investment_strategy"] == "mediacao_venda"
        assert deal["owner_name"] == "Sr. Silva"
        assert deal["commission_pct"] == 5.0

    def test_mediation_deal_rejects_investor_strategy(self) -> None:
        prop_id = self._create_test_property()
        with pytest.raises(ValueError, match="nao e de mediacao"):
            self.service.create_mediation_deal({
                "property_id": prop_id,
                "investment_strategy": "fix_and_flip",
                "title": "Test",
                "commission_pct": 5.0,
            })

    def test_mediation_venda_full_route(self) -> None:
        """Pipeline: lead -> angariacao -> ... -> concluido."""
        deal = self._create_mediation_deal()
        route = [
            "angariacao", "cma", "acordo_mediacao",
            "marketing_activo", "com_leads", "visitas_agendadas",
            "proposta_recebida", "negociacao", "cpcv_compra",
            "escritura_compra", "concluido",
        ]
        for target in route:
            deal = self.service.advance_deal(deal["id"], target)
            assert deal["status"] == target
        assert deal["progress_pct"] == 100.0

    def test_generate_cma(self) -> None:
        deal = self._create_mediation_deal()
        comparables = [
            {"price": 350000, "area_m2": 100},
            {"price": 380000, "area_m2": 110},
            {"price": 400000, "area_m2": 105},
        ]
        cma = self.service.generate_cma(deal["id"], comparables)
        assert cma["min_value"] == 350000
        assert cma["max_value"] == 400000
        assert cma["estimated_value"] == 380000
        assert cma["comparables_count"] == 3
        assert cma["price_per_m2"] is not None

    def test_cma_with_recommended_price(self) -> None:
        deal = self._create_mediation_deal()
        cma = self.service.generate_cma(
            deal["id"],
            [{"price": 300000, "area_m2": 90}, {"price": 400000, "area_m2": 110}],
            recommended_price=360000,
        )
        assert cma["recommended_price"] == 360000

    def test_register_visit(self) -> None:
        from datetime import datetime, timezone
        deal = self._create_mediation_deal()
        visit = self.service.register_visit(deal["id"], {
            "visitor_name": "Familia Costa",
            "visitor_phone": "+351963456789",
            "visit_date": datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
            "visit_type": "presencial",
        })
        assert visit["visitor_name"] == "Familia Costa"
        assert visit["visit_type"] == "presencial"

    def test_update_visit_feedback(self) -> None:
        from datetime import datetime, timezone
        deal = self._create_mediation_deal()
        visit = self.service.register_visit(deal["id"], {
            "visitor_name": "Ana Silva",
            "visit_date": datetime(2026, 3, 16, 14, 0, tzinfo=timezone.utc),
        })
        updated = self.service.update_visit(visit["id"], {
            "interest_level": "alto",
            "feedback": "Gostou muito da cozinha",
            "wants_second_visit": True,
        })
        assert updated["interest_level"] == "alto"
        assert updated["wants_second_visit"] is True

    def test_list_visits(self) -> None:
        from datetime import datetime, timezone
        deal = self._create_mediation_deal()
        self.service.register_visit(deal["id"], {
            "visitor_name": "Visitante 1",
            "visit_date": datetime(2026, 3, 15, tzinfo=timezone.utc),
        })
        self.service.register_visit(deal["id"], {
            "visitor_name": "Visitante 2",
            "visit_date": datetime(2026, 3, 16, tzinfo=timezone.utc),
        })
        visits = self.service.list_visits(deal["id"])
        assert len(visits) == 2

    def test_commission_calculation(self) -> None:
        """5% de 300k = 15k bruto, 18.450 com IVA."""
        deal = self._create_mediation_deal()
        # Set target sale price
        self.service.update_deal(deal["id"], {"target_sale_price": 300000})
        calc = self.service.calculate_commission(deal["id"])
        assert calc["commission_pct"] == 5.0
        assert calc["commission_gross"] == 15000.0
        assert calc["commission_with_vat"] == 18450.0

    def test_commission_split(self) -> None:
        """Partilha 50/50: cada mediador recebe metade."""
        prop_id = self._create_test_property()
        deal = self.service.create_mediation_deal({
            "property_id": prop_id,
            "investment_strategy": "mediacao_venda",
            "title": "Test split",
            "commission_pct": 5.0,
            "commission_split_pct": 50.0,
            "commission_split_agent": "Outro Mediador",
        })
        self.service.update_deal(deal["id"], {"target_sale_price": 300000})
        calc = self.service.calculate_commission(deal["id"])
        assert calc["is_shared"] is True
        assert calc["share_pct"] == 50.0
        assert calc["my_commission"] == 9225.0  # 18450 * 50%
        assert calc["other_agent_commission"] == 9225.0

    def test_create_commission_record(self) -> None:
        deal = self._create_mediation_deal()
        record = self.service.create_commission_record(deal["id"], 380000)
        assert record["sale_price"] == 380000
        assert record["commission_gross"] == 19000.0  # 380k * 5%
        assert record["payment_status"] == "pendente"

    def test_mediation_stats(self) -> None:
        deal = self._create_mediation_deal()
        self.service.update_deal(deal["id"], {"target_sale_price": 380000})
        stats = self.service.get_mediation_stats()
        assert stats["active_mediations"] == 1
        assert stats["total_portfolio_value"] == 380000
        assert stats["potential_commission"] > 0

    def test_investor_and_mediator_coexist(self) -> None:
        """Deals de investidor e mediador coexistem."""
        # Criar deal investidor
        prop_id = self._create_test_property()
        inv_deal = self.service.create_deal({
            "property_id": prop_id,
            "investment_strategy": "fix_and_flip",
            "title": "Investimento test",
            "purchase_price": 200000,
        })
        # Criar deal mediacao
        med_deal = self._create_mediation_deal()

        # Kanban mostra ambos
        kanban = self.service.get_kanban_data()
        all_deals = []
        for col_deals in kanban["columns"].values():
            all_deals.extend(col_deals)
        assert len(all_deals) == 2
        roles = {d["role"] for d in all_deals}
        assert "investidor" in roles
        assert "mediador" in roles

        # Stats separados
        stats = self.service.get_pipeline_stats()
        assert stats["total_deals"] == 2
        med_stats = self.service.get_mediation_stats()
        assert med_stats["active_mediations"] == 1

    def test_auto_tasks_mediation(self) -> None:
        """Tasks automaticas na angariacao."""
        deal = self._create_mediation_deal()
        deal = self.service.advance_deal(deal["id"], "angariacao")
        upcoming = self.service.get_upcoming_tasks(limit=100)
        auto = [t for t in upcoming if t["deal_id"] == deal["id"]]
        assert len(auto) >= 3  # angariacao tem 3 auto-tasks
