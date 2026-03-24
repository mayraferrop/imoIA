"""Testes para os novos modelos em models_v2.py."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base
from src.database.models_v2 import (
    CalendarEvent,
    ClosingProcess,
    Deal,
    DealPnL,
    DealStateHistory,
    Document,
    DueDiligenceItem,
    FinancialModel,
    Lead,
    LeadInteraction,
    Listing,
    Notification,
    Property,
    Proposal,
    Renovation,
    RenovationExpense,
    Tenant,
    Transaction,
    User,
)


@pytest.fixture()
def db_session():
    """Cria BD em memoria para testes."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def tenant_id(db_session: Session) -> str:
    """Cria e retorna um tenant de teste."""
    tenant = Tenant(
        id=str(uuid4()),
        name="Teste",
        slug="teste",
        country="PT",
    )
    db_session.add(tenant)
    db_session.commit()
    return tenant.id


def test_create_tenant(db_session: Session) -> None:
    """Cria um tenant e verifica que foi guardado."""
    t = Tenant(id=str(uuid4()), name="Test", slug="test", country="PT")
    db_session.add(t)
    db_session.commit()

    result = db_session.execute(select(Tenant)).scalar_one()
    assert result.name == "Test"
    assert result.slug == "test"


def test_create_user(db_session: Session, tenant_id: str) -> None:
    """Cria um user associado a um tenant."""
    u = User(
        id=str(uuid4()),
        tenant_id=tenant_id,
        email="test@test.com",
        name="Teste",
        role="investor",
    )
    db_session.add(u)
    db_session.commit()

    result = db_session.execute(select(User)).scalar_one()
    assert result.email == "test@test.com"
    assert result.tenant_id == tenant_id


def test_create_property(db_session: Session, tenant_id: str) -> None:
    """Cria uma property com todos os campos principais."""
    p = Property(
        id=str(uuid4()),
        tenant_id=tenant_id,
        source="manual",
        country="PT",
        district="Lisboa",
        municipality="Cascais",
        property_type="moradia",
        asking_price=350000,
        gross_area_m2=150,
        bedrooms=3,
        condition="para_renovar",
        status="lead",
        is_off_market=True,
        tags=["heranca", "off_market"],
    )
    db_session.add(p)
    db_session.commit()

    result = db_session.execute(select(Property)).scalar_one()
    assert result.municipality == "Cascais"
    assert result.asking_price == 350000
    assert result.is_off_market is True
    assert "heranca" in result.tags


def test_all_stub_models_create(
    db_session: Session, tenant_id: str
) -> None:
    """Verifica que todos os stubs M2-M9 criam registos."""
    prop = Property(
        id=str(uuid4()),
        tenant_id=tenant_id,
        source="test",
        status="lead",
    )
    db_session.add(prop)
    db_session.flush()

    deal = Deal(
        id=str(uuid4()),
        tenant_id=tenant_id,
        property_id=prop.id,
        investment_strategy="fix_and_flip",
        status="lead",
        title="Test Deal",
    )
    db_session.add(deal)
    db_session.flush()

    # Criar um registo de cada stub
    stubs = [
        FinancialModel(
            tenant_id=tenant_id, property_id=prop.id, scenario_name="test"
        ),
        Proposal(tenant_id=tenant_id, deal_id=deal.id, amount=175000),
        DealStateHistory(
            tenant_id=tenant_id, deal_id=deal.id, from_status="lead",
            to_status="oportunidade",
        ),
        DueDiligenceItem(
            tenant_id=tenant_id, deal_id=deal.id,
            category="legal", item_name="Certidao predial",
            item_key="certidao_predial",
        ),
        Renovation(
            tenant_id=tenant_id, deal_id=deal.id, initial_budget=35000,
        ),
        Listing(
            tenant_id=tenant_id, deal_id=deal.id,
            listing_type="venda", listing_price=280000,
        ),
        Lead(tenant_id=tenant_id, name="Test Lead"),
        Transaction(
            tenant_id=tenant_id, property_id=prop.id,
            transaction_type="purchase", amount=180000,
        ),
        ClosingProcess(
            tenant_id=tenant_id, deal_id=deal.id,
            property_id=prop.id, closing_type="compra",
        ),
        DealPnL(
            tenant_id=tenant_id, deal_id=deal.id, property_id=prop.id,
        ),
        CalendarEvent(tenant_id=tenant_id, property_id=prop.id),
        Document(
            tenant_id=tenant_id, deal_id=deal.id,
            filename="test.pdf", stored_filename="test_123.pdf",
            file_path="/tmp/test_123.pdf",
        ),
        Notification(tenant_id=tenant_id, property_id=prop.id),
    ]

    for stub in stubs:
        db_session.add(stub)

    db_session.commit()

    # Verificar que todos foram criados
    for model_class in [
        FinancialModel, Proposal, DealStateHistory, DueDiligenceItem,
        Renovation, Listing, Lead, Transaction, ClosingProcess, DealPnL,
        CalendarEvent, Document, Notification,
    ]:
        count = db_session.execute(
            select(model_class)
        ).scalars().all()
        assert len(count) >= 1, f"{model_class.__name__} nao foi criado"
