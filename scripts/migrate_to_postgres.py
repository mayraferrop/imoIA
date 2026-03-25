#!/usr/bin/env python3
"""Migracao dos dados legacy (SQLite) para PostgreSQL (Supabase).

Pode ser executado multiplas vezes (idempotente).

Uso:
    python scripts/migrate_to_postgres.py --pg-url postgresql://user:pass@host/db

Etapas:
    1. Le todas as tabelas do SQLite
    2. Cria um tenant "default" no PostgreSQL
    3. Migra groups, messages, opportunities, market_data
    4. Cria Property para cada Opportunity com is_opportunity=true
    5. Cria as novas tabelas (models_v2) no PostgreSQL
    6. Valida contagens: SQLite vs PostgreSQL
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import uuid4

# Garantir que o projecto esta no sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.database.migrations import export_all_data, validate_migration
from src.database.models import Base as ExistingBase
from src.database.models_v2 import (
    Base,
    Property,
    Tenant,
)


def main() -> None:
    """Executa a migracao."""
    parser = argparse.ArgumentParser(description="Migrar SQLite para PostgreSQL")
    parser.add_argument("--pg-url", required=True, help="URL do PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostrar o que seria feito")
    args = parser.parse_args()

    logger.info(f"Migracao SQLite → PostgreSQL iniciada")
    logger.info(f"Destino: {args.pg_url[:30]}...")

    # 1. Exportar dados do SQLite
    logger.info("Etapa 1: A exportar dados do SQLite...")
    data = export_all_data()

    sqlite_counts = {
        "groups": len(data["groups"]),
        "messages": len(data["messages"]),
        "opportunities": len(data["opportunities"]),
        "market_data": len(data["market_data"]),
    }

    if args.dry_run:
        logger.info(f"DRY RUN — dados a migrar: {sqlite_counts}")
        return

    # 2. Conectar ao PostgreSQL e criar tabelas
    logger.info("Etapa 2: A criar tabelas no PostgreSQL...")
    pg_engine = create_engine(args.pg_url)
    ExistingBase.metadata.create_all(bind=pg_engine)
    Base.metadata.create_all(bind=pg_engine)

    PgSession = sessionmaker(bind=pg_engine)

    # 3. Criar tenant default
    logger.info("Etapa 3: A criar tenant default...")
    with PgSession() as session:
        existing_tenant = session.execute(
            text("SELECT id FROM tenants WHERE slug = 'default'")
        ).fetchone()

        if existing_tenant:
            tenant_id = existing_tenant[0]
            logger.info(f"Tenant default ja existe: {tenant_id}")
        else:
            tenant_id = str(uuid4())
            tenant = Tenant(
                id=tenant_id,
                name="ImoIA",
                slug="default",
                country="PT",
            )
            session.add(tenant)
            session.commit()
            logger.info(f"Tenant default criado: {tenant_id}")

    # 4-6: TODO — implementar insercao de dados no PostgreSQL
    # (a completar quando for hora de migrar)
    logger.info(
        "Etapas 4-6: Insercao de dados — TODO quando migrar para Supabase. "
        f"Dados prontos para migracao: {sqlite_counts}"
    )

    logger.info("Migracao concluida (estrutura criada, dados pendentes)")


if __name__ == "__main__":
    main()
