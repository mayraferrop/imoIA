"""ImoIA API — plataforma de gestao de investimento imobiliario fix and flip.

Uso:
    uvicorn src.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


async def _migrate_from_supabase(payload: dict):
    """Endpoint temporario para migrar dados do Supabase para SQLite."""
    from uuid import uuid4
    from src.database.db import get_session
    from src.database.models_v2 import (
        Property, Tenant, FinancialModel, PaymentCondition,
        CashflowProjection,
    )
    from src.database.models import Opportunity

    stats = {"tenants": 0, "properties": 0, "models": 0, "conditions": 0, "projections": 0, "opportunities": 0, "skipped": 0}

    with get_session() as session:
        # Tenant
        for t in payload.get("tenants", []):
            existing = session.get(Tenant, t["id"])
            if existing:
                stats["skipped"] += 1
                continue
            session.add(Tenant(id=t["id"], name=t.get("name", "ImoIA"), slug=t.get("slug", "default"), country=t.get("country", "PT")))
            stats["tenants"] += 1
        session.flush()

        # Properties
        for p in payload.get("properties", []):
            existing = session.get(Property, p["id"])
            if existing:
                stats["skipped"] += 1
                continue
            obj = Property(id=p["id"], tenant_id=p.get("tenant_id"))
            for k in ["source", "country", "district", "municipality", "parish", "address", "postal_code",
                       "property_type", "typology", "gross_area_m2", "net_area_m2", "bedrooms", "bathrooms",
                       "asking_price", "condition", "status", "notes", "tags", "is_off_market",
                       "contact_name", "contact_phone", "contact_email", "url", "portal"]:
                if k in p and p[k] is not None:
                    setattr(obj, k, p[k])
            session.add(obj)
            stats["properties"] += 1
        session.flush()

        # Financial Models
        for m in payload.get("financial_models", []):
            existing = session.get(FinancialModel, m["id"])
            if existing:
                stats["skipped"] += 1
                continue
            obj = FinancialModel(id=m["id"])
            for k, v in m.items():
                if k not in ("id", "created_at", "updated_at") and hasattr(FinancialModel, k) and v is not None:
                    try:
                        setattr(obj, k, v)
                    except Exception:
                        pass
            session.add(obj)
            stats["models"] += 1
        session.flush()

        # Payment Conditions
        for c in payload.get("payment_conditions", []):
            existing = session.get(PaymentCondition, c["id"])
            if existing:
                stats["skipped"] += 1
                continue
            obj = PaymentCondition(id=c["id"])
            for k, v in c.items():
                if k not in ("id", "created_at", "updated_at") and hasattr(PaymentCondition, k) and v is not None:
                    try:
                        setattr(obj, k, v)
                    except Exception:
                        pass
            session.add(obj)
            stats["conditions"] += 1
        session.flush()

        # Cashflow Projections
        for p in payload.get("cashflow_projections", []):
            existing = session.get(CashflowProjection, p["id"])
            if existing:
                stats["skipped"] += 1
                continue
            obj = CashflowProjection(id=p["id"])
            for k, v in p.items():
                if k not in ("id", "created_at", "updated_at") and hasattr(CashflowProjection, k) and v is not None:
                    try:
                        setattr(obj, k, v)
                    except Exception:
                        pass
            session.add(obj)
            stats["projections"] += 1
        session.flush()

        # Opportunities
        for o in payload.get("opportunities", []):
            try:
                existing = session.get(Opportunity, o.get("id"))
                if existing:
                    stats["skipped"] += 1
                    continue
                obj = Opportunity(id=o.get("id"))
                for k, v in o.items():
                    if k not in ("id", "created_at", "updated_at") and hasattr(Opportunity, k) and v is not None:
                        try:
                            setattr(obj, k, v)
                        except Exception:
                            pass
                session.add(obj)
                stats["opportunities"] += 1
            except Exception:
                stats["skipped"] += 1
        session.flush()

    return stats


def create_app() -> FastAPI:
    """Cria e configura a aplicacao FastAPI."""
    app = FastAPI(
        title="ImoIA API",
        version="0.2.0",
        description=(
            "Plataforma de gestao de investimento imobiliario fix and flip."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://imoia.vercel.app",
            "https://imoia-frontend.vercel.app",
            "https://frontend-three-omega-51.vercel.app",
            "http://localhost:3000",
        ],
        allow_origin_regex=r"https://frontend-.*-mayraferrops-projects\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def on_startup() -> None:
        """Inicializa a BD ao arrancar (cria tabelas se necessario)."""
        try:
            init_db()
            import src.database.models_v2  # noqa: F401
            from src.database.models import Base
            from src.database.db import _get_engine
            Base.metadata.create_all(bind=_get_engine())
        except Exception as e:
            logger.warning(f"Aviso ao inicializar BD (tabelas podem ja existir): {e}")
        logger.info("ImoIA API iniciada")

    @app.post("/api/v1/admin/migrate", tags=["Admin"])
    async def migrate_endpoint(payload: dict):
        return await _migrate_from_supabase(payload)

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
