"""ImoIA API — plataforma de gestao de investimento imobiliario fix and flip.

Uso:
    uvicorn src.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.dependencies.auth import get_current_organization, get_current_user

from src.api.health import router as health_router
from src.api.ingestor import router as ingestor_router
from src.api.invites import router as invites_router
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
from src.modules.m1_ingestor.strategy_router import router as strategy_router
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


def _sync_from_supabase():
    """Puxa dados do Supabase REST API para o SQLite local (cold start)."""
    import json
    import os
    import urllib.request
    from src.database.db import get_session
    from src.database.models_v2 import (
        Property, Tenant, FinancialModel, PaymentCondition, CashflowProjection,
    )
    from src.database.models import Opportunity

    supa_url = os.getenv("SUPABASE_URL", "")
    supa_key = os.getenv("SUPABASE_ANON_KEY", "")
    if not supa_url or not supa_key:
        logger.info("SUPABASE_URL/KEY nao configurados — sync ignorado")
        return

    def fetch(table, limit=1000, offset=0):
        url = f"{supa_url}/rest/v1/{table}?select=*&limit={limit}&offset={offset}&order=created_at.desc"
        req = urllib.request.Request(url, headers={"apikey": supa_key, "Authorization": f"Bearer {supa_key}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())

    with get_session() as session:
        # Verificar se ja tem dados (nao re-sincronizar)
        existing = session.execute(
            __import__("sqlalchemy").select(Property).limit(1)
        ).first()
        if existing:
            logger.info("SQLite ja tem dados — sync ignorado")
            return

        logger.info("A sincronizar dados do Supabase...")

        # Tenants
        for t in fetch("tenants"):
            session.merge(Tenant(id=t["id"], name=t.get("name", "ImoIA"), slug=t.get("slug", "default"), country=t.get("country", "PT")))
        session.flush()

        # Properties (em batches)
        for off in range(0, 500, 100):
            batch = fetch("properties", 100, off)
            for p in batch:
                obj = Property(id=p["id"], tenant_id=p.get("tenant_id"))
                for k in ["source", "country", "district", "municipality", "parish", "address",
                           "postal_code", "property_type", "typology", "gross_area_m2", "net_area_m2",
                           "bedrooms", "bathrooms", "asking_price", "condition", "status", "notes",
                           "tags", "is_off_market", "contact_name", "contact_phone", "contact_email", "url", "portal"]:
                    if k in p and p[k] is not None:
                        setattr(obj, k, p[k])
                session.merge(obj)
            if len(batch) < 100:
                break
        session.flush()

        # Financial Models
        for m in fetch("financial_models"):
            obj = FinancialModel(id=m["id"])
            for k, v in m.items():
                if k not in ("id", "created_at", "updated_at") and hasattr(FinancialModel, k) and v is not None:
                    try:
                        setattr(obj, k, v)
                    except Exception:
                        pass
            session.merge(obj)
        session.flush()

        # Payment Conditions
        for c in fetch("payment_conditions"):
            try:
                obj = PaymentCondition(id=c["id"])
                for k, v in c.items():
                    if k not in ("id", "created_at", "updated_at") and hasattr(PaymentCondition, k) and v is not None:
                        try:
                            setattr(obj, k, v)
                        except Exception:
                            pass
                session.merge(obj)
            except Exception as e:
                logger.debug(f"PaymentCondition skip: {e}")
        session.flush()

        # Cashflow Projections
        for p in fetch("cashflow_projections"):
            obj = CashflowProjection(id=p["id"])
            for k, v in p.items():
                if k not in ("id", "created_at", "updated_at") and hasattr(CashflowProjection, k) and v is not None:
                    try:
                        setattr(obj, k, v)
                    except Exception:
                        pass
            session.merge(obj)
        session.flush()

        # Opportunities (em batches)
        for off in range(0, 5000, 1000):
            batch = fetch("opportunities", 1000, off)
            for o in batch:
                try:
                    obj = Opportunity(id=o.get("id"))
                    for k, v in o.items():
                        if k not in ("id", "created_at", "updated_at") and hasattr(Opportunity, k) and v is not None:
                            try:
                                setattr(obj, k, v)
                            except Exception:
                                pass
                    session.merge(obj)
                except Exception:
                    pass
            if len(batch) < 1000:
                break
        session.flush()

        # Tabelas dos módulos M4-M9 (sync genérico)
        from src.database.models_v2 import (
            Deal, DealTask, DealStateHistory, Proposal, DealVisit, DealCommission, DealRental,
            DueDiligenceItem,
            Renovation, RenovationMilestone, RenovationExpense, RenovationPhoto,
            BrandKit, Listing, ListingCreative, EmailCampaign,
            SocialMediaAccount, SocialMediaPost,
            Lead, LeadInteraction, NurtureSequence,
            ClosingProcess, DealPnL,
            InvestmentStrategy, ClassificationSignal,
        )

        module_tables = [
            ("deals", Deal),
            ("deal_tasks", DealTask),
            ("deal_state_history", DealStateHistory),
            ("proposals", Proposal),
            ("deal_visits", DealVisit),
            ("deal_commissions", DealCommission),
            ("deal_rentals", DealRental),
            ("due_diligence_items", DueDiligenceItem),
            ("renovations", Renovation),
            ("renovation_milestones", RenovationMilestone),
            ("renovation_expenses", RenovationExpense),
            ("renovation_photos", RenovationPhoto),
            ("brand_kits", BrandKit),
            ("listings", Listing),
            ("listing_creatives", ListingCreative),
            ("email_campaigns", EmailCampaign),
            ("social_media_accounts", SocialMediaAccount),
            ("social_media_posts", SocialMediaPost),
            ("leads", Lead),
            ("lead_interactions", LeadInteraction),
            ("nurture_sequences", NurtureSequence),
            ("closing_processes", ClosingProcess),
            ("deal_pnl", DealPnL),
            ("investment_strategies", InvestmentStrategy),
            ("classification_signals", ClassificationSignal),
        ]

        for table_name, ModelClass in module_tables:
            try:
                for off in range(0, 2000, 500):
                    batch = fetch(table_name, 500, off)
                    if not batch:
                        break
                    for row in batch:
                        try:
                            obj = ModelClass(id=row.get("id"))
                            for k, v in row.items():
                                if k not in ("id", "created_at", "updated_at") and hasattr(ModelClass, k) and v is not None:
                                    try:
                                        setattr(obj, k, v)
                                    except Exception:
                                        pass
                            session.merge(obj)
                        except Exception:
                            pass
                    if len(batch) < 500:
                        break
                session.flush()
            except Exception as e:
                logger.debug(f"Sync {table_name} skip: {e}")

    logger.info("Sync Supabase completo")


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
            "https://imo-ia.vercel.app",
            "https://imoia-frontend.vercel.app",
            "https://frontend-three-omega-51.vercel.app",
            "http://localhost:3000",
        ],
        allow_origin_regex=r"https://(frontend|imo)-.*-mayraferrops-projects\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def on_startup() -> None:
        """Inicializa a BD local (tabelas legacy) e valida conexao Supabase."""
        try:
            init_db()
            import src.database.models_v2  # noqa: F401
            from src.database.models import Base
            from src.database.db import _get_engine
            Base.metadata.create_all(bind=_get_engine())
        except Exception as e:
            logger.warning(f"Aviso ao inicializar BD local: {e}")

        # Validar conexao Supabase REST
        try:
            from src.database.supabase_rest import _ensure_config
            _ensure_config()
            logger.info("Supabase REST configurado")
        except Exception as e:
            logger.warning(f"Supabase REST nao configurado: {e}")

        logger.info("ImoIA API iniciada")

    # Auth dependencies aplicadas a todos os routers excepto health
    auth_deps = [Depends(get_current_user), Depends(get_current_organization)]

    app.include_router(health_router, tags=["Sistema"])
    app.include_router(
        ingestor_router, prefix="/api/v1/ingest",
        tags=["Propriedades (retrocompat)"], dependencies=auth_deps,
    )
    app.include_router(
        properties_router, prefix="/api/v1/properties",
        tags=["Propriedades"], dependencies=auth_deps,
    )
    app.include_router(
        market_router, prefix="/api/v1/market",
        tags=["M2 - Pesquisa de Mercado"], dependencies=auth_deps,
    )
    app.include_router(
        financial_router, prefix="/api/v1/financial",
        tags=["M3 - Motor Financeiro"], dependencies=auth_deps,
    )
    app.include_router(
        deal_pipeline_router, prefix="/api/v1/deals",
        tags=["M4 - Deal Pipeline"], dependencies=auth_deps,
    )
    app.include_router(
        due_diligence_router, prefix="/api/v1/due-diligence",
        tags=["M5 - Due Diligence"], dependencies=auth_deps,
    )
    app.include_router(
        renovation_router, prefix="/api/v1/renovations",
        tags=["M6 - Gestao de Obra"], dependencies=auth_deps,
    )
    app.include_router(
        marketing_router, prefix="/api/v1/marketing",
        tags=["M7 - Marketing"], dependencies=auth_deps,
    )
    app.include_router(
        leads_router, prefix="/api/v1/leads",
        tags=["M8 - CRM de Leads"], dependencies=auth_deps,
    )
    app.include_router(
        closing_router, prefix="/api/v1",
        tags=["M9 - Fecho + P&L"], dependencies=auth_deps,
    )
    app.include_router(
        document_router, prefix="/api/v1/documents",
        tags=["Documentos"], dependencies=auth_deps,
    )
    app.include_router(
        strategy_router, prefix="/api/v1/strategies",
        tags=["Estratégias de Investimento"], dependencies=auth_deps,
    )
    # Invites: sem auth_deps globais (validate/{token} e publico;
    # os outros endpoints definem Depends() individualmente)
    app.include_router(
        invites_router, prefix="/api/v1/invites",
        tags=["Convites de Organizacao"],
    )

    return app


app = create_app()
