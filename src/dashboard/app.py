"""Dashboard Streamlit do ImoScout.

Frontend completo para o detector de oportunidades imobiliarias.
Inclui dashboard principal, gestao de pipeline, configuracao e grupos.
Design system: Light Mode + Teal/Blue + Cinzel/Josefin Sans.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from loguru import logger
from sqlalchemy import func, select

from src.database.db import get_session, init_db
from src.database.models import Group, MarketData, Message, Opportunity

# ---------------------------------------------------------------------------
# Design System — Cores e constantes visuais
# ---------------------------------------------------------------------------

COLORS = {
    "primary": "#0F766E",
    "primary_light": "#14B8A6",
    "cta": "#0369A1",
    "bg_dark": "#FFFFFF",
    "bg_card": "#F8FAFC",
    "bg_card_hover": "#F1F5F9",
    "text_primary": "#1E293B",
    "text_secondary": "#475569",
    "text_muted": "#94A3B8",
    "success": "#16A34A",
    "warning": "#D97706",
    "danger": "#DC2626",
    "info": "#2563EB",
    "purple": "#7C3AED",
    "border": "#E2E8F0",
    "border_hover": "#CBD5E1",
}

OPPORTUNITY_TYPES: List[str] = [
    "abaixo_mercado", "venda_urgente", "off_market", "reabilitacao",
    "leilao", "heranca", "divorcio", "dacao_banco", "rendimento",
    "terreno", "predio_inteiro", "terreno_viabilidade", "yield_alto",
]

PROPERTY_TYPES: List[str] = [
    "apartamento", "moradia", "terreno", "predio", "loja", "armazem", "escritorio",
]

STATUS_OPTIONS: List[str] = [
    "nova", "analisada", "interessante", "descartada", "contactada",
]

STATUS_COLORS: Dict[str, str] = {
    "nova": COLORS["info"],
    "analisada": COLORS["warning"],
    "interessante": COLORS["success"],
    "descartada": COLORS["danger"],
    "contactada": COLORS["purple"],
}

OPPORTUNITY_TYPE_LABELS: Dict[str, str] = {
    "abaixo_mercado": "Abaixo do Mercado",
    "venda_urgente": "Venda Urgente",
    "off_market": "Off-Market",
    "reabilitacao": "Reabilitacao",
    "leilao": "Leilao",
    "heranca": "Heranca",
    "divorcio": "Divorcio",
    "dacao_banco": "Dacao em Pagamento",
    "rendimento": "Rendimento",
    "terreno": "Terreno",
    "predio_inteiro": "Predio Inteiro",
    "terreno_viabilidade": "Terreno c/ Viabilidade",
    "yield_alto": "Yield Alto",
}

# Icones SVG inline (sem emojis — best practice UI/UX Pro Max)
ICONS = {
    "dashboard": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>',
    "pipeline": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "config": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>',
    "groups": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "home": '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
}

# ---------------------------------------------------------------------------
# CSS Global — Design System
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Josefin+Sans:wght@300;400;500;600;700&display=swap');

    /* Base typography */
    .main h1, .main h2, .main h3 {
        font-family: 'Cinzel', serif !important;
        color: #1E293B !important;
        letter-spacing: 0.02em;
    }
    .main p, .main span, .main div, .main label {
        font-family: 'Josefin Sans', sans-serif !important;
    }

    /* Navigation buttons */
    .nav-btn {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 16px;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        background: #FFFFFF;
        color: #475569;
        cursor: pointer;
        transition: all 200ms ease;
        font-family: 'Josefin Sans', sans-serif;
        font-size: 0.95rem;
        width: 100%;
        text-align: left;
        margin-bottom: 4px;
    }
    .nav-btn:hover {
        background: #F1F5F9;
        border-color: #14B8A6;
        color: #1E293B;
    }
    .nav-btn.active {
        background: linear-gradient(135deg, #0F766E10, #14B8A620);
        border-color: #14B8A6;
        color: #0F766E;
    }

    /* Metric cards */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 20px 24px;
        transition: all 200ms ease;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    .metric-card:hover {
        border-color: #14B8A6;
        box-shadow: 0 4px 12px rgba(20, 184, 166, 0.1);
    }
    .metric-value {
        font-family: 'Cinzel', serif;
        font-size: 2rem;
        font-weight: 700;
        color: #0F766E;
        line-height: 1.2;
    }
    .metric-label {
        font-family: 'Josefin Sans', sans-serif;
        font-size: 0.85rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 4px;
    }

    /* Opportunity cards */
    .opp-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        transition: all 200ms ease;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    .opp-card:hover {
        border-color: #CBD5E1;
        background: #F8FAFC;
    }
    .opp-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .opp-title {
        font-family: 'Josefin Sans', sans-serif;
        font-size: 1.05rem;
        font-weight: 600;
        color: #1E293B;
    }
    .opp-meta {
        font-family: 'Josefin Sans', sans-serif;
        font-size: 0.85rem;
        color: #64748B;
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-family: 'Josefin Sans', sans-serif;
        font-size: 0.8rem;
        font-weight: 500;
        letter-spacing: 0.02em;
    }
    .badge-confidence-high { background: #DCFCE7; color: #15803D; border: 1px solid #BBF7D0; }
    .badge-confidence-mid { background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }
    .badge-confidence-low { background: #F1F5F9; color: #64748B; border: 1px solid #E2E8F0; }
    .badge-status-nova { background: #DBEAFE; color: #1D4ED8; border: 1px solid #BFDBFE; }
    .badge-status-interessante { background: #DCFCE7; color: #15803D; border: 1px solid #BBF7D0; }
    .badge-status-descartada { background: #FEE2E2; color: #B91C1C; border: 1px solid #FECACA; }
    .badge-status-contactada { background: #EDE9FE; color: #6D28D9; border: 1px solid #DDD6FE; }
    .badge-status-analisada { background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }

    /* Section dividers */
    .section-title {
        font-family: 'Cinzel', serif;
        font-size: 1.4rem;
        color: #1E293B;
        margin: 24px 0 16px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #14B8A640;
    }

    /* Config cards */
    .config-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    .config-card h3 {
        font-size: 1.1rem !important;
        margin-bottom: 16px !important;
        color: #0F766E !important;
    }

    /* Info box */
    .info-box {
        background: #F0FDFA;
        border: 1px solid #99F6E4;
        border-radius: 10px;
        padding: 16px 20px;
        color: #0F766E;
        font-family: 'Josefin Sans', sans-serif;
        font-size: 0.9rem;
    }

    /* Warning box */
    .warn-box {
        background: #FFFBEB;
        border: 1px solid #FDE68A;
        border-radius: 10px;
        padding: 16px 20px;
        color: #B45309;
        font-family: 'Josefin Sans', sans-serif;
        font-size: 0.9rem;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #64748B;
    }
    .empty-state h3 {
        color: #475569 !important;
        font-size: 1.3rem !important;
        margin-bottom: 8px !important;
    }
    .empty-state p {
        font-size: 0.95rem;
    }

    /* Plotly chart overrides */
    .js-plotly-plot .plotly .modebar { display: none !important; }

    /* Streamlit overrides for light theme */
    .stExpander {
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        background: #FFFFFF !important;
    }
    .stExpander:hover {
        border-color: #CBD5E1 !important;
    }
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    div[data-testid="stMetric"]:hover {
        border-color: #14B8A680;
    }
    div[data-testid="stMetricValue"] {
        font-family: 'Cinzel', serif !important;
        color: #0F766E !important;
    }
    div[data-testid="stMetricLabel"] {
        font-family: 'Josefin Sans', sans-serif !important;
        color: #94A3B8 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.8rem !important;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: #F8FAFC !important;
        border-right: 1px solid #E2E8F0;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    /* Button overrides */
    .stButton > button {
        font-family: 'Josefin Sans', sans-serif !important;
        border-radius: 10px !important;
        transition: all 200ms ease !important;
        cursor: pointer !important;
    }
    .stButton > button:hover {
        border-color: #14B8A6 !important;
        box-shadow: 0 0 12px rgba(20, 184, 166, 0.15) !important;
    }

    /* Pipeline log */
    .pipeline-log {
        background: #F1F5F9;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        font-family: 'JetBrains Mono', 'SF Mono', monospace;
        font-size: 0.82rem;
        color: #475569;
        max-height: 400px;
        overflow-y: auto;
    }
    .pipeline-log .log-success { color: #16A34A; }
    .pipeline-log .log-error { color: #DC2626; }
    .pipeline-log .log-info { color: #2563EB; }
    .pipeline-log .log-warning { color: #D97706; }

    /* Group cards */
    .group-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 200ms ease;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    .group-card:hover {
        border-color: #CBD5E1;
    }
    .group-name {
        font-family: 'Josefin Sans', sans-serif;
        font-weight: 600;
        color: #1E293B;
    }
    .group-stats {
        font-family: 'Josefin Sans', sans-serif;
        font-size: 0.85rem;
        color: #64748B;
    }

    /* Market data highlight */
    .market-positive { color: #16A34A; font-weight: 600; }
    .market-negative { color: #DC2626; font-weight: 600; }
</style>
"""

# ---------------------------------------------------------------------------
# Plotly theme
# ---------------------------------------------------------------------------

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Josefin Sans, sans-serif", color="#475569", size=13),
    title_font=dict(family="Cinzel, serif", color="#1E293B", size=16),
    xaxis=dict(gridcolor="#E2E8F0", zerolinecolor="#E2E8F0"),
    yaxis=dict(gridcolor="#E2E8F0", zerolinecolor="#E2E8F0"),
    margin=dict(l=20, r=20, t=50, b=20),
    colorway=["#14B8A6", "#0369A1", "#7C3AED", "#D97706", "#DC2626", "#16A34A", "#EC4899"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


GRADE_COLORS: Dict[str, str] = {
    "A": "#16A34A",
    "B": "#0369A1",
    "C": "#D97706",
    "D": "#DC2626",
    "F": "#94A3B8",
}

ITEMS_PER_PAGE = 20


def _deal_grade_badge(grade: str | None, score: int | None) -> str:
    """Gera badge HTML para o deal grade."""
    if not grade:
        return '<span style="background:#F1F5F9; color:#94A3B8; padding:2px 10px; border-radius:6px; font-size:0.8rem; font-weight:600;">N/D</span>'
    color = GRADE_COLORS.get(grade, "#94A3B8")
    score_text = f" ({score})" if score is not None else ""
    return (
        f'<span style="background:{color}15; color:{color}; border:1px solid {color}40; '
        f'padding:2px 10px; border-radius:6px; font-size:0.8rem; font-weight:700;">'
        f'{grade}{score_text}</span>'
    )


def _confidence_badge(confidence: float) -> str:
    """Retorna badge HTML conforme o nivel de confianca."""
    if confidence > 0.8:
        cls = "badge-confidence-high"
        label = "Alta"
    elif confidence >= 0.6:
        cls = "badge-confidence-mid"
        label = "Media"
    else:
        cls = "badge-confidence-low"
        label = "Baixa"
    return f'<span class="badge {cls}">{confidence:.0%} {label}</span>'


def _status_badge(status: str) -> str:
    """Retorna badge HTML conforme o status."""
    cls = f"badge-status-{status}"
    return f'<span class="badge {cls}">{status.capitalize()}</span>'


def _format_price(price: Optional[float]) -> str:
    """Formata preco em euros."""
    if price is None:
        return "N/D"
    return f"{price:,.0f} EUR".replace(",", ".")


def _env_path() -> Path:
    """Retorna o caminho para o ficheiro .env."""
    return Path(__file__).resolve().parent.parent.parent / ".env"


def _load_env_values() -> Dict[str, str]:
    """Carrega valores do ficheiro .env."""
    env_file = _env_path()
    values: Dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


def _save_env_values(new_values: Dict[str, str]) -> None:
    """Guarda valores no ficheiro .env, preservando entradas existentes."""
    env_file = _env_path()
    existing = _load_env_values()
    existing.update(new_values)
    lines = []
    for key, val in existing.items():
        lines.append(f"{key}={val}")
    env_file.write_text("\n".join(lines) + "\n")


def _mask_key(key: str) -> str:
    """Mascara uma chave API para apresentacao."""
    if not key or len(key) < 8:
        return key
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


# ---------------------------------------------------------------------------
# Queries de dados
# ---------------------------------------------------------------------------


def fetch_opportunities(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_confidence: float = 0.0,
    opportunity_types: Optional[List[str]] = None,
    property_types: Optional[List[str]] = None,
    districts: Optional[List[str]] = None,
    municipalities: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
) -> List[Dict]:
    """Consulta oportunidades da BD com filtros aplicados."""
    results: List[Dict] = []

    with get_session() as session:
        stmt = (
            select(Opportunity, MarketData, Message)
            .outerjoin(MarketData, MarketData.opportunity_id == Opportunity.id)
            .join(Message, Message.id == Opportunity.message_id)
            .where(Opportunity.is_opportunity.is_(True))
        )

        if start_date is not None:
            stmt = stmt.where(Opportunity.created_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date is not None:
            stmt = stmt.where(Opportunity.created_at <= datetime.combine(end_date, datetime.max.time()))
        if min_confidence > 0.0:
            stmt = stmt.where(Opportunity.confidence >= min_confidence)
        if opportunity_types:
            stmt = stmt.where(Opportunity.opportunity_type.in_(opportunity_types))
        if property_types:
            stmt = stmt.where(Opportunity.property_type.in_(property_types))
        if districts:
            stmt = stmt.where(Opportunity.district.in_(districts))
        if municipalities:
            stmt = stmt.where(Opportunity.municipality.in_(municipalities))
        if statuses:
            stmt = stmt.where(Opportunity.status.in_(statuses))

        stmt = stmt.order_by(
            Opportunity.deal_score.desc().nullslast(),
            Opportunity.created_at.desc(),
        )
        rows = session.execute(stmt).all()

        for opp, md, msg in rows:
            row: Dict = {
                "id": opp.id,
                "created_at": opp.created_at,
                "group_name": msg.group_name,
                "opportunity_type": opp.opportunity_type,
                "property_type": opp.property_type,
                "location": opp.location_extracted,
                "municipality": opp.municipality,
                "district": opp.district,
                "price": opp.price_mentioned,
                "area_m2": opp.area_m2,
                "bedrooms": opp.bedrooms,
                "confidence": opp.confidence,
                "status": opp.status,
                "deal_score": opp.deal_score,
                "deal_grade": opp.deal_grade,
                "notes": opp.notes,
                "original_message": opp.original_message,
                "ai_reasoning": opp.ai_reasoning,
                # INE
                "ine_median_price_m2": md.ine_median_price_m2 if md else None,
                # Casafari
                "casafari_avg_price_m2": md.casafari_avg_price_m2 if md else None,
                "casafari_median_price_m2": md.casafari_median_price_m2 if md else None,
                "casafari_comparables_count": md.casafari_comparables_count if md else None,
                # Infocasa
                "infocasa_avg_price_m2": md.infocasa_avg_price_m2 if md else None,
                "infocasa_median_price_m2": md.infocasa_median_price_m2 if md else None,
                "infocasa_comparables_count": md.infocasa_comparables_count if md else None,
                # SIR
                "sir_median_price_m2": md.sir_median_price_m2 if md else None,
                "sir_market_position": md.sir_market_position if md else None,
                "sir_price_vs_market_pct": md.sir_price_vs_market_pct if md else None,
                # Idealista
                "idealista_avg_price_m2": md.idealista_avg_price_m2 if md else None,
                "idealista_listings_count": md.idealista_listings_count if md else None,
                # Estimativas
                "estimated_market_value": md.estimated_market_value if md else None,
                "estimated_monthly_rent": md.estimated_monthly_rent if md else None,
                "gross_yield_pct": md.gross_yield_pct if md else None,
                "net_yield_pct": md.net_yield_pct if md else None,
                "price_vs_market_pct": md.price_vs_market_pct if md else None,
                "imt_estimate": md.imt_estimate if md else None,
                "stamp_duty_estimate": md.stamp_duty_estimate if md else None,
                "total_acquisition_cost": md.total_acquisition_cost if md else None,
            }
            results.append(row)

    return results


def fetch_filter_options() -> Dict[str, List[str]]:
    """Busca distritos e concelhos existentes na BD."""
    with get_session() as session:
        districts_q = (
            session.execute(
                select(Opportunity.district)
                .where(Opportunity.district.isnot(None))
                .where(Opportunity.is_opportunity.is_(True))
                .distinct()
            ).scalars().all()
        )
        municipalities_q = (
            session.execute(
                select(Opportunity.municipality)
                .where(Opportunity.municipality.isnot(None))
                .where(Opportunity.is_opportunity.is_(True))
                .distinct()
            ).scalars().all()
        )
    return {
        "districts": sorted(districts_q),
        "municipalities": sorted(municipalities_q),
    }


def fetch_daily_counts(days: int = 30) -> List[Dict]:
    """Retorna contagem de oportunidades por dia."""
    since = datetime.now() - timedelta(days=days)
    with get_session() as session:
        rows = session.execute(
            select(
                func.date(Opportunity.created_at).label("day"),
                func.count(Opportunity.id).label("total"),
            )
            .where(Opportunity.is_opportunity.is_(True))
            .where(Opportunity.created_at >= since)
            .group_by(func.date(Opportunity.created_at))
            .order_by(func.date(Opportunity.created_at))
        ).all()
    return [{"day": str(r.day), "total": r.total} for r in rows]


def fetch_type_distribution() -> List[Dict]:
    """Retorna distribuicao por tipo de oportunidade."""
    with get_session() as session:
        rows = session.execute(
            select(
                Opportunity.opportunity_type,
                func.count(Opportunity.id).label("total"),
            )
            .where(Opportunity.is_opportunity.is_(True))
            .where(Opportunity.opportunity_type.isnot(None))
            .group_by(Opportunity.opportunity_type)
        ).all()
    return [{"type": r.opportunity_type, "total": r.total} for r in rows]


def fetch_top_municipalities(limit: int = 10) -> List[Dict]:
    """Retorna top concelhos com mais oportunidades."""
    with get_session() as session:
        rows = session.execute(
            select(
                Opportunity.municipality,
                func.count(Opportunity.id).label("total"),
            )
            .where(Opportunity.is_opportunity.is_(True))
            .where(Opportunity.municipality.isnot(None))
            .group_by(Opportunity.municipality)
            .order_by(func.count(Opportunity.id).desc())
            .limit(limit)
        ).all()
    return [{"municipality": r.municipality, "total": r.total} for r in rows]


def update_opportunity_status(opportunity_id: int, new_status: str) -> None:
    """Atualiza o status de uma oportunidade na BD."""
    with get_session() as session:
        opp = session.get(Opportunity, opportunity_id)
        if opp is not None:
            opp.status = new_status
            logger.info(f"Oportunidade {opportunity_id} atualizada para '{new_status}'")


def update_opportunity_notes(opportunity_id: int, notes: str) -> None:
    """Atualiza as notas de uma oportunidade na BD."""
    with get_session() as session:
        opp = session.get(Opportunity, opportunity_id)
        if opp is not None:
            opp.notes = notes
            logger.info(f"Notas da oportunidade {opportunity_id} atualizadas")


def fetch_today_metrics() -> Dict:
    """Retorna metricas do dia atual."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())

    with get_session() as session:
        total_today = session.execute(
            select(func.count(Opportunity.id))
            .where(Opportunity.is_opportunity.is_(True))
            .where(Opportunity.created_at >= today_start)
            .where(Opportunity.created_at <= today_end)
        ).scalar() or 0

        avg_confidence = session.execute(
            select(func.avg(Opportunity.confidence))
            .where(Opportunity.is_opportunity.is_(True))
            .where(Opportunity.created_at >= today_start)
            .where(Opportunity.created_at <= today_end)
        ).scalar()

        groups_today = session.execute(
            select(func.count(Group.id))
            .where(Group.last_processed_at >= today_start)
            .where(Group.last_processed_at <= today_end)
        ).scalar() or 0

        best_confidence = session.execute(
            select(func.max(Opportunity.confidence))
            .where(Opportunity.is_opportunity.is_(True))
            .where(Opportunity.created_at >= today_start)
            .where(Opportunity.created_at <= today_end)
        ).scalar()

        total_all = session.execute(
            select(func.count(Opportunity.id))
            .where(Opportunity.is_opportunity.is_(True))
        ).scalar() or 0

        # Grade distribution
        grade_counts: Dict[str, int] = {}
        for grade_val in ["A", "B", "C", "D", "F"]:
            cnt = session.execute(
                select(func.count(Opportunity.id))
                .where(Opportunity.is_opportunity.is_(True))
                .where(Opportunity.deal_grade == grade_val)
            ).scalar() or 0
            grade_counts[grade_val] = cnt

        best_score = session.execute(
            select(func.max(Opportunity.deal_score))
            .where(Opportunity.is_opportunity.is_(True))
        ).scalar()

        below_market = session.execute(
            select(func.count(MarketData.id))
            .join(Opportunity, MarketData.opportunity_id == Opportunity.id)
            .where(Opportunity.is_opportunity.is_(True))
            .where(MarketData.price_vs_market_pct < 100)
            .where(MarketData.price_vs_market_pct.isnot(None))
        ).scalar() or 0

        pipeline_value = session.execute(
            select(func.sum(Opportunity.price_mentioned))
            .where(Opportunity.is_opportunity.is_(True))
            .where(Opportunity.status.in_(["nova", "analisada", "interessante"]))
            .where(Opportunity.price_mentioned.isnot(None))
        ).scalar() or 0

    return {
        "total_today": total_today,
        "avg_confidence": avg_confidence,
        "groups_today": groups_today,
        "best_confidence": best_confidence,
        "total_all": total_all,
        "grade_counts": grade_counts,
        "best_score": best_score,
        "below_market": below_market,
        "pipeline_value": pipeline_value,
    }


def fetch_groups() -> List[Dict]:
    """Retorna todos os grupos registados."""
    with get_session() as session:
        groups = session.execute(
            select(Group).order_by(Group.name)
        ).scalars().all()
        return [
            {
                "id": g.id,
                "whatsapp_group_id": g.whatsapp_group_id,
                "name": g.name,
                "is_active": g.is_active,
                "last_processed_at": g.last_processed_at,
                "message_count": g.message_count,
                "opportunity_count": g.opportunity_count,
                "created_at": g.created_at,
            }
            for g in groups
        ]


def toggle_group_active(group_id: int, is_active: bool) -> None:
    """Ativa ou desativa um grupo."""
    with get_session() as session:
        group = session.get(Group, group_id)
        if group:
            group.is_active = is_active


# ---------------------------------------------------------------------------
# Pagina: Dashboard
# ---------------------------------------------------------------------------


def _get_pipeline_status() -> Optional[Dict]:
    """Retorna estado atual do pipeline a partir do ficheiro de estado."""
    status_file = Path(__file__).resolve().parent.parent.parent / "logs" / "pipeline_status.json"
    if not status_file.exists():
        return None
    try:
        data = json.loads(status_file.read_text())
        if "timestamp" in data:
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return data
    except (json.JSONDecodeError, ValueError):
        return None


def _render_pipeline_banner() -> None:
    """Mostra banner com estado do pipeline no dashboard."""
    status = _get_pipeline_status()
    if not status:
        return

    ts = status.get("timestamp")
    state = status.get("state", "")
    time_str = ts.strftime("%H:%M") if ts else "?"
    date_str = ts.strftime("%d/%m") if ts else "?"

    if ts and ts.date() == date.today():
        date_label = f"hoje as {time_str}"
    elif ts:
        date_label = f"{date_str} as {time_str}"
    else:
        date_label = ""

    if state == "a_correr":
        st.warning(f"Pipeline a correr desde {date_label}...")
    elif state == "concluido":
        msgs = status.get("mensagens", 0)
        opps = status.get("oportunidades", 0)
        grupos = status.get("grupos", 0)
        erros = status.get("erros", 0)
        resumo = f"{opps} oportunidades, {grupos} grupos, {msgs} mensagens, {erros} erros"
        st.success(f"Pipeline concluido {date_label} -- {resumo}")
    elif state == "erro":
        detalhe = status.get("detalhe", "desconhecido")
        st.error(f"Pipeline falhou {date_label} -- {detalhe}")


def _run_pipeline_now() -> Dict[str, Any]:
    """Executa o pipeline directamente (sincrono, com feedback).

    Returns:
        Dict com resultado ou erro.
    """
    try:
        from src.pipeline.run import run_pipeline

        # Gravar estado "a_correr"
        status_file = Path(__file__).resolve().parent.parent.parent / "logs" / "pipeline_status.json"
        status_file.parent.mkdir(exist_ok=True)
        status_file.write_text(json.dumps({
            "state": "a_correr",
            "timestamp": datetime.now().isoformat(),
        }))

        result = run_pipeline()

        # Gravar estado final
        status_file.write_text(json.dumps({
            "state": "concluido",
            "timestamp": datetime.now().isoformat(),
            "mensagens": result.messages_fetched,
            "oportunidades": result.opportunities_found,
            "grupos": result.groups_processed,
            "erros": len(result.errors),
        }))

        return {
            "success": True,
            "messages": result.messages_fetched,
            "opportunities": result.opportunities_found,
            "groups": result.groups_processed,
            "errors": result.errors,
        }
    except Exception as e:
        logger.exception("Pipeline falhou")
        return {"success": False, "error": str(e)}


def _write_pipeline_status(state: str, **kwargs: Any) -> None:
    """Escreve estado do pipeline no ficheiro de status."""
    status_file = Path(__file__).resolve().parent.parent.parent / "logs" / "pipeline_status.json"
    status_file.parent.mkdir(exist_ok=True)
    data = {"state": state, "timestamp": datetime.now().isoformat()}
    data.update(kwargs)
    status_file.write_text(json.dumps(data))


def page_dashboard() -> None:
    """Pagina principal com oportunidades, metricas e graficos."""
    st.markdown('<h2 class="section-title">Painel de Oportunidades</h2>', unsafe_allow_html=True)

    # Banner + botao executar
    col_banner, col_btn = st.columns([5, 1])
    with col_banner:
        _render_pipeline_banner()
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        status = _get_pipeline_status()
        is_running = status and status.get("state") == "a_correr"
        if st.button("Executar agora", disabled=is_running, use_container_width=True):
            with st.spinner("A executar o pipeline..."):
                result = _run_pipeline_now()
            if result.get("success"):
                st.toast(
                    f"Pipeline concluido: {result['opportunities']} oportunidades, "
                    f"{result['groups']} grupos"
                )
            else:
                st.error(f"Pipeline falhou: {result.get('error', 'erro desconhecido')}")
            st.rerun()

    # Metricas
    metrics = fetch_today_metrics()
    gc = metrics.get("grade_counts", {})
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Oportunidades", metrics["total_today"], delta=f"{metrics['total_all']} total")
    with col2:
        best_score_val = str(metrics.get("best_score", "N/D")) if metrics.get("best_score") is not None else "N/D"
        st.metric("Melhor Deal Score", best_score_val)
    with col3:
        abc_count = gc.get("A", 0) + gc.get("B", 0) + gc.get("C", 0)
        st.metric("Grades A/B/C", abc_count)
    with col4:
        st.metric("Abaixo Mercado", metrics.get("below_market", 0))
    with col5:
        pv = metrics.get("pipeline_value", 0)
        pv_str = _format_price(pv) if pv else "0 EUR"
        st.metric("Pipeline Valor", pv_str)

    st.markdown("")

    # Pipeline status bar
    status_counts: Dict[str, int] = {}
    with get_session() as session:
        for s in STATUS_OPTIONS:
            cnt = session.execute(
                select(func.count(Opportunity.id))
                .where(Opportunity.is_opportunity.is_(True))
                .where(Opportunity.status == s)
            ).scalar() or 0
            status_counts[s] = cnt
    total_status = sum(status_counts.values()) or 1
    bar_html = '<div style="display:flex; border-radius:8px; overflow:hidden; height:28px; margin:8px 0 16px 0;">'
    for s, cnt in status_counts.items():
        pct = cnt / total_status * 100
        color = STATUS_COLORS.get(s, "#94A3B8")
        if pct > 0:
            bar_html += (
                f'<div style="width:{pct}%; background:{color}; display:flex; align-items:center; '
                f'justify-content:center;"><span style="font-size:0.7rem; color:white; '
                f'font-weight:600;">{s.capitalize()} ({cnt})</span></div>'
            )
    bar_html += '</div>'
    st.markdown(bar_html, unsafe_allow_html=True)

    # Filtros inline
    with st.container():
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1:
            period = st.selectbox(
                "Periodo",
                options=["Ultimos 7 dias", "Ultimos 30 dias", "Ultimos 90 dias", "Tudo"],
                index=1,
            )
        with f2:
            selected_grades = st.multiselect(
                "Deal Grade",
                options=["A", "B", "C", "D", "F"],
                default=[],
                help="A (80+) Excelente | B (60-79) Bom | C (40-59) Razoavel | D (20-39) Fraco | F (<20) Mau",
            )
        with f3:
            min_confidence = st.slider("Confianca minima", 0.0, 1.0, 0.6, 0.05)
        with f4:
            selected_opp_types = st.multiselect(
                "Tipo de oportunidade",
                options=OPPORTUNITY_TYPES,
                format_func=lambda x: OPPORTUNITY_TYPE_LABELS.get(x, x),
            )
        with f5:
            selected_statuses = st.multiselect(
                "Status",
                options=STATUS_OPTIONS,
                format_func=lambda x: x.capitalize(),
            )

    # Inicializar variaveis de filtros avancados ANTES do expander
    selected_prop_types: List[str] = []
    selected_districts: List[str] = []
    selected_municipalities: List[str] = []

    # Filtros avancados
    with st.expander("Filtros avancados"):
        fa1, fa2, fa3 = st.columns(3)
        with fa1:
            selected_prop_types = st.multiselect(
                "Tipo de imovel",
                options=PROPERTY_TYPES,
                format_func=lambda x: x.capitalize(),
            )
        filter_options = fetch_filter_options()
        with fa2:
            selected_districts = st.multiselect("Distrito", options=filter_options["districts"])
        with fa3:
            selected_municipalities = st.multiselect("Concelho", options=filter_options["municipalities"])

    # Calcular datas do periodo (unica vez)
    if period == "Tudo":
        start_date = None
        end_date = None
    else:
        days_map = {"Ultimos 7 dias": 7, "Ultimos 30 dias": 30, "Ultimos 90 dias": 90}
        start_date = date.today() - timedelta(days=days_map[period])
        end_date = date.today()

    # Buscar oportunidades
    opportunities = fetch_opportunities(
        start_date=start_date,
        end_date=end_date,
        min_confidence=min_confidence,
        opportunity_types=selected_opp_types or None,
        property_types=selected_prop_types or None,
        districts=selected_districts or None,
        municipalities=selected_municipalities or None,
        statuses=selected_statuses or None,
    )

    # Filtro por grade (client-side, ja temos os dados)
    if selected_grades:
        opportunities = [o for o in opportunities if o.get("deal_grade") in selected_grades]

    # Pesquisa textual
    search_query = st.text_input(
        "Pesquisar",
        placeholder="Localidade, tipo, mensagem...",
        label_visibility="collapsed",
    )
    if search_query:
        q = search_query.lower()
        opportunities = [
            o for o in opportunities
            if q in (o.get("original_message") or "").lower()
            or q in (o.get("location") or "").lower()
            or q in (o.get("municipality") or "").lower()
        ]

    # Ordenacao
    sort_options = {
        "Melhor Score": lambda o: (-(o.get("deal_score") or 0), o["created_at"]),
        "Mais Recentes": lambda o: o["created_at"],
        "Menor Preco": lambda o: (o.get("price") or float("inf")),
        "Maior Desconto": lambda o: (o.get("price_vs_market_pct") or float("inf")),
    }
    sort_by = st.selectbox("Ordenar por", options=list(sort_options.keys()), index=0)
    if sort_by == "Mais Recentes":
        opportunities.sort(key=sort_options[sort_by], reverse=True)
    else:
        opportunities.sort(key=sort_options[sort_by])

    st.markdown("")

    # Tabela de oportunidades
    if not opportunities:
        st.markdown(
            '<div class="empty-state">'
            "<h3>Sem oportunidades encontradas</h3>"
            "<p>Execute o pipeline para comecar a detetar oportunidades nos seus grupos de WhatsApp.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        # Header com contagem e export CSV
        hdr1, hdr2 = st.columns([4, 1])
        with hdr1:
            st.markdown(f'<h2 class="section-title">Oportunidades ({len(opportunities)})</h2>', unsafe_allow_html=True)
        with hdr2:
            df = pd.DataFrame(opportunities)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Exportar CSV", csv, "oportunidades.csv", "text/csv", use_container_width=False,
            )

        # Paginacao
        total_pages = max(1, (len(opportunities) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        if "page" not in st.session_state:
            st.session_state.page = 1
        # Garantir que a pagina nao excede o total
        if st.session_state.page > total_pages:
            st.session_state.page = total_pages
        page_num = st.session_state.page
        start_idx = (page_num - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_opps = opportunities[start_idx:end_idx]

        for opp in page_opps:
            opp_date = opp["created_at"].strftime("%d/%m/%Y %H:%M") if opp["created_at"] else "N/D"
            opp_type_label = OPPORTUNITY_TYPE_LABELS.get(opp["opportunity_type"] or "", opp["opportunity_type"] or "N/D")
            prop_type = (opp["property_type"] or "N/D").capitalize()
            location = opp["location"] or opp["municipality"] or "N/D"
            price_str = _format_price(opp["price"])

            grade_prefix = f"[{opp.get('deal_grade', '?')}{opp.get('deal_score', '')}] " if opp.get("deal_grade") else ""
            pvm = ""
            if opp.get("price_vs_market_pct") is not None:
                diff = opp["price_vs_market_pct"] - 100
                pvm = f"  |  {diff:+.0f}% vs mercado"
            header = f"{grade_prefix}{opp_type_label}  |  {prop_type}  |  {location}  |  {price_str}{pvm}"

            with st.expander(header):
                # Badges row
                badge_html = (
                    f'{_deal_grade_badge(opp.get("deal_grade"), opp.get("deal_score"))} &nbsp; '
                    f'{_confidence_badge(opp["confidence"])} &nbsp; '
                    f'{_status_badge(opp["status"])} &nbsp; '
                    f'<span class="opp-meta">{opp_date} &mdash; {opp["group_name"]}</span>'
                )
                # Match indicator
                try:
                    from src.analyzer.preferences import match_opportunity
                    match_result = match_opportunity(opp)
                    match_pct = match_result.get("match_pct", 50)
                    if match_result.get("total", 0) > 0:
                        if match_pct >= 80:
                            match_color = "#16A34A"
                        elif match_pct >= 60:
                            match_color = "#0369A1"
                        elif match_pct >= 40:
                            match_color = "#D97706"
                        else:
                            match_color = "#DC2626"
                        badge_html += (
                            f' &nbsp; <span style="background:{match_color}15; color:{match_color}; '
                            f'border:1px solid {match_color}40; padding:2px 10px; border-radius:6px; '
                            f'font-size:0.8rem; font-weight:600;">'
                            f'Match {match_pct}%</span>'
                        )
                except Exception:
                    pass
                st.markdown(badge_html, unsafe_allow_html=True)
                st.markdown("")

                # Mensagem original
                st.markdown("**Mensagem original do WhatsApp:**")
                st.markdown(
                    f'<div style="background:#F1F5F9; padding:12px 16px; border-radius:8px; '
                    f'border-left:3px solid #14B8A6; font-style:italic; color:#475569;">'
                    f'{opp["original_message"]}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("")

                # Raciocinio da IA
                if opp["ai_reasoning"]:
                    st.markdown("**Analise da IA:**")
                    st.markdown(
                        f'<div style="background:#EFF6FF; padding:12px 16px; border-radius:8px; '
                        f'border-left:3px solid #0369A1; color:#1E40AF;">'
                        f'{opp["ai_reasoning"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("")

                # Detalhes do imovel
                d1, d2, d3, d4 = st.columns(4)
                with d1:
                    st.markdown(f"**Preco:** {price_str}")
                with d2:
                    st.markdown(f"**Area:** {opp['area_m2']} m2" if opp["area_m2"] else "**Area:** N/D")
                with d3:
                    st.markdown(f"**Quartos:** T{opp['bedrooms']}" if opp["bedrooms"] else "**Quartos:** N/D")
                with d4:
                    st.markdown(f"**Distrito:** {opp['district'] or 'N/D'}")

                # Dados de mercado
                market_keys = [
                    "ine_median_price_m2", "casafari_median_price_m2",
                    "infocasa_median_price_m2", "sir_median_price_m2",
                    "idealista_avg_price_m2", "estimated_market_value",
                    "sir_market_position", "gross_yield_pct",
                ]
                has_market = any(opp[k] is not None for k in market_keys)

                if has_market:
                    st.markdown("---")
                    st.markdown("**Dados de Mercado**")

                    # SIR — posicao no mercado (destaque principal)
                    if opp["sir_market_position"]:
                        sir_labels = {
                            "muito_abaixo": ("Muito abaixo do mercado", COLORS["success"]),
                            "abaixo": ("Abaixo do mercado", COLORS["success"]),
                            "dentro": ("Dentro do mercado", COLORS["info"]),
                            "acima": ("Acima do mercado", COLORS["warning"]),
                            "muito_acima": ("Muito acima do mercado", COLORS["danger"]),
                        }
                        sir_label, sir_color = sir_labels.get(
                            opp["sir_market_position"],
                            (opp["sir_market_position"], COLORS["text_secondary"]),
                        )
                        sir_pct = ""
                        if opp["sir_price_vs_market_pct"] is not None:
                            sir_pct = f" ({opp['sir_price_vs_market_pct']:.0f}%)"
                        st.markdown(
                            f'<div style="background:#F8FAFC; border:1px solid {sir_color}; '
                            f'border-radius:8px; padding:12px 16px; margin-bottom:12px; text-align:center;">'
                            f'<strong style="color:{sir_color}; font-size:1.1rem;">'
                            f'{sir_label}{sir_pct}</strong>'
                            f'<br/><span style="color:#64748B; font-size:0.85rem;">SIR / Confidencial Imobiliario</span>'
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                    m1, m2, m3 = st.columns(3)

                    with m1:
                        st.markdown("**Fontes de preco/m2:**")
                        if opp["casafari_median_price_m2"] is not None:
                            st.markdown(
                                f"Casafari: **{_format_price(opp['casafari_median_price_m2'])}** "
                                f"({opp['casafari_comparables_count'] or 0} comp.)"
                            )
                        if opp["infocasa_median_price_m2"] is not None:
                            st.markdown(
                                f"Infocasa: **{_format_price(opp['infocasa_median_price_m2'])}** "
                                f"({opp['infocasa_comparables_count'] or 0} comp.)"
                            )
                        if opp["sir_median_price_m2"] is not None:
                            st.markdown(f"SIR (transacoes): **{_format_price(opp['sir_median_price_m2'])}**")
                        if opp["ine_median_price_m2"] is not None:
                            st.markdown(f"INE (baseline): **{_format_price(opp['ine_median_price_m2'])}**")
                        if opp["idealista_avg_price_m2"] is not None:
                            st.markdown(f"Idealista: **{_format_price(opp['idealista_avg_price_m2'])}**")

                    with m2:
                        if opp["estimated_market_value"] is not None:
                            st.markdown(f"Valor mercado: **{_format_price(opp['estimated_market_value'])}**")
                        if opp["estimated_monthly_rent"] is not None:
                            st.markdown(f"Renda est.: **{_format_price(opp['estimated_monthly_rent'])}/mes**")
                        if opp["price_vs_market_pct"] is not None:
                            diff = opp["price_vs_market_pct"] - 100
                            cls = "market-positive" if diff < 0 else "market-negative"
                            st.markdown(
                                f'Dif. mercado: <span class="{cls}">{diff:+.1f}%</span>',
                                unsafe_allow_html=True,
                            )

                    with m3:
                        if opp["gross_yield_pct"] is not None:
                            st.markdown(f"Yield bruto: **{opp['gross_yield_pct']:.1f}%**")
                        if opp["net_yield_pct"] is not None:
                            st.markdown(f"Yield liquido: **{opp['net_yield_pct']:.1f}%**")
                        if opp["imt_estimate"] is not None:
                            st.markdown(f"IMT: **{_format_price(opp['imt_estimate'])}**")
                        if opp["total_acquisition_cost"] is not None:
                            st.markdown(f"Custo total: **{_format_price(opp['total_acquisition_cost'])}**")

                # Score breakdown
                if opp.get("deal_score") is not None:
                    st.markdown("---")
                    st.markdown("**Deal Score Breakdown**")
                    score_val = opp.get("deal_score", 0)
                    st.progress(min(score_val / 100.0, 1.0))

                # Copiar resumo
                if st.button("Copiar resumo", key=f"copy_{opp['id']}"):
                    summary = (
                        f"{opp_type_label} | {prop_type} | {location}\n"
                        f"Preco: {price_str}\n"
                        f"Area: {opp['area_m2'] or 'N/D'} m2 | Quartos: T{opp['bedrooms'] or 'N/D'}\n"
                        f"Score: {opp.get('deal_score', 'N/D')} ({opp.get('deal_grade', 'N/D')})\n"
                        f"Grupo: {opp['group_name']}\n"
                        f"---\n{opp['original_message']}"
                    )
                    st.code(summary, language=None)

                # Notes
                current_notes = opp.get("notes") or ""
                new_notes = st.text_area(
                    "Notas",
                    value=current_notes,
                    key=f"notes_{opp['id']}",
                    height=80,
                    placeholder="Adicionar notas...",
                )
                if new_notes != current_notes:
                    if st.button("Guardar notas", key=f"save_notes_{opp['id']}"):
                        update_opportunity_notes(opp["id"], new_notes)
                        st.rerun()

                # Botoes de acao
                st.markdown("---")
                a0, a1, a2, a3, a4 = st.columns(5)
                with a0:
                    if st.button("Nova", key=f"nov_{opp['id']}", use_container_width=True):
                        update_opportunity_status(opp["id"], "nova")
                        st.rerun()
                with a1:
                    if st.button("Interessante", key=f"int_{opp['id']}", use_container_width=True):
                        update_opportunity_status(opp["id"], "interessante")
                        st.rerun()
                with a2:
                    if st.button("Analisada", key=f"ana_{opp['id']}", use_container_width=True):
                        update_opportunity_status(opp["id"], "analisada")
                        st.rerun()
                with a3:
                    if st.button("Contactada", key=f"con_{opp['id']}", use_container_width=True):
                        update_opportunity_status(opp["id"], "contactada")
                        st.rerun()
                with a4:
                    with st.popover("Descartar", use_container_width=True):
                        discard_reasons = [
                            "Preco alto",
                            "Localizacao nao interessa",
                            "Estado do imovel",
                            "Nao e oportunidade real",
                            "Ja contactado sem sucesso",
                            "Informacao insuficiente",
                            "Outro",
                        ]
                        reason = st.selectbox(
                            "Razao do descarte",
                            options=discard_reasons,
                            key=f"reason_{opp['id']}",
                        )
                        obs = st.text_input(
                            "Observacao (opcional)",
                            key=f"obs_{opp['id']}",
                            placeholder="Detalhe adicional...",
                        )
                        if st.button("Confirmar descarte", key=f"confirm_dis_{opp['id']}", type="primary", use_container_width=True):
                            note_text = f"[DESCARTADA] {reason}"
                            if obs:
                                note_text += f" — {obs}"
                            existing_notes = opp.get("notes") or ""
                            if existing_notes:
                                note_text = f"{existing_notes}\n{note_text}"
                            update_opportunity_notes(opp["id"], note_text)
                            update_opportunity_status(opp["id"], "descartada")
                            st.rerun()

        # Paginacao controls
        if total_pages > 1:
            p1, p2, p3 = st.columns([1, 2, 1])
            with p1:
                if st.button("Anterior", disabled=page_num <= 1):
                    st.session_state.page -= 1
                    st.rerun()
            with p2:
                st.markdown(
                    f"<p style='text-align:center'>Pagina {page_num} de {total_pages}</p>",
                    unsafe_allow_html=True,
                )
            with p3:
                if st.button("Seguinte", disabled=page_num >= total_pages):
                    st.session_state.page += 1
                    st.rerun()

    # Graficos
    st.markdown("")
    st.markdown('<h2 class="section-title">Analise</h2>', unsafe_allow_html=True)

    # Calcular dias para o grafico a partir do periodo selecionado
    days_for_chart = {"Ultimos 7 dias": 7, "Ultimos 30 dias": 30, "Ultimos 90 dias": 90}.get(period, 9999)
    daily_data = fetch_daily_counts(days=days_for_chart)
    if daily_data:
        fig_daily = px.bar(
            daily_data, x="day", y="total",
            title=f"Oportunidades por dia ({period.lower()})",
            labels={"day": "Data", "total": "Total"},
        )
        fig_daily.update_layout(**PLOTLY_LAYOUT)
        fig_daily.update_traces(marker_color="#14B8A6", marker_line_width=0)
        st.plotly_chart(fig_daily, use_container_width=True)
    else:
        st.caption("Sem dados para o grafico diario.")

    chart_c1, chart_c2, chart_c3 = st.columns(3)

    type_data = fetch_type_distribution()
    with chart_c1:
        if type_data:
            for item in type_data:
                item["label"] = OPPORTUNITY_TYPE_LABELS.get(item["type"], item["type"])
            fig_pie = px.pie(
                type_data, values="total", names="label",
                title="Distribuicao por tipo",
                hole=0.45,
            )
            fig_pie.update_layout(**PLOTLY_LAYOUT)
            fig_pie.update_traces(textfont_color="#475569")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.caption("Sem dados para distribuicao por tipo.")

    muni_data = fetch_top_municipalities(limit=10)
    with chart_c2:
        if muni_data:
            fig_muni = px.bar(
                muni_data, x="total", y="municipality", orientation="h",
                title="Top concelhos",
                labels={"municipality": "Concelho", "total": "Total"},
            )
            fig_muni.update_layout(**PLOTLY_LAYOUT)
            fig_muni.update_layout(yaxis={"categoryorder": "total ascending"})
            fig_muni.update_traces(marker_color="#0369A1", marker_line_width=0)
            st.plotly_chart(fig_muni, use_container_width=True)
        else:
            st.caption("Sem dados para top concelhos.")

    # Grade distribution donut chart
    with chart_c3:
        grade_data = [
            {"grade": g, "count": gc.get(g, 0)}
            for g in ["A", "B", "C", "D", "F"]
            if gc.get(g, 0) > 0
        ]
        if grade_data:
            fig_grades = px.pie(
                grade_data, values="count", names="grade",
                title="Distribuicao por Grade",
                hole=0.5,
                color="grade",
                color_discrete_map=GRADE_COLORS,
            )
            fig_grades.update_layout(**PLOTLY_LAYOUT)
            st.plotly_chart(fig_grades, use_container_width=True)
        else:
            st.caption("Sem dados para distribuicao por grade.")


# ---------------------------------------------------------------------------
# Pagina: Pipeline
# ---------------------------------------------------------------------------


def page_pipeline() -> None:
    """Pagina de gestao do pipeline."""
    st.markdown('<h2 class="section-title">Pipeline de Processamento</h2>', unsafe_allow_html=True)

    st.markdown(
        '<div class="info-box">'
        "O pipeline busca mensagens dos seus grupos de WhatsApp, analisa-as com IA "
        "e enriquece as oportunidades com dados de mercado."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")

    # Status
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Executar Pipeline")
        st.markdown("Corra o pipeline manualmente para processar novas mensagens.")
        if st.button("Executar Pipeline Agora", use_container_width=True, type="primary"):
            try:
                from src.pipeline.run import run_pipeline

                _write_pipeline_status("a_correr")
                with st.spinner("A executar o pipeline..."):
                    result = run_pipeline()
                _write_pipeline_status(
                    "concluido",
                    mensagens=result.messages_fetched,
                    oportunidades=result.opportunities_found,
                    grupos=result.groups_processed,
                    erros=len(result.errors),
                )
                st.success(
                    f"Pipeline concluido: {result.messages_fetched} mensagens processadas, "
                    f"{result.opportunities_found} oportunidades encontradas em "
                    f"{result.groups_processed} grupos."
                )
                if result.errors:
                    for err in result.errors:
                        st.warning(err)
                st.rerun()
            except ImportError:
                st.error("Modulo do pipeline nao disponivel. Verifique a instalacao.")
            except Exception as exc:
                logger.exception("Erro no pipeline")
                _write_pipeline_status("erro", detalhe=str(exc))
                st.error(f"Erro ao executar: {exc}")

        st.markdown("")
        st.markdown("### Re-pontuar Oportunidades")
        st.markdown("Re-calcula o Deal Score de todas as oportunidades existentes.")
        if st.button("Rescore All", use_container_width=True):
            try:
                from src.analyzer.deal_scorer import rescore_all_opportunities
                with st.spinner("A re-pontuar oportunidades..."):
                    results = rescore_all_opportunities()
                rescore_gc: Dict[str, int] = {}
                for r in results:
                    rescore_gc[r["grade"]] = rescore_gc.get(r["grade"], 0) + 1
                st.success(
                    f"Rescoring concluido: {len(results)} oportunidades. "
                    f"A:{rescore_gc.get('A', 0)} B:{rescore_gc.get('B', 0)} C:{rescore_gc.get('C', 0)} "
                    f"D:{rescore_gc.get('D', 0)} F:{rescore_gc.get('F', 0)}"
                )
                st.rerun()
            except Exception as exc:
                logger.exception("Erro no rescoring")
                st.error(f"Erro: {exc}")

    with col2:
        st.markdown("### Agendamento Automatico")
        st.markdown("O pipeline pode ser agendado para correr automaticamente todos os dias as 08:00.")

        st.code("bash scripts/setup_cron.sh", language="bash")
        st.caption("Execute este comando no terminal para ativar o cron job.")

    st.markdown("")

    # Metricas globais
    st.markdown("### Estatisticas Globais")
    metrics = fetch_today_metrics()

    g1, g2, g3 = st.columns(3)
    with g1:
        st.metric("Total de Oportunidades", metrics["total_all"])
    with g2:
        st.metric("Oportunidades Hoje", metrics["total_today"])
    with g3:
        st.metric("Grupos Processados Hoje", metrics["groups_today"])

    # Log de processamento por grupo
    st.markdown("")
    st.markdown("### Log de Processamento por Grupo")

    groups_log_file = Path(__file__).resolve().parent.parent.parent / "logs" / "pipeline_groups.json"
    if groups_log_file.exists():
        try:
            groups_log = json.loads(groups_log_file.read_text())
            log_ts = groups_log.get("timestamp", "")
            resumo = groups_log.get("resumo", {})
            st.caption(
                f"Ultima execucao: {log_ts[:19].replace('T', ' ')} UTC | "
                f"{resumo.get('grupos', 0)} grupos, {resumo.get('mensagens', 0)} msgs, "
                f"{resumo.get('oportunidades', 0)} oportunidades, {resumo.get('erros', 0)} erros"
            )

            grupos = groups_log.get("grupos", [])
            if grupos:
                rows = []
                for g in grupos:
                    ultima = g.get("ultima_mensagem")
                    rows.append({
                        "Grupo": g.get("grupo", ""),
                        "Estado": g.get("estado", ""),
                        "Msgs": g.get("mensagens_buscadas", 0),
                        "Filtradas": g.get("mensagens_filtradas", 0),
                        "Oportunidades": g.get("oportunidades", 0),
                        "Ultima Msg": (ultima.get("conteudo", "")[:80] if ultima else "-"),
                        "Remetente": (ultima.get("remetente", "") if ultima else "-"),
                        "Hora Msg": (ultima.get("timestamp", "")[:19].replace("T", " ") if ultima else "-"),
                        "Erro": g.get("erro", "") or "",
                    })
                df_log = pd.DataFrame(rows)
                st.dataframe(df_log, use_container_width=True, height=500)
        except Exception as exc:
            st.warning(f"Erro ao ler log de grupos: {exc}")
    else:
        st.markdown(
            '<div class="info-box">Sem log de grupos. Execute o pipeline para gerar.</div>',
            unsafe_allow_html=True,
        )

    # Ultimas execucoes (log file)
    st.markdown("")
    st.markdown("### Registo de Execucoes (Raw)")

    log_file = Path(__file__).resolve().parent.parent.parent / "logs" / "pipeline.log"
    if log_file.exists():
        log_content = log_file.read_text()
        lines = log_content.strip().split("\n")[-50:]  # Ultimas 50 linhas
        with st.expander("Ver log raw"):
            st.text_area("Ultimas entradas do log", value="\n".join(lines), height=300)
    else:
        st.markdown(
            '<div class="info-box">Sem registos de execucao.</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Pagina: Configuracao
# ---------------------------------------------------------------------------


def page_configuracao() -> None:
    """Pagina de configuracao de API keys e settings."""
    st.markdown('<h2 class="section-title">Configuracao</h2>', unsafe_allow_html=True)

    env_values = _load_env_values()
    env_file = _env_path()

    if not env_file.exists():
        st.markdown(
            '<div class="warn-box">'
            "Ficheiro .env nao encontrado. Preencha os campos abaixo para criar a configuracao."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")

    # WhatsApp
    st.markdown("### WhatsApp")
    st.caption(
        "Por defeito, o ImoScout conecta-se diretamente ao WhatsApp via Baileys Bridge "
        "(gratuito). Opcionalmente, pode usar a API paga Whapi.Cloud."
    )

    whapi_token = st.text_input(
        "WHAPI_TOKEN (Opcional)",
        value=env_values.get("WHAPI_TOKEN", ""),
        type="password",
        help="Token da API Whapi.Cloud. Deixe vazio para usar o Baileys Bridge gratuito.",
    )
    current_whapi = env_values.get("WHAPI_TOKEN", "")
    if current_whapi:
        st.caption(f"Whapi.Cloud configurado: {_mask_key(current_whapi)}")
    else:
        st.caption("A usar Baileys Bridge (gratuito). Configure na pagina WhatsApp.")

    st.markdown("")

    # Anthropic
    st.markdown("### Anthropic (Claude Haiku)")
    st.caption("Obrigatorio para a analise de mensagens com IA.")

    anthropic_key = st.text_input(
        "ANTHROPIC_API_KEY",
        value=env_values.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Chave API da Anthropic",
    )
    current_anthropic = env_values.get("ANTHROPIC_API_KEY", "")
    if current_anthropic:
        st.caption(f"Configurado: {_mask_key(current_anthropic)}")

    st.markdown("")

    # Casafari
    st.markdown("### Casafari")
    st.caption("Comparaveis e estatisticas de mercado. Token de acesso a API.")

    casafari_token = st.text_input(
        "CASAFARI_API_TOKEN",
        value=env_values.get("CASAFARI_API_TOKEN", ""),
        type="password",
        help="Token de acesso a API Casafari",
    )

    st.markdown("")

    # SIR / Confidencial Imobiliario
    st.markdown("### SIR / Confidencial Imobiliario")
    st.caption("Precos de transacao reais. Usado para validar se o preco esta dentro, acima ou abaixo do mercado.")

    s1, s2 = st.columns(2)
    with s1:
        sir_user = st.text_input(
            "SIR_USERNAME",
            value=env_values.get("SIR_USERNAME", ""),
            help="Username do SIR",
        )
    with s2:
        sir_pass = st.text_input(
            "SIR_PASSWORD",
            value=env_values.get("SIR_PASSWORD", ""),
            type="password",
            help="Password do SIR",
        )

    st.markdown("")

    # Idealista
    st.markdown("### Idealista (Opcional)")
    st.caption("Listings ativos do Idealista. Opcional -- o sistema funciona sem esta configuracao.")

    i1, i2 = st.columns(2)
    with i1:
        idealista_id = st.text_input(
            "IDEALISTA_CLIENT_ID",
            value=env_values.get("IDEALISTA_CLIENT_ID", ""),
            help="Client ID da API Idealista",
        )
    with i2:
        idealista_secret = st.text_input(
            "IDEALISTA_CLIENT_SECRET",
            value=env_values.get("IDEALISTA_CLIENT_SECRET", ""),
            type="password",
            help="Client Secret da API Idealista",
        )

    st.markdown("")

    # Configuracoes do pipeline
    st.markdown("### Pipeline")
    p1, p2, p3 = st.columns(3)
    with p1:
        min_conf = st.number_input(
            "Confianca minima",
            min_value=0.0, max_value=1.0,
            value=float(env_values.get("MIN_CONFIDENCE", "0.6")),
            step=0.05,
            help="Confianca minima para enriquecer com dados de mercado",
        )
    with p2:
        batch_size = st.number_input(
            "Tamanho do batch",
            min_value=5, max_value=50,
            value=int(env_values.get("BATCH_SIZE", "20")),
            step=5,
            help="Numero de mensagens por chamada a IA",
        )
    with p3:
        timezone = st.text_input(
            "Timezone",
            value=env_values.get("TIMEZONE", "Europe/Lisbon"),
            help="Fuso horario para o pipeline",
        )

    # Base de dados
    st.markdown("")
    st.markdown("### Base de Dados")
    db_url = st.text_input(
        "DATABASE_URL",
        value=env_values.get("DATABASE_URL", "sqlite:///data/imoscout.db"),
        help="URL de conexao a base de dados",
    )

    st.markdown("")
    st.markdown("---")

    # Guardar
    if st.button("Guardar Configuracao", type="primary", use_container_width=True):
        new_values = {
            "WHAPI_TOKEN": whapi_token,
            "ANTHROPIC_API_KEY": anthropic_key,
            "CASAFARI_API_TOKEN": casafari_token,
            "SIR_USERNAME": sir_user,
            "SIR_PASSWORD": sir_pass,
            "IDEALISTA_CLIENT_ID": idealista_id,
            "IDEALISTA_CLIENT_SECRET": idealista_secret,
            "DATABASE_URL": db_url,
            "MIN_CONFIDENCE": str(min_conf),
            "BATCH_SIZE": str(batch_size),
            "TIMEZONE": timezone,
        }
        _save_env_values(new_values)
        st.success("Configuracao guardada com sucesso. Reinicie o pipeline para aplicar as alteracoes.")

    # Status da configuracao
    st.markdown("")
    st.markdown("### Estado da Configuracao")
    checks = [
        ("WhatsApp (Baileys ou Whapi)", True),
        ("Anthropic (Claude Haiku)", bool(anthropic_key)),
        ("Casafari", bool(casafari_token)),
        ("SIR / Confidencial Imobiliario", bool(sir_user and sir_pass)),
        ("Idealista (Opcional)", bool(idealista_id and idealista_secret)),
        ("Base de Dados", bool(db_url)),
    ]
    for name, ok in checks:
        color = COLORS["success"] if ok else COLORS["text_muted"]
        label = "Configurado" if ok else "Nao configurado"
        st.markdown(
            f'<div style="display:flex; align-items:center; gap:10px; padding:8px 0;">'
            f'<span style="color:{color}; font-size:1.2rem; font-weight:bold;">'
            f'{"&#10003;" if ok else "&#10007;"}</span>'
            f'<span style="color:#1E293B;">{name}</span>'
            f'<span style="color:{color}; font-size:0.85rem;">({label})</span>'
            f"</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Pagina: WhatsApp
# ---------------------------------------------------------------------------


def page_whatsapp() -> None:
    """Pagina de conexao e estado do WhatsApp via Baileys Bridge."""
    st.markdown('<h2 class="section-title">WhatsApp</h2>', unsafe_allow_html=True)

    st.markdown(
        '<p style="color:#64748B; margin-bottom:24px;">'
        "Conexao direta ao WhatsApp via Baileys Bridge (gratuito). "
        "Nenhuma API paga necessaria."
        "</p>",
        unsafe_allow_html=True,
    )

    # Verificar se o bridge esta a correr
    bridge_url = os.environ.get("BRIDGE_URL", "http://localhost:3000")

    try:
        import httpx
        with httpx.Client(timeout=5.0) as http_client:
            resp = http_client.get(f"{bridge_url}/status")
            status_data = resp.json()
    except Exception:
        status_data = None

    if status_data is None:
        st.markdown(
            '<div class="warn-box">'
            "<strong>Bridge offline</strong> -- O servidor Baileys nao esta a correr.<br/><br/>"
            "Para iniciar:<br/>"
            "<code>cd whatsapp-bridge && npm start</code>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Verificar novamente", use_container_width=True):
            st.rerun()
        return

    connection_status = status_data.get("status", "disconnected")
    connected = status_data.get("connected", False)
    qr = status_data.get("qr")
    user_info = status_data.get("user")

    # Estado da conexao
    if connected:
        user_name = user_info.get("name", "N/A") if user_info else "N/A"
        st.markdown(
            f'<div style="background:#F0FDF4; border:1px solid #16A34A; border-radius:12px; '
            f'padding:24px; text-align:center; margin-bottom:24px;">'
            f'<span style="color:#16A34A; font-size:2rem;">&#10003;</span>'
            f'<h3 style="color:#16A34A; margin:8px 0 4px 0;">Conectado</h3>'
            f'<p style="color:#64748B; margin:0;">Sessao ativa como <strong style="color:#1E293B;">{user_name}</strong></p>'
            f"</div>",
            unsafe_allow_html=True,
        )

        # Acoes
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Atualizar Estado", use_container_width=True):
                st.rerun()
        with c2:
            if st.button("Desconectar", type="secondary", use_container_width=True):
                try:
                    import httpx as hx
                    with hx.Client(timeout=10.0) as hc:
                        hc.post(f"{bridge_url}/logout")
                    st.warning("Sessao terminada. Reinicie o bridge para reconectar.")
                except Exception as e:
                    st.error(f"Erro ao desconectar: {e}")

    elif connection_status == "waiting_qr" and qr:
        st.markdown(
            '<div style="background:#FFFBEB; border:1px solid #D97706; border-radius:12px; '
            'padding:24px; text-align:center; margin-bottom:24px;">'
            '<h3 style="color:#B45309; margin:0 0 8px 0;">A aguardar scan do QR Code</h3>'
            '<p style="color:#64748B; margin:0 0 16px 0;">'
            "Abra o WhatsApp no telemovel &gt; Dispositivos ligados &gt; Ligar dispositivo</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        # Gerar QR code como imagem
        try:
            import qrcode
            import io
            import base64

            qr_img = qrcode.make(qr)
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG")
            qr_b64 = base64.b64encode(buf.getvalue()).decode()

            st.markdown(
                f'<div style="text-align:center; padding:16px;">'
                f'<img src="data:image/png;base64,{qr_b64}" '
                f'style="max-width:300px; border-radius:8px; background:white; padding:16px;" />'
                f"</div>",
                unsafe_allow_html=True,
            )
        except ImportError:
            st.code(qr, language=None)
            st.caption("Instale 'qrcode[pil]' para ver o QR code como imagem.")

        if st.button("Atualizar QR Code", use_container_width=True):
            st.rerun()

    else:
        st.markdown(
            '<div style="background:#FEF2F2; border:1px solid #DC2626; border-radius:12px; '
            'padding:24px; text-align:center; margin-bottom:24px;">'
            '<h3 style="color:#DC2626; margin:0 0 8px 0;">Desconectado</h3>'
            '<p style="color:#64748B; margin:0;">'
            "O bridge esta a correr mas nao esta conectado ao WhatsApp.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Verificar novamente", use_container_width=True):
            st.rerun()

    # Informacoes do bridge
    st.markdown("")
    st.markdown("### Informacoes")
    st.markdown(
        f'<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:16px;">'
        f'<p style="color:#64748B; margin:4px 0;"><strong style="color:#1E293B;">Bridge URL:</strong> {bridge_url}</p>'
        f'<p style="color:#64748B; margin:4px 0;"><strong style="color:#1E293B;">Estado:</strong> {connection_status}</p>'
        f'<p style="color:#64748B; margin:4px 0;"><strong style="color:#1E293B;">Backend:</strong> Baileys (gratuito)</p>'
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Pagina: Grupos
# ---------------------------------------------------------------------------


def page_grupos() -> None:
    """Pagina de gestao dos grupos de WhatsApp."""
    st.markdown('<h2 class="section-title">Grupos de WhatsApp</h2>', unsafe_allow_html=True)

    groups = fetch_groups()

    if not groups:
        st.markdown(
            '<div class="empty-state">'
            "<h3>Sem grupos registados</h3>"
            "<p>Os grupos serao registados automaticamente apos a primeira execucao do pipeline. "
            "Conecte o WhatsApp na pagina WhatsApp.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Metricas
    active_count = sum(1 for g in groups if g["is_active"])
    total_msgs = sum(g["message_count"] for g in groups)
    total_opps = sum(g["opportunity_count"] for g in groups)

    g1, g2, g3 = st.columns(3)
    with g1:
        st.metric("Grupos Ativos", f"{active_count}/{len(groups)}")
    with g2:
        st.metric("Total Mensagens", total_msgs)
    with g3:
        st.metric("Total Oportunidades", total_opps)

    st.markdown("")

    # Lista de grupos
    for group in groups:
        with st.container():
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])

            with c1:
                status_icon = "&#9679;" if group["is_active"] else "&#9675;"
                status_color = COLORS["success"] if group["is_active"] else COLORS["text_muted"]
                last_proc = (
                    group["last_processed_at"].strftime("%d/%m/%Y %H:%M")
                    if group["last_processed_at"] else "Nunca"
                )
                st.markdown(
                    f'<div style="padding:8px 0;">'
                    f'<span style="color:{status_color}; margin-right:8px;">{status_icon}</span>'
                    f'<strong style="color:#1E293B;">{group["name"]}</strong>'
                    f'<br/><span style="color:#64748B; font-size:0.85rem;">'
                    f'Ultimo processamento: {last_proc}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

            with c2:
                st.markdown(
                    f'<div style="text-align:center; padding:12px 0;">'
                    f'<span style="color:#64748B; font-size:0.85rem;">Mensagens</span><br/>'
                    f'<strong style="color:#1E293B;">{group["message_count"]}</strong>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

            with c3:
                st.markdown(
                    f'<div style="text-align:center; padding:12px 0;">'
                    f'<span style="color:#64748B; font-size:0.85rem;">Oportunidades</span><br/>'
                    f'<strong style="color:#14B8A6;">{group["opportunity_count"]}</strong>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

            with c4:
                new_state = not group["is_active"]
                label = "Desativar" if group["is_active"] else "Ativar"
                if st.button(label, key=f"toggle_{group['id']}", use_container_width=True):
                    toggle_group_active(group["id"], new_state)
                    st.rerun()

            st.markdown('<hr style="border-color:#E2E8F0; margin:4px 0;">', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Pagina: Preferencias
# ---------------------------------------------------------------------------


def page_preferencias() -> None:
    """Pagina de preferencias do utilizador."""
    st.markdown('<h2 class="section-title">O Que Procuro</h2>', unsafe_allow_html=True)

    st.markdown(
        '<div class="info-box">'
        "Defina o seu perfil de investimento. As oportunidades que encaixam no perfil "
        "recebem um bonus no Deal Score e sao destacadas no dashboard."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")

    from src.analyzer.preferences import load_preferences, save_preferences

    prefs = load_preferences()

    # Descricao livre
    st.markdown("### Descricao geral")
    description = st.text_area(
        "Descreva o que procura (opcional)",
        value=prefs.get("description", ""),
        height=80,
        placeholder="Ex: Procuro T2/T3 em Lisboa ou margem sul, ate 350k, para investimento de rendimento...",
    )

    st.markdown("")

    # Tipos
    st.markdown("### Tipo de imovel e oportunidade")
    t1, t2 = st.columns(2)
    with t1:
        property_types = st.multiselect(
            "Tipos de imovel",
            options=["apartamento", "moradia", "terreno", "predio", "loja", "armazem", "escritorio"],
            default=prefs.get("property_types", []),
            format_func=lambda x: x.capitalize(),
            help="Deixe vazio para aceitar todos os tipos",
        )
    with t2:
        opportunity_types = st.multiselect(
            "Tipos de oportunidade",
            options=[
                "abaixo_mercado", "venda_urgente", "off_market", "reabilitacao",
                "leilao", "heranca", "divorcio", "dacao_banco", "rendimento",
                "terreno", "predio_inteiro", "terreno_viabilidade", "yield_alto",
            ],
            default=prefs.get("opportunity_types", []),
            format_func=lambda x: OPPORTUNITY_TYPE_LABELS.get(x, x),
            help="Deixe vazio para aceitar todos os tipos",
        )

    st.markdown("")

    # Localizacao
    st.markdown("### Localizacao")
    l1, l2 = st.columns(2)

    filter_options = fetch_filter_options()

    with l1:
        locations_include = st.multiselect(
            "Concelhos que me interessam",
            options=filter_options.get("municipalities", []),
            default=[l for l in prefs.get("locations_include", []) if l in filter_options.get("municipalities", [])],
            help="Deixe vazio para aceitar todos",
        )
    with l2:
        locations_exclude = st.multiselect(
            "Concelhos a excluir",
            options=filter_options.get("municipalities", []),
            default=[l for l in prefs.get("locations_exclude", []) if l in filter_options.get("municipalities", [])],
            help="Oportunidades nestes concelhos serao penalizadas",
        )

    st.markdown("")

    # Preco e area
    st.markdown("### Orcamento e caracteristicas")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        price_min = st.number_input(
            "Preco minimo (EUR)",
            min_value=0,
            value=prefs.get("price_min") or 0,
            step=10000,
            help="0 = sem minimo",
        )
    with p2:
        price_max = st.number_input(
            "Preco maximo (EUR)",
            min_value=0,
            value=prefs.get("price_max") or 0,
            step=10000,
            help="0 = sem maximo",
        )
    with p3:
        area_min = st.number_input(
            "Area minima (m2)",
            min_value=0,
            value=prefs.get("area_min") or 0,
            step=10,
            help="0 = sem minimo",
        )
    with p4:
        area_max = st.number_input(
            "Area maxima (m2)",
            min_value=0,
            value=prefs.get("area_max") or 0,
            step=10,
            help="0 = sem maximo",
        )

    b1, b2 = st.columns(2)
    with b1:
        bedrooms_min = st.number_input(
            "Quartos minimo (T?)",
            min_value=0,
            max_value=10,
            value=prefs.get("bedrooms_min") or 0,
            help="0 = sem minimo",
        )
    with b2:
        bedrooms_max = st.number_input(
            "Quartos maximo (T?)",
            min_value=0,
            max_value=10,
            value=prefs.get("bedrooms_max") or 0,
            help="0 = sem maximo",
        )

    st.markdown("")

    # Criterios financeiros
    st.markdown("### Criterios financeiros")
    fin1, fin2 = st.columns(2)
    with fin1:
        max_pvm = st.number_input(
            "Preco maximo vs mercado (%)",
            min_value=0,
            max_value=200,
            value=prefs.get("max_price_vs_market_pct") or 0,
            step=5,
            help="Ex: 95 = so quero imoveis ate 95%% do valor de mercado. 0 = sem limite.",
        )
    with fin2:
        min_yield = st.number_input(
            "Yield bruto minimo (%)",
            min_value=0.0,
            max_value=30.0,
            value=float(prefs.get("min_yield_pct") or 0),
            step=0.5,
            help="Ex: 5.0 = so quero imoveis com yield >= 5%%. 0 = sem limite.",
        )

    st.markdown("")
    st.markdown("---")

    # Guardar
    if st.button("Guardar Preferencias", type="primary", use_container_width=True):
        new_prefs = {
            "description": description,
            "property_types": property_types,
            "opportunity_types": opportunity_types,
            "locations_include": locations_include,
            "locations_exclude": locations_exclude,
            "price_min": price_min if price_min > 0 else None,
            "price_max": price_max if price_max > 0 else None,
            "area_min": area_min if area_min > 0 else None,
            "area_max": area_max if area_max > 0 else None,
            "bedrooms_min": bedrooms_min if bedrooms_min > 0 else None,
            "bedrooms_max": bedrooms_max if bedrooms_max > 0 else None,
            "max_price_vs_market_pct": max_pvm if max_pvm > 0 else None,
            "min_yield_pct": min_yield if min_yield > 0 else None,
        }
        save_preferences(new_prefs)
        st.success("Preferencias guardadas! As oportunidades serao re-avaliadas na proxima execucao do pipeline ou ao clicar 'Rescore All'.")

    # Preview: mostrar preferencias ativas
    st.markdown("")
    st.markdown("### Resumo do perfil")
    active_prefs = []
    if property_types:
        active_prefs.append(f"Tipos: {', '.join(t.capitalize() for t in property_types)}")
    if opportunity_types:
        active_prefs.append(f"Oportunidades: {', '.join(OPPORTUNITY_TYPE_LABELS.get(t, t) for t in opportunity_types)}")
    if locations_include:
        active_prefs.append(f"Concelhos: {', '.join(locations_include)}")
    if locations_exclude:
        active_prefs.append(f"Excluir: {', '.join(locations_exclude)}")
    if price_min > 0 or price_max > 0:
        price_range = f"{price_min:,.0f}".replace(",", ".") if price_min > 0 else "0"
        price_range += f" - {price_max:,.0f} EUR".replace(",", ".") if price_max > 0 else "+ EUR"
        active_prefs.append(f"Preco: {price_range}")
    if area_min > 0 or area_max > 0:
        active_prefs.append(f"Area: {area_min or 0} - {area_max or '...'} m2")
    if bedrooms_min > 0 or bedrooms_max > 0:
        active_prefs.append(f"Quartos: T{bedrooms_min or 0} - T{bedrooms_max or '...'}")
    if max_pvm > 0:
        active_prefs.append(f"Max vs mercado: {max_pvm}%")
    if min_yield > 0:
        active_prefs.append(f"Yield minimo: {min_yield}%")

    if active_prefs:
        for p in active_prefs:
            st.markdown(f"- {p}")
    else:
        st.caption("Nenhuma preferencia definida. Todas as oportunidades serao avaliadas igualmente.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Ponto de entrada principal do dashboard."""
    st.set_page_config(
        page_title="ImoScout",
        page_icon="https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f3e0.png",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Injectar CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Garantir BD
    init_db()

    # Sidebar — Navegacao
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center; padding:16px 0 24px 0;">'
            '<h1 style="font-family:Cinzel,serif; font-size:1.8rem; color:#14B8A6; '
            'margin:0; letter-spacing:0.05em;">ImoScout</h1>'
            '<p style="font-family:Josefin Sans,sans-serif; font-size:0.8rem; '
            'color:#64748B; margin:4px 0 0 0;">Detetor de Oportunidades</p>'
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown('<hr style="border-color:#E2E8F0; margin:0 0 16px 0;">', unsafe_allow_html=True)

        page = st.radio(
            "Navegacao",
            options=["Dashboard", "Pipeline", "Preferencias", "WhatsApp", "Configuracao", "Grupos"],
            label_visibility="collapsed",
        )

        st.markdown("")
        st.markdown("")

        # Rodape sidebar
        st.markdown(
            '<div style="position:fixed; bottom:16px; padding:0 16px;">'
            '<p style="font-family:Josefin Sans,sans-serif; font-size:0.75rem; color:#475569;">'
            "ImoScout v0.1.0</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    # Renderizar pagina
    if page == "Dashboard":
        page_dashboard()
    elif page == "Pipeline":
        page_pipeline()
    elif page == "WhatsApp":
        page_whatsapp()
    elif page == "Preferencias":
        page_preferencias()
    elif page == "Configuracao":
        page_configuracao()
    elif page == "Grupos":
        page_grupos()


if __name__ == "__main__":
    main()
