"""ImoIA API — plataforma de gestao de investimento imobiliario fix and flip.

Uso:
    uvicorn src.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from loguru import logger

from src.api.health import router as health_router
from src.api.ingestor import router as ingestor_router
from src.api.properties import router as properties_router
from src.modules.m2_market.router import router as market_router
from src.modules.m3_financial.router import router as financial_router
from src.modules.m4_deal_pipeline.router import router as deal_pipeline_router
from src.modules.m5_due_diligence.router import router as due_diligence_router
from src.modules.m6_renovation.router import router as renovation_router
from src.modules.m7_marketing.router import router as marketing_router
from src.modules.m8_leads.router import router as leads_router
from src.modules.m9_closing.router import router as closing_router
from src.shared.document_router import router as document_router
from src.database.db import init_db


def create_app() -> FastAPI:
    """Cria e configura a aplicacao FastAPI."""
    app = FastAPI(
        title="ImoIA API",
        version="0.2.0",
        description=(
            "Plataforma de gestao de investimento imobiliario fix and flip."
        ),
    )

    @app.on_event("startup")
    def on_startup() -> None:
        """Inicializa a BD ao arrancar (cria tabelas se necessario)."""
        init_db()
        import src.database.models_v2  # noqa: F401

        from src.database.models import Base
        from src.database.db import _get_engine

        Base.metadata.create_all(bind=_get_engine())
        logger.info("ImoIA API iniciada — tabelas verificadas")

    app.include_router(health_router, tags=["Sistema"])
    app.include_router(
        ingestor_router, prefix="/api/v1/ingest", tags=["Propriedades (retrocompat)"]
    )
    app.include_router(
        properties_router, prefix="/api/v1/properties", tags=["Propriedades"]
    )
    app.include_router(
        market_router,
        prefix="/api/v1/market",
        tags=["M2 - Pesquisa de Mercado"],
    )
    app.include_router(
        financial_router,
        prefix="/api/v1/financial",
        tags=["M3 - Motor Financeiro"],
    )
    app.include_router(
        deal_pipeline_router,
        prefix="/api/v1/deals",
        tags=["M4 - Deal Pipeline"],
    )
    app.include_router(
        due_diligence_router,
        prefix="/api/v1/due-diligence",
        tags=["M5 - Due Diligence"],
    )
    app.include_router(
        renovation_router,
        prefix="/api/v1/renovations",
        tags=["M6 - Gestao de Obra"],
    )
    app.include_router(
        marketing_router,
        prefix="/api/v1/marketing",
        tags=["M7 - Marketing"],
    )
    app.include_router(
        leads_router,
        prefix="/api/v1/leads",
        tags=["M8 - CRM de Leads"],
    )
    app.include_router(
        closing_router,
        prefix="/api/v1",
        tags=["M9 - Fecho + P&L"],
    )
    app.include_router(
        document_router,
        prefix="/api/v1/documents",
        tags=["Documentos"],
    )

    return app


app = create_app()
