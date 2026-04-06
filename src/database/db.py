"""Gestão da sessão de base de dados SQLAlchemy 2.0.

Fornece o engine, a session factory e a função de inicialização.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from urllib.parse import quote_plus, urlparse

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.database.models import Base

_engine = None
_SessionLocal = None


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
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
