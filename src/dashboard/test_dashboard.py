"""ImoIA — Painel de Teste para M1 (Ingestor) e M3 (Motor Financeiro).

Consome a API FastAPI em http://localhost:8000.
NAO acede a BD directamente.

Uso:
    streamlit run src/dashboard/test_dashboard.py --server.port 8502
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8000"
TIMEOUT = 15.0

TEAL = "#0F766E"
TEAL_LIGHT = "#14B8A6"
CORAL = "#DC2626"
GRADE_COLORS = {
    "A": "#16A34A",
    "B": "#14B8A6",
    "C": "#D97706",
    "D": "#94A3B8",
    "F": "#DC2626",
}
OPP_TYPE_LABELS = {
    "abaixo_mercado": "Abaixo Mercado",
    "venda_urgente": "Venda Urgente",
    "off_market": "Off-Market",
    "reabilitacao": "Reabilitação",
    "leilao": "Leilão",
    "predio_inteiro": "Prédio Inteiro",
    "terreno_viabilidade": "Terreno c/ Viab.",
    "yield_alto": "Yield Alto",
    "outro": "Outro",
}

st.set_page_config(
    page_title="ImoIA — Painel de Teste",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown(
    f"""
<style>
    .grade-badge {{
        display: inline-block;
        padding: 2px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
        color: white;
    }}
    .go-badge {{
        display: inline-block;
        padding: 8px 24px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 1.2rem;
        color: white;
    }}
    .kpi-big {{
        font-size: 2.4rem;
        font-weight: 700;
        line-height: 1.1;
    }}
    .kpi-label {{
        font-size: 0.85rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    .detail-card {{
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }}
    .detail-card h4 {{
        color: {TEAL};
        margin: 0 0 10px 0;
        font-size: 0.95rem;
    }}
    .detail-row {{
        display: flex;
        justify-content: space-between;
        padding: 3px 0;
        font-size: 0.9rem;
    }}
    .detail-row .label {{ color: #64748B; }}
    .detail-row .value {{ font-weight: 500; }}
    .flow-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
    }}
    .flow-table th {{
        color: {TEAL};
        padding: 8px 6px;
        text-align: right;
        border-bottom: 2px solid #E2E8F0;
    }}
    .flow-table th:first-child {{ text-align: left; }}
    .flow-table td {{
        padding: 6px;
        text-align: right;
        border-bottom: 1px solid #F1F5F9;
    }}
    .flow-table td:first-child {{ text-align: left; font-weight: 600; }}
    .flow-table tr:last-child td {{ font-weight: 700; color: {TEAL}; border-top: 2px solid {TEAL}; }}
    .flow-negative {{ color: {CORAL} !important; }}
    .flow-positive {{ color: {TEAL} !important; }}
    .prop-card {{
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 8px;
        transition: border-color 0.15s;
    }}
    .prop-card:hover {{ border-color: #94A3B8; }}
    .prop-card .prop-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }}
    .prop-card .prop-title {{ font-weight: 600; font-size: 0.95rem; }}
    .prop-card .prop-specs {{
        display: flex;
        gap: 16px;
        color: #64748B;
        font-size: 0.82rem;
        margin: 4px 0;
    }}
    .prop-card .prop-price {{
        font-size: 1.15rem;
        font-weight: 700;
        color: {TEAL};
    }}
    .sidebar-section {{
        font-size: 0.7rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 16px;
        margin-bottom: 8px;
    }}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _friendly_error(endpoint: str, e: Exception) -> str:
    """Converte erro tecnico em mensagem user-friendly."""
    msg = str(e)
    if "Connection refused" in msg:
        return "API nao esta a responder. Verifique se o servidor esta a correr."
    if "500 Internal Server Error" in msg:
        return "Erro interno do servidor. Tente novamente."
    if "404" in msg:
        return "Recurso nao encontrado."
    if "405" in msg:
        return "Operacao nao suportada neste recurso."
    if "timeout" in msg.lower():
        return "O servidor demorou demasiado a responder."
    return f"Erro de comunicacao com a API."


def api_get(endpoint: str, params: Optional[Dict] = None, silent_404: bool = False) -> Optional[Any]:
    """GET request a API."""
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            r = client.get(f"{API_BASE}{endpoint}", params=params)
            if r.status_code == 404 and silent_404:
                return None
            r.raise_for_status()
            return r.json()
    except Exception as e:
        if not silent_404:
            st.error(_friendly_error(endpoint, e))
        return None


def api_post(endpoint: str, json_body: Optional[Dict] = None) -> Optional[Any]:
    """POST request a API."""
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            r = client.post(f"{API_BASE}{endpoint}", json=json_body)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        st.error(_friendly_error(endpoint, e))
        return None


def api_patch(endpoint: str, json_body: Optional[Dict] = None) -> Optional[Any]:
    """PATCH request a API."""
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            r = client.patch(f"{API_BASE}{endpoint}", json=json_body)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        st.error(_friendly_error(endpoint, e))
        return None


def api_upload(endpoint: str, filename: str, content: bytes, data: Optional[Dict] = None) -> Optional[Any]:
    """Upload multipart/form-data a API."""
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            files = {"file": (filename, content)}
            r = client.post(f"{API_BASE}{endpoint}", files=files, data=data or {})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        st.error(_friendly_error(endpoint, e))
        return None


def api_delete(endpoint: str) -> Optional[Any]:
    """DELETE request a API."""
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            r = client.delete(f"{API_BASE}{endpoint}")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        st.error(_friendly_error(endpoint, e))
        return None


def check_api() -> bool:
    """Verifica se a API esta a correr."""
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{API_BASE}/health")
            return r.status_code == 200
    except Exception:
        return False


@st.cache_data(ttl=60)
def check_api_status() -> str:
    """Verifica estado detalhado da API: 'full', 'partial', 'down'.

    'partial' significa que a API principal funciona mas servicos
    externos (CASAFARI) tem acesso limitado (ex: HTTP 402).
    """
    if not check_api():
        return "down"
    try:
        overview = api_get("/api/v1/market/overview")
        if overview:
            if overview.get("casafari_search_access"):
                return "full"
            if overview.get("casafari_configured"):
                return "partial"  # Login OK mas sem acesso pesquisa (402)
        return "full"  # API OK, CASAFARI nao configurada (nao e erro)
    except Exception:
        return "full"


def fmt_eur(value: Optional[float]) -> str:
    """Formata valor em EUR (formato PT: 80.000 €)."""
    if value is None:
        return "N/D"
    # Formato PT: separador milhares = ponto, decimais = vírgula
    if value == int(value):
        return f"{int(value):,} €".replace(",", ".")
    formatted = f"{value:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{formatted} €"


def fmt_pct(value: Optional[float]) -> str:
    """Formata percentagem."""
    if value is None:
        return "N/D"
    return f"{value:,.2f}%"


def grade_badge_html(grade: Optional[str], score: Optional[int] = None) -> str:
    """Gera badge HTML para deal grade."""
    if not grade:
        return '<span class="grade-badge" style="background:#475569;">N/D</span>'
    color = GRADE_COLORS.get(grade, "#475569")
    score_str = f" ({score})" if score is not None else ""
    return f'<span class="grade-badge" style="background:{color};">{grade}{score_str}</span>'


def go_nogo_badge(decision: str) -> str:
    """Badge grande para decisao go/no-go."""
    if decision == "go":
        return f'<span class="go-badge" style="background:{TEAL};">GO</span>'
    elif decision == "marginal":
        return f'<span class="go-badge" style="background:#D97706;">MARGINAL</span>'
    else:
        return f'<span class="go-badge" style="background:{CORAL};">NO GO</span>'


def apply_chart_theme(fig: go.Figure, height: int = 350) -> go.Figure:
    """Aplica tema visual consistente a todos os graficos Plotly."""
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#475569", size=12),
        xaxis=dict(gridcolor="#F1F5F9"),
        yaxis=dict(gridcolor="#F1F5F9"),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.15,
            xanchor="center", x=0.5,
            font=dict(size=11),
        ),
        colorway=[TEAL, "#D97706", "#DC2626", "#2563EB", "#7C3AED", "#16A34A"],
    )
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("ImoIA")
    st.caption("Gestao de Investimento Imobiliario")
    st.divider()

    api_status = check_api_status()
    if api_status == "full":
        st.success("API activa")
    elif api_status == "partial":
        st.warning("CASAFARI limitada (402)")
    else:
        st.error("API inactiva")
        st.code("uvicorn src.main:app --reload --port 8000", language="bash")

    st.markdown('<p class="sidebar-section">Aquisicao</p>', unsafe_allow_html=True)
    module = st.radio(
        "Modulo",
        [
            "M1 — Ingestor",
            "M2 — Mercado",
            "M3 — Financeiro",
            "M4 — Deal Pipeline",
            "M5 — Due Diligence",
            "M6 — Obra",
            "M7 — Marketing",
            "M8 — Leads CRM",
            "M9 — Fecho + P&L",
        ],
        index=0,
        label_visibility="collapsed",
    )

if api_status == "down":
    st.warning(
        "A API nao esta a correr. Arranca com:\n\n"
        "`uvicorn src.main:app --reload --port 8000`"
    )
    st.stop()


# ===================================================================
# M1 — INGESTOR
# ===================================================================

if module == "M1 — Ingestor":
    st.header("M1 — Ingestor")

    with st.spinner("A carregar dados..."):
        stats = api_get("/api/v1/ingest/stats")
    if not stats:
        st.stop()

    # ------ Seccao 1: Resumo geral ------
    total_groups = stats.get("groups", {}).get("total", 0)
    active_groups = stats.get("groups", {}).get("active", 0)
    total_msgs = stats.get("messages", 0)
    total_opps = stats.get("opportunities", 0)
    conversion = (total_opps / total_msgs * 100) if total_msgs > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Grupos", f"{total_groups}", delta=f"{active_groups} activos")
    c2.metric("Mensagens", f"{total_msgs:,}")
    c3.metric("Oportunidades", f"{total_opps}")
    c4.metric("Taxa conversão", f"{conversion:.1f}%")

    # --- Trigger manual + status ---
    col_trigger, col_status = st.columns([1, 2])

    with col_trigger:
        if st.button("Rodar pipeline agora", type="primary", use_container_width=True):
            progress_bar = st.progress(0, text="A iniciar pipeline...")
            log_area = st.empty()
            try:
                from src.modules.m1_ingestor.service import run_pipeline, PipelineResult
                from src.modules.m1_ingestor.whatsapp_client import WhatsAppClient
                from src.modules.m1_ingestor.classifier import OpportunityClassifier
                from src.database.db import get_session, init_db
                from src.database.models import Group
                from src.config import get_settings
                from sqlalchemy import select
                import time

                init_db()
                settings = get_settings()
                logs: list = []

                def _log(msg: str) -> None:
                    logs.append(msg)
                    log_area.code("\n".join(logs[-12:]), language=None)

                # Etapa 1: Conectar ao WhatsApp
                progress_bar.progress(5, text="A conectar ao WhatsApp...")
                _log("Conectando ao WhatsApp...")
                wa = WhatsAppClient()
                _log(f"Backend: {wa.backend} ({wa.base_url})")

                # Etapa 2: Listar grupos
                progress_bar.progress(10, text="A buscar grupos activos...")
                _log("A buscar grupos activos...")
                try:
                    groups = wa.list_active_groups()
                except Exception as e:
                    _log(f"ERRO ao listar grupos: {e}")
                    progress_bar.progress(100, text="Erro!")
                    st.error(f"Falha ao listar grupos WhatsApp: {e}")
                    st.info(
                        "Verifique se o WHAPI_TOKEN esta preenchido no .env "
                        "ou se o Baileys Bridge esta a correr em localhost:3000"
                    )
                    st.stop()

                _log(f"{len(groups)} grupos encontrados")

                # Etapa 3: Filtrar grupos activos na BD
                with get_session() as session:
                    db_groups = session.execute(select(Group)).scalars().all()
                    active_ids = {g.whatsapp_group_id for g in db_groups if g.is_active}
                active_groups = [g for g in groups if g.get("id") in active_ids or g.get("whatsapp_group_id") in active_ids]
                _log(f"{len(active_groups)} grupos activos na BD")

                # Etapa 4: Correr pipeline completo
                progress_bar.progress(20, text="A executar pipeline completo...")
                _log("A correr pipeline (classificacao + enriquecimento)...")
                _log("Isto pode demorar 1-3 minutos...")

                result = run_pipeline()

                # Etapa 5: Mostrar resultados
                progress_bar.progress(100, text="Pipeline concluido!")
                _log(f"--- RESULTADO ---")
                _log(f"Mensagens processadas: {result.messages_fetched}")
                _log(f"Oportunidades encontradas: {result.opportunities_found}")
                _log(f"Grupos processados: {result.groups_processed}")
                if result.errors:
                    for err in result.errors:
                        _log(f"ERRO: {err}")
                    st.warning(f"Pipeline concluido com {len(result.errors)} erro(s)")
                else:
                    st.success(
                        f"Pipeline concluido: {result.messages_fetched} mensagens, "
                        f"{result.opportunities_found} oportunidades, "
                        f"{result.groups_processed} grupos"
                    )
                time.sleep(2)
                st.rerun()

            except ImportError as e:
                progress_bar.progress(100, text="Erro de importacao!")
                st.error(f"Modulo nao disponivel: {e}")
            except Exception as e:
                progress_bar.progress(100, text="Erro!")
                st.error(f"Erro ao executar pipeline: {e}")

    with col_status:
        status_resp = api_get("/api/v1/ingest/status")
        if status_resp and status_resp.get("state") != "nunca_executado":
            _ts_raw = status_resp.get("timestamp", "")
            last_msgs = status_resp.get("mensagens", 0)
            last_opps = status_resp.get("oportunidades", 0)
            try:
                from datetime import datetime as _dt
                _parsed = _dt.fromisoformat(_ts_raw.replace("Z", "+00:00"))
                last_ts = _parsed.strftime("%d %b %Y, %H:%M")
            except Exception:
                last_ts = _ts_raw
            st.caption(
                f"Último pipeline: {last_ts} — "
                f"{last_msgs} msgs, {last_opps} oportunidades"
            )
        else:
            st.caption("Pipeline nunca executado")

    st.divider()

    # ------ Seccao 2: Distribuicao ------
    st.subheader("Distribuição")

    col_left, col_right = st.columns(2)

    # Oportunidades por distrito
    with col_left:
        districts = stats.get("top_districts", [])
        if districts:
            fig = go.Figure(
                go.Bar(
                    y=[d["district"] for d in reversed(districts)],
                    x=[d["count"] for d in reversed(districts)],
                    orientation="h",
                    marker_color=TEAL,
                )
            )
            fig.update_layout(title="Oportunidades por Distrito (Top 10)")
            apply_chart_theme(fig, height=400)
            st.plotly_chart(fig, use_container_width=True)

    # Distribuicao por grade
    with col_right:
        grades = stats.get("grade_distribution", {})
        if grades:
            grade_labels = list(grades.keys())
            grade_values = list(grades.values())
            grade_colors = [GRADE_COLORS.get(g, "#475569") for g in grade_labels]

            fig = go.Figure()
            for g_label, g_value, g_color in zip(grade_labels, grade_values, grade_colors):
                fig.add_trace(go.Bar(
                    x=[g_label],
                    y=[g_value],
                    marker_color=g_color,
                    text=[g_value],
                    textposition="auto",
                    name=f"Grade {g_label}",
                    showlegend=True,
                ))
            fig.update_layout(title="Distribuição por Deal Grade", barmode="group")
            apply_chart_theme(fig, height=400)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ------ Seccao 3: Top oportunidades ------
    st.subheader("Oportunidades")

    # Filtros
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        min_score = st.slider("Deal Score mínimo", 0, 100, 0)
    with fc2:
        grade_filter = st.multiselect("Deal Grade", ["A", "B", "C", "D", "F"])
    with fc3:
        district_filter = st.multiselect(
            "Distrito",
            [d["district"] for d in stats.get("top_districts", [])],
        )

    # Buscar oportunidades
    params: Dict[str, Any] = {"limit": 100, "min_confidence": 0.0}
    if grade_filter:
        # A API aceita 1 grade de cada vez — buscar todas e filtrar client-side
        pass
    if district_filter:
        pass  # filtrar client-side

    opps_data = api_get("/api/v1/ingest/opportunities", params=params)
    if opps_data:
        items = opps_data.get("items", [])

        # Filtrar client-side
        if min_score > 0:
            items = [o for o in items if (o.get("deal_score") or 0) >= min_score]
        if grade_filter:
            items = [o for o in items if o.get("deal_grade") in grade_filter]
        if district_filter:
            items = [o for o in items if o.get("district") in district_filter]

        st.caption(f"{len(items)} oportunidades encontradas")

        for opp in items:
            grade = opp.get("deal_grade") or "?"
            score = opp.get("deal_score")
            opp_type = OPP_TYPE_LABELS.get(
                opp.get("opportunity_type", ""), opp.get("opportunity_type", "?")
            )
            muni = opp.get("municipality") or "?"
            dist = opp.get("district") or "?"
            price = opp.get("price")
            conf = opp.get("confidence", 0)
            area = opp.get("area_m2")
            bedrooms = opp.get("bedrooms")
            grade_color = GRADE_COLORS.get(grade, "#94A3B8")

            price_str = fmt_eur(price) if price else "N/D"
            area_str = f"{int(area)} m2" if area else "?"
            bed_str = f"T{bedrooms}" if bedrooms else "?"
            price_m2 = f"{int(price / area)} EUR/m2" if price and area and area > 0 else ""

            st.markdown(f"""
            <div class="prop-card" style="border-left: 4px solid {grade_color};">
                <div class="prop-header">
                    <span class="prop-title">{muni}, {dist}</span>
                    {grade_badge_html(grade, score)}
                </div>
                <div class="prop-specs">
                    <span>{opp_type}</span>
                    <span>{area_str}</span>
                    <span>{bed_str}</span>
                    <span>Conf. {conf:.0%}</span>
                    {'<span>' + price_m2 + '</span>' if price_m2 else ''}
                </div>
                <div style="margin-top:6px;">
                    <span class="prop-price">{price_str}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("Ver detalhes", expanded=False):
                st.markdown("**Mensagem original:**")
                st.text(opp.get("original_message", "N/D")[:500])
                st.markdown("**Raciocinio IA:**")
                st.info(opp.get("ai_reasoning", "N/D"))

                # Buscar detalhe com market data
                detail = api_get(f"/api/v1/ingest/opportunities/{opp['id']}")
                if detail and detail.get("market_data"):
                    md = detail["market_data"]
                    st.markdown("**Dados de mercado:**")
                    md_cols = st.columns(3)
                    md_cols[0].metric(
                        "INE €/m²",
                        fmt_eur(md.get("ine_median_price_m2")),
                    )
                    md_cols[1].metric(
                        "Yield bruto",
                        fmt_pct(md.get("gross_yield_pct")),
                    )
                    md_cols[2].metric(
                        "Preço vs Mercado",
                        fmt_pct(md.get("price_vs_market_pct")),
                    )

                # Acções
                st.divider()
                act1, act2, act3 = st.columns(3)
                with act1:
                    if st.button("Criar Deal", key=f"m1_deal_{opp['id']}", type="primary"):
                        result = api_post(
                            f"/api/v1/properties/from-opportunity/{opp['id']}"
                        )
                        if result:
                            prop_id = result.get("id")
                            deal_result = api_post("/api/v1/deals", {
                                "property_id": prop_id,
                                "investment_strategy": "fix_and_flip",
                                "title": f"{opp.get('property_type', '?')} {muni} — {fmt_eur(price)}",
                            })
                            if deal_result:
                                st.success(f"Deal criado! ID: {deal_result.get('id', '?')[:8]}...")
                            else:
                                st.success(f"Property criada: {prop_id[:8]}... (cria deal no M4)")
                with act2:
                    if st.button("Descartar", key=f"m1_skip_{opp['id']}"):
                        api_patch(
                            f"/api/v1/ingest/opportunities/{opp['id']}",
                            {"status": "descartada"},
                        )
                        st.warning("Oportunidade descartada.")
                        st.rerun()
                with act3:
                    if st.button("Analisar M2", key=f"m1_m2_{opp['id']}"):
                        with st.spinner("A analisar..."):
                            m2_result = api_post(f"/api/v1/market/opportunities/{opp['id']}/enrich")
                            if m2_result:
                                src = m2_result.get("source", "?")
                                disc = m2_result.get("discount_vs_market_pct")
                                disc_str = f"{disc:+.1f}%" if disc is not None else "?"
                                st.info(f"Fonte: {src.upper()} | vs Mercado: {disc_str}")


# ===================================================================
# M2 — MERCADO
# ===================================================================

elif module == "M2 — Mercado":
    st.header("M2 — Pesquisa de Mercado")

    # Overview
    overview = api_get("/api/v1/market/overview")
    if overview:
        if overview.get("casafari_search_access"):
            st.success("CASAFARI API activa — pesquisa de comparáveis em tempo real.", icon="🟢")
        elif overview.get("casafari_configured"):
            st.warning(
                "CASAFARI: login OK mas sem acesso à pesquisa (HTTP 402). "
                "O plano actual não inclui a API de listing alerts. "
                "A usar dados INE como alternativa. Contacte a CASAFARI para upgrade.",
                icon="⚠️",
            )
        else:
            st.warning("CASAFARI não configurada. Configure no .env e reinicie a API. Dados INE disponíveis.")

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Comparáveis em cache", overview.get("comparables_cached", 0))
        k2.metric("Avaliações feitas", overview.get("valuations_total", 0))
        k3.metric("Alertas activos", overview.get("alerts_active", 0))
        k4.metric("Zonas monitorizadas", overview.get("zones_monitored", 0))
        casafari_count = overview.get("comparables_casafari", 0)
        ine_count = overview.get("comparables_ine", 0)
        k5.metric("Fontes (CASAFARI / INE)", f"{casafari_count} / {ine_count}")

    st.divider()

    tab_opps, tab_comps, tab_vals, tab_alerts, tab_ine = st.tabs([
        "Enriquecer Oportunidades", "Comparáveis", "Avaliações", "Alertas", "Dados INE",
    ])

    # --- TAB: Enriquecer Oportunidades ---
    with tab_opps:
        st.subheader("Oportunidades disponíveis para análise de mercado")
        st.caption("Selecciona uma oportunidade e clica 'Analisar' para buscar comparáveis (CASAFARI se configurada, senão dados INE).")

        opps_data = api_get("/api/v1/ingest/opportunities", params={"limit": 50, "min_confidence": 0.6})
        opps = opps_data.get("items", []) if opps_data else []

        if not opps:
            st.info("Nenhuma oportunidade disponível.")
        else:
            # Filtro por municipio
            municipalities = sorted({o.get("municipality", "") for o in opps if o.get("municipality")})
            sel_mun = st.selectbox("Filtrar por município", ["Todos"] + municipalities, key="m2_mun_f")
            if sel_mun != "Todos":
                opps = [o for o in opps if o.get("municipality") == sel_mun]

            for opp in opps[:30]:
                oid = opp.get("id", "?")
                mun = opp.get("municipality") or "?"
                ptype = opp.get("property_type") or "?"
                price = opp.get("price") or opp.get("price_mentioned")
                area = opp.get("area_m2")
                grade = opp.get("deal_grade") or "-"

                price_str = fmt_eur(price) if price else "?"
                area_str = f"{area:.0f}m²" if area else "?"
                conf = opp.get("confidence")
                conf_str = f"{conf:.0f}%" if conf else "?"

                grade_color = GRADE_COLORS.get(grade, "#94A3B8")
                bed_str = f"T{opp.get('bedrooms')}" if opp.get('bedrooms') else "?"
                st.markdown(f"""
                <div class="prop-card" style="border-left: 4px solid {grade_color};">
                    <div class="prop-header">
                        <span class="prop-title">{mun}</span>
                        {grade_badge_html(grade, opp.get('deal_score'))}
                    </div>
                    <div class="prop-specs">
                        <span>{ptype}</span>
                        <span>{area_str}</span>
                        <span>{bed_str}</span>
                        <span>Conf. {conf_str}</span>
                    </div>
                    <div style="margin-top:6px;"><span class="prop-price">{price_str}</span></div>
                </div>
                """, unsafe_allow_html=True)
                with st.expander("Analisar mercado", expanded=False):
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**Município:** {mun}")
                    c1.markdown(f"**Tipo:** {ptype}")
                    c1.markdown(f"**Preço:** {price_str}")
                    c2.markdown(f"**Área:** {area_str}")
                    c2.markdown(f"**Quartos:** {opp.get('bedrooms') or '?'}")
                    c2.markdown(f"**Confiança IA:** {conf_str}")

                    if st.button("Analisar com CASAFARI", key=f"m2_enrich_{oid}"):
                        with st.spinner(f"A buscar comparáveis para #{oid} em {mun}..."):
                            result = api_post(f"/api/v1/market/opportunities/{oid}/enrich")
                            if result:
                                n = result.get("comparables_found", 0)
                                median = result.get("zone_median_price_m2")
                                disc = result.get("discount_vs_market_pct")
                                arv = result.get("arv_estimated")
                                src = result.get("source", "?")

                                if src == "casafari":
                                    st.success("Análise concluída via CASAFARI! (comparáveis reais)")
                                elif src == "ine":
                                    st.warning("Estimativa baseada em dados INE (preço mediano municipal). Configure CASAFARI para comparáveis reais.")
                                else:
                                    st.success(f"Análise concluída via {src.upper()}!")
                                r1, r2, r3, r4 = st.columns(4)
                                if src == "casafari":
                                    r1.metric("Comparáveis", n)
                                else:
                                    r1.metric("Fonte", "INE (mediana)")
                                r2.metric("Mediana zona", f"{median:,.0f} €/m²" if median else "-")
                                r3.metric("vs Mercado", f"{disc:+.1f}%" if disc is not None else "-")
                                r4.metric("ARV estimado", f"{arv:,.0f} €" if arv else "-")

    # --- TAB: Comparáveis ---
    with tab_comps:
        st.subheader("Pesquisar comparáveis")

        with st.form("m2_search_form"):
            sc1, sc2, sc3 = st.columns(3)
            s_mun = sc1.text_input("Município", "Lisboa")
            s_type = sc2.selectbox("Tipo", ["apartamento", "moradia", "terreno", "predio", "armazem"])
            s_beds = sc3.number_input("Quartos", value=2, min_value=0, max_value=10)

            sc4, sc5, sc6 = st.columns(3)
            s_area = sc4.number_input("Área m²", value=80.0, min_value=10.0)
            s_max = sc5.number_input("Max resultados", value=20, min_value=1, max_value=100)
            s_months = sc6.number_input("Meses atras", value=12, min_value=1, max_value=36)

            submitted = st.form_submit_button("Pesquisar")

        if submitted:
            with st.spinner("A pesquisar comparáveis..."):
                result = api_post("/api/v1/market/comparables/search", {
                    "municipality": s_mun,
                    "property_type": s_type,
                    "bedrooms": s_beds,
                    "area_m2": s_area,
                    "max_results": s_max,
                    "months_back": s_months,
                })
                if result:
                    comps = result.get("comparables", [])
                    stats = result.get("stats", {})
                    st.success(f"{len(comps)} comparáveis encontrados!")

                    if stats:
                        s1, s2, s3, s4 = st.columns(4)
                        s1.metric("Total", stats.get("count", 0))
                        s2.metric("Mediana €/m²", f"{stats.get('median_price_m2', 0):,.0f}")
                        s3.metric("Min €/m²", f"{stats.get('min_price_m2', 0):,.0f}")
                        s4.metric("Max €/m²", f"{stats.get('max_price_m2', 0):,.0f}")

                    if comps:
                        # Histograma de precos/m2
                        prices = [c["price_per_m2"] for c in comps if c.get("price_per_m2") and c["price_per_m2"] > 0]
                        if prices:
                            import plotly.express as px
                            fig = px.histogram(
                                x=prices, nbins=20,
                                title="Distribuição de Preços/m²",
                                labels={"x": "€/m²", "y": "Frequência"},
                            )
                            fig.update_traces(marker_color=TEAL)
                            fig.update_layout(
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#94A3B8"),
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        # Tabela
                        import pandas as pd
                        df = pd.DataFrame(comps)
                        cols = [c for c in ["municipality", "parish", "property_type", "bedrooms",
                                            "listing_price", "price_per_m2", "gross_area_m2",
                                            "condition", "comparison_type"] if c in df.columns]
                        if cols:
                            st.dataframe(df[cols].rename(columns={
                                "municipality": "Município", "parish": "Freguesia",
                                "property_type": "Tipo", "bedrooms": "Quartos",
                                "listing_price": "Preço €", "price_per_m2": "€/m²",
                                "gross_area_m2": "Área m²", "condition": "Estado",
                                "comparison_type": "Status",
                            }), use_container_width=True, hide_index=True)

                        # Mapa
                        coords = [{"lat": c["latitude"], "lon": c["longitude"]}
                                  for c in comps if c.get("latitude") and c.get("longitude")]
                        if coords:
                            st.subheader("Mapa")
                            import pandas as pd
                            st.map(pd.DataFrame(coords), latitude="lat", longitude="lon")

    # --- TAB: Avaliações ---
    with tab_vals:
        st.subheader("Avaliação AVM")

        with st.form("m2_valuation_form"):
            v1, v2, v3 = st.columns(3)
            v_mun = v1.text_input("Município", "Lisboa", key="m2v_mun")
            v_type = v2.selectbox("Tipo", ["apartamento", "moradia", "terreno", "predio", "armazem"], key="m2v_type")
            v_beds = v3.number_input("Quartos", value=2, min_value=0, key="m2v_beds")

            v4, v5 = st.columns(2)
            v_area = v4.number_input("Área m²", value=80.0, min_value=10.0, key="m2v_area")
            v_cond = v5.selectbox("Estado", ["usado", "renovado", "novo", "para_renovar"], key="m2v_cond")

            v_submit = st.form_submit_button("Avaliar")

        if v_submit:
            with st.spinner("A avaliar..."):
                result = api_post("/api/v1/market/valuate", {
                    "municipality": v_mun,
                    "property_type": v_type,
                    "bedrooms": v_beds,
                    "gross_area_m2": v_area,
                    "condition": v_cond,
                })
                if result:
                    val = result.get("estimated_value")
                    low = result.get("estimated_value_low")
                    high = result.get("estimated_value_high")
                    conf = result.get("confidence_score")
                    pm2 = result.get("estimated_price_per_m2")
                    n_comp = result.get("comparables_count", 0)

                    st.success("Avaliação concluída!")
                    rv1, rv2, rv3, rv4 = st.columns(4)
                    rv1.metric("Valor estimado", f"{val:,.0f} €" if val else "-")
                    rv2.metric("€/m²", f"{pm2:,.0f}" if pm2 else "-")
                    rv3.metric("Confiança", f"{conf:.0f}%" if conf else "-")
                    rv4.metric("Comparáveis", n_comp)

                    if low and high:
                        st.info(f"Intervalo: {low:,.0f} € — {high:,.0f} €")

    # --- TAB: Alertas ---
    with tab_alerts:
        st.subheader("Alertas de mercado")

        # Criar alerta
        with st.expander("Novo alerta", expanded=False):
            al_name = st.text_input("Nome", key="m2_al_name")
            al_type = st.selectbox("Tipo", ["new_listing", "price_drop", "below_market"], key="m2_al_type")
            al_dist = st.multiselect(
                "Distritos", ["Lisboa", "Porto", "Setubal", "Braga", "Faro", "Aveiro", "Coimbra", "Leiria"],
                key="m2_al_dist",
            )
            al_ptypes = st.multiselect(
                "Tipos imóvel", ["apartamento", "moradia", "predio", "terreno", "armazem"],
                key="m2_al_pt",
            )
            al_pmax = st.number_input("Preço máximo €", value=0, step=50000, key="m2_al_pmax")

            if st.button("Criar alerta", key="m2_al_btn"):
                if al_name:
                    result = api_post("/api/v1/market/alerts", {
                        "alert_name": al_name,
                        "alert_type": al_type,
                        "districts": al_dist,
                        "property_types": al_ptypes,
                        "price_max": al_pmax if al_pmax > 0 else None,
                    })
                    if result:
                        feed = result.get("casafari_feed_id")
                        st.success(f"Alerta criado!" + (f" (CASAFARI feed #{feed})" if feed else ""))
                        st.rerun()

        # Lista
        alerts = api_get("/api/v1/market/alerts")
        if alerts:
            for a in alerts:
                ac1, ac2, ac3 = st.columns([4, 2, 1])
                active = "🟢" if a.get("is_active") else "⭕"
                dists = ", ".join(a.get("districts", [])) or "Todas"
                ac1.markdown(f"{active} **{a['alert_name']}** ({a['alert_type']}) — {dists}")
                ac2.markdown(f"Disparou {a.get('total_triggers', 0)}x")
                if ac3.button("Apagar", key=f"m2_del_{a['id']}", type="secondary"):
                    st.session_state[f"confirm_del_{a['id']}"] = True
                if st.session_state.get(f"confirm_del_{a['id']}"):
                    cc1, cc2 = st.columns(2)
                    if cc1.button("Confirmar", key=f"m2_confirm_{a['id']}", type="primary"):
                        api_delete(f"/api/v1/market/alerts/{a['id']}")
                        del st.session_state[f"confirm_del_{a['id']}"]
                        st.rerun()
                    if cc2.button("Cancelar", key=f"m2_cancel_{a['id']}"):
                        del st.session_state[f"confirm_del_{a['id']}"]
                        st.rerun()

            if st.button("Verificar alertas agora", key="m2_check"):
                with st.spinner("A verificar..."):
                    result = api_post("/api/v1/market/alerts/check")
                    if result:
                        st.success(f"{result.get('new_results', 0)} novos resultados.")
        else:
            st.info("Nenhum alerta. Cria um acima.")

    # --- TAB: Dados INE ---
    with tab_ine:
        st.subheader("Preços medianos INE (gratuito)")
        st.caption("Instituto Nacional de Estatística — sem API key.")

        ine_mun = st.text_input("Município", "Lisboa", key="m2_ine_mun")
        if st.button("Consultar", key="m2_ine_btn"):
            result = api_get("/api/v1/market/ine/housing-prices", params={"municipality": ine_mun})
            if result:
                st.metric(
                    f"Mediana {result.get('municipality', ine_mun)}",
                    f"{result['price_m2']:,.0f} €/m²",
                    help=f"Período: {result.get('quarter', '?')} | Fonte: INE",
                )


# ===================================================================
# M3 — FINANCEIRO
# ===================================================================

elif module == "M3 — Financeiro":
    st.header("M3 — Motor Financeiro")

    tab1, tab2, tab3 = st.tabs(
        ["Calculadora IMT", "Calculadora MAO", "Simulador Completo"]
    )

    # ------ Tab 1: IMT ------
    with tab1:
        st.subheader("Cálculo rápido de IMT")

        # Exemplo pré-calculado
        with st.container():
            st.caption("Exemplo: T2 Sacavém, 295.000 €, não HPP")
            ex1, ex2, ex3 = st.columns(3)
            ex1.metric("IMT", "11.370,50 €", help="Tabela 4 — secundário/investimento")
            ex2.metric("Imposto de Selo", "2.360,00 €", help="0,8% do valor")
            ex3.metric("Total Impostos", "13.730,50 €", help="IMT + IS (4,7% do valor)")
        st.divider()

        ic1, ic2, ic3 = st.columns(3)
        with ic1:
            imt_value = st.number_input(
                "Valor do imóvel (€)", value=295_000, step=5_000, min_value=1
            )
        with ic2:
            imt_country = st.selectbox("Pais", ["PT", "BR"], index=0)
        with ic3:
            imt_hpp = st.checkbox("Habitação própria permanente (HPP)?", value=False)

        if st.button("Calcular IMT", type="primary"):
            result = api_post(
                "/api/v1/financial/quick-imt",
                {"value": imt_value, "country": imt_country, "is_hpp": imt_hpp},
            )
            if result:
                if imt_country == "PT":
                    rc1, rc2, rc3 = st.columns(3)
                    rc1.metric("IMT", fmt_eur(result.get("imt")))
                    rc2.metric("Imposto de Selo", fmt_eur(result.get("imposto_selo")))
                    rc3.metric("Total Impostos", fmt_eur(result.get("total_impostos")))
                    st.caption(
                        f"Tabela: {result.get('tabela', '?')} | {result.get('nota', '')}"
                    )
                else:
                    rc1, rc2 = st.columns(2)
                    rc1.metric("ITBI", fmt_eur(result.get("itbi")))
                    rc2.metric("ITBI %", fmt_pct(result.get("itbi_pct")))
                    st.caption(result.get("nota", ""))

    # ------ Tab 2: MAO ------
    with tab2:
        st.subheader("MAO — Maximum Allowable Offer (Regra 70%)")

        mc1, mc2 = st.columns(2)
        with mc1:
            mao_arv = st.number_input(
                "ARV — Valor pos-obra (€)", value=500_000, step=10_000, min_value=1
            )
        with mc2:
            mao_reno = st.number_input(
                "Custo total de obra (€)", value=100_000, step=5_000, min_value=0
            )

        if st.button("Calcular MAO", type="primary"):
            result = api_post(
                "/api/v1/financial/mao",
                {"arv": mao_arv, "renovation_total": mao_reno},
            )
            if result:
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("MAO 70% (activo)", fmt_eur(result.get("mao_70pct")))
                mc2.metric("MAO 65% (normal)", fmt_eur(result.get("mao_65pct")))
                mc3.metric("MAO 60% (lento)", fmt_eur(result.get("mao_60pct")))
                st.caption(result.get("nota", ""))

    # ------ Tab 3: Simulador completo ------
    with tab3:
        st.subheader("Simulador — Caso de Negócio")
        st.caption("Valores default: Caso Sacavem (2 unidades, financiamento 75%)")

        with st.form("financial_form"):
            st.markdown("##### Estrutura da operação")
            es1, es2 = st.columns(2)
            with es1:
                entity_structure = st.selectbox(
                    "Estrutura",
                    options=["pf_jp", "pf_only", "jp_only"],
                    format_func=lambda x: {
                        "pf_jp": "PF + Empresa (crédito PF, duplo IMT, IRC)",
                        "pf_only": "Só PF (crédito, um IMT, IRS mais-valias)",
                        "jp_only": "So Empresa (cash, um IMT, IRC)",
                    }[x],
                    index=0,
                )
            with es2:
                imt_resale_regime = st.selectbox(
                    "Regime IMT revenda (Art. 7 CIMT)",
                    options=["none", "reembolso", "isencao"],
                    format_func=lambda x: {
                        "none": "Sem benefício — paga IMT normal",
                        "reembolso": "Reembolso — recupera se vender <1 ano",
                        "isencao": "Isenção automática (certidão 2 anos)",
                    }[x],
                    index=0,
                )

            st.markdown("##### Compra")
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                purchase_price = st.number_input(
                    "Preço de compra (€)", value=295_000, step=5_000, min_value=1
                )
            with fc2:
                financing_type = st.selectbox(
                    "Financiamento", ["cash", "mortgage", "mixed"], index=1
                )
            with fc3:
                comissao_compra_pct = st.number_input(
                    "Comissão compra %", value=0.0, step=0.5, min_value=0.0
                )

            st.markdown("##### Obra")
            oc1, oc2, oc3 = st.columns(3)
            with oc1:
                renovation_budget = st.number_input(
                    "Orçamento obra (€)", value=98_400, step=1_000, min_value=0
                )
            with oc2:
                renovation_contingency_pct = st.number_input(
                    "Contingencia %", value=0.0, step=5.0, min_value=0.0, max_value=50.0
                )
            with oc3:
                renovation_duration_months = st.number_input(
                    "Meses de obra", value=3, step=1, min_value=0, max_value=36
                )

            st.markdown("##### Financiamento")
            lc1, lc2, lc3 = st.columns(3)
            with lc1:
                loan_amount = st.number_input(
                    "Valor emprestimo (€)", value=221_250, step=1_000, min_value=0
                )
            with lc2:
                interest_rate_pct = st.number_input(
                    "TAN %", value=2.73, step=0.1, min_value=0.0, max_value=20.0
                )
            with lc3:
                loan_term_years = st.number_input(
                    "Prazo (anos)", value=30, step=1, min_value=1, max_value=40
                )

            st.markdown("##### Venda")
            vc1, vc2, vc3 = st.columns(3)
            with vc1:
                estimated_sale_price = st.number_input(
                    "Preço de venda estimado / ARV (€)",
                    value=500_000,
                    step=10_000,
                    min_value=0,
                )
            with vc2:
                comissao_venda_pct = st.number_input(
                    "Comissão venda + IVA %",
                    value=6.15,
                    step=0.5,
                    min_value=0.0,
                    max_value=15.0,
                )
            with vc3:
                additional_holding_months = st.number_input(
                    "Meses ate venda (apos obra)",
                    value=6,
                    step=1,
                    min_value=0,
                    max_value=24,
                )

            st.markdown("##### Outros")
            xc1, xc2, xc3 = st.columns(3)
            with xc1:
                monthly_condominio = st.number_input(
                    "Manutenção mensal (€)", value=100, step=10, min_value=0
                )
            with xc2:
                annual_insurance = st.number_input(
                    "Seguro anual (€)", value=0, step=50, min_value=0
                )
            with xc3:
                roi_target_pct = st.number_input(
                    "ROI target %", value=15.0, step=1.0, min_value=0.0
                )

            submitted = st.form_submit_button("Calcular", type="primary")

        if submitted:
            payload = {
                "purchase_price": purchase_price,
                "country": "PT",
                "scenario_name": "simulacao",
                "entity_structure": entity_structure,
                "imt_resale_regime": imt_resale_regime,
                "renovation_budget": renovation_budget,
                "renovation_contingency_pct": renovation_contingency_pct,
                "renovation_duration_months": renovation_duration_months,
                "financing_type": financing_type,
                "loan_amount": loan_amount if financing_type != "cash" else 0,
                "interest_rate_pct": interest_rate_pct if financing_type != "cash" else 0,
                "loan_term_months": loan_term_years * 12,
                "estimated_sale_price": estimated_sale_price,
                "comissao_venda_pct": comissao_venda_pct,
                "additional_holding_months": additional_holding_months,
                "monthly_condominio": monthly_condominio,
                "annual_insurance": annual_insurance,
                "comissao_compra_pct": comissao_compra_pct,
                "roi_target_pct": roi_target_pct,
            }

            result = api_post("/api/v1/financial/simulate", payload)

            if not result:
                st.error("Erro ao calcular modelo financeiro")
                st.stop()

            # Guardar no session_state para sobreviver a re-runs
            st.session_state["m3_result"] = result
            st.session_state["m3_payload"] = payload
            st.session_state["m3_model_id"] = result.get("model_id")

        # Mostrar resultado (do submit actual ou do session_state)
        result = st.session_state.get("m3_result") if not submitted else result
        if result:
            payload = st.session_state.get("m3_payload", {})
            model_id = st.session_state.get("m3_model_id")

            st.divider()

            # === KPIs + Detalhe ===
            kpi_col, detail_col = st.columns([1, 1])

            roi = result.get("roi_pct", 0)
            net_profit = result.get("net_profit", 0)
            moic_val = result.get("moic", 0)
            decision = result.get("go_nogo", "pending")

            with kpi_col:
                st.markdown("### Resultado")

                # Go/No-Go gauge circular
                gauge_score = min(100, max(0, roi * 3))  # Escalar ROI para 0-100
                gauge_color = TEAL if decision == "go" else ("#D97706" if decision == "marginal" else CORAL)
                gauge_label = "GO" if decision == "go" else ("MARGINAL" if decision == "marginal" else "NO GO")

                import plotly.graph_objects as go_fig
                fig_gauge = go_fig.Figure(go_fig.Indicator(
                    mode="gauge+number",
                    value=roi,
                    number={"suffix": "%", "font": {"size": 28, "color": gauge_color}},
                    title={"text": gauge_label, "font": {"size": 20, "color": gauge_color}},
                    gauge={
                        "axis": {"range": [0, 50], "tickwidth": 1, "tickcolor": "#E2E8F0"},
                        "bar": {"color": gauge_color},
                        "bgcolor": "#F8FAFC",
                        "steps": [
                            {"range": [0, 10], "color": "#FEE2E2"},
                            {"range": [10, 20], "color": "#FEF3C7"},
                            {"range": [20, 50], "color": "#DCFCE7"},
                        ],
                        "threshold": {"line": {"color": gauge_color, "width": 3}, "thickness": 0.8, "value": roi},
                    },
                ))
                fig_gauge.update_layout(
                    height=200,
                    margin=dict(t=50, b=0, l=30, r=30),
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#475569"),
                )
                st.plotly_chart(fig_gauge, use_container_width=True)

                # KPIs em linha
                m1, m2, m3 = st.columns(3)
                with m1:
                    profit_color = TEAL if net_profit >= 0 else CORAL
                    st.markdown(
                        f'<div class="kpi-label">Lucro Liquido</div>'
                        f'<div style="font-size:1.4rem;font-weight:700;color:{profit_color};">{fmt_eur(net_profit)}</div>',
                        unsafe_allow_html=True,
                    )
                with m2:
                    st.markdown(
                        f'<div class="kpi-label">MOIC</div>'
                        f'<div style="font-size:1.4rem;font-weight:700;color:#475569;">{moic_val:.2f}x</div>',
                        unsafe_allow_html=True,
                    )
                with m3:
                    st.markdown(
                        f'<div class="kpi-label">ROI Simples</div>'
                        f'<div style="font-size:1.4rem;font-weight:700;color:#475569;">{fmt_pct(result.get("roi_simple_pct"))}</div>',
                        unsafe_allow_html=True,
                    )

                warnings = result.get("warnings", [])
                for w in warnings:
                    st.warning(w)

            with detail_col:
                st.markdown("### Detalhe")

                # Card: Custos de compra
                imt_val = result.get("imt", 0)
                is_val = result.get("imposto_selo", 0)
                notario = result.get("notario_registo", 0)
                total_acq = result.get("total_acquisition_cost", 0)
                imt_2_val = result.get("imt_2", 0)
                imt_2_orig = result.get("imt_2_original", 0)
                is_2_val = result.get("is_2", 0)
                esc_2_val = result.get("escritura_2", 0)
                total_acq_2 = result.get("total_acquisition_cost_2", 0)

                if entity_structure == "pf_jp":
                    # Duas escrituras
                    card_html = f"""<div class="detail-card">
                    <h4>Custos de compra (2 escrituras)</h4>
                    <div class="detail-row" style="opacity:0.7;font-size:0.8rem;"><span class="label">Escritura 1: Vendedor → PF</span><span class="value"></span></div>
                    <div class="detail-row"><span class="label">IMT</span><span class="value">{fmt_eur(imt_val)}</span></div>
                    <div class="detail-row"><span class="label">Imposto de Selo</span><span class="value">{fmt_eur(is_val)}</span></div>
                    <div class="detail-row"><span class="label">Escritura + Registo</span><span class="value">{fmt_eur(notario)}</span></div>
                    <div class="detail-row" style="opacity:0.7;font-size:0.8rem;margin-top:8px;"><span class="label">Escritura 2: PF → JP</span><span class="value"></span></div>
                    <div class="detail-row"><span class="label">IMT</span><span class="value">{fmt_eur(imt_2_val)}</span></div>
                    <div class="detail-row"><span class="label">Imposto de Selo</span><span class="value">{fmt_eur(is_2_val)}</span></div>
                    <div class="detail-row"><span class="label">Escritura + Registo</span><span class="value">{fmt_eur(esc_2_val)}</span></div>
                    <div class="detail-row" style="border-top:1px solid #475569; padding-top:6px; font-weight:700;">
                        <span class="label">Total aquisição</span><span class="value">{fmt_eur(total_acq)}</span>
                    </div>
                    </div>"""
                    st.markdown(card_html, unsafe_allow_html=True)

                    if imt_resale_regime != "none" and imt_2_orig > 0:
                        regime_label = "Reembolso Art. 7 CIMT" if imt_resale_regime == "reembolso" else "Isenção Art. 7 CIMT"
                        st.success(f"Poupança IMT: {fmt_eur(imt_2_orig)} ({regime_label})")
                else:
                    st.markdown(
                        f"""<div class="detail-card">
                        <h4>Custos de compra</h4>
                        <div class="detail-row"><span class="label">IMT</span><span class="value">{fmt_eur(imt_val)}</span></div>
                        <div class="detail-row"><span class="label">Imposto de Selo</span><span class="value">{fmt_eur(is_val)}</span></div>
                        <div class="detail-row"><span class="label">Escritura + Registo</span><span class="value">{fmt_eur(notario)}</span></div>
                        <div class="detail-row" style="border-top:1px solid #475569; padding-top:6px; font-weight:700;">
                            <span class="label">Total aquisição</span><span class="value">{fmt_eur(total_acq)}</span>
                        </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                # Card: Financiamento
                if financing_type != "cash":
                    loan_val = result.get("loan_amount", 0)
                    equity = purchase_price - loan_val
                    pmt = result.get("monthly_payment", 0)
                    payoff = result.get("payoff_at_sale", 0)
                    bank_fees_val = result.get("bank_fees", 0)
                    holding_m = result.get("holding_months", 0)

                    st.markdown(
                        f"""<div class="detail-card">
                        <h4>Financiamento</h4>
                        <div class="detail-row"><span class="label">Emprestimo</span><span class="value">{fmt_eur(loan_val)}</span></div>
                        <div class="detail-row"><span class="label">Equity (capital próprio)</span><span class="value">{fmt_eur(equity)}</span></div>
                        <div class="detail-row"><span class="label">PMT mensal</span><span class="value">{fmt_eur(pmt)}</span></div>
                        <div class="detail-row"><span class="label">Payoff mes {holding_m}</span><span class="value">{fmt_eur(payoff)}</span></div>
                        <div class="detail-row"><span class="label">Custos hipoteca</span><span class="value">{fmt_eur(bank_fees_val)}</span></div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                # Card: Venda
                venda_liq = estimated_sale_price * (1 - comissao_venda_pct / 100)
                comissao_v = result.get("comissao_venda", 0)

                st.markdown(
                    f"""<div class="detail-card">
                    <h4>Venda</h4>
                    <div class="detail-row"><span class="label">Preço bruto</span><span class="value">{fmt_eur(estimated_sale_price)}</span></div>
                    <div class="detail-row"><span class="label">Comissão ({comissao_venda_pct}%)</span><span class="value">-{fmt_eur(comissao_v)}</span></div>
                    <div class="detail-row" style="border-top:1px solid #475569; padding-top:6px; font-weight:700;">
                        <span class="label">Venda liquida</span><span class="value">{fmt_eur(venda_liq)}</span>
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

                # Card: Resultado
                caixa_closing = result.get("caixa_closing", 0)
                total_inv = result.get("total_investment", 0)
                payoff_val = result.get("payoff_at_sale", 0)

                cgt = result.get("capital_gains_tax", 0)

                st.markdown(
                    f"""<div class="detail-card">
                    <h4>Resultado</h4>
                    <div class="detail-row"><span class="label">Venda liquida</span><span class="value">{fmt_eur(venda_liq)}</span></div>
                    <div class="detail-row"><span class="label">- Payoff emprestimo</span><span class="value">-{fmt_eur(payoff_val)}</span></div>
                    <div class="detail-row"><span class="label">= Caixa no closing</span><span class="value">{fmt_eur(caixa_closing)}</span></div>
                    <div class="detail-row"><span class="label">- Caixa investido</span><span class="value">-{fmt_eur(total_inv)}</span></div>
                    <div class="detail-row" style="border-top:1px solid #475569; padding-top:6px; font-weight:700;">
                        <span class="label">= Lucro (cash)</span>
                        <span class="value" style="color:{TEAL if net_profit >= 0 else CORAL};">{fmt_eur(net_profit)}</span>
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

                if entity_structure == "pf_only" and cgt > 0:
                    st.markdown(
                        f"""<div class="detail-card" style="border-color:#D97706;">
                        <h4 style="color:#D97706;">Informação fiscal (PF)</h4>
                        <div class="detail-row"><span class="label">Estimativa mais-valias IRS</span><span class="value" style="color:#D97706;">~{fmt_eur(cgt)}</span></div>
                        <div class="detail-row" style="opacity:0.7;"><span class="label" style="font-size:0.8rem;">Pago no IRS, nao no closing</span><span class="value"></span></div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                elif entity_structure in ("pf_jp", "jp_only"):
                    irc_est = result.get("irc_estimated", 0)
                    derrama = result.get("derrama_estimated", 0)
                    total_corp = result.get("total_corporate_tax", 0)
                    irc_taxable = result.get("irc_taxable_income", 0)
                    entity_label = "Jornada Prometida, Lda" if entity_structure == "pf_jp" else "Empresa"
                    pf_mv = "PF mais-valias = 0 EUR (venda ao custo)" if entity_structure == "pf_jp" else ""

                    st.markdown(
                        f"""<div class="detail-card" style="border-color:#D97706;">
                        <h4 style="color:#D97706;">Informação fiscal ({entity_label})</h4>
                        <div class="detail-row"><span class="label">Lucro tributavel (estimativa)</span><span class="value">{fmt_eur(irc_taxable)}</span></div>
                        <div class="detail-row"><span class="label">IRC (21%)</span><span class="value" style="color:#D97706;">~{fmt_eur(irc_est)}</span></div>
                        <div class="detail-row"><span class="label">Derrama municipal (~1.5%)</span><span class="value" style="color:#D97706;">~{fmt_eur(derrama)}</span></div>
                        <div class="detail-row" style="border-top:1px solid #475569; padding-top:6px; font-weight:700;">
                            <span class="label">Total imposto estimado</span><span class="value" style="color:#D97706;">~{fmt_eur(total_corp)}</span>
                        </div>
                        <div class="detail-row" style="opacity:0.7;"><span class="label" style="font-size:0.8rem;">{pf_mv}</span><span class="value"></span></div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

            # === Guardar modelo para cenários e fluxo de caixa ===
            st.divider()
            if not model_id:
                if st.button("Guardar modelo e ver cenarios + fluxo de caixa", type="secondary"):
                    # 1. Criar property temporaria para associar o modelo
                    prop_data = {
                        "property_type": "apartamento",
                        "asking_price": payload.get("purchase_price"),
                        "municipality": "Simulacao",
                        "notes": "Criado automaticamente pelo simulador M3",
                        "tags": ["simulacao"],
                    }
                    prop = api_post("/api/v1/properties/", prop_data)
                    if prop and prop.get("id"):
                        prop_id = prop["id"]
                        # 2. Criar modelo financeiro associado a property
                        saved = api_post(f"/api/v1/financial/?property_id={prop_id}", payload)
                        if saved and saved.get("model_id"):
                            model_id = saved["model_id"]
                            st.session_state["m3_model_id"] = model_id
                            st.rerun()
                        else:
                            st.warning("Modelo calculado mas nao foi possivel guardar.")
                    else:
                        st.warning("Nao foi possivel criar a propriedade.")

            # === Cenários (Conservador / Base / Optimista) ===
            if model_id:
                st.subheader("Cenarios")
                scenarios_data = api_get(f"/api/v1/financial/scenarios/{model_id}", silent_404=True)
                if scenarios_data and scenarios_data.get("scenarios"):
                    sc_list = scenarios_data["scenarios"]
                    sc_labels = {"conservative": "Conservador", "base": "Base", "optimistic": "Optimista"}
                    sc_colors = {"conservative": "#DC2626", "base": "#D97706", "optimistic": "#16A34A"}
                    sc_cols = st.columns(len(sc_list))
                    for j, sc in enumerate(sc_list):
                        label = sc_labels.get(sc.get("label", ""), sc.get("label", "?"))
                        color = sc_colors.get(sc.get("label", ""), "#94A3B8")
                        with sc_cols[j]:
                            with st.container(border=True):
                                st.markdown(f'<div style="text-align:center;font-weight:700;color:{color};margin-bottom:8px;">{label}</div>', unsafe_allow_html=True)
                                st.metric("ROI", f"{sc.get('roi_pct', 0):.1f}%")
                                st.metric("Lucro", fmt_eur(sc.get("net_profit", 0)))
                                st.metric("MAO", fmt_eur(sc.get("mao", 0)))
                else:
                    st.caption("Cenarios nao disponiveis para este modelo.")

            # === Fluxo de caixa mensal ===
            # Usar cash flow inline (do /simulate) ou buscar via API (se model_id)
            cf_data = result.get("cash_flow")
            if not cf_data and model_id:
                cf_data = api_get(f"/api/v1/financial/{model_id}/cash-flow")

            if cf_data:
                st.divider()
                st.subheader("Fluxo de Caixa Mensal")
                flows = cf_data.get("flows", [])
                pico = cf_data.get("pico_caixa_necessario", 0)
                saldo_final = cf_data.get("saldo_final", 0)

                pc1, pc2 = st.columns(2)
                pc1.metric("Pico de caixa necessário", fmt_eur(pico))
                pc2.metric("Saldo final", fmt_eur(saldo_final))

                # Grafico
                labels = [f["label"] for f in flows]
                fluxos = [f.get("fluxo", 0) for f in flows]
                acumulados = [f.get("acumulado", 0) for f in flows]

                bar_colors = [
                    TEAL if v >= 0 else CORAL for v in fluxos
                ]

                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=labels,
                        y=fluxos,
                        name="Fluxo do período",
                        marker_color=bar_colors,
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=labels,
                        y=acumulados,
                        name="Acumulado",
                        mode="lines+markers",
                        line=dict(color="#818CF8", width=2),
                        marker=dict(size=6),
                    )
                )
                fig.update_layout(
                    title="Fluxo de Caixa — Saidas vs Acumulado",
                    barmode="relative",
                )
                apply_chart_theme(fig, height=400)
                st.plotly_chart(fig, use_container_width=True)

                # Tabela interactiva
                st.markdown("**Detalhe mensal** (clique num periodo para ver decomposicao)")

                def _fmt_cell(v: float) -> str:
                    if v == 0:
                        return "-"
                    return f"{v:,.0f}".replace(",", ".")

                # Tabela com valores clicaveis que abrem modal (dialog)
                cat_colors = {"aquisicao": "#2563EB", "obra": "#D97706", "holding": "#94A3B8", "venda": "#16A34A"}

                table_html = '<table class="flow-table">'
                table_html += (
                    "<tr><th>Periodo</th><th>Saidas</th><th>PMT</th>"
                    "<th>Manut.</th><th>Juros</th><th>Amort.</th>"
                    "<th>Payoff</th><th>Fluxo</th><th>Acumulado</th></tr>"
                )

                for f in flows:
                    label = f.get("label", "")
                    cat = f.get("categoria", "")
                    saidas = f.get("aquisicao", 0) + f.get("obra", 0)
                    pmt_v = f.get("pmt", 0)
                    manut = f.get("manut", 0)
                    juros = f.get("juros", 0)
                    amort = f.get("amort", 0)
                    payoff_v = f.get("payoff", 0)
                    fluxo = f.get("fluxo", 0)
                    acum = f.get("acumulado", 0)
                    cat_color = cat_colors.get(cat, "#94A3B8")

                    fluxo_cls = "flow-negative" if fluxo < 0 else "flow-positive"
                    acum_cls = "flow-negative" if acum < 0 else "flow-positive"

                    table_html += (
                        f'<tr style="border-left:3px solid {cat_color};">'
                        f"<td>{label}</td>"
                        f"<td>{_fmt_cell(saidas) if saidas else '-'}</td>"
                        f"<td>{_fmt_cell(pmt_v)}</td>"
                        f"<td>{_fmt_cell(manut)}</td>"
                        f"<td>{_fmt_cell(juros)}</td>"
                        f"<td>{_fmt_cell(amort)}</td>"
                        f"<td>{_fmt_cell(payoff_v)}</td>"
                        f'<td class="{fluxo_cls}">{_fmt_cell(fluxo)}</td>'
                        f'<td class="{acum_cls}">{_fmt_cell(acum)}</td>'
                        f"</tr>"
                    )

                table_html += "</table>"
                st.markdown(table_html, unsafe_allow_html=True)

                # Botoes por periodo — abre dialog com decomposicao
                st.markdown("")
                bcols = st.columns(min(len(flows), 6))
                for i, f in enumerate(flows):
                    col_idx = i % min(len(flows), 6)
                    label = f.get("label", "")
                    cat = f.get("categoria", "")
                    cat_color = cat_colors.get(cat, "#94A3B8")

                    @st.dialog(f"{label}")
                    def _show_detail(flow=f):
                        c = flow.get("categoria", "")
                        flx = flow.get("fluxo", 0)
                        acm = flow.get("acumulado", 0)
                        fl_c = TEAL if flx >= 0 else CORAL
                        ac_c = TEAL if acm >= 0 else CORAL

                        if c == "aquisicao":
                            st.markdown("##### Decomposicao da aquisicao")
                            componentes = flow.get("componentes", [])
                            if componentes:
                                for comp in componentes:
                                    st.markdown(
                                        f'<div class="detail-row"><span class="label">{comp["nome"]}</span>'
                                        f'<span class="value">{fmt_eur(comp["valor"])}</span></div>',
                                        unsafe_allow_html=True,
                                    )
                            else:
                                st.markdown(
                                    f'<div class="detail-row"><span class="label">Sinal (10% do preco)</span>'
                                    f'<span class="value">{fmt_eur(flow.get("aquisicao", 0))}</span></div>',
                                    unsafe_allow_html=True,
                                )

                        elif c in ("obra", "holding"):
                            st.markdown(f"##### {'Mes de obra' if c == 'obra' else 'Mes de holding'}")
                            ob = flow.get("obra", 0)
                            if ob:
                                st.markdown(
                                    f'<div class="detail-row"><span class="label">Obra (renovacao)</span>'
                                    f'<span class="value">{fmt_eur(ob)}</span></div>',
                                    unsafe_allow_html=True,
                                )
                            pmt = flow.get("pmt", 0)
                            if pmt:
                                j = flow.get("juros", 0)
                                a = flow.get("amort", 0)
                                st.markdown(
                                    f'<div class="detail-row"><span class="label">Prestacao (PMT)</span>'
                                    f'<span class="value">{fmt_eur(pmt)}</span></div>'
                                    f'<div class="detail-row" style="padding-left:16px;">'
                                    f'<span class="label" style="color:#64748B;">Juros</span>'
                                    f'<span class="value" style="color:#64748B;">{fmt_eur(j)}</span></div>'
                                    f'<div class="detail-row" style="padding-left:16px;">'
                                    f'<span class="label" style="color:#64748B;">Amortizacao</span>'
                                    f'<span class="value" style="color:#64748B;">{fmt_eur(a)}</span></div>',
                                    unsafe_allow_html=True,
                                )
                            mt = flow.get("manut", 0)
                            if mt:
                                st.markdown(
                                    f'<div class="detail-row"><span class="label">Manutencao</span>'
                                    f'<span class="value">{fmt_eur(mt)}</span></div>',
                                    unsafe_allow_html=True,
                                )
                            sd = flow.get("saldo_devedor")
                            if sd:
                                st.markdown(
                                    f'<div class="detail-row" style="border-top:1px solid #E2E8F0;padding-top:4px;margin-top:8px;">'
                                    f'<span class="label">Saldo devedor</span>'
                                    f'<span class="value">{fmt_eur(sd)}</span></div>',
                                    unsafe_allow_html=True,
                                )

                        elif c == "venda":
                            st.markdown("##### Decomposicao da venda")
                            vb = flow.get("venda_bruta", 0)
                            cv = flow.get("comissao_venda", 0)
                            vl = flow.get("venda_liquida", 0)
                            po = flow.get("payoff", 0)
                            st.markdown(
                                f'<div class="detail-row"><span class="label">Venda bruta</span>'
                                f'<span class="value">{fmt_eur(vb)}</span></div>'
                                f'<div class="detail-row"><span class="label">Comissao venda + IVA</span>'
                                f'<span class="value" style="color:{CORAL};">{fmt_eur(-cv)}</span></div>'
                                f'<div class="detail-row"><span class="label">Venda liquida</span>'
                                f'<span class="value">{fmt_eur(vl)}</span></div>'
                                f'<div class="detail-row"><span class="label">Payoff emprestimo</span>'
                                f'<span class="value" style="color:{CORAL};">{fmt_eur(po)}</span></div>',
                                unsafe_allow_html=True,
                            )

                        # Totais
                        st.markdown(
                            f'<div style="border-top:2px solid {cat_colors.get(c, "#94A3B8")};padding-top:8px;margin-top:12px;">'
                            f'<div class="detail-row" style="font-weight:700;">'
                            f'<span class="label">Fluxo do periodo</span>'
                            f'<span class="value" style="color:{fl_c};">{fmt_eur(flx)}</span></div>'
                            f'<div class="detail-row" style="font-weight:700;">'
                            f'<span class="label">Acumulado</span>'
                            f'<span class="value" style="color:{ac_c};">{fmt_eur(acm)}</span></div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    with bcols[col_idx]:
                        if st.button(label, key=f"cf_btn_{i}", use_container_width=True):
                            _show_detail(f)

                # Botao exportar para Cash Flow Pro
                st.markdown("")
                st.divider()

                @st.dialog("Exportar para Cash Flow Pro")
                def _export_cfp_dialog(cfp_flows=flows, cfp_model_id=model_id):
                    from src.modules.m3_financial.cashflow_export import get_deal_dates, _calc_dates

                    st.markdown(f"**{len(cfp_flows)} periodos** serao exportados como lancamentos individuais.")

                    # Buscar deals para puxar datas
                    deals = api_get("/api/v1/deals/", params={"limit": 50}, silent_404=True)
                    deal_items = deals.get("items", []) if deals else []
                    deal_options = {"Nenhum (datas manuais)": None}
                    for d in deal_items:
                        deal_options[f"{d.get('title', '?')} ({d.get('status_label', '')})"] = d.get("id")

                    selected_deal = st.selectbox("Associar a um deal (puxa datas automaticamente):", list(deal_options.keys()), key="cfp_deal")
                    deal_id = deal_options[selected_deal]

                    # Se tem deal, buscar datas
                    deal_dates = None
                    if deal_id:
                        deal_dates = get_deal_dates(deal_id)

                    proj_name = st.text_input(
                        "Nome do projecto",
                        value=deal_dates["title"] if deal_dates and deal_dates.get("title") else "Simulacao",
                        key="cfp_proj_name",
                    )

                    # Defaults do deal ou calculados
                    default_cpcv = deal_dates["cpcv_date"] if deal_dates and deal_dates.get("cpcv_date") else None
                    default_esc = deal_dates["escritura_date"] if deal_dates and deal_dates.get("escritura_date") else None
                    default_obra = deal_dates["obra_start_date"] if deal_dates and deal_dates.get("obra_start_date") else None
                    default_venda = deal_dates["sale_date"] if deal_dates and deal_dates.get("sale_date") else None

                    st.markdown("**Cronograma** (ajuste as datas conforme necessario):")
                    dc1, dc2, dc3, dc4 = st.columns(4)
                    with dc1:
                        cpcv_input = st.date_input("CPCV", value=default_cpcv, key="cfp_cpcv")
                    with dc2:
                        # Sugerir escritura = CPCV + 60 dias se nao tiver default
                        esc_default = default_esc
                        if not esc_default and cpcv_input:
                            from datetime import timedelta as _td
                            esc_default = cpcv_input + _td(days=60)
                        esc_input = st.date_input("Escritura", value=esc_default, key="cfp_esc")
                    with dc3:
                        # Sugerir inicio obra = escritura + 1 dia
                        obra_default = default_obra
                        if not obra_default and esc_input:
                            from datetime import timedelta as _td
                            obra_default = esc_input + _td(days=1)
                        obra_input = st.date_input("Inicio obra", value=obra_default, key="cfp_obra")
                    with dc4:
                        # Sugerir venda = inicio obra + holding months
                        hold_months = len([f for f in cfp_flows if f.get("label", "").startswith("Mes")])
                        venda_default = default_venda
                        if not venda_default and obra_input:
                            from datetime import timedelta as _td
                            venda_default = obra_input + _td(days=30 * hold_months)
                        venda_input = st.date_input("Venda prevista", value=venda_default, key="cfp_venda")

                    if st.button("Exportar lancamentos", type="primary", key="cfp_export_confirm"):
                        if not cpcv_input:
                            st.error("Preencha a data do CPCV.")
                            return
                        try:
                            from src.modules.m3_financial.cashflow_export import export_to_cashflow_pro
                            with st.spinner("A exportar lancamentos..."):
                                result = export_to_cashflow_pro(
                                    flows=cfp_flows,
                                    model_id=cfp_model_id or "simulacao",
                                    project_name=proj_name,
                                    cpcv_date=cpcv_input,
                                    deal_id=deal_id,
                                    escritura_date=esc_input,
                                    obra_start_date=obra_input,
                                    sale_date=venda_input,
                                    holding_months=hold_months,
                                )
                            ins = result.get("inserted_count", 0)
                            skip = result.get("skipped_count", 0)
                            total = result.get("total_entries", 0)
                            cfp_dates = result.get("dates", {})
                            st.success(
                                f"{ins} lancamentos criados no Cash Flow Pro "
                                f"({skip} duplicados ignorados, {total} total)"
                            )
                            if cfp_dates:
                                st.caption(
                                    f"CPCV: {cfp_dates.get('cpcv')} → "
                                    f"Escritura: {cfp_dates.get('escritura')} → "
                                    f"Obra: {cfp_dates.get('obra_inicio')} → "
                                    f"Venda: {cfp_dates.get('venda')}"
                                )
                        except ValueError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Erro ao exportar: {e}")

                if st.button("Exportar para Cash Flow Pro", type="primary", key="m3_export_cfp"):
                    _export_cfp_dialog(flows, model_id)


# ===================================================================
# M4 — DEAL PIPELINE
# ===================================================================

elif module == "M4 — Deal Pipeline":
    st.header("M4 — Deal Pipeline")

    # Carregar dados
    strategies = api_get("/api/v1/deals/strategies") or []
    statuses = api_get("/api/v1/deals/statuses") or []
    stats = api_get("/api/v1/deals/stats")

    if not stats:
        st.stop()

    # ------ KPIs ------
    kpi_cols = st.columns(5)
    with kpi_cols[0]:
        st.metric("Deals activos", stats.get("active_deals", 0))
    with kpi_cols[1]:
        st.metric("Concluídos", stats.get("completed_deals", 0))
    with kpi_cols[2]:
        st.metric("Descartados", stats.get("discarded_deals", 0))
    with kpi_cols[3]:
        st.metric("Valor investido", fmt_eur(stats.get("total_invested")))
    with kpi_cols[4]:
        st.metric("Renda mensal", fmt_eur(stats.get("total_monthly_rent")))

    st.divider()

    # ------ Tabs: Kanban / Criar Deal / Portfolio / Mediacao ------
    tab_kanban, tab_create, tab_portfolio, tab_mediacao = st.tabs(
        ["Kanban", "Criar Deal", "Portfolio", "Mediação"]
    )

    # ====== TAB KANBAN ======
    with tab_kanban:
        strategy_options = ["Todas"] + [
            f"{s.get('icon', '')} {s['label']}" for s in strategies
        ]
        strategy_keys = [None] + [s["key"] for s in strategies]

        selected_idx = st.selectbox(
            "Filtrar por estratégia",
            range(len(strategy_options)),
            format_func=lambda i: strategy_options[i],
        )
        selected_strategy = strategy_keys[selected_idx]

        kanban = api_get(
            "/api/v1/deals/kanban",
            params={"strategy": selected_strategy} if selected_strategy else None,
        )

        if kanban and kanban.get("columns"):
            columns = kanban["columns"]
            status_cfg = kanban.get("status_config", {})

            # Max 6 colunas visiveis
            col_keys = list(columns.keys())
            max_visible = min(len(col_keys), 6)
            cols = st.columns(max_visible)

            for i, status_key in enumerate(col_keys[:max_visible]):
                deals_in_col = columns[status_key]
                cfg = status_cfg.get(status_key, {})
                color = cfg.get("color", "#94A3B8")
                label = cfg.get("label", status_key)
                icon = cfg.get("icon", "")

                # Valor total da coluna
                col_value = sum(d.get("purchase_price", 0) or 0 for d in deals_in_col)
                value_str = f" — {fmt_eur(col_value)}" if col_value > 0 else ""

                with cols[i]:
                    st.markdown(
                        f'<div style="text-align:center;padding:8px;'
                    f'background:{color}15;border-radius:8px;'
                    f'border-bottom:3px solid {color};margin-bottom:10px;">'
                    f'<b>{icon} {label}</b><br>'
                    f'<small style="color:#64748B;">{len(deals_in_col)} deal(s){value_str}</small></div>',
                    unsafe_allow_html=True,
                )

                for deal in deals_in_col:
                    s_icon = deal.get("strategy_icon", "")
                    title = deal.get("title", "")
                    price = deal.get("purchase_price")
                    days = deal.get("days_in_status", 0)
                    progress = deal.get("progress_pct", 0)

                    # Stalled deal highlighting
                    border_color = "#DC2626" if days > 14 else "#D97706" if days > 7 else "#E2E8F0"
                    days_color = "#DC2626" if days > 14 else "#D97706" if days > 7 else "#64748B"

                    price_str = fmt_eur(price) if price else ""
                    card_html = (
                        f'<div style="border:1px solid {border_color};'
                        f'border-left:4px solid {color};'
                        f'border-radius:10px;padding:12px 14px;margin-bottom:8px;">'
                        f'<b>{s_icon} {title}</b><br>'
                        f'<small style="color:#64748B;">{price_str}</small><br>'
                        f'<small style="color:{days_color};">{days}d neste estado</small>'
                        f'<div style="background:#E2E8F0;border-radius:4px;'
                        f'height:5px;margin-top:6px;">'
                        f'<div style="background:{color};width:{progress}%;'
                        f'height:5px;border-radius:4px;"></div></div>'
                        f'</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)

            # Colunas extra (>6) mostradas como resumo
            if len(col_keys) > max_visible:
                extra = col_keys[max_visible:]
                extra_text = ", ".join(
                f"{status_cfg.get(k, {}).get('label', k)} ({len(columns[k])})"
                for k in extra
                )
                st.caption(f"Mais estados: {extra_text}")
        else:
            st.markdown(
                '<div style="text-align:center;padding:40px 20px;color:#94A3B8;">'
                '<h3 style="color:#475569;">Sem deals no pipeline</h3>'
                '<p>Use a tab "Criar Deal" para adicionar o primeiro deal.</p>'
                '</div>',
                unsafe_allow_html=True,
            )

        # ------ Detalhe de deal ------
        st.divider()
        st.subheader("Detalhe do Deal")

        deals_list = api_get("/api/v1/deals/", params={"limit": 100})
        if deals_list and deals_list.get("items"):
            deal_options = {
                f"{d['strategy_icon']} {d['title']} ({d['status_label']})": d["id"]
                for d in deals_list["items"]
            }
            selected_deal_label = st.selectbox("Seleccionar deal", list(deal_options.keys()))
            selected_deal_id = deal_options[selected_deal_label]

            deal = api_get(f"/api/v1/deals/{selected_deal_id}")
            if deal:
                detail_tabs = st.tabs(
                ["Resumo", "Propostas", "Tasks", "DD", "Obra", "Docs", "Renda", "Hist."]
                )

                # --- TAB RESUMO ---
                with detail_tabs[0]:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(
                            f'**Estratégia:** {deal["strategy_icon"]} {deal["strategy_label"]}'
                        )
                        st.markdown(f'**Estado:** {deal["status_icon"]} {deal["status_label"]}')
                        st.markdown(f'**Progresso:** {deal["progress_pct"]:.0f}%')
                        if deal.get("purchase_price"):
                            st.markdown(f'**Compra:** {fmt_eur(deal["purchase_price"])}')
                        if deal.get("target_sale_price"):
                            st.markdown(f'**Venda alvo:** {fmt_eur(deal["target_sale_price"])}')
                        if deal.get("monthly_rent"):
                            st.markdown(f'**Renda:** {fmt_eur(deal["monthly_rent"])}/mes')
                        if deal.get("renovation_budget"):
                            st.markdown(f'**Orçamento obra:** {fmt_eur(deal["renovation_budget"])}')

                    with col2:
                        if deal.get("contact_name"):
                            st.markdown(f'**Contacto:** {deal["contact_name"]}')
                        if deal.get("contact_phone"):
                            st.markdown(f'**Telefone:** {deal["contact_phone"]}')
                        if deal.get("notes"):
                            st.markdown(f'**Notas:** {deal["notes"]}')
                        if deal.get("days_in_status"):
                            st.markdown(f'**Dias no estado:** {deal["days_in_status"]}')

                    # Accoes
                    st.divider()
                    st.markdown("**Próximas acções:**")
                    next_actions = api_get(f"/api/v1/deals/{selected_deal_id}/next-actions")
                    if next_actions:
                        # Inicializar session_state para confirmacao de accoes com motivo
                        if "pending_deal_action" not in st.session_state:
                            st.session_state.pending_deal_action = None

                        pending = st.session_state.pending_deal_action

                        # Se ha uma accao pendente de confirmacao, mostrar input + botao confirmar
                        if pending and pending.get("deal_id") == selected_deal_id:
                            st.warning(
                                f'Confirmar **{pending["label"]}** — indique o motivo:'
                            )
                            reason = st.text_input(
                                "Motivo",
                                key=f"reason_{pending['status']}",
                            )
                            confirm_col, cancel_col, _ = st.columns([1, 1, 4])
                            with confirm_col:
                                if st.button("Confirmar", key="confirm_deal_action", type="primary"):
                                    result = api_post(
                                        f"/api/v1/deals/{selected_deal_id}/advance",
                                        {"target_status": pending["status"], "reason": reason or None},
                                    )
                                    st.session_state.pending_deal_action = None
                                    if result:
                                        st.success(
                                            f'Avançado para {pending["label"]}'
                                        )
                                        st.rerun()
                            with cancel_col:
                                if st.button("Cancelar", key="cancel_deal_action"):
                                    st.session_state.pending_deal_action = None
                                    st.rerun()
                        else:
                            action_cols = st.columns(
                                min(len(next_actions.get("next_statuses", [])), 4) or 1
                            )
                            for j, action in enumerate(next_actions.get("next_statuses", [])):
                                col_idx = j % len(action_cols)
                                with action_cols[col_idx]:
                                    btn_label = f'{action.get("icon", "")} {action.get("label", action["status"])}'
                                    if st.button(btn_label, key=f"advance_{action['status']}"):
                                        if action["status"] in ("descartado", "em_pausa"):
                                            # Accao requer motivo — guardar em session_state e rerun
                                            st.session_state.pending_deal_action = {
                                                "deal_id": selected_deal_id,
                                                "status": action["status"],
                                                "label": action.get("label", action["status"]),
                                            }
                                            st.rerun()
                                        else:
                                            result = api_post(
                                                f"/api/v1/deals/{selected_deal_id}/advance",
                                                {"target_status": action["status"], "reason": None},
                                            )
                                            if result:
                                                st.success(
                                                    f'Avançado para {action.get("label", action["status"])}'
                                                )
                                                st.rerun()

                    # --- TAB PROPOSTAS ---
                with detail_tabs[1]:
                    proposals = api_get(f"/api/v1/deals/{selected_deal_id}/proposals")
                    if proposals:
                        for p in proposals:
                            st.markdown(
                                f'**{p["proposal_type"].upper()}** — {fmt_eur(p["amount"])} '
                                f'| Sinal: {p["deposit_pct"]}% '
                                f'| Status: {p["status"]} '
                                f'| {p.get("created_at", "")[:10]}'
                            )
                            if p.get("conditions"):
                                st.caption(f'Condições: {p["conditions"]}')
                    else:
                        st.info("Sem propostas.")

                    with st.expander("Nova proposta"):
                        p_amount = st.number_input("Valor (EUR)", min_value=1.0, step=1000.0, key="p_amount")
                        p_type = st.selectbox("Tipo", ["offer", "counter"], key="p_type")
                        p_deposit = st.number_input("Sinal (%)", value=10.0, key="p_deposit")
                        p_conditions = st.text_area("Condições", key="p_conditions")
                        if st.button("Enviar proposta"):
                            result = api_post(
                                f"/api/v1/deals/{selected_deal_id}/proposals",
                                {
                                    "proposal_type": p_type,
                                    "amount": p_amount,
                                    "deposit_pct": p_deposit,
                                    "conditions": p_conditions or None,
                                },
                            )
                            if result:
                                st.success("Proposta criada!")
                                st.rerun()

                    # --- TAB TASKS ---
                with detail_tabs[2]:
                    upcoming = api_get("/api/v1/deals/tasks/upcoming", params={"limit": 50})
                    if upcoming:
                        deal_tasks = [t for t in upcoming if t.get("deal_id") == selected_deal_id]
                        for t in deal_tasks:
                            icon = "\u2705" if t["is_completed"] else "\u2b1c"
                            prio_color = {"high": "#EF4444", "urgent": "#DC2626", "medium": "#F59E0B"}.get(
                                t["priority"], "#9CA3AF"
                            )
                            due = t.get("due_date", "")[:10] if t.get("due_date") else ""
                            st.markdown(
                                f'{icon} **{t["title"]}** '
                                f'<span style="color:{prio_color};font-size:0.8rem;">[{t["priority"]}]</span> '
                                f'{due}',
                                unsafe_allow_html=True,
                            )
                            if not t["is_completed"]:
                                if st.button("Concluir", key=f"complete_{t['id']}"):
                                    api_patch(f"/api/v1/deals/tasks/{t['id']}/complete")
                                    st.rerun()
                    else:
                        st.info("Sem tarefas pendentes.")

                    with st.expander("Nova tarefa"):
                        t_title = st.text_input("Título", key="t_title")
                        t_priority = st.selectbox("Prioridade", ["low", "medium", "high", "urgent"], index=1, key="t_prio")
                        if st.button("Criar tarefa") and t_title:
                            api_post(
                                f"/api/v1/deals/{selected_deal_id}/tasks",
                                {"title": t_title, "priority": t_priority},
                            )
                            st.success("Tarefa criada!")
                            st.rerun()

                    # --- TAB DUE DILIGENCE ---
                with detail_tabs[3]:
                    dd_checklist = api_get(
                        f"/api/v1/due-diligence/deals/{selected_deal_id}/checklist"
                    )
                    if dd_checklist and dd_checklist.get("total_items", 0) > 0:
                        # KPIs
                        dc1, dc2, dc3, dc4, dc5 = st.columns(5)
                        with dc1:
                            st.metric(
                                "Progresso",
                                f'{dd_checklist["progress_pct"]:.0f}%',
                            )
                        with dc2:
                            st.metric(
                                "Obtidos",
                                f'{dd_checklist["completed"]}/{dd_checklist["total_items"]}',
                            )
                        with dc3:
                            st.metric("Pendentes", dd_checklist["pending"])
                        with dc4:
                            st.metric("Red Flags", dd_checklist["red_flags"])
                        with dc5:
                            st.metric(
                                "Custo estimado",
                                fmt_eur(dd_checklist.get("estimated_cost")),
                            )

                        # Barra de progresso
                        st.progress(dd_checklist["progress_pct"] / 100)

                        # Can proceed?
                        proceed = api_get(
                            f"/api/v1/due-diligence/deals/{selected_deal_id}/can-proceed"
                        )
                        if proceed:
                            if proceed.get("can_proceed"):
                                st.success(
                                    "Due diligence completa — pode avançar"
                                )
                            else:
                                blocking = proceed.get("blocking_items", [])
                                critical = proceed.get("critical_flags", [])
                                if blocking:
                                    st.warning(
                                        f'{len(blocking)} item(ns) obrigatório(s) pendente(s)'
                                    )
                                if critical:
                                    st.error(
                                        f'{len(critical)} red flag(s) crítico(s)'
                                    )

                        # Itens por categoria
                        categories = dd_checklist.get("items_by_category", {})
                        category_labels = {
                            "registos": "Registos",
                            "fiscal": "Fiscal",
                            "licenciamento": "Licenciamento",
                            "condominio": "Condomínio",
                            "servicos": "Serviços",
                            "urbano": "Urbanismo",
                            "tecnico": "Técnico",
                            "judicial": "Judicial",
                            "trabalhista": "Trabalhista",
                        }
                        for cat_key, cat_items in categories.items():
                            done_count = sum(
                                1 for i in cat_items
                                if i.get("status") in ("obtido", "na")
                            )
                            cat_label = category_labels.get(cat_key, cat_key.title())
                            with st.expander(
                                f'{cat_label} ({done_count}/{len(cat_items)})'
                            ):
                                for item in cat_items:
                                    ic1, ic2, ic3 = st.columns([1, 6, 4])
                                    with ic1:
                                        status_icons = {
                                            "pendente": "\u2b1c",
                                            "em_curso": "\U0001f504",
                                            "obtido": "\u2705",
                                            "problema": "\u26a0\ufe0f",
                                            "na": "\u2796",
                                        }
                                        st.write(
                                            status_icons.get(
                                                item["status"], "\u2753"
                                            )
                                        )
                                    with ic2:
                                        name = item["item_name"]
                                        req = " *" if item.get("is_required") else ""
                                        st.markdown(f'**{name}**{req}')
                                        if item.get("description"):
                                            st.caption(
                                                item["description"][:150]
                                                + ("..." if len(item.get("description", "")) > 150 else "")
                                            )
                                        if item.get("red_flag"):
                                            sev = item.get("red_flag_severity", "?")
                                            desc = item.get("red_flag_description", "")
                                            sev_colors = {
                                                "low": "#EAB308",
                                                "medium": "#F97316",
                                                "high": "#EF4444",
                                                "critical": "#DC2626",
                                            }
                                            color = sev_colors.get(sev, "#EF4444")
                                            st.markdown(
                                                f'<span style="color:{color};font-weight:bold;">'
                                                f'[{sev.upper()}] {desc}</span>',
                                                unsafe_allow_html=True,
                                            )
                                        # Documento associado
                                        if item.get("document_url"):
                                            doc_col, rm_col = st.columns([3, 1])
                                            with doc_col:
                                                st.markdown(
                                                    f'[Ver documento]({API_BASE}{item["document_url"]})'
                                                )
                                            with rm_col:
                                                if st.button(
                                                    "Remover",
                                                    key=f'rm_doc_{item["id"]}',
                                                ):
                                                    api_delete(
                                                        f'/api/v1/due-diligence/items/{item["id"]}/document'
                                                    )
                                                    st.rerun()
                                        elif item.get("status") not in ("obtido", "na"):
                                            # Upload disponível para itens pendentes/em_curso/problema
                                            uploaded_file = st.file_uploader(
                                                "Upload",
                                                type=["pdf", "jpg", "jpeg", "png", "doc", "docx"],
                                                key=f'upload_{item["id"]}',
                                                label_visibility="collapsed",
                                            )
                                            if uploaded_file:
                                                result = api_upload(
                                                    f'/api/v1/due-diligence/items/{item["id"]}/upload',
                                                    uploaded_file.name,
                                                    uploaded_file.getvalue(),
                                                )
                                                if result:
                                                    st.success(
                                                        f'{uploaded_file.name} carregado'
                                                    )
                                                    st.rerun()
                                    with ic3:
                                        new_st = st.selectbox(
                                            "Status",
                                            ["pendente", "em_curso", "obtido", "problema", "na"],
                                            index=["pendente", "em_curso", "obtido", "problema", "na"].index(
                                                item.get("status", "pendente")
                                            ),
                                            key=f'dd_st_{item["id"]}',
                                            label_visibility="collapsed",
                                        )
                                        if new_st != item.get("status"):
                                            api_patch(
                                                f'/api/v1/due-diligence/items/{item["id"]}',
                                                {"status": new_st},
                                            )
                                            st.rerun()
                    else:
                        st.info(
                            "Sem checklist de due diligence. "
                            "O checklist e gerado automaticamente quando o deal "
                            "avanca para o estado 'Due Diligence'."
                        )
                        if st.button(
                            "Gerar checklist manualmente",
                            key="btn_gen_dd",
                        ):
                            result = api_post(
                                f"/api/v1/due-diligence/deals/{selected_deal_id}/generate"
                            )
                            if result:
                                st.success(
                                    f'Checklist gerado: {result.get("total_items")} itens'
                                )
                                st.rerun()

                    # --- TAB OBRA (M6) ---
                with detail_tabs[4]:
                    reno_data = api_get(
                        f"/api/v1/renovations/deals/{selected_deal_id}"
                    )
                    if reno_data and reno_data.get("renovation"):
                        reno = reno_data["renovation"]
                        milestones = reno_data.get("milestones", [])
                        exp_summary = reno_data.get("expense_summary", {})

                        # KPIs
                        rc1, rc2, rc3, rc4, rc5 = st.columns(5)
                        with rc1:
                            st.metric("Orçamento", fmt_eur(reno.get("current_budget") or reno.get("initial_budget")))
                        with rc2:
                            spent = reno.get("total_spent", 0)
                            var = reno.get("budget_variance_pct", 0)
                            st.metric("Gasto", fmt_eur(spent), delta=f"{var:+.1f}%", delta_color="inverse")
                        with rc3:
                            budget = reno.get("current_budget") or reno.get("initial_budget") or 0
                            st.metric("Restante", fmt_eur(budget - spent))
                        with rc4:
                            st.metric("Progresso", f'{reno.get("progress_pct", 0):.0f}%')
                        with rc5:
                            st.metric("Empreiteiro", reno.get("contractor_name", "N/D"))

                        # Barra de progresso
                        health = reno_data.get("budget_health", "on_track")
                        st.progress(min(reno.get("progress_pct", 0) / 100, 1.0))

                        # Alertas
                        reno_id = reno["id"]
                        alerts = api_get(f"/api/v1/renovations/{reno_id}/alerts")
                        if alerts:
                            for alert in alerts:
                                sev = alert.get("severity", "")
                                msg = alert.get("message", "")
                                if sev == "critical":
                                    st.error(msg)
                                elif sev in ("high", "medium"):
                                    st.warning(msg)
                                else:
                                    st.info(msg)

                        # Milestones
                        st.markdown("**Milestones:**")
                        for m in milestones:
                            m_status_icon = {
                                "pendente": "\u2b1c",
                                "em_curso": "\U0001f504",
                                "concluido": "\u2705",
                                "bloqueado": "\U0001f512",
                            }.get(m["status"], "\u2753")
                            m_budget = m.get("budget", 0)
                            m_spent = m.get("spent", 0)
                            m_pct = m.get("completion_pct", 0)
                            with st.expander(
                                f'{m_status_icon} {m["name"]} — '
                                f'{fmt_eur(m_spent)} / {fmt_eur(m_budget)} ({m_pct}%)'
                            ):
                                if m.get("description"):
                                    st.caption(m["description"][:200])
                                if m.get("supplier_name"):
                                    st.write(f'Fornecedor: {m["supplier_name"]}')

                                # Accoes
                                mc1, mc2, mc3 = st.columns(3)
                                with mc1:
                                    if m["status"] == "pendente":
                                        if st.button("Iniciar", key=f'ms_start_{m["id"]}'):
                                            api_post(f'/api/v1/renovations/milestones/{m["id"]}/start')
                                            st.rerun()
                                with mc2:
                                    if m["status"] == "em_curso":
                                        if st.button("Concluir", key=f'ms_done_{m["id"]}'):
                                            api_post(f'/api/v1/renovations/milestones/{m["id"]}/complete')
                                            st.rerun()
                                with mc3:
                                    if st.button("Eliminar", key=f'ms_del_{m["id"]}'):
                                        api_delete(f'/api/v1/renovations/milestones/{m["id"]}')
                                        st.rerun()

                                # Editar orçamento e progresso
                                if m["status"] in ("pendente", "em_curso"):
                                    st.markdown("---")
                                    ec1, ec2 = st.columns(2)
                                    with ec1:
                                        new_budget = st.number_input(
                                            "Orçamento (EUR)",
                                            value=float(m_budget),
                                            step=100.0,
                                            key=f'ms_budget_{m["id"]}',
                                        )
                                    with ec2:
                                        new_pct = st.slider(
                                            "Progresso %",
                                            0, 100, m_pct,
                                            key=f'ms_pct_{m["id"]}',
                                        )
                                    if st.button("Guardar alterações", key=f'ms_save_{m["id"]}'):
                                        update_data = {}
                                        if new_budget != m_budget:
                                            update_data["budget"] = new_budget
                                        if new_pct != m_pct:
                                            update_data["completion_pct"] = new_pct
                                        if update_data:
                                            api_patch(
                                                f'/api/v1/renovations/milestones/{m["id"]}',
                                                update_data,
                                            )
                                            st.rerun()

                        # Resumo financeiro
                        if exp_summary:
                            st.divider()
                            st.markdown("**Resumo financeiro:**")
                            fc1, fc2, fc3 = st.columns(3)
                            with fc1:
                                st.metric("Total gasto", fmt_eur(exp_summary.get("total_spent", 0)))
                            with fc2:
                                st.metric("Dedutível", fmt_eur(exp_summary.get("total_deductible", 0)))
                            with fc3:
                                st.metric("Não dedutível", fmt_eur(exp_summary.get("total_non_deductible", 0)))

                        # Nova despesa
                        with st.expander("Nova despesa"):
                            from datetime import date as dt_date
                            ed = st.text_input("Descrição", key="reno_exp_desc")
                            ea = st.number_input("Valor (EUR)", min_value=0.0, step=100.0, key="reno_exp_amt")
                            ec = st.selectbox("Categoria", ["material", "mao_de_obra", "equipamento", "licenca", "projecto", "outro"], key="reno_exp_cat")
                            ep = st.selectbox("Metodo pagamento", ["transferencia", "cartao", "mbway", "cheque", "numerario"], key="reno_exp_pay")
                            ei = st.checkbox("Factura valida com NIF?", key="reno_exp_inv")
                            if st.button("Registar despesa", key="btn_reno_exp") and ed and ea > 0:
                                api_post(
                                    f"/api/v1/renovations/{reno_id}/expenses",
                                    {
                                        "description": ed,
                                        "amount": ea,
                                        "expense_date": f"{dt_date.today()}T00:00:00",
                                        "category": ec,
                                        "payment_method": ep,
                                        "has_valid_invoice": ei,
                                    },
                                )
                                st.success("Despesa registada!")
                                st.rerun()

                        # Cash Flow Pro sync
                        st.divider()
                        st.markdown("**Cash Flow Pro**")

                        if reno.get("cashflow_project_id"):
                            cfp_name = reno.get("cashflow_project_name", "")
                            last_sync = reno.get("last_synced_at", "")
                            if last_sync:
                                last_sync_str = last_sync[:16].replace("T", " ")
                            else:
                                last_sync_str = "nunca"

                            st.markdown(
                                f'Projecto: **{cfp_name}** | '
                                f'Última sync: {last_sync_str}'
                            )
                            sc1, sc2 = st.columns(2)
                            with sc1:
                                if st.button("Sincronizar gastos", key="btn_cfp_sync"):
                                    result = api_post(
                                        f"/api/v1/renovations/{reno_id}/cashflow/sync"
                                    )
                                    if result:
                                        st.success(
                                            f'{result.get("created", 0)} novas, '
                                            f'{result.get("updated", 0)} actualizadas, '
                                            f'{result.get("unchanged", 0)} sem alteração'
                                        )
                                        st.rerun()
                            with sc2:
                                if st.button("Atribuir etapas automaticamente", key="btn_cfp_assign"):
                                    result = api_post(
                                        f"/api/v1/renovations/{reno_id}/cashflow/auto-assign"
                                    )
                                    if result:
                                        st.success(
                                            f'{result.get("assigned", 0)} atribuidas'
                                        )
                                        st.rerun()
                        else:
                            st.caption("Ligar ao Cash Flow Pro para sincronizar gastos automaticamente.")
                            cfp_proj_id = st.text_input("Project ID do Cash Flow Pro", key="cfp_proj_id")
                            cfp_proj_name = st.text_input("Nome do projecto", key="cfp_proj_name")
                            if st.button("Ligar projecto", key="btn_cfp_link") and cfp_proj_id:
                                result = api_post(
                                    f"/api/v1/renovations/{reno_id}/cashflow/link",
                                    {
                                        "cashflow_project_id": cfp_proj_id,
                                        "cashflow_project_name": cfp_proj_name or cfp_proj_id,
                                    },
                                )
                                if result:
                                    st.success("Projecto ligado!")
                                    st.rerun()
                    else:
                        st.info(
                            "Sem obra associada. A obra e criada automaticamente "
                            "quando o deal avanca para o estado 'Obra'."
                        )
                        if st.button("Criar obra manualmente", key="btn_create_reno"):
                            result = api_post(
                                f"/api/v1/renovations/deals/{selected_deal_id}/create",
                                {
                                    "initial_budget": deal.get("renovation_budget") or 50000,
                                    "auto_milestones": True,
                                },
                            )
                            if result:
                                st.success(f'Obra criada com {result.get("milestone_count", 0)} milestones')
                                st.rerun()

                    # --- TAB DOCUMENTOS ---
                with detail_tabs[5]:
                    docs = api_get(
                        "/api/v1/documents/",
                        params={"deal_id": selected_deal_id},
                    )
                    if docs:
                        st.markdown(f'**{len(docs)} documento(s) associado(s) a este deal:**')

                        # Filtro por tipo
                        doc_types = sorted(set(
                            d.get("document_type", "outro") for d in docs
                        ))
                        if len(doc_types) > 1:
                            selected_type = st.selectbox(
                                "Filtrar por tipo",
                                ["Todos"] + doc_types,
                                key="doc_filter_type",
                            )
                            if selected_type != "Todos":
                                docs = [
                                    d for d in docs
                                    if d.get("document_type") == selected_type
                                ]

                        for doc in docs:
                            dc1, dc2, dc3, dc4 = st.columns([4, 2, 2, 1])
                            with dc1:
                                fname = doc.get("filename", "?")
                                dtype = doc.get("document_type", "outro")
                                st.markdown(f'**{fname}**')
                                st.caption(f'Tipo: {dtype}')
                            with dc2:
                                size = doc.get("file_size")
                                if size:
                                    if size > 1_000_000:
                                        size_str = f'{size / 1_000_000:.1f} MB'
                                    else:
                                        size_str = f'{size / 1_000:.0f} KB'
                                    st.caption(size_str)
                            with dc3:
                                date = doc.get("created_at", "")[:10] if doc.get("created_at") else ""
                                by = doc.get("uploaded_by", "")
                                st.caption(f'{date} por {by}')
                            with dc4:
                                dl_url = f'{API_BASE}/api/v1/documents/{doc["id"]}/download'
                                st.markdown(f'[Download]({dl_url})')
                    else:
                        st.info("Sem documentos. Faça upload na tab 'Due Diligence' ou aqui.")

                    # Upload generico
                    with st.expander("Upload de documento"):
                        uf = st.file_uploader(
                            "Ficheiro",
                            type=["pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx"],
                            key="doc_upload_general",
                        )
                        uf_type = st.selectbox(
                            "Tipo de documento",
                            ["certidao", "caderneta", "contrato", "factura",
                             "foto", "planta", "relatorio", "outro"],
                            key="doc_upload_type",
                        )
                        uf_desc = st.text_input("Descrição (opcional)", key="doc_upload_desc")
                        if st.button("Carregar", key="btn_doc_upload") and uf:
                            result = api_upload(
                                "/api/v1/documents/upload",
                                uf.name,
                                uf.getvalue(),
                                data={
                                    "deal_id": selected_deal_id,
                                    "document_type": uf_type,
                                    "description": uf_desc or "",
                                },
                            )
                            if result:
                                st.success(f'{uf.name} carregado')
                                st.rerun()

                    # --- TAB ARRENDAMENTO ---
                with detail_tabs[6]:
                    if deal.get("investment_strategy") in ("buy_and_hold", "brrrr", "alojamento_local"):
                        st.markdown(f'**Renda actual:** {fmt_eur(deal.get("monthly_rent"))}/mes')
                        # Mostrar rentals (simplificado — via deal info)
                        if deal.get("monthly_rent"):
                            annual = (deal.get("monthly_rent") or 0) * 12
                            gross_yield = 0
                            if deal.get("purchase_price") and deal["purchase_price"] > 0:
                                gross_yield = annual / deal["purchase_price"] * 100
                            st.metric("Renda anual", fmt_eur(annual))
                            st.metric("Yield bruta", fmt_pct(gross_yield))
                        else:
                            st.info("Sem dados de arrendamento.")
                    else:
                        st.info("Arrendamento nao aplicável a esta estratégia.")

                    # --- TAB HISTORICO ---
                with detail_tabs[7]:
                    history = api_get(f"/api/v1/deals/{selected_deal_id}/history")
                    if history:
                        for h in history:
                            from_s = h.get("from_status") or "inicio"
                            to_s = h.get("to_status", "")
                            reason = h.get("reason", "")
                            date = h.get("created_at", "")[:19] if h.get("created_at") else ""
                            st.markdown(
                                f'**{from_s}** \u2192 **{to_s}** '
                                f'| {reason} | {date}'
                            )
                    else:
                        st.info("Sem histórico.")
        else:
            st.info("Sem deals criados.")

    # ====== TAB CRIAR DEAL ======
    with tab_create:
        st.subheader("Criar novo deal")

        # === 1. Escolher papel ===
        role = st.radio(
            "Qual é o seu papel neste negócio?",
            ["Investidor — Compro para mim", "Mediador — Represento cliente"],
            key="create_role",
        )
        is_mediator = role.startswith("Mediador")

        # === 2. Estrategia filtrada pelo papel ===
        role_filter = "mediador" if is_mediator else "investidor"
        filtered_strategies = [s for s in strategies if s.get("role", "investidor") == role_filter]
        strategy_labels = {
            s["key"]: f'{s.get("icon", "")} {s["label"]} — {s.get("description", "")}'
            for s in filtered_strategies
        }
        selected_strategy_key = st.selectbox(
            "Estratégia",
            list(strategy_labels.keys()),
            format_func=lambda k: strategy_labels[k],
            key="create_strategy",
        )

        # === 3. Propriedade ===
        if not is_mediator:
            create_method = st.radio("Origem", ["Manual", "De oportunidade M1"], key="create_method")
        else:
            create_method = "Manual"

        props = api_get("/api/v1/properties/", params={"limit": 100})
        prop_id = None
        if create_method == "Manual":
            if props and props.get("items"):
                prop_options = {
                f'{p.get("municipality", "?")} — {p.get("typology", "?")} ({fmt_eur(p.get("asking_price"))})': p["id"]
                for p in props["items"]
                }
                selected_prop = st.selectbox("Propriedade", list(prop_options.keys()), key="create_prop")
                prop_id = prop_options[selected_prop]
            else:
                st.warning("Sem propriedades. Cria uma primeiro em /api/v1/properties.")

        # === 4. Campos comuns ===
        d_title = st.text_input("Título do deal", key="create_title")

        # === 5. Campos especificos por papel ===
        if is_mediator:
            st.markdown("---")
            st.markdown("**Dados do proprietário**")
            mc1, mc2 = st.columns(2)
            with mc1:
                d_owner_name = st.text_input("Nome do proprietário", key="create_owner_name")
                d_owner_phone = st.text_input("Telefone do proprietário", key="create_owner_phone")
            with mc2:
                d_owner_email = st.text_input("Email do proprietário", key="create_owner_email")
                d_contract_type = st.selectbox(
                "Tipo de contrato (CMI)",
                ["exclusivo", "aberto", "partilha"],
                key="create_contract_type",
                )

            st.markdown("**Comissão**")
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                d_commission_pct = st.number_input("Comissão %", value=5.0, step=0.5, key="create_comm_pct")
            with cc2:
                d_sale_price = st.number_input("Preço de venda (EUR)", min_value=0.0, step=1000.0, key="create_sale_price")
            with cc3:
                d_commission_vat = st.checkbox("IVA incluído na comissão?", key="create_comm_vat")

            d_shared = st.checkbox("Partilha com outro mediador?", key="create_shared")
            d_split_pct = None
            d_split_agent = None
            if d_shared:
                sc1, sc2 = st.columns(2)
                with sc1:
                    d_split_pct = st.slider("A minha parte %", 10, 90, 50, key="create_split_pct")
                    with sc2:
                        d_split_agent = st.text_input("Nome do outro mediador", key="create_split_agent")

            d_notes = st.text_area("Notas", key="create_med_notes")

            if st.button("Criar deal de mediação", key="btn_create_med") and prop_id and d_title:
                body = {
                "property_id": prop_id,
                "investment_strategy": selected_strategy_key,
                "title": d_title,
                "owner_name": d_owner_name or None,
                "owner_phone": d_owner_phone or None,
                "owner_email": d_owner_email or None,
                "mediation_contract_type": d_contract_type,
                "commission_pct": d_commission_pct,
                "commission_vat_included": d_commission_vat,
                "target_sale_price": d_sale_price or None,
                "notes": d_notes or None,
                }
                if d_shared and d_split_pct:
                    body["commission_split_pct"] = float(d_split_pct)
                    body["commission_split_agent"] = d_split_agent
                    result = api_post("/api/v1/deals/mediation", body)
                    if result:
                        st.success(f'Deal de mediação criado: {result.get("title")}')
                        st.rerun()

        else:
            # === Investidor ===
            ic1, ic2 = st.columns(2)
            with ic1:
                d_purchase = st.number_input("Preço compra (EUR)", min_value=0.0, step=1000.0, key="create_purchase")
                d_sale = st.number_input("Preço venda alvo (EUR)", min_value=0.0, step=1000.0, key="create_sale")
            with ic2:
                d_rent = st.number_input("Renda mensal (EUR)", min_value=0.0, step=100.0, key="create_rent")
                d_reno = st.number_input("Orçamento obra (EUR)", min_value=0.0, step=1000.0, key="create_reno")

            if create_method == "Manual":
                if st.button("Criar deal", key="btn_create_inv") and prop_id and d_title:
                    result = api_post(
                        "/api/v1/deals/",
                        {
                            "property_id": prop_id,
                            "investment_strategy": selected_strategy_key,
                            "title": d_title,
                            "purchase_price": d_purchase or None,
                            "target_sale_price": d_sale or None,
                            "monthly_rent": d_rent or None,
                            "renovation_budget": d_reno or None,
                        },
                    )
                    if result:
                        st.success(f'Deal criado: {result.get("title")}')
                        st.rerun()
            else:
                # De oportunidade M1
                opps = api_get("/api/v1/ingest/opportunities", params={"limit": 50})
                if opps and opps.get("items"):
                    opp_options = {
                        f'#{o["id"]} {o.get("municipality", "?")} — {o.get("property_type", "?")} ({fmt_eur(o.get("price_mentioned"))})': o["id"]
                        for o in opps["items"]
                        if o.get("is_opportunity")
                    }
                    if opp_options:
                        selected_opp = st.selectbox(
                            "Oportunidade", list(opp_options.keys()), key="create_opp"
                        )
                        opp_id = opp_options[selected_opp]

                        if st.button("Criar deal a partir de oportunidade", key="btn_create_opp"):
                            result = api_post(
                                f"/api/v1/deals/from-opportunity/{opp_id}",
                                {"investment_strategy": selected_strategy_key},
                            )
                            if result:
                                st.success(f'Deal criado: {result.get("title")}')
                                st.rerun()
                    else:
                        st.info("Sem oportunidades classificadas.")
                else:
                    st.info("Sem oportunidades disponíveis.")

    # ====== TAB PORTFOLIO ======
    with tab_portfolio:
        st.subheader("Portfolio de investimento")

        if stats.get("by_strategy"):
            st.markdown("**Distribuição por estratégia:**")
            for strat_key, count in stats["by_strategy"].items():
                s_info = next(
                (s for s in strategies if s["key"] == strat_key), {}
                )
                icon = s_info.get("icon", "")
                label = s_info.get("label", strat_key)
                st.markdown(f'{icon} **{label}:** {count} deal(s)')

        if stats.get("by_status"):
            st.divider()
            st.markdown("**Valor por estado:**")
            for s_key, s_data in stats["by_status"].items():
                s_cfg = next(
                (s for s in statuses if s["key"] == s_key), {}
                )
                label = s_cfg.get("label", s_key)
                icon = s_cfg.get("icon", "")
                st.markdown(
                f'{icon} **{label}:** {s_data["count"]} deal(s) — '
                f'{fmt_eur(s_data["value"])}'
                )

    # ====== TAB MEDIACAO ======
    with tab_mediacao:
        st.subheader("Carteira de Mediação")

        med_stats = api_get("/api/v1/deals/stats/mediation")
        if med_stats:
            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                st.metric("Angariação activas", med_stats.get("active_mediations", 0))
            with mc2:
                st.metric("Valor em carteira", fmt_eur(med_stats.get("total_portfolio_value")))
            with mc3:
                st.metric("Comissão potencial", fmt_eur(med_stats.get("potential_commission")))
            with mc4:
                st.metric("Taxa conversão", fmt_pct(med_stats.get("conversion_rate_pct")))

            st.divider()

        # Kanban filtrado por mediacao
        med_kanban = api_get("/api/v1/deals/kanban", params={"strategy": "mediacao_venda"})
        if med_kanban and med_kanban.get("columns"):
            st.markdown("**Pipeline de mediacao venda:**")
            columns = med_kanban["columns"]
            status_cfg = med_kanban.get("status_config", {})
            col_keys = list(columns.keys())
            max_vis = min(len(col_keys), 6)
            cols = st.columns(max_vis)
            for i, status_key in enumerate(col_keys[:max_vis]):
                deals_in_col = columns[status_key]
                cfg = status_cfg.get(status_key, {})
                color = cfg.get("color", "#94A3B8")
                label = cfg.get("label", status_key)
                icon = cfg.get("icon", "")
                with cols[i]:
                    st.markdown(
                        f'<div style="text-align:center;padding:8px;'
                    f'background:{color}15;border-radius:8px;'
                    f'border-bottom:3px solid {color};margin-bottom:10px;">'
                    f'<b>{icon} {label}</b><br>'
                    f'<small style="color:#64748B;">{len(deals_in_col)} deal(s)</small></div>',
                    unsafe_allow_html=True,
                )
                for deal in deals_in_col:
                    price = deal.get("target_sale_price") or deal.get("purchase_price")
                    days = deal.get("days_in_status", 0)
                    border_color = "#DC2626" if days > 14 else "#D97706" if days > 7 else "#E2E8F0"
                    st.markdown(
                        f'<div style="border:1px solid {border_color};border-left:4px solid {color};'
                        f'border-radius:10px;padding:12px 14px;margin-bottom:8px;">'
                        f'<b>{deal.get("strategy_icon", "")} '
                        f'{deal.get("title", "")}</b><br>'
                        f'<small style="color:#64748B;">{fmt_eur(price) if price else ""}</small>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.divider()

        # Calculadora de comissão
        st.subheader("Calculadora de Comissão")
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            calc_price = st.number_input("Preço de venda (EUR)", value=295000.0, step=1000.0, key="calc_price")
        with cc2:
            calc_pct = st.number_input("Comissão %", value=5.0, step=0.5, key="calc_pct")
        with cc3:
            calc_shared = st.checkbox("Partilha com outro mediador?", key="calc_shared")

        calc_share = 50.0
        if calc_shared:
            calc_share = st.slider("A minha parte %", 0, 100, 50, key="calc_share_slider")

        gross = calc_price * calc_pct / 100
        vat = gross * 0.23
        total = gross + vat
        my_part = total * calc_share / 100 if calc_shared else total

        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            st.metric("Comissão bruta", fmt_eur(gross))
        with rc2:
            st.metric("Com IVA (23%)", fmt_eur(total))
        with rc3:
            if calc_shared:
                st.metric("A minha parte", fmt_eur(my_part))
            else:
                st.metric("Total (sem partilha)", fmt_eur(total))

        st.divider()

        # Registar visita
        st.subheader("Registar Visita")
        deals_list_med = api_get("/api/v1/deals/", params={"strategy": "mediacao_venda", "limit": 50})
        med_deals = (deals_list_med or {}).get("items", [])
        if med_deals:
            med_deal_options = {
                f'{d["strategy_icon"]} {d["title"]}': d["id"] for d in med_deals
            }
            selected_med_deal = st.selectbox(
                "Deal de mediação", list(med_deal_options.keys()), key="visit_deal"
            )
            sel_deal_id = med_deal_options[selected_med_deal]

            # Listar visitas existentes
            visits = api_get(f"/api/v1/deals/{sel_deal_id}/visits")
            if visits:
                st.markdown(f"**{len(visits)} visita(s) registada(s):**")
                for v in visits:
                    interest = v.get("interest_level", "?")
                interest_color = {
                    "baixo": "#9CA3AF", "médio": "#F59E0B",
                    "alto": "#22C55E", "muito_alto": "#10B981",
                }.get(interest, "#666")
                st.markdown(
                    f'**{v["visitor_name"]}** — {v.get("visit_date", "")[:10]} '
                    f'<span style="color:{interest_color};">[{interest}]</span> '
                    f'{v.get("feedback", "")}',
                    unsafe_allow_html=True,
                )

            with st.expander("Nova visita"):
                import datetime as dt_mod
                v_name = st.text_input("Nome do visitante", key="v_name")
                v_phone = st.text_input("Telefone", key="v_phone")
                v_date = st.date_input("Data", value=dt_mod.date.today(), key="v_date")
                v_type = st.selectbox("Tipo", ["presencial", "virtual", "open_house"], key="v_type")
                if st.button("Registar visita") and v_name:
                    api_post(
                    f"/api/v1/deals/{sel_deal_id}/visits",
                    {
                        "visitor_name": v_name,
                        "visitor_phone": v_phone or None,
                        "visit_date": f"{v_date}T10:00:00",
                        "visit_type": v_type,
                    },
                    )
                    st.success("Visita registada!")
                    st.rerun()
        else:
            st.info("Sem deals de mediação. Crie um na tab 'Criar Deal'.")


# ===================================================================
# M5 — DUE DILIGENCE
# ===================================================================

elif module == "M5 — Due Diligence":
    st.header("M5 — Due Diligence")

    deals_data = api_get("/api/v1/deals", params={"limit": 50})
    deals = deals_data.get("items", []) if deals_data else []
    active_deals = [d for d in deals if d.get("status") not in ("descartado", "fechado")]

    if not active_deals:
        st.markdown(
            '<div style="text-align:center;padding:40px 20px;color:#94A3B8;">'
            '<h3 style="color:#475569;">Sem deals activos</h3>'
            '<p>Cria um deal no M4 — Deal Pipeline para iniciar due diligence.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"{len(active_deals)} deals activos com due diligence.")
        for deal in active_deals[:20]:
            did = deal.get("id", "")
            title = deal.get("title", "Sem título")
            status = deal.get("status", "?")
            dd_items = api_get(f"/api/v1/due-diligence/deals/{did}/items", silent_404=True)
            items = dd_items if isinstance(dd_items, list) else (dd_items.get("items", []) if dd_items else [])
            total = len(items)
            done = sum(1 for i in items if i.get("status") == "verificado")
            red_flags = sum(1 for i in items if i.get("red_flag"))
            pct = int(done / total * 100) if total > 0 else 0
            flag_str = f" | \U0001f6a9 {red_flags} red flags" if red_flags else ""
            with st.expander(f"{title} ({status}) — {done}/{total} verificados ({pct}%){flag_str}"):
                if not items:
                    if st.button("Gerar checklist", key=f"m5_gen_{did}"):
                        result = api_post(f"/api/v1/due-diligence/deals/{did}/generate")
                        if result:
                            st.success("Checklist gerado!")
                            st.rerun()
                else:
                    for item in items:
                        iname = item.get("item_name", "?")
                        istatus = item.get("status", "pendente")
                        cat = item.get("category", "")
                        flag = "\U0001f6a9 " if item.get("red_flag") else ""
                        icon = "\u2705" if istatus == "verificado" else "\u23f3" if istatus == "pendente" else "\u274c"
                        st.markdown(f"{icon} {flag}**{iname}** ({cat}) — {istatus}")


# ===================================================================
# M6 — GESTÃO DE OBRA
# ===================================================================

elif module == "M6 — Obra":
    st.header("M6 — Gestão de Obra")

    with st.spinner("A carregar obras..."):
        deals_data = api_get("/api/v1/deals", params={"limit": 50})
        deals = deals_data.get("items", []) if deals_data else []
        renovations = []
        for deal in deals[:20]:
            did = deal.get("id", "")
            ren = api_get(f"/api/v1/renovations/deals/{did}", silent_404=True)
            if ren and not isinstance(ren, list):
                ren["deal_title"] = deal.get("title", "?")
                renovations.append(ren)
            elif isinstance(ren, list):
                for r in ren:
                    r["deal_title"] = deal.get("title", "?")
                    renovations.append(r)

    if not renovations:
        st.markdown(
            '<div style="text-align:center;padding:40px 20px;color:#94A3B8;">'
            '<h3 style="color:#475569;">Sem obras activas</h3>'
            '<p>Crie uma renovacao a partir do detalhe de um deal no M4.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        total_budget = sum(r.get("initial_budget", 0) for r in renovations)
        total_spent = sum(r.get("total_spent", 0) for r in renovations)
        avg_progress = sum(r.get("progress_pct", 0) for r in renovations) / len(renovations)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Obras activas", len(renovations))
        k2.metric("Orçamento total", fmt_eur(total_budget))
        k3.metric("Total gasto", fmt_eur(total_spent))
        k4.metric("Progresso médio", f"{avg_progress:.0f}%")
        st.divider()
        for ren in renovations:
            title = ren.get("deal_title", "?")
            budget = ren.get("initial_budget", 0)
            spent = ren.get("total_spent", 0)
            progress = ren.get("progress_pct", 0)
            status = ren.get("status", "?")
            variance = ren.get("budget_variance_pct", 0)
            var_str = f" | Desvio: {variance:+.1f}%" if variance != 0 else ""
            with st.expander(f"{title} — {status} | {progress:.0f}% | {fmt_eur(spent)} / {fmt_eur(budget)}{var_str}"):
                st.progress(min(progress / 100, 1.0))
                contractor = ren.get("contractor_name")
                if contractor:
                    st.markdown(f"**Empreiteiro:** {contractor}")
                scope = ren.get("scope_description")
                if scope:
                    st.markdown(f"**Âmbito:** {scope}")


# ===================================================================
# M7 — MARKETING
# ===================================================================

elif module == "M7 — Marketing":
    st.header("M7 — Marketing Engine")

    bk = api_get("/api/v1/marketing/brand-kit")
    has_brand_kit = bk and bk.get("brand_name")

    if has_brand_kit:
        tab_marca, tab_pub = st.tabs(["Marca", "Publicações"])
    else:
        tab_marca = st.container()
        tab_pub = None

    # ====== TAB MARCA ======
    with tab_marca:
        if not has_brand_kit:
            st.subheader("Configure a sua marca para começar")
            st.caption("O brand kit define cores, fontes e tom de voz para todo o conteúdo gerado.")

        # Brand Kit form (wizard se novo, edição se existente)
        show_form = not has_brand_kit
        if has_brand_kit:
            # Show current brand kit summary
            bc1, bc2 = st.columns([3, 1])
            with bc1:
                st.markdown(f'**{bk["brand_name"]}** — {bk.get("tagline", "")}')
                st.markdown(f'{bk.get("website_url", "")} | {bk.get("contact_phone", "")} | {bk.get("contact_email", "")}')
                st.markdown(
                f'Tom: {bk.get("voice_tone", "N/A")} | '
                f'Idiomas: {", ".join(bk.get("active_languages", []))} | '
                f'Fontes: {bk.get("font_heading", "?")} / {bk.get("font_body", "?")}',
                )
                for ck in ("color_primary", "color_secondary", "color_accent"):
                    cv = bk.get(ck, "#000")
                st.markdown(
                    f'<span style="display:inline-block;width:20px;height:20px;'
                    f'background:{cv};border-radius:3px;vertical-align:middle;'
                    f'margin-right:4px;border:1px solid #ddd;"></span>{ck.split("_")[-1]}: {cv} ',
                    unsafe_allow_html=True,
                )
            with bc2:
                if st.button("Editar marca", key="btn_edit_bk"):
                    st.session_state["show_bk_form"] = True

            # Logo uploads
            st.markdown("---")
            st.markdown("**Logos**")
            logo_cols = st.columns(3)
            for li, (logo_type, logo_label, logo_field) in enumerate([
                ("primary", "Logo principal", "logo_primary_url"),
                ("white", "Logo fundo escuro", "logo_white_url"),
                ("icon", "Favicon", "logo_icon_url"),
            ]):
                with logo_cols[li]:
                    current = bk.get(logo_field)
                if current:
                    st.caption(f"{logo_label}: ✅ configurado")
                    # Mostrar preview do logo (cache em session_state para evitar fetch a cada render)
                    cache_key = f"logo_cache_{logo_type}"
                    cached_url = st.session_state.get(cache_key)
                    full_url = f"{API_BASE}{current}" if current.startswith("/") else current
                    if cached_url != full_url:
                        st.session_state[cache_key] = full_url
                    try:
                        st.image(st.session_state[cache_key], use_container_width=True)
                    except Exception:
                        st.info(f"Preview indisponível ({logo_type})")
                else:
                    st.caption(f"{logo_label}: não configurado")
                logo_file = st.file_uploader(
                    logo_label,
                    type=["png", "svg", "jpg", "webp", "ico"],
                    key=f"logo_{logo_type}",
                )
                upload_flag = f"logo_uploaded_{logo_type}"
                if logo_file and not st.session_state.get(upload_flag):
                    st.session_state[upload_flag] = True
                    result = api_upload(
                        f"/api/v1/marketing/brand-kit/logo?logo_type={logo_type}",
                        logo_file.name,
                        logo_file.getvalue(),
                    )
                    if result:
                        st.success(f"{logo_label} carregado!")
                        # Limpar cache do logo para forcar reload
                        cache_key_clear = f"logo_cache_{logo_type}"
                        if cache_key_clear in st.session_state:
                            del st.session_state[cache_key_clear]
                        st.rerun()
                elif not logo_file:
                    # Reset flag quando file_uploader limpa
                    st.session_state.pop(upload_flag, None)

            show_form = st.session_state.get("show_bk_form", False)

        if show_form:
            with st.form("brand_kit_form"):
                st.markdown("**Identidade**")
                fc1, fc2 = st.columns(2)
                with fc1:
                    bk_name = st.text_input("Nome da marca *", value=bk.get("brand_name", "HABTA") if bk else "")
                bk_tagline = st.text_input("Tagline", value=bk.get("tagline", "") if bk else "")
                with fc2:
                    bk_website = st.text_input("Website", value=bk.get("website_url", "") if bk else "")

                st.markdown("**Cores**")
                cc1, cc2, cc3 = st.columns(3)
                with cc1:
                    bk_primary = st.color_picker("Primária", value=bk.get("color_primary", "#1E3A5F") if bk else "#1E3A5F")
                with cc2:
                    bk_secondary = st.color_picker("Secundária", value=bk.get("color_secondary", "#F4A261") if bk else "#F4A261")
                with cc3:
                    bk_accent = st.color_picker("Destaque", value=bk.get("color_accent", "#E76F51") if bk else "#E76F51")

                st.markdown("**Fontes**")
                ff1, ff2 = st.columns(2)
                fonts = ["Montserrat", "Inter", "Poppins", "Roboto", "Open Sans", "Lato", "Playfair Display", "Merriweather"]
                with ff1:
                    bk_font_h = st.selectbox("Heading", fonts, index=fonts.index(bk.get("font_heading", "Montserrat")) if bk and bk.get("font_heading") in fonts else 0)
                with ff2:
                    bk_font_b = st.selectbox("Body", fonts, index=fonts.index(bk.get("font_body", "Inter")) if bk and bk.get("font_body") in fonts else 1)

                st.markdown("**Tom de voz**")
                tones = ["profissional", "luxo", "casual", "tecnico"]
                bk_tone = st.selectbox("Tom", tones, index=tones.index(bk.get("voice_tone", "profissional")) if bk and bk.get("voice_tone") in tones else 0)
                bk_voice_desc = st.text_area("Descrição do tom", value=bk.get("voice_description", "") if bk else "", height=60)
                bk_forbidden = st.text_input("Palavras proibidas (separadas por virgula)", value=", ".join(bk.get("voice_forbidden_words", [])) if bk else "")

                st.markdown("**Contacto**")
                ct1, ct2, ct3 = st.columns(3)
                with ct1:
                    bk_phone = st.text_input("Telefone", value=bk.get("contact_phone", "") if bk else "")
                with ct2:
                    bk_email_c = st.text_input("Email", value=bk.get("contact_email", "") if bk else "")
                with ct3:
                    bk_whatsapp = st.text_input("WhatsApp", value=bk.get("contact_whatsapp", "") if bk else "")

                st.markdown("**Idiomas activos**")
                all_langs = {"pt-PT": "Português (PT)", "pt-BR": "Português (BR)", "en": "English", "fr": "Français", "zh": "Zhongwen"}
                active = bk.get("active_languages", ["pt-PT"]) if bk else ["pt-PT"]
                selected_langs = []
                lang_cols = st.columns(5)
                for i, (lk, lv) in enumerate(all_langs.items()):
                    with lang_cols[i]:
                        if st.checkbox(lv, value=lk in active, key=f"lang_{lk}"):
                            selected_langs.append(lk)

                submitted = st.form_submit_button("Guardar Brand Kit" if has_brand_kit else "Guardar e começar")
                if submitted and bk_name:
                    forbidden_list = [w.strip() for w in bk_forbidden.split(",") if w.strip()] if bk_forbidden else []
                api_post("/api/v1/marketing/brand-kit", {
                    "brand_name": bk_name, "tagline": bk_tagline,
                    "website_url": bk_website,
                    "color_primary": bk_primary, "color_secondary": bk_secondary,
                    "color_accent": bk_accent,
                    "font_heading": bk_font_h, "font_body": bk_font_b,
                    "voice_tone": bk_tone, "voice_description": bk_voice_desc,
                    "voice_forbidden_words": forbidden_list,
                    "contact_phone": bk_phone, "contact_email": bk_email_c,
                    "contact_whatsapp": bk_whatsapp,
                    "active_languages": selected_langs or ["pt-PT"],
                })
                st.session_state["show_bk_form"] = False
                st.success("Brand Kit guardado!")
                st.rerun()

    # ====== TAB PUBLICACOES ======
    if tab_pub is not None:
      with tab_pub:
        mkt_stats = api_get("/api/v1/marketing/stats")
        if mkt_stats:
            mk1, mk2, mk3, mk4, mk5 = st.columns(5)
            with mk1:
                st.metric("Publicações", mkt_stats.get("active_listings", 0))
            with mk2:
                st.metric("Valor total", fmt_eur(mkt_stats.get("total_value")))
            with mk3:
                st.metric("Views", mkt_stats.get("total_views", 0))
            with mk4:
                st.metric("Contactos", mkt_stats.get("total_contacts", 0))
            with mk5:
                st.metric("DOM médio", f'{mkt_stats.get("avg_days_on_market", 0):.0f}d')

        st.divider()

        # Listings
        listings_data = api_get("/api/v1/marketing/listings", params={"limit": 100})
        items = listings_data.get("items", []) if listings_data else []

        if not items:
            st.info("Sem publicações. As publicações são criadas automaticamente quando um deal avança para 'Em Venda'.")
        else:
            for listing in items:
                title = listing.get("title_pt") or listing.get("notes") or "Publicação"
                price = listing.get("listing_price", 0)
                status = listing.get("status", "?")
                lid = listing["id"]

                with st.expander(f'{title} — {fmt_eur(price)} | {status}'):
                # Header
                    hc1, hc2 = st.columns(2)
                with hc1:
                    st.markdown(f'**Tipo:** {listing.get("listing_type", "N/A")}')
                    st.markdown(f'**Preço:** {fmt_eur(price)}')
                    st.markdown(f'**Status:** {status}')
                    if listing.get("slug"):
                        st.markdown(f'**Slug:** `{listing["slug"]}`')
                with hc2:
                    if listing.get("short_description_pt"):
                        st.caption(listing["short_description_pt"])
                    if listing.get("highlights"):
                        for h in listing["highlights"][:6]:
                            st.markdown(f'- {h}')

                # Sub-tabs
                st1, st_media, st2, st3, st4 = st.tabs(
                    ["Conteúdo", "Media", "Criativos", "Vídeos", "Redes Sociais"]
                )

                # == CONTEUDO ==
                with st1:
                    # Website
                    st.markdown("**Website**")
                    if listing.get("title_pt"):
                        st.text_input("Título", value=listing["title_pt"], key=f'tit_{lid}', disabled=True)
                    if listing.get("description_pt"):
                        st.text_area("Descrição", value=listing["description_pt"], height=100, key=f'desc_{lid}')

                    # WhatsApp (copyable)
                    wa = listing.get("content_whatsapp")
                    if wa:
                        st.markdown("---")
                        st.markdown("**WhatsApp** (copiar e colar)")
                        st.code(wa, language=None)

                    # Instagram
                    ig = listing.get("content_instagram_post")
                    if ig:
                        st.markdown("---")
                        st.markdown("**Instagram** (copiar caption)")
                        st.code(ig, language=None)

                    # Facebook
                    fb = listing.get("content_facebook_post")
                    if fb:
                        st.markdown("---")
                        st.markdown("**Facebook** (copiar post)")
                        st.code(fb, language=None)

                    # LinkedIn
                    li = listing.get("content_linkedin")
                    if li:
                        st.markdown("---")
                        st.markdown("**LinkedIn** (copiar post)")
                        st.code(li, language=None)

                    # Portal
                    portal = listing.get("content_portal")
                    if portal:
                        st.markdown("---")
                        st.markdown("**Portal (Idealista)** (copiar)")
                        st.code(portal, language=None)

                    # Email
                    subj = listing.get("content_email_subject")
                    if subj:
                        st.markdown("---")
                        st.markdown(f'**Email** Subject: `{subj}`')

                    # SEO
                    if listing.get("meta_title") or listing.get("meta_description"):
                        st.markdown("---")
                        st.markdown("**SEO**")
                        if listing.get("meta_title"):
                            st.markdown(f'Title: `{listing["meta_title"]}`')
                        if listing.get("meta_description"):
                            st.caption(listing["meta_description"])

                # == MEDIA (fotos do imóvel) ==
                with st_media:
                    st.markdown("**Fotos do imóvel**")
                    # Show existing photos
                    existing_photos = listing.get("photos") or []
                    if existing_photos:
                        st.caption(f"{len(existing_photos)} foto(s)")
                        for row_start in range(0, len(existing_photos), 4):
                            row_photos = existing_photos[row_start:row_start + 4]
                            cols = st.columns(4)
                            for ci, photo in enumerate(row_photos):
                                pi = row_start + ci
                                with cols[ci]:
                                    photo_url = photo.get("url") or ""
                                    if photo_url.startswith("/api"):
                                        full_url = f"{API_BASE}{photo_url}"
                                    elif photo_url.startswith("http"):
                                        full_url = photo_url
                                    else:
                                        full_url = ""
                                    if full_url:
                                        try:
                                            import httpx as hx
                                            resp = hx.get(full_url, timeout=5.0, follow_redirects=True)
                                            if resp.status_code == 200 and len(resp.content) > 100:
                                                st.image(resp.content, width=150)
                                        except Exception:
                                            st.caption(f"Foto {pi+1}")
                                    is_cover = photo.get("is_cover", False)
                                    bc1, bc2 = st.columns(2)
                                    with bc1:
                                        if is_cover:
                                            st.caption("⭐ Capa")
                                        else:
                                            if st.button("⭐", key=f"cover_{lid}_{pi}", help="Definir como capa"):
                                                updated = []
                                                for j, p in enumerate(existing_photos):
                                                    p2 = dict(p)
                                                    p2["is_cover"] = j == pi
                                                    updated.append(p2)
                                                new_cover = photo_url if photo_url.startswith("/api") else photo_url
                                                api_patch(f"/api/v1/marketing/listings/{lid}", {
                                                    "photos": updated,
                                                    "cover_photo_url": new_cover,
                                                })
                                                st.rerun()
                                    with bc2:
                                        if st.button("✕", key=f"rm_{lid}_{pi}", help="Remover"):
                                            new_photos = [p for j, p in enumerate(existing_photos) if j != pi]
                                            api_patch(f"/api/v1/marketing/listings/{lid}", {"photos": new_photos})
                                            st.rerun()
                        if st.button("Remover todas", key=f"rm_all_{lid}"):
                            api_patch(f"/api/v1/marketing/listings/{lid}", {"photos": [], "cover_photo_url": None})
                            st.rerun()
                    else:
                        st.info("Sem fotos. Faça upload abaixo.")

                    # Upload — usar botão explícito para evitar rerun loops
                    uploaded_files = st.file_uploader(
                        "Seleccionar fotos",
                        type=["jpg", "jpeg", "png", "webp"],
                        accept_multiple_files=True,
                        key=f"photo_upload_{lid}",
                    )
                    if uploaded_files:
                        st.caption(f"{len(uploaded_files)} ficheiro(s) seleccionado(s)")
                        if st.button(f"Carregar {len(uploaded_files)} foto(s)", key=f"btn_upload_{lid}"):
                            import httpx as hx
                            files_data = [
                                ("files", (f.name, f.getvalue(), f.type or "image/jpeg"))
                                for f in uploaded_files
                            ]
                            try:
                                with hx.Client(timeout=30.0) as client:
                                    resp = client.post(
                                        f"{API_BASE}/api/v1/marketing/listings/{lid}/photos",
                                        files=files_data,
                                    )
                                    if resp.status_code == 200:
                                        result = resp.json()
                                        st.success(f'{result.get("uploaded", 0)} foto(s) carregada(s)')
                                        st.rerun()
                                    else:
                                        st.error(f"Erro: {resp.status_code}")
                            except Exception as e:
                                st.error(f"Erro no upload: {e}")

                    # Cover photo URL
                    if listing.get("cover_photo_url"):
                        st.markdown(f'**Foto de capa:** `{listing["cover_photo_url"]}`')

                # == CRIATIVOS ==
                with st2:
                    creatives = api_get(f'/api/v1/marketing/listings/{lid}/creatives')
                    if creatives:
                        rc1, rc2 = st.columns([3, 1])
                        with rc1:
                            st.markdown(f'**{len(creatives)} peças:**')
                        with rc2:
                            regen_key = f"regen_cr_done_{lid}"
                            if st.session_state.get(regen_key):
                                st.success("Criativos regenerados!")
                                st.session_state[regen_key] = False
                            elif st.button("Regenerar criativos", key=f"regen_cr_{lid}"):
                                with st.spinner("A regenerar criativos…"):
                                    for c in creatives:
                                        api_delete(f'/api/v1/marketing/creatives/{c["id"]}')
                                    api_post(f'/api/v1/marketing/listings/{lid}/creatives/generate-all')
                                st.session_state[regen_key] = True
                                st.rerun()
                        for c in creatives:
                            ctype = c.get("creative_type", "?")
                            cfmt = c.get("format", "?")
                            cw = c.get("width", "?")
                            ch_val = c.get("height", "?")
                            doc_id = c.get("document_id")

                            st.markdown(f'**{ctype}** ({cw}x{ch_val} {cfmt})')

                            if doc_id:
                                dl_url = f'{API_BASE}/api/v1/documents/{doc_id}/download'
                                if cfmt in ("png", "jpg", "jpeg"):
                                    try:
                                        import httpx as hx
                                        with hx.Client(timeout=5.0) as cl:
                                            resp = cl.get(dl_url)
                                            if resp.status_code == 200:
                                                st.image(resp.content, width=300)
                                    except Exception:
                                        st.markdown(f'[Ver imagem]({dl_url})')
                                st.markdown(f'[Download]({dl_url})')
                            else:
                                st.caption("Ficheiro não disponível")
                            st.markdown("---")
                    else:
                        st.info("Sem criativos.")
                        gen_key = f"gen_cr_done_{lid}"
                        if st.session_state.get(gen_key):
                            st.success("Criativos gerados!")
                            st.session_state[gen_key] = False
                        elif st.button("Gerar criativos", key=f'gen_cr_{lid}'):
                            with st.spinner("A gerar criativos…"):
                                api_post(f'/api/v1/marketing/listings/{lid}/creatives/generate-all')
                            st.session_state[gen_key] = True
                            st.rerun()

                # == VIDEOS ==
                with st3:
                    videos = api_get(f'/api/v1/marketing/listings/{lid}/videos')
                    if videos:
                        for v in videos:
                            vicon = {"pending": "\u23f3", "completed": "\u2705", "failed": "\u274c"}.get(v.get("status"), "\u2753")
                            st.markdown(
                                f'{vicon} **{v.get("video_type")}** '
                                f'({v.get("width")}x{v.get("height")}) '
                                f'| {v.get("duration_seconds", "?")}s | {v.get("status")}'
                            )
                    else:
                        st.info("Sem videos.")
                        if st.button("Gerar videos", key=f'gen_vid_{lid}'):
                            api_post(f'/api/v1/marketing/listings/{lid}/videos/generate-all')
                            st.rerun()

                # == REDES SOCIAIS ==
                with st4:
                    posts = api_get(f'/api/v1/marketing/listings/{lid}/social')
                    if posts:
                        for p in posts:
                            picon = {"instagram_post": "\U0001f4f7", "facebook_post": "\U0001f4d8", "linkedin_post": "\U0001f4bc"}.get(p.get("platform"), "\U0001f4f1")
                            cap = (p.get("caption") or "")[:100]
                            st.markdown(f'{picon} **{p.get("platform")}** | {p.get("status")}')
                            if cap:
                                st.caption(cap + ("..." if len(p.get("caption", "")) > 100 else ""))
                    else:
                        st.info("Sem posts.")
                        if st.button("Criar posts", key=f'gen_soc_{lid}'):
                            api_post(f'/api/v1/marketing/listings/{lid}/social/create-all')
                            st.rerun()

        # Manual create button (discrete)
        with st.expander("Criar publicação manualmente"):
            deals_all = api_get("/api/v1/deals/", params={"limit": 100})
            if deals_all and deals_all.get("items"):
                deal_opts = {f'{d["title"][:50]} ({d["status"]})': d["id"] for d in deals_all["items"]}
                sel_deal = st.selectbox("Deal", list(deal_opts.keys()), key="mkt_deal")
                sel_deal_id = deal_opts[sel_deal]
                lt = st.selectbox("Tipo", ["venda", "arrendamento"], key="mkt_lt")
                lp = st.number_input("Preço (EUR)", min_value=0.0, step=1000.0, key="mkt_lp")
                lt_title = st.text_input("Título", key="mkt_title")
                if st.button("Criar", key="btn_mkt_create") and lp > 0:
                    result = api_post(f"/api/v1/marketing/deals/{sel_deal_id}/listing", {"listing_type": lt, "listing_price": lp, "auto_generate": False})
                if result and lt_title:
                    api_patch(f'/api/v1/marketing/listings/{result["id"]}', {"title_pt": lt_title})
                if result:
                    st.success("Publicação criada!")
                    st.rerun()


# ===================================================================
# M8 — LEADS CRM
# ===================================================================

elif module == "M8 — Leads CRM":
    st.header("M8 — CRM de Leads")
    st.caption("Gestao do pipeline de compradores e inquilinos")

    STAGE_LABELS = {
        "new": "Novo", "contacted": "Contactado", "qualified": "Qualificado",
        "visit": "Visita", "visiting": "Visita", "proposal": "Proposta",
        "negotiation": "Negociacao", "closed_won": "Ganho", "won": "Ganho",
        "closed_lost": "Perdido", "lost": "Perdido",
    }
    STAGE_COLORS = {
        "new": "#94A3B8", "contacted": "#2563EB", "qualified": "#7C3AED",
        "visit": "#D97706", "visiting": "#D97706", "proposal": "#0F766E",
        "negotiation": "#14B8A6", "closed_won": "#16A34A", "won": "#16A34A",
        "closed_lost": "#DC2626", "lost": "#DC2626",
    }
    GRADE_COLORS = {"A": "#16A34A", "B": "#14B8A6", "C": "#D97706", "D": "#94A3B8", "F": "#DC2626"}

    # --- Metricas ---
    stats = api_get("/api/v1/leads/stats")
    if stats:
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Total Leads", stats.get("total_leads", 0))
        mc2.metric("Este Mes", stats.get("leads_this_month", 0))
        mc3.metric("Score Medio", f'{stats.get("avg_score", 0):.0f}')
        mc4.metric("Taxa Conversao", f'{stats.get("conversion_rate", 0):.0f}%')

    st.divider()

    # --- Pipeline Kanban ---
    st.subheader("Pipeline")
    pipeline = api_get("/api/v1/leads/pipeline-summary")
    if pipeline:
        cols = st.columns(len(pipeline))
        for i, stage_data in enumerate(pipeline):
            stage = stage_data.get("stage", "?")
            count = stage_data.get("count", 0)
            label = STAGE_LABELS.get(stage, stage)
            color = STAGE_COLORS.get(stage, "#94A3B8")
            with cols[i]:
                st.markdown(
                f"""<div style="background:{color}15; border:2px solid {color};
                border-radius:8px; padding:8px; text-align:center; min-height:70px;">
                <p style="font-size:0.7rem; font-weight:600; color:{color};
                margin:0; text-transform:uppercase;">{label}</p>
                <p style="font-size:1.4rem; font-weight:700; color:{color}; margin:4px 0;">{count}</p>
                </div>""",
                unsafe_allow_html=True,
                )

    st.divider()

    # --- Graficos ---
    gcol1, gcol2 = st.columns(2)
    with gcol1:
        st.subheader("Leads por Source")
        breakdown = api_get("/api/v1/leads/source-breakdown")
        if breakdown and any(b.get("count", 0) > 0 for b in breakdown):
            import plotly.express as px
            df_src = {b["source"]: b["count"] for b in breakdown if b.get("count", 0) > 0}
            fig = go.Figure(data=[go.Pie(
                labels=list(df_src.keys()),
                values=list(df_src.values()),
                hole=0.4,
                marker_colors=["#14B8A6", "#0369A1", "#7C3AED", "#D97706", "#16A34A", "#DC2626"],
            )])
            apply_chart_theme(fig, height=250)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de source")

    with gcol2:
        st.subheader("Distribuicao por Grade")
        grades = api_get("/api/v1/leads/grades-summary")
        if grades and isinstance(grades, dict) and any(v > 0 for v in grades.values()):
            grade_labels = list(grades.keys())
            grade_counts = list(grades.values())
            grade_colors = [GRADE_COLORS.get(g, "#94A3B8") for g in grade_labels]
            fig = go.Figure(data=[go.Bar(
                x=grade_labels, y=grade_counts,
                marker_color=grade_colors,
            )])
            apply_chart_theme(fig, height=250)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de grades")

    st.divider()

    # --- Criar Lead ---
    with st.expander("Criar Novo Lead"):
        with st.form("m8_create_lead"):
            cc1, cc2 = st.columns(2)
            with cc1:
                lead_name = st.text_input("Nome *", key="m8_name")
                lead_email = st.text_input("Email", key="m8_email")
                lead_phone = st.text_input("Phone (+351...)", key="m8_phone")
                lead_source = st.selectbox("Source", ["habta.eu", "whatsapp", "idealista", "referral", "instagram", "direct"], key="m8_src")
            with cc2:
                lead_bmin = st.number_input("Budget Min (€)", min_value=0, step=10000, key="m8_bmin")
                lead_bmax = st.number_input("Budget Max (€)", min_value=0, step=10000, key="m8_bmax")
                lead_typology = st.selectbox("Tipologia", ["", "T0", "T1", "T2", "T3", "T4", "T5+"], key="m8_typ")
                lead_timeline = st.selectbox("Timeline", ["", "imediato", "1-3 meses", "3-6 meses", "6+ meses"], key="m8_tl")

            lead_financing = st.selectbox("Financiamento", ["unknown", "cash", "pre_approved", "needs_approval"], key="m8_fin")
            lead_notes = st.text_area("Notas", key="m8_notes")

            if st.form_submit_button("Criar Lead"):
                if not lead_name:
                    st.error("Nome e obrigatorio")
                else:
                    body: Dict[str, Any] = {"name": lead_name, "source": lead_source}
                if lead_email:
                    body["email"] = lead_email
                if lead_phone:
                    body["phone"] = lead_phone
                if lead_bmin > 0:
                    body["budget_min"] = float(lead_bmin)
                if lead_bmax > 0:
                    body["budget_max"] = float(lead_bmax)
                if lead_typology:
                    body["preferred_typology"] = lead_typology
                if lead_timeline:
                    body["timeline"] = lead_timeline
                if lead_financing != "unknown":
                    body["financing"] = lead_financing
                if lead_notes:
                    body["notes"] = lead_notes

                result = api_post("/api/v1/leads/", body)
                if result:
                    st.success(f"Lead criado: {result.get('name')} (Score: {result.get('score', 0)}, Grade: {result.get('grade', '?')})")
                    st.rerun()

    # --- Sincronizar habta.eu ---
    sc1, sc2 = st.columns([1, 3])
    with sc1:
        if st.button("Sincronizar habta.eu", type="primary", key="m8_sync"):
            with st.spinner("A sincronizar..."):
                sync_result = api_post("/api/v1/leads/sync-habta")
            if sync_result:
                st.success(
                f"Importados: {sync_result.get('imported', 0)} | "
                f"Actualizados: {sync_result.get('updated', 0)} | "
                f"Erros: {sync_result.get('errors', 0)}"
                )
    with sc2:
        st.caption("Importa/actualiza leads da tabela contacts do habta.eu")

    st.divider()

    # --- Tabela de Leads ---
    st.subheader("Leads")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        f_stage = st.selectbox("Filtrar Stage", ["Todos"] + list(set(STAGE_LABELS.values())), key="m8_fstage")
    with fc2:
        f_grade = st.selectbox("Filtrar Grade", ["Todos", "A", "B", "C", "D", "F"], key="m8_fgrade")
    with fc3:
        f_source = st.text_input("Filtrar Source", key="m8_fsource")
    with fc4:
        f_search = st.text_input("Pesquisar", key="m8_fsearch")

    params: Dict[str, Any] = {"limit": 50}
    if f_stage != "Todos":
        stage_key = next((k for k, v in STAGE_LABELS.items() if v == f_stage), None)
        if stage_key:
            params["stage"] = stage_key
    if f_grade != "Todos":
        params["grade"] = f_grade
    if f_source:
        params["source"] = f_source
    if f_search:
        params["search"] = f_search

    leads_data = api_get("/api/v1/leads/", params=params)
    if leads_data and leads_data.get("items"):
        leads_list = leads_data["items"]
        st.caption(f"{leads_data.get('total', 0)} leads encontrados")

        for lead in leads_list:
            grade_color = GRADE_COLORS.get(lead.get("grade", "D"), "#94A3B8")
            budget = ""
            if lead.get("budget_min") or lead.get("budget_max"):
                bmin = f"{lead['budget_min']/1000:.0f}k" if lead.get("budget_min") else "?"
                bmax = f"{lead['budget_max']/1000:.0f}k" if lead.get("budget_max") else "?"
                budget = f"{bmin}-{bmax} EUR"

            stage_label = STAGE_LABELS.get(lead.get("stage", ""), lead.get("stage", ""))
            st.markdown(f"""
            <div class="prop-card" style="border-left: 4px solid {grade_color};">
                <div class="prop-header">
                <span class="prop-title">{lead['name']}</span>
                {grade_badge_html(lead.get('grade', 'D'), lead.get('score'))}
                </div>
                <div class="prop-specs">
                <span>{stage_label}</span>
                <span>{lead.get('source', '—')}</span>
                <span>{lead.get('preferred_typology') or '—'}</span>
                {'<span>' + budget + '</span>' if budget else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("Ver detalhes", expanded=False):
                dc1, dc2, dc3 = st.columns([2, 1, 1])
                with dc1:
                    st.markdown(f"**Email:** {lead.get('email') or '—'}")
                st.markdown(f"**Phone:** {lead.get('phone') or '—'}")
                st.markdown(f"**Tipologia:** {lead.get('preferred_typology') or '—'}")
                if lead.get("preferred_locations"):
                    st.markdown(f"**Localizacoes:** {', '.join(lead['preferred_locations'])}")
                if lead.get("notes"):
                    st.markdown(f"**Notas:** {lead['notes'][:200]}")

                with dc2:
                    st.markdown(
                    f"""<div style="background:{grade_color}15; border:2px solid {grade_color};
                    border-radius:12px; padding:12px; text-align:center;">
                    <p style="font-size:1.8rem; font-weight:700; color:{grade_color}; margin:0;">
                    {lead.get('grade', 'D')}</p>
                    <p style="font-size:0.9rem; color:{grade_color}; margin:0;">
                    {lead.get('score', 0)} pts</p>
                    </div>""",
                    unsafe_allow_html=True,
                )

                with dc3:
                # Mudar stage
                    all_stages = ["new", "contacted", "qualified", "visit", "visiting", "proposal", "negotiation", "won", "lost"]
                current_idx = 0
                for i, s in enumerate(all_stages):
                    if s == lead.get("stage"):
                        current_idx = i
                        break
                new_stage = st.selectbox(
                    "Stage", all_stages, index=current_idx,
                    format_func=lambda s: STAGE_LABELS.get(s, s),
                    key=f"m8_stage_{lead['id']}",
                )
                if new_stage != lead.get("stage"):
                    if st.button("Aplicar", key=f"m8_apply_{lead['id']}"):
                        api_patch(f"/api/v1/leads/{lead['id']}/stage", {"stage": new_stage})
                        st.rerun()

                if st.button("Recalcular Score", key=f"m8_rescore_{lead['id']}"):
                    api_post(f"/api/v1/leads/{lead['id']}/recalculate-score")
                    st.rerun()

                # Timeline de interaccoes
                st.markdown("**Timeline:**")
                timeline = api_get(f"/api/v1/leads/{lead['id']}/timeline")
                if timeline:
                    for inter in timeline[:10]:
                        icons = {
                        "whatsapp_sent": "📤", "whatsapp_received": "📥",
                        "email_sent": "📧", "call": "📞", "visit": "🏠",
                        "proposal_sent": "📄", "note": "📝", "stage_change": "🔄",
                        "auto_nurture": "🤖", "listing_view": "👁",
                    }
                    icon = icons.get(inter.get("type", ""), "•")
                    ts = str(inter.get("created_at", ""))[:16]
                    content = inter.get("content", "") or inter.get("subject", "") or ""
                    if len(content) > 100:
                        content = content[:100] + "..."
                    st.markdown(f"{icon} `{ts}` **{inter.get('type', '?')}** — {content}")
                else:
                    st.caption("Sem interaccoes")

                # Matches
                if st.button("Ver Matches", key=f"m8_match_{lead['id']}"):
                    matches = api_get(f"/api/v1/leads/{lead['id']}/matches", silent_404=True)
                    if matches:
                        for m in matches[:5]:
                            summary = m.get("listing_summary", {})
                            st.markdown(
                                f"**Score {m.get('match_score', 0):.0f}** — "
                                f"{summary.get('municipality', '?')} | "
                                f"{summary.get('typology', '?')} | "
                                f"{summary.get('listing_price', 0)/1000:.0f}k€"
                            )
                    else:
                        st.info("Sem matches")

                # Nurture
                nc1, nc2 = st.columns(2)
                with nc1:
                    if st.button("Iniciar Nurture", key=f"m8_nurt_{lead['id']}"):
                        nr = api_post(f"/api/v1/leads/{lead['id']}/nurture/start")
                    if nr:
                        st.success("Nurture iniciado")
                with nc2:
                    nurture_status = api_get(f"/api/v1/leads/{lead['id']}/nurture/status")
                if nurture_status and nurture_status.get("status") != "none":
                    st.markdown(
                        f"Nurture: **{nurture_status.get('status')}** "
                        f"(step {nurture_status.get('current_step', 0)})"
                    )
    else:
        st.info("Nenhum lead encontrado. Crie um acima ou sincronize com habta.eu.")

elif module == "M9 — Fecho + P&L":
    st.header("M9 — Fecho + P&L")
    st.caption("Workflow de fecho e analise de rentabilidade real vs estimada")

    m9_tab1, m9_tab2, m9_tab3, m9_tab4 = st.tabs([
        "Processos de Fecho", "P&L Comparativo", "Portfolio", "Relatorio Fiscal",
    ])

    # -----------------------------------------------------------------------
    # Tab 1: Processos de Fecho
    # -----------------------------------------------------------------------
    with m9_tab1:
        # Criar novo closing
        with st.expander("Criar processo de fecho", expanded=False):
            deals_resp = api_get("/api/v1/deals", silent_404=True) or {}
            deals_list = deals_resp.get("items", []) if isinstance(deals_resp, dict) else deals_resp
            if not deals_list:
                st.info("Nenhum deal encontrado. Crie um deal no M4 primeiro.")
            else:
                deal_options = {d["id"]: f"{d.get('title', d['id'][:8])}" for d in deals_list}
                sel_deal = st.selectbox("Deal", list(deal_options.keys()),
                                        format_func=lambda x: deal_options[x],
                                        key="m9_close_deal")
                sel_type = st.radio("Tipo", ["compra", "venda"], key="m9_close_type", horizontal=True)
                sel_price = st.number_input("Preco transaccao (EUR)", min_value=0, step=1000,
                                            key="m9_close_price")

                if st.button("Criar Closing", key="m9_create_close"):
                    deal_data = next((d for d in deals_list if d["id"] == sel_deal), {})
                    payload = {
                        "deal_id": sel_deal,
                        "property_id": deal_data.get("property_id", ""),
                        "closing_type": sel_type,
                        "transaction_price": sel_price if sel_price > 0 else None,
                    }
                    result = api_post("/api/v1/closing", payload)
                    if result:
                        st.success(f"Closing criado: {result['id'][:8]}")
                        st.rerun()

        # Listar closings
        closings = api_get("/api/v1/closing") or []
        if not closings:
            st.info("Nenhum processo de fecho encontrado.")
        else:
            STATUS_LABELS = {
                "pending": ("Pendente", "gray"),
                "imt_paid": ("IMT Pago", "orange"),
                "deed_scheduled": ("Escritura Agendada", "blue"),
                "deed_done": ("Escritura Realizada", "violet"),
                "registered": ("Registado", "cyan"),
                "completed": ("Concluido", "green"),
                "cancelled": ("Cancelado", "red"),
            }
            STEPS = ["pending", "imt_paid", "deed_scheduled", "deed_done", "registered", "completed"]

            for closing in closings:
                status = closing["status"]
                label, color = STATUS_LABELS.get(status, (status, "gray"))
                c_type = "Compra" if closing["closing_type"] == "compra" else "Venda"
                price_str = f"{closing['transaction_price']:,.0f} EUR" if closing.get("transaction_price") else "N/A"

                with st.expander(f"{c_type} — :{color}[{label}] — {price_str}", expanded=False):
                    # Barra de progresso
                    if status in STEPS:
                        idx = STEPS.index(status)
                        st.progress(idx / (len(STEPS) - 1), text=f"{label} ({idx+1}/{len(STEPS)})")
                    elif status == "cancelled":
                        st.error("Cancelado")

                    # Datas-chave
                    dc1, dc2, dc3 = st.columns(3)
                    with dc1:
                        st.metric("CPCV", closing.get("cpcv_date", "—") or "—")
                    with dc2:
                        st.metric("Escritura", closing.get("deed_actual_date", "—") or "—")
                    with dc3:
                        st.metric("Registo", closing.get("registration_date", "—") or "—")

                    # Alertas de guias fiscais
                    from datetime import datetime
                    now = datetime.utcnow()
                    for gtype, prefix in [("IMT", "imt"), ("IS", "is")]:
                        expires_str = closing.get(f"{prefix}_guide_expires_at")
                        if expires_str:
                            try:
                                expires = datetime.fromisoformat(expires_str)
                                hours_left = (expires - now).total_seconds() / 3600
                                if hours_left < 0:
                                    st.error(f"Guia {gtype} EXPIRADA!")
                                elif hours_left < 12:
                                    st.warning(f"Guia {gtype} expira em {hours_left:.0f}h!")
                                else:
                                    st.success(f"Guia {gtype}: {hours_left:.0f}h restantes")
                            except (ValueError, TypeError):
                                pass

                    # Checklist
                    checklist = closing.get("checklist", {})
                    progress_info = closing.get("checklist_progress", {})
                    st.markdown(
                        f"**Checklist** — {progress_info.get('done', 0)}/{progress_info.get('total', 0)} "
                        f"({progress_info.get('pct', 0)}%)"
                    )
                    for key, item in sorted(checklist.items(), key=lambda x: x[1].get("order", 99)):
                        done = item.get("done", False)
                        checked = "x" if done else " "
                        new_val = st.checkbox(
                            item.get("label", key),
                            value=done,
                            key=f"cl_{closing['id']}_{key}",
                        )
                        if new_val != done:
                            api_patch(
                                f"/api/v1/closing/{closing['id']}/checklist/{key}?done={'true' if new_val else 'false'}"
                            )
                            st.rerun()

                    # Accoes
                    st.markdown("---")
                    ac1, ac2, ac3 = st.columns(3)

                    # Avancar status
                    with ac1:
                        TRANSITIONS = {
                            "pending": ["imt_paid", "cancelled"],
                            "imt_paid": ["deed_scheduled", "cancelled"],
                            "deed_scheduled": ["deed_done", "cancelled"],
                            "deed_done": ["registered", "completed", "cancelled"],
                            "registered": ["completed", "cancelled"],
                            "cancelled": ["pending"],
                        }
                        next_opts = TRANSITIONS.get(status, [])
                        if next_opts:
                            target = st.selectbox(
                                "Avancar para", next_opts,
                                key=f"adv_{closing['id']}",
                            )
                            if st.button("Avancar", key=f"advbtn_{closing['id']}"):
                                r = api_patch(
                                    f"/api/v1/closing/{closing['id']}/status",
                                    {"target_status": target},
                                )
                                if r:
                                    st.success(f"Avancado para {target}")
                                    st.rerun()

                    # Emitir guia
                    with ac2:
                        g_type = st.selectbox("Guia", ["imt", "is"], key=f"gt_{closing['id']}")
                        g_amount = st.number_input("Valor", min_value=0.0, step=100.0,
                                                    key=f"ga_{closing['id']}")
                        if st.button("Emitir Guia", key=f"gbtn_{closing['id']}"):
                            if g_amount > 0:
                                r = api_post(
                                    f"/api/v1/closing/{closing['id']}/tax-guide",
                                    {"guide_type": g_type, "amount": g_amount},
                                )
                                if r:
                                    st.success(f"Guia {g_type.upper()} emitida")
                                    st.rerun()

                    # Direito preferencia
                    with ac3:
                        entities_str = st.text_input(
                            "Entidades (virgula)", key=f"pref_{closing['id']}",
                            placeholder="Camara Municipal, Inquilino",
                        )
                        if st.button("Notificar Preferencia", key=f"prefbtn_{closing['id']}"):
                            if entities_str.strip():
                                entities = [e.strip() for e in entities_str.split(",") if e.strip()]
                                r = api_post(
                                    f"/api/v1/closing/{closing['id']}/preference-right",
                                    {"entities": entities},
                                )
                                if r:
                                    st.success("Direito de preferencia notificado")
                                    st.rerun()

    # -----------------------------------------------------------------------
    # Tab 2: P&L Comparativo
    # -----------------------------------------------------------------------
    with m9_tab2:
        deals_resp2 = api_get("/api/v1/deals", silent_404=True) or {}
        deals_list2 = deals_resp2.get("items", []) if isinstance(deals_resp2, dict) else deals_resp2
        if not deals_list2:
            st.info("Nenhum deal encontrado.")
        else:
            deal_opts = {d["id"]: f"{d.get('title', d['id'][:8])}" for d in deals_list2}
            sel_pnl_deal = st.selectbox("Deal", list(deal_opts.keys()),
                                         format_func=lambda x: deal_opts[x],
                                         key="m9_pnl_deal")

            pc1, pc2 = st.columns([3, 1])
            with pc2:
                pnl_sale_price = st.number_input("Preco venda", min_value=0, step=1000,
                                                  key="m9_pnl_sale")
                pnl_months = st.number_input("Meses holding", min_value=0, step=1,
                                              key="m9_pnl_months")
                if st.button("Calcular P&L", key="m9_calc_pnl"):
                    params = {"sale_price": pnl_sale_price, "holding_months": pnl_months}
                    r = api_post(f"/api/v1/pnl/{sel_pnl_deal}/calculate?sale_price={pnl_sale_price}&holding_months={pnl_months}")
                    if r:
                        st.success("P&L calculado")
                        st.rerun()

            with pc1:
                pnl_data = api_get(f"/api/v1/pnl/{sel_pnl_deal}", silent_404=True)
                if not pnl_data:
                    st.info("P&L nao calculado para este deal. Use o botao ao lado.")
                else:
                    # Metricas principais
                    km1, km2, km3, km4 = st.columns(4)
                    with km1:
                        st.metric(
                            "ROI Anualizado",
                            f"{pnl_data.get('roi_annualized_pct', 0):.1f}%",
                            delta=f"{pnl_data.get('roi_variance_pct', 0):+.1f}%",
                        )
                    with km2:
                        st.metric("MOIC", f"{pnl_data.get('moic', 0):.2f}x")
                    with km3:
                        st.metric(
                            "Lucro Liquido",
                            f"{pnl_data.get('net_profit', 0):,.0f} EUR",
                            delta=f"{pnl_data.get('profit_variance', 0):+,.0f}",
                        )
                    with km4:
                        st.metric("Margem", f"{pnl_data.get('profit_margin_pct', 0):.1f}%")

                    # Tabela comparativa
                    st.markdown("### Estimado vs Real")
                    import pandas as pd
                    rows = [
                        ("Preco Compra", pnl_data.get("purchase_price", 0), pnl_data.get("purchase_price", 0)),
                        ("IMT + IS", pnl_data.get("imt_cost", 0) + pnl_data.get("is_cost", 0),
                         pnl_data.get("imt_cost", 0) + pnl_data.get("is_cost", 0)),
                        ("Obra (orcamento vs real)", pnl_data.get("renovation_budget", 0),
                         pnl_data.get("renovation_actual", 0)),
                        ("Preco Venda", pnl_data.get("sale_price", 0), pnl_data.get("sale_price", 0)),
                        ("Comissao Venda", pnl_data.get("sale_commission", 0), pnl_data.get("sale_commission", 0)),
                        ("Lucro Liquido", pnl_data.get("estimated_profit", 0), pnl_data.get("net_profit", 0)),
                        ("ROI (%)", pnl_data.get("estimated_roi_pct", 0), pnl_data.get("roi_annualized_pct", 0)),
                    ]
                    df = pd.DataFrame(rows, columns=["Item", "Estimado", "Real"])
                    df["Desvio"] = df["Real"] - df["Estimado"]
                    df["Desvio %"] = df.apply(
                        lambda r: round(r["Desvio"] / r["Estimado"] * 100, 1) if r["Estimado"] else 0,
                        axis=1,
                    )
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    # Botao finalizar
                    if pnl_data.get("status") != "final":
                        if st.button("Finalizar P&L", key="m9_finalize"):
                            r = api_post(f"/api/v1/pnl/{sel_pnl_deal}/finalize")
                            if r:
                                st.success("P&L finalizado")
                                st.rerun()
                    else:
                        st.success("P&L finalizado")

    # -----------------------------------------------------------------------
    # Tab 3: Portfolio
    # -----------------------------------------------------------------------
    with m9_tab3:
        summary = api_get("/api/v1/portfolio/summary") or {}

        pk1, pk2, pk3, pk4 = st.columns(4)
        with pk1:
            st.metric("Deals Fechados", summary.get("total_deals", 0))
        with pk2:
            st.metric("Total Investido", f"{summary.get('total_invested', 0):,.0f} EUR")
        with pk3:
            st.metric("Lucro Total", f"{summary.get('total_profit', 0):,.0f} EUR")
        with pk4:
            st.metric("ROI Medio", f"{summary.get('avg_roi_pct', 0):.1f}%")

        deals_summary = summary.get("deals", [])
        if deals_summary:
            import pandas as pd
            import plotly.express as px

            df = pd.DataFrame(deals_summary)

            # Grafico ROI por deal
            if "roi_annualized_pct" in df.columns and not df.empty:
                st.markdown("### ROI por Deal")
                fig = px.bar(
                    df,
                    x="property_name",
                    y="roi_annualized_pct",
                    color="roi_annualized_pct",
                    color_continuous_scale=["#EF4444", "#F59E0B", "#16A34A"],
                    labels={"roi_annualized_pct": "ROI Anualizado (%)", "property_name": "Propriedade"},
                )
                fig.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig, use_container_width=True)

            # Tabela
            st.markdown("### Detalhe por Deal")
            display_cols = ["property_name", "purchase_price", "sale_price",
                            "net_profit", "roi_annualized_pct", "moic", "holding_months"]
            existing = [c for c in display_cols if c in df.columns]
            if existing:
                st.dataframe(df[existing], use_container_width=True, hide_index=True)

            # Best/worst
            bw1, bw2 = st.columns(2)
            with bw1:
                best = summary.get("best_deal")
                if best:
                    st.success(
                        f"Melhor deal: {best.get('property_name', 'N/A')} — "
                        f"ROI {best.get('roi_annualized_pct', 0):.1f}% — "
                        f"Lucro {best.get('net_profit', 0):,.0f} EUR"
                    )
            with bw2:
                worst = summary.get("worst_deal")
                if worst:
                    st.error(
                        f"Pior deal: {worst.get('property_name', 'N/A')} — "
                        f"ROI {worst.get('roi_annualized_pct', 0):.1f}% — "
                        f"Lucro {worst.get('net_profit', 0):,.0f} EUR"
                    )
        else:
            st.info("Nenhum deal com P&L calculado.")

    # -----------------------------------------------------------------------
    # Tab 4: Relatorio Fiscal
    # -----------------------------------------------------------------------
    with m9_tab4:
        from datetime import datetime
        current_year = datetime.now().year
        sel_year = st.selectbox("Ano Fiscal", list(range(current_year, 2020, -1)), key="m9_fiscal_year")

        report = api_get(f"/api/v1/portfolio/fiscal-report?year={sel_year}") or {}

        fk1, fk2, fk3, fk4 = st.columns(4)
        with fk1:
            st.metric("Mais-Valias Totais", f"{report.get('total_capital_gains', 0):,.0f} EUR")
        with fk2:
            st.metric("Despesas Dedutiveis", f"{report.get('total_deductible_expenses', 0):,.0f} EUR")
        with fk3:
            st.metric("Base Tributavel (50%)", f"{report.get('taxable_amount', 0):,.0f} EUR")
        with fk4:
            st.metric("Imposto Estimado", f"{report.get('estimated_tax', 0):,.0f} EUR")

        fiscal_deals = report.get("deals", [])
        if fiscal_deals:
            import pandas as pd
            st.markdown("### Detalhe por Deal")
            df = pd.DataFrame(fiscal_deals)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info(f"Nenhum deal com P&L em {sel_year}.")
