"""Seed data para M4 — Deal Pipeline.

Cria dois deals de teste:
  1. Sacavem (fix_and_flip, status: cpcv_compra) — com historico e tasks
  2. Alapraia (buy_and_hold, status: arrendamento) — com DealRental

Uso:
    python -m scripts.seed_m4
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from loguru import logger

from src.database.db import get_session, init_db
from src.database.models import Base
from src.database.models_v2 import (
    Deal,
    DealCommission,
    DealRental,
    DealStateHistory,
    DealTask,
    DealVisit,
    Property,
    Tenant,
)

# Importar models_v2 para registar todas as tabelas
import src.database.models_v2  # noqa: F401

from src.database.db import _get_engine


def seed() -> None:
    """Popula a BD com dados de teste para M4."""
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)

    with get_session() as session:
        # Tenant default
        from sqlalchemy import select

        tenant = session.execute(
            select(Tenant).where(Tenant.slug == "default")
        ).scalar_one_or_none()

        if not tenant:
            tenant = Tenant(
                id=str(uuid4()),
                name="ImoIA",
                slug="default",
                country="PT",
            )
            session.add(tenant)
            session.flush()

        tid = tenant.id

        # ---------------------------------------------------------------
        # 1. Sacavem — Fix and Flip (status: cpcv_compra)
        # ---------------------------------------------------------------

        prop1_id = str(uuid4())
        prop1 = Property(
            id=prop1_id,
            tenant_id=tid,
            source="manual",
            country="PT",
            district="Lisboa",
            municipality="Loures",
            parish="Sacavem",
            property_type="apartamento",
            typology="T3",
            gross_area_m2=110.0,
            bedrooms=3,
            asking_price=295000,
            condition="para_renovar",
            status="cpcv_compra",
        )
        session.add(prop1)
        session.flush()

        deal1_id = str(uuid4())
        now = datetime.now(timezone.utc)
        deal1 = Deal(
            id=deal1_id,
            tenant_id=tid,
            property_id=prop1_id,
            investment_strategy="fix_and_flip",
            status="cpcv_compra",
            title="T3 Sacavem — Fix and Flip",
            purchase_price=295000,
            target_sale_price=500000,
            renovation_budget=98400,
            contact_name="Joao Silva",
            contact_phone="+351912345678",
            contact_role="mediador",
            is_financed=True,
            is_off_market=False,
            status_changed_at=now,
            notes="CPCV assinado. Reforco em Abril, escritura em Julho.",
            tags=["fix_and_flip", "sacavem", "grade_A"],
        )
        session.add(deal1)
        session.flush()

        # Historico: lead -> oportunidade -> analise -> proposta -> negociacao -> cpcv_compra
        transitions = [
            ("", "lead", "Deal criado"),
            ("lead", "oportunidade", "Merece investigacao"),
            ("oportunidade", "analise", "M2+M3 a correr"),
            ("analise", "proposta", "Proposta 280k enviada"),
            ("proposta", "negociacao", "Contraproposta 295k"),
            ("negociacao", "cpcv_compra", "CPCV assinado a 295k"),
        ]
        for from_s, to_s, reason in transitions:
            h = DealStateHistory(
                id=str(uuid4()),
                tenant_id=tid,
                deal_id=deal1_id,
                from_status=from_s,
                to_status=to_s,
                changed_by="system",
                reason=reason,
            )
            session.add(h)

        # Tasks
        tasks_sacavem = [
            ("Reforco sinal — Abril 2026", "high", "2026-04-15"),
            ("Escritura compra — Julho 2026", "high", "2026-07-01"),
            ("Inicio obra — Agosto 2026", "medium", "2026-08-01"),
            ("Obter certidao predial", "high", None),
            ("Agendar reforco", "medium", None),
        ]
        for title, priority, due in tasks_sacavem:
            t = DealTask(
                id=str(uuid4()),
                tenant_id=tid,
                deal_id=deal1_id,
                title=title,
                task_type="auto" if due is None else "manual",
                priority=priority,
                due_date=datetime.fromisoformat(due) if due else None,
            )
            session.add(t)

        # ---------------------------------------------------------------
        # 2. Alapraia — Buy and Hold (status: arrendamento)
        # ---------------------------------------------------------------

        prop2_id = str(uuid4())
        prop2 = Property(
            id=prop2_id,
            tenant_id=tid,
            source="manual",
            country="PT",
            district="Lisboa",
            municipality="Cascais",
            parish="Alapraia",
            property_type="apartamento",
            typology="T2",
            gross_area_m2=85.0,
            bedrooms=2,
            asking_price=280000,
            condition="bom_estado",
            status="arrendamento",
        )
        session.add(prop2)
        session.flush()

        deal2_id = str(uuid4())
        deal2 = Deal(
            id=deal2_id,
            tenant_id=tid,
            property_id=prop2_id,
            investment_strategy="buy_and_hold",
            status="arrendamento",
            title="T2 Alapraia — Buy and Hold",
            purchase_price=280000,
            monthly_rent=2100,
            is_financed=True,
            status_changed_at=now,
            notes="Arrendado desde Janeiro 2026.",
            tags=["buy_and_hold", "cascais", "arrendado"],
        )
        session.add(deal2)
        session.flush()

        # Historico buy_and_hold
        transitions2 = [
            ("", "lead", "Deal criado"),
            ("lead", "oportunidade", None),
            ("oportunidade", "analise", None),
            ("analise", "proposta", "Proposta 275k"),
            ("proposta", "negociacao", None),
            ("negociacao", "cpcv_compra", "CPCV a 280k"),
            ("cpcv_compra", "escritura_compra", "Escritura feita"),
            ("escritura_compra", "arrendamento", "Arrendado a 2100/mes"),
        ]
        for from_s, to_s, reason in transitions2:
            h = DealStateHistory(
                id=str(uuid4()),
                tenant_id=tid,
                deal_id=deal2_id,
                from_status=from_s,
                to_status=to_s,
                changed_by="system",
                reason=reason,
            )
            session.add(h)

        # Rental
        rental = DealRental(
            id=str(uuid4()),
            tenant_id=tid,
            deal_id=deal2_id,
            rental_type="longa_duracao",
            monthly_rent=2100,
            deposit_months=2,
            tenant_name="Maria Costa",
            tenant_phone="+351963456789",
            tenant_email="maria.costa@email.pt",
            lease_start=datetime(2026, 1, 15, tzinfo=timezone.utc),
            lease_end=datetime(2027, 1, 14, tzinfo=timezone.utc),
            lease_duration_months=12,
            condominio_monthly=85,
            imi_annual=620,
            insurance_annual=250,
            management_fee_pct=0,
            status="activo",
        )
        session.add(rental)

        # ---------------------------------------------------------------
        # 3. Oeiras — Mediacao Venda (status: marketing_activo)
        # ---------------------------------------------------------------

        prop3_id = str(uuid4())
        prop3 = Property(
            id=prop3_id,
            tenant_id=tid,
            source="manual",
            country="PT",
            district="Lisboa",
            municipality="Oeiras",
            parish="Oeiras e Sao Juliao da Barra",
            property_type="apartamento",
            typology="T3",
            gross_area_m2=120.0,
            bedrooms=3,
            asking_price=380000,
            condition="bom_estado",
            status="marketing_activo",
        )
        session.add(prop3)
        session.flush()

        deal3_id = str(uuid4())
        deal3 = Deal(
            id=deal3_id,
            tenant_id=tid,
            property_id=prop3_id,
            investment_strategy="mediacao_venda",
            status="marketing_activo",
            title="T3 Oeiras — Mediacao venda",
            role="mediador",
            target_sale_price=380000,
            owner_name="Sr. Antonio Silva",
            owner_phone="+351912345678",
            owner_email="antonio.silva@email.pt",
            mediation_contract_type="exclusivo",
            mediation_contract_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
            mediation_contract_expiry=datetime(2026, 8, 1, tzinfo=timezone.utc),
            commission_pct=5.0,
            commission_vat_included=False,
            cma_estimated_value=375000,
            cma_min_value=350000,
            cma_max_value=410000,
            cma_recommended_price=380000,
            cma_date=datetime(2026, 2, 5, tzinfo=timezone.utc),
            contact_name="Sr. Antonio Silva",
            contact_phone="+351912345678",
            status_changed_at=now,
            notes="Exclusivo 6 meses. Proprietario motivado.",
            tags=["mediacao", "oeiras", "exclusivo"],
        )
        session.add(deal3)
        session.flush()

        # Historico mediacao
        transitions3 = [
            ("", "lead", "Deal mediacao criado"),
            ("lead", "angariacao", "Contacto com proprietario"),
            ("angariacao", "cma", "CMA em preparacao"),
            ("cma", "acordo_mediacao", "CMI assinado — exclusivo 6 meses"),
            ("acordo_mediacao", "marketing_activo", "Anuncios publicados"),
        ]
        for from_s, to_s, reason in transitions3:
            h = DealStateHistory(
                id=str(uuid4()),
                tenant_id=tid,
                deal_id=deal3_id,
                from_status=from_s,
                to_status=to_s,
                changed_by="system",
                reason=reason,
            )
            session.add(h)

        # Visitas
        visit1 = DealVisit(
            id=str(uuid4()),
            tenant_id=tid,
            deal_id=deal3_id,
            visitor_name="Familia Costa",
            visitor_phone="+351963456789",
            visit_date=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
            visit_type="presencial",
            duration_minutes=45,
            interest_level="alto",
            feedback="Gostaram muito da cozinha. Preocupados com estacionamento.",
            wants_second_visit=True,
            accompanied_by="Maya Ferro",
        )
        session.add(visit1)

        visit2 = DealVisit(
            id=str(uuid4()),
            tenant_id=tid,
            deal_id=deal3_id,
            visitor_name="Joao Mendes",
            visitor_phone="+351934567890",
            visit_date=datetime(2026, 3, 17, 14, 30, tzinfo=timezone.utc),
            visit_type="presencial",
            duration_minutes=30,
            interest_level="medio",
            feedback="Achou pequeno para familia de 4.",
            wants_second_visit=False,
            accompanied_by="Maya Ferro",
        )
        session.add(visit2)

        session.flush()
        logger.info(
            f"Seed M4 concluido: "
            f"Sacavem ({deal1_id}), Alapraia ({deal2_id}), "
            f"Oeiras mediacao ({deal3_id})"
        )


if __name__ == "__main__":
    seed()
