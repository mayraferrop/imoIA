#!/usr/bin/env python3
"""Seed de dados de desenvolvimento para o ImoIA.

Cria um tenant default e algumas properties de teste.

Uso:
    python scripts/seed_dev.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from loguru import logger

from src.database.db import get_session, init_db
from src.database.models import Base
from src.database.models_v2 import Property, Tenant

# Importar models_v2 para registar no metadata
import src.database.models_v2  # noqa: F401
from src.database.db import _get_engine


def seed() -> None:
    """Cria dados de desenvolvimento."""
    init_db()
    Base.metadata.create_all(bind=_get_engine())

    with get_session() as session:
        # Tenant
        from sqlalchemy import select

        tenant = session.execute(
            select(Tenant).where(Tenant.slug == "default")
        ).scalar_one_or_none()

        if not tenant:
            tenant = Tenant(
                id=str(uuid4()),
                name="ImoIA Dev",
                slug="default",
                country="PT",
            )
            session.add(tenant)
            session.flush()
            logger.info(f"Tenant criado: {tenant.id}")
        else:
            logger.info(f"Tenant ja existe: {tenant.id}")

        # Properties de teste
        test_properties = [
            {
                "district": "Lisboa",
                "municipality": "Lisboa",
                "parish": "Mouraria",
                "property_type": "predio",
                "asking_price": 650000,
                "gross_area_m2": 400,
                "condition": "para_renovar",
                "is_off_market": True,
                "tags": ["reabilitacao", "off_market", "grade_C"],
                "notes": "Predio inteiro em Mouraria, 4 fraccoes",
            },
            {
                "district": "Lisboa",
                "municipality": "Cascais",
                "parish": "Sao Domingos de Rana",
                "property_type": "moradia",
                "asking_price": 420000,
                "gross_area_m2": 200,
                "bedrooms": 4,
                "condition": "para_renovar",
                "is_off_market": True,
                "tags": ["heranca", "off_market", "urgente"],
                "notes": "Moradia T4 em heranca, familia quer resolver rapido",
            },
        ]

        for data in test_properties:
            prop = Property(
                id=str(uuid4()),
                tenant_id=tenant.id,
                source="seed",
                country="PT",
                status="lead",
                **data,
            )
            session.add(prop)

        logger.info(f"{len(test_properties)} properties de teste criadas")

    logger.info("Seed concluido")


if __name__ == "__main__":
    seed()
