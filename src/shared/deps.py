"""Dependencias partilhadas para FastAPI.

Fornece injecao de dependencias para sessao de BD e tenant.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Optional

from src.database.db import get_session


def get_db() -> Generator:
    """Dependencia FastAPI para obter sessao de BD.

    Reutiliza o get_session() existente do ImoScout.
    """
    with get_session() as session:
        yield session


def get_current_tenant() -> Optional[str]:
    """Dependencia FastAPI para obter o tenant actual.

    TODO: Implementar autenticacao e extraccao de tenant do token JWT.
    Por agora retorna None (single-tenant).
    """
    return None
