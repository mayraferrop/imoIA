"""Gestão da sessão de base de dados SQLAlchemy 2.0.

Fornece o engine, a session factory e a função de inicialização.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Optional
from urllib.parse import quote_plus, urlparse

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.database.models import Base

_engine = None
_SessionLocal = None
_default_org_id: Optional[str] = None


def _get_engine():
    """Cria ou retorna o engine SQLAlchemy (PostgreSQL via Supabase)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.database_url

        if not db_url:
            raise ValueError(
                "DATABASE_URL não configurado. "
                "Defina no .env: postgresql://user.ref:pass@host:6543/postgres"
            )

        # Garantir que a password está URL-encoded (caracteres especiais como @)
        parsed = urlparse(db_url)
        if parsed.password and "%" not in parsed.password:
            encoded_pw = quote_plus(parsed.password)
            db_url = db_url.replace(f":{parsed.password}@", f":{encoded_pw}@", 1)

        # Pool settings para Supabase Transaction pooler
        _engine = create_engine(
            db_url,
            echo=False,
            pool_size=2,
            max_overflow=3,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        logger.info(f"Engine SQLAlchemy criado: {db_url[:50]}...")
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    """Cria ou retorna a session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), expire_on_commit=False)
    return _SessionLocal


def _sync_sequences(engine) -> None:
    """Sincroniza sequences do PostgreSQL com o max(id) de cada tabela.

    Evita erros de duplicate key quando a sequence está dessincronizada
    (ex: dados importados sem passar pelo auto-increment).
    """
    tables = ["messages", "groups", "opportunities", "market_data"]
    try:
        with engine.connect() as conn:
            for table in tables:
                conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE(MAX(id), 1)) FROM {table}"
                ))
            conn.commit()
        logger.info("Sequences PostgreSQL sincronizadas")
    except Exception as e:
        logger.warning(f"Aviso ao sincronizar sequences: {e}")


def _apply_migrations(engine) -> None:
    """Aplica migracoes incrementais (ALTER TABLE) para colunas em falta."""
    migrations = [
        ("financial_models", "tir_anual_pct", "ALTER TABLE financial_models ADD COLUMN tir_anual_pct FLOAT DEFAULT 0"),
        ("financial_models", "loan_pct_purchase", "ALTER TABLE financial_models ADD COLUMN loan_pct_purchase FLOAT DEFAULT 0"),
        ("financial_models", "loan_pct_renovation", "ALTER TABLE financial_models ADD COLUMN loan_pct_renovation FLOAT DEFAULT 0"),
    ]
    try:
        with engine.connect() as conn:
            for table, col, sql in migrations:
                try:
                    conn.execute(text(sql))
                    logger.info(f"Migracao aplicada: {table}.{col}")
                except Exception:
                    pass  # Coluna ja existe
            conn.commit()
    except Exception as e:
        logger.debug(f"Migracoes ignoradas: {e}")


def init_db() -> None:
    """Inicializa a base de dados — cria todas as tabelas."""
    engine = _get_engine()
    try:
        Base.metadata.create_all(bind=engine)
        _apply_migrations(engine)
        _sync_sequences(engine)
        logger.info("Base de dados inicializada com sucesso")
    except Exception as e:
        logger.warning(f"Aviso ao criar tabelas (podem ja existir): {e}")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager para sessões de base de dados.

    Exemplo:
        with get_session() as session:
            result = session.execute(select(Opportunity))
    """
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Reseta o engine e a session factory (útil para testes)."""
    global _engine, _SessionLocal, _default_org_id
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    _default_org_id = None


def get_default_organization_id() -> str:
    """Retorna o organization_id usado pelo pipeline do M1 (single-tenant).

    Ordem de resolução:
    1. Env var IMOIA_DEFAULT_ORGANIZATION_ID (UUID literal)
    2. Env var IMOIA_DEFAULT_ORGANIZATION_SLUG → lookup em organizations (default: 'habta')
    3. Fallback: se existe apenas 1 organização no DB, usa essa
    """
    global _default_org_id
    if _default_org_id is not None:
        return _default_org_id

    explicit = os.getenv("IMOIA_DEFAULT_ORGANIZATION_ID", "").strip()
    if explicit:
        _default_org_id = explicit
        return _default_org_id

    slug = os.getenv("IMOIA_DEFAULT_ORGANIZATION_SLUG", "habta").strip()
    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM organizations WHERE slug = :slug LIMIT 1"),
            {"slug": slug},
        ).first()
        if row is not None:
            _default_org_id = str(row[0])
            return _default_org_id

        rows = conn.execute(text("SELECT id FROM organizations LIMIT 2")).all()
        if len(rows) == 1:
            _default_org_id = str(rows[0][0])
            logger.warning(
                f"Organização slug='{slug}' não encontrada — usando a única organização existente"
            )
            return _default_org_id

    raise RuntimeError(
        "Não foi possível determinar a organização default. "
        "Configure IMOIA_DEFAULT_ORGANIZATION_ID ou IMOIA_DEFAULT_ORGANIZATION_SLUG."
    )
