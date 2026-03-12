"""Gestão da sessão de base de dados SQLAlchemy 2.0.

Fornece o engine, a session factory e a função de inicialização.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.database.models import Base

_engine = None
_SessionLocal = None


def _get_engine():
    """Cria ou retorna o engine SQLAlchemy."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.database_url

        # Garantir que o diretório data/ existe para SQLite
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        _engine = create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        )
        logger.info(f"Engine SQLAlchemy criado: {db_url}")
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    """Cria ou retorna a session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), expire_on_commit=False)
    return _SessionLocal


def init_db() -> None:
    """Inicializa a base de dados — cria todas as tabelas."""
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Base de dados inicializada com sucesso")


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
