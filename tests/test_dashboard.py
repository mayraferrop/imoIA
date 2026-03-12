"""Testes para o dashboard Streamlit do ImoScout.

Testa funcoes de query, filtragem e helpers usando BD SQLite in-memory.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database import db as db_module
from src.database.models import Base, Group, MarketData, Message, Opportunity


@pytest.fixture()
def in_memory_db(monkeypatch: pytest.MonkeyPatch):
    """Configura BD SQLite in-memory para testes."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    test_session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    monkeypatch.setattr(db_module, "_engine", engine)
    monkeypatch.setattr(db_module, "_SessionLocal", test_session_factory)

    yield engine

    engine.dispose()


@pytest.fixture()
def seeded_db(in_memory_db) -> None:
    """Popula a BD in-memory com dados de teste."""
    factory = db_module._SessionLocal
    session = factory()
    try:
        group = Group(
            whatsapp_group_id="g1",
            name="Partilhas AML",
            is_active=True,
            last_processed_at=datetime.now(),
            message_count=5,
            opportunity_count=3,
        )
        session.add(group)
        session.flush()

        now = datetime.now()

        msg1 = Message(
            whatsapp_message_id="m1",
            group_id=group.id,
            group_name="Partilhas AML",
            content="T2 em Sacavem, 85m2, remodelado. Preco: 195.000 EUR.",
            timestamp=now - timedelta(hours=2),
        )
        msg2 = Message(
            whatsapp_message_id="m2",
            group_id=group.id,
            group_name="Partilhas AML",
            content="URGENTE - Divorcio T3 Almada 180.000 EUR",
            timestamp=now - timedelta(hours=1),
        )
        msg3 = Message(
            whatsapp_message_id="m3",
            group_id=group.id,
            group_name="Partilhas AML",
            content="Moradia T4 Cascais heranca 420.000 EUR",
            timestamp=now,
        )
        session.add_all([msg1, msg2, msg3])
        session.flush()

        opp1 = Opportunity(
            message_id=msg1.id,
            is_opportunity=True,
            confidence=0.75,
            opportunity_type="abaixo_mercado",
            property_type="apartamento",
            location_extracted="Sacavem",
            municipality="Loures",
            district="Lisboa",
            price_mentioned=195000.0,
            area_m2=85.0,
            bedrooms=2,
            ai_reasoning="Preco abaixo da mediana para a zona.",
            original_message="T2 em Sacavem, 85m2, remodelado. Preco: 195.000 EUR.",
            status="nova",
            created_at=now - timedelta(hours=2),
        )
        opp2 = Opportunity(
            message_id=msg2.id,
            is_opportunity=True,
            confidence=0.92,
            opportunity_type="divorcio",
            property_type="apartamento",
            location_extracted="Almada, Pragal",
            municipality="Almada",
            district="Setubal",
            price_mentioned=180000.0,
            area_m2=110.0,
            bedrooms=3,
            ai_reasoning="Venda urgente por divorcio, preco negociavel.",
            original_message="URGENTE - Divorcio T3 Almada 180.000 EUR",
            status="nova",
            created_at=now - timedelta(hours=1),
        )
        opp3 = Opportunity(
            message_id=msg3.id,
            is_opportunity=True,
            confidence=0.88,
            opportunity_type="heranca",
            property_type="moradia",
            location_extracted="Cascais, Sao Domingos de Rana",
            municipality="Cascais",
            district="Lisboa",
            price_mentioned=420000.0,
            area_m2=200.0,
            bedrooms=4,
            ai_reasoning="Heranca com venda rapida.",
            original_message="Moradia T4 Cascais heranca 420.000 EUR",
            status="interessante",
            created_at=now,
        )
        session.add_all([opp1, opp2, opp3])
        session.flush()

        md1 = MarketData(
            opportunity_id=opp1.id,
            ine_median_price_m2=2500.0,
            idealista_avg_price_m2=2800.0,
            idealista_listings_count=15,
            estimated_market_value=212500.0,
            estimated_monthly_rent=850.0,
            gross_yield_pct=5.2,
            net_yield_pct=3.8,
            price_vs_market_pct=-8.2,
            imt_estimate=3500.0,
            stamp_duty_estimate=1560.0,
            total_acquisition_cost=200060.0,
        )
        session.add(md1)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class TestImport:
    """Verifica que o modulo do dashboard importa sem erros."""

    def test_import_app(self) -> None:
        """O modulo app.py deve importar corretamente."""
        from src.dashboard import app

        assert hasattr(app, "main")
        assert hasattr(app, "fetch_opportunities")
        assert hasattr(app, "page_dashboard")
        assert hasattr(app, "page_pipeline")
        assert hasattr(app, "page_configuracao")
        assert hasattr(app, "page_grupos")

    def test_import_constants(self) -> None:
        """As constantes devem estar definidas."""
        from src.dashboard.app import (
            OPPORTUNITY_TYPES,
            PROPERTY_TYPES,
            STATUS_OPTIONS,
            COLORS,
        )

        assert len(OPPORTUNITY_TYPES) == 13
        assert len(PROPERTY_TYPES) == 7
        assert len(STATUS_OPTIONS) == 5
        assert "primary" in COLORS
        assert "bg_dark" in COLORS

    def test_import_design_system(self) -> None:
        """Design system deve estar definido."""
        from src.dashboard.app import CUSTOM_CSS, PLOTLY_LAYOUT

        assert "Cinzel" in CUSTOM_CSS
        assert "Josefin Sans" in CUSTOM_CSS
        assert "paper_bgcolor" in PLOTLY_LAYOUT


class TestHelpers:
    """Testa funcoes auxiliares de apresentacao."""

    def test_confidence_badge_high(self) -> None:
        """Badge alta para confianca > 0.8."""
        from src.dashboard.app import _confidence_badge

        badge = _confidence_badge(0.95)
        assert "badge-confidence-high" in badge
        assert "95%" in badge
        assert "Alta" in badge

    def test_confidence_badge_medium(self) -> None:
        """Badge media para confianca entre 0.6 e 0.8."""
        from src.dashboard.app import _confidence_badge

        badge = _confidence_badge(0.7)
        assert "badge-confidence-mid" in badge
        assert "70%" in badge
        assert "Media" in badge

    def test_confidence_badge_low(self) -> None:
        """Badge baixa para confianca < 0.6."""
        from src.dashboard.app import _confidence_badge

        badge = _confidence_badge(0.4)
        assert "badge-confidence-low" in badge
        assert "40%" in badge
        assert "Baixa" in badge

    def test_status_badge(self) -> None:
        """Badges de status com classes corretas."""
        from src.dashboard.app import _status_badge

        badge_nova = _status_badge("nova")
        assert "badge-status-nova" in badge_nova
        assert "Nova" in badge_nova

        badge_int = _status_badge("interessante")
        assert "badge-status-interessante" in badge_int

    def test_format_price(self) -> None:
        """Formatacao de preco em euros."""
        from src.dashboard.app import _format_price

        assert _format_price(195000.0) == "195.000 EUR"
        assert _format_price(None) == "N/D"
        assert _format_price(1500000.0) == "1.500.000 EUR"

    def test_mask_key(self) -> None:
        """Mascara chaves API corretamente."""
        from src.dashboard.app import _mask_key

        result = _mask_key("sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "*" in result
        assert _mask_key("abc") == "abc"
        assert _mask_key("") == ""


class TestFetchOpportunities:
    """Testa queries de oportunidades com filtros."""

    def test_fetch_all(self, seeded_db: None) -> None:
        """Busca todas as oportunidades sem filtros."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities()
        assert len(results) == 3

    def test_fetch_with_min_confidence(self, seeded_db: None) -> None:
        """Filtra por confianca minima."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities(min_confidence=0.85)
        assert len(results) == 2
        assert all(r["confidence"] >= 0.85 for r in results)

    def test_fetch_by_opportunity_type(self, seeded_db: None) -> None:
        """Filtra por tipo de oportunidade."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities(opportunity_types=["divorcio"])
        assert len(results) == 1
        assert results[0]["opportunity_type"] == "divorcio"

    def test_fetch_by_property_type(self, seeded_db: None) -> None:
        """Filtra por tipo de imovel."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities(property_types=["moradia"])
        assert len(results) == 1
        assert results[0]["property_type"] == "moradia"

    def test_fetch_by_district(self, seeded_db: None) -> None:
        """Filtra por distrito."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities(districts=["Lisboa"])
        assert len(results) == 2

    def test_fetch_by_municipality(self, seeded_db: None) -> None:
        """Filtra por concelho."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities(municipalities=["Almada"])
        assert len(results) == 1

    def test_fetch_by_status(self, seeded_db: None) -> None:
        """Filtra por status."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities(statuses=["interessante"])
        assert len(results) == 1
        assert results[0]["status"] == "interessante"

    def test_fetch_combined_filters(self, seeded_db: None) -> None:
        """Filtra com multiplos criterios."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities(
            min_confidence=0.8,
            districts=["Lisboa"],
        )
        assert len(results) == 1
        assert results[0]["municipality"] == "Cascais"

    def test_fetch_returns_market_data(self, seeded_db: None) -> None:
        """Verifica que dados de mercado sao incluidos."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities(municipalities=["Loures"])
        assert len(results) == 1
        opp = results[0]
        assert opp["ine_median_price_m2"] == 2500.0
        assert opp["idealista_avg_price_m2"] == 2800.0
        assert opp["gross_yield_pct"] == 5.2
        assert opp["price_vs_market_pct"] == -8.2
        assert opp["total_acquisition_cost"] == 200060.0

    def test_fetch_empty_db(self, in_memory_db) -> None:
        """BD vazia retorna lista vazia."""
        from src.dashboard.app import fetch_opportunities

        results = fetch_opportunities()
        assert results == []


class TestFilterOptions:
    """Testa opcoes de filtro dinamicas."""

    def test_fetch_filter_options(self, seeded_db: None) -> None:
        """Distritos e concelhos populados da BD."""
        from src.dashboard.app import fetch_filter_options

        options = fetch_filter_options()
        assert "Lisboa" in options["districts"]
        assert "Setubal" in options["districts"]
        assert "Almada" in options["municipalities"]
        assert "Cascais" in options["municipalities"]
        assert "Loures" in options["municipalities"]

    def test_fetch_filter_options_empty(self, in_memory_db) -> None:
        """BD vazia retorna listas vazias."""
        from src.dashboard.app import fetch_filter_options

        options = fetch_filter_options()
        assert options["districts"] == []
        assert options["municipalities"] == []


class TestAggregationQueries:
    """Testa queries de agregacao para metricas e graficos."""

    def test_fetch_daily_counts(self, seeded_db: None) -> None:
        """Contagem diaria de oportunidades."""
        from src.dashboard.app import fetch_daily_counts

        data = fetch_daily_counts(days=7)
        assert len(data) > 0
        assert all("day" in d and "total" in d for d in data)

    def test_fetch_type_distribution(self, seeded_db: None) -> None:
        """Distribuicao por tipo de oportunidade."""
        from src.dashboard.app import fetch_type_distribution

        data = fetch_type_distribution()
        assert len(data) == 3
        types = [d["type"] for d in data]
        assert "divorcio" in types
        assert "heranca" in types

    def test_fetch_top_municipalities(self, seeded_db: None) -> None:
        """Top concelhos."""
        from src.dashboard.app import fetch_top_municipalities

        data = fetch_top_municipalities(limit=10)
        assert len(data) == 3
        assert all("municipality" in d and "total" in d for d in data)

    def test_aggregation_empty_db(self, in_memory_db) -> None:
        """Queries de agregacao com BD vazia."""
        from src.dashboard.app import (
            fetch_daily_counts,
            fetch_top_municipalities,
            fetch_type_distribution,
        )

        assert fetch_daily_counts() == []
        assert fetch_type_distribution() == []
        assert fetch_top_municipalities() == []


class TestUpdateStatus:
    """Testa atualizacao de status de oportunidades."""

    def test_update_status(self, seeded_db: None) -> None:
        """Atualiza status de uma oportunidade."""
        from src.dashboard.app import fetch_opportunities, update_opportunity_status

        opps = fetch_opportunities()
        target_id = opps[0]["id"]

        update_opportunity_status(target_id, "contactada")

        updated = fetch_opportunities(statuses=["contactada"])
        assert any(o["id"] == target_id for o in updated)

    def test_update_nonexistent(self, in_memory_db) -> None:
        """Atualizar ID inexistente nao levanta excepcao."""
        from src.dashboard.app import update_opportunity_status

        update_opportunity_status(99999, "descartada")


class TestTodayMetrics:
    """Testa metricas do dia."""

    def test_today_metrics_with_data(self, seeded_db: None) -> None:
        """Metricas do dia com dados existentes."""
        from src.dashboard.app import fetch_today_metrics

        metrics = fetch_today_metrics()
        assert "total_today" in metrics
        assert "avg_confidence" in metrics
        assert "groups_today" in metrics
        assert "best_confidence" in metrics
        assert "total_all" in metrics
        assert metrics["total_all"] == 3

    def test_today_metrics_empty_db(self, in_memory_db) -> None:
        """Metricas do dia com BD vazia."""
        from src.dashboard.app import fetch_today_metrics

        metrics = fetch_today_metrics()
        assert metrics["total_today"] == 0
        assert metrics["avg_confidence"] is None
        assert metrics["groups_today"] == 0
        assert metrics["best_confidence"] is None


class TestGroups:
    """Testa funcoes de gestao de grupos."""

    def test_fetch_groups(self, seeded_db: None) -> None:
        """Busca todos os grupos."""
        from src.dashboard.app import fetch_groups

        groups = fetch_groups()
        assert len(groups) == 1
        assert groups[0]["name"] == "Partilhas AML"
        assert groups[0]["is_active"] is True
        assert groups[0]["message_count"] == 5

    def test_fetch_groups_empty(self, in_memory_db) -> None:
        """BD vazia retorna lista vazia de grupos."""
        from src.dashboard.app import fetch_groups

        groups = fetch_groups()
        assert groups == []

    def test_toggle_group_active(self, seeded_db: None) -> None:
        """Desativa e reativa um grupo."""
        from src.dashboard.app import fetch_groups, toggle_group_active

        groups = fetch_groups()
        group_id = groups[0]["id"]

        toggle_group_active(group_id, False)
        updated = fetch_groups()
        assert updated[0]["is_active"] is False

        toggle_group_active(group_id, True)
        updated = fetch_groups()
        assert updated[0]["is_active"] is True


class TestEnvConfig:
    """Testa funcoes de configuracao .env."""

    def test_mask_key_long(self) -> None:
        """Mascara chaves longas."""
        from src.dashboard.app import _mask_key

        result = _mask_key("sk-ant-api03-1234567890abcdefghij")
        assert result.startswith("sk-a")
        assert result.endswith("ghij")
        assert "*" in result

    def test_mask_key_short(self) -> None:
        """Chaves curtas nao sao mascaradas."""
        from src.dashboard.app import _mask_key

        assert _mask_key("short") == "short"

    def test_load_save_env(self, tmp_path) -> None:
        """Guarda e carrega valores .env."""
        from src.dashboard import app as app_module

        env_file = tmp_path / ".env"
        original_fn = app_module._env_path
        app_module._env_path = lambda: env_file

        try:
            values = {"KEY1": "value1", "KEY2": "value2"}
            app_module._save_env_values(values)

            loaded = app_module._load_env_values()
            assert loaded["KEY1"] == "value1"
            assert loaded["KEY2"] == "value2"
        finally:
            app_module._env_path = original_fn
