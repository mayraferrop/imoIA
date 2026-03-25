"""Gestão da sessão de base de dados SQLAlchemy 2.0.

Fornece o engine, a session factory e a função de inicialização.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from urllib.parse import quote_plus, urlparse

from loguru import logger
from sqlalchemy import create_engine, text
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

        # Garantir que a password está URL-encoded (caracteres especiais como @)
        if "postgresql" in db_url:
            parsed = urlparse(db_url)
            if parsed.password and "%" not in parsed.password:
                encoded_pw = quote_plus(parsed.password)
                db_url = db_url.replace(f":{parsed.password}@", f":{encoded_pw}@", 1)

        # Garantir que o diretório data/ existe para SQLite
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        connect_args = {}
        kwargs = {}
        if "sqlite" in db_url:
            connect_args["check_same_thread"] = False
        else:
            # PostgreSQL — pool settings para Supabase Transaction pooler
            kwargs["pool_size"] = 2
            kwargs["max_overflow"] = 3
            kwargs["pool_pre_ping"] = True
            kwargs["pool_recycle"] = 300

        _engine = create_engine(
            db_url,
            echo=False,
            connect_args=connect_args,
            **kwargs,
        )
        logger.info(f"Engine SQLAlchemy criado: {db_url}")
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
    if "sqlite" in str(engine.url):
        return
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


def init_db() -> None:
    """Inicializa a base de dados — cria todas as tabelas."""
    engine = _get_engine()
    try:
        Base.metadata.create_all(bind=engine)
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
