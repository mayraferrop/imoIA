"""Pagina de CRM de Leads para o dashboard Streamlit.

Pipeline kanban, metricas, tabela de leads com filtros,
timeline de interaccoes e sync habta.eu.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from loguru import logger

from src.database.db import get_session
from src.modules.m8_leads.service import LeadService

# Cores consistentes com o design system do dashboard principal
COLORS = {
    "primary": "#0F766E",
    "primary_light": "#14B8A6",
    "cta": "#0369A1",
    "success": "#16A34A",
    "warning": "#D97706",
    "danger": "#DC2626",
    "info": "#2563EB",
    "purple": "#7C3AED",
    "text_primary": "#1E293B",
    "text_secondary": "#475569",
    "text_muted": "#94A3B8",
    "bg_card": "#F8FAFC",
    "border": "#E2E8F0",
}

STAGE_LABELS = {
    "new": "Novo",
    "contacted": "Contactado",
    "qualified": "Qualificado",
    "visit": "Visita",
    "proposal": "Proposta",
    "negotiation": "Negociacao",
    "closed_won": "Ganho",
    "closed_lost": "Perdido",
}

STAGE_COLORS = {
    "new": "#94A3B8",
    "contacted": "#2563EB",
    "qualified": "#7C3AED",
    "visit": "#D97706",
    "proposal": "#0F766E",
    "negotiation": "#14B8A6",
    "closed_won": "#16A34A",
    "closed_lost": "#DC2626",
}

GRADE_COLORS = {
    "A": "#16A34A",
    "B": "#14B8A6",
    "C": "#D97706",
    "D": "#94A3B8",
    "F": "#DC2626",
}


def _get_service() -> LeadService:
    """Cria uma instancia do LeadService."""
    return LeadService()


def _render_metric_card(label: str, value: str, delta: str = "", color: str = "#0F766E") -> None:
    """Renderiza um card de metrica."""
    delta_html = f'<p style="font-size:0.8rem; color:{color}; margin:0;">{delta}</p>' if delta else ""
    st.markdown(
        f"""<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px;
        padding:16px; text-align:center;">
        <p style="font-size:0.8rem; color:#475569; margin:0 0 4px 0;">{label}</p>
        <p style="font-size:1.8rem; font-weight:700; color:{color}; margin:0;">{value}</p>
        {delta_html}
        </div>""",
        unsafe_allow_html=True,
    )


def _render_pipeline_kanban(service: LeadService) -> None:
    """Renderiza o pipeline kanban com cards por stage."""
    summary = service.get_pipeline_summary()
    stages_to_show = ["new", "contacted", "qualified", "visit", "proposal", "negotiation", "closed_won", "closed_lost"]

    cols = st.columns(len(stages_to_show))
    for i, stage in enumerate(stages_to_show):
        count = summary.get(stage, 0)
        label = STAGE_LABELS.get(stage, stage)
        color = STAGE_COLORS.get(stage, "#94A3B8")

        with cols[i]:
            st.markdown(
                f"""<div style="background:{color}15; border:2px solid {color};
                border-radius:8px; padding:8px; text-align:center; min-height:80px;">
                <p style="font-size:0.75rem; font-weight:600; color:{color};
                margin:0; text-transform:uppercase;">{label}</p>
                <p style="font-size:1.5rem; font-weight:700; color:{color}; margin:4px 0;">{count}</p>
                </div>""",
                unsafe_allow_html=True,
            )

    # Cards de leads por stage (expandivel)
    for stage in stages_to_show:
        count = summary.get(stage, 0)
        if count == 0:
            continue

        label = STAGE_LABELS.get(stage, stage)
        with st.expander(f"{label} ({count} leads)"):
            result = service.list_leads(stage=stage, limit=20)
            for lead in result["leads"]:
                grade_color = GRADE_COLORS.get(lead["grade"], "#94A3B8")
                source = lead.get("source") or "—"
                budget = ""
                if lead.get("budget_min") or lead.get("budget_max"):
                    bmin = f"{lead['budget_min']/1000:.0f}k" if lead.get("budget_min") else "?"
                    bmax = f"{lead['budget_max']/1000:.0f}k" if lead.get("budget_max") else "?"
                    budget = f" | {bmin}-{bmax}€"

                st.markdown(
                    f"""<div style="background:white; border:1px solid #E2E8F0; border-left:4px solid {grade_color};
                    border-radius:8px; padding:10px 14px; margin-bottom:6px;">
                    <span style="font-weight:600; color:#1E293B;">{lead['name']}</span>
                    <span style="float:right; background:{grade_color}20; color:{grade_color};
                    padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600;">
                    {lead['grade']} — {lead['score']}pts</span>
                    <br><span style="font-size:0.75rem; color:#475569;">{source}{budget}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )


def _render_metrics(service: LeadService) -> None:
    """Renderiza metricas principais."""
    stats = service.get_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _render_metric_card("Total Leads", str(stats.get("total", 0)))
    with col2:
        _render_metric_card("Este Mes", str(stats.get("this_month", 0)), color=COLORS["info"])
    with col3:
        avg_score = stats.get("avg_score", 0)
        _render_metric_card("Score Medio", f"{avg_score:.0f}", color=COLORS["purple"])
    with col4:
        funnel = service.get_conversion_funnel()
        visit_to_proposal = 0
        for f in funnel:
            if f["from_stage"] == "visit" and f["to_stage"] == "proposal":
                visit_to_proposal = f["conversion_rate"]
                break
        _render_metric_card("Visita→Proposta", f"{visit_to_proposal:.0f}%", color=COLORS["success"])


def _render_charts(service: LeadService) -> None:
    """Renderiza graficos de leads."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Leads por Source**")
        breakdown = service.get_source_breakdown()
        if breakdown:
            df = pd.DataFrame(breakdown)
            fig = px.pie(
                df, names="source", values="count",
                color_discrete_sequence=["#14B8A6", "#0369A1", "#7C3AED", "#D97706", "#16A34A", "#DC2626"],
                hole=0.4,
            )
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=250, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de source")

    with col2:
        st.markdown("**Pipeline Funnel**")
        summary = service.get_pipeline_summary()
        stages = ["new", "contacted", "qualified", "visit", "proposal", "negotiation", "closed_won"]
        labels = [STAGE_LABELS.get(s, s) for s in stages]
        values = [summary.get(s, 0) for s in stages]
        colors = [STAGE_COLORS.get(s, "#94A3B8") for s in stages]

        if any(v > 0 for v in values):
            fig = go.Figure(go.Funnel(
                y=labels,
                x=values,
                marker=dict(color=colors),
                textinfo="value+percent initial",
            ))
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=250)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de pipeline")


def _render_grades_chart(service: LeadService) -> None:
    """Renderiza grafico de distribuicao por grade."""
    grades = service.get_grades_summary()
    if not grades:
        return

    st.markdown("**Distribuicao por Grade**")
    df = pd.DataFrame(grades)
    fig = px.bar(
        df, x="grade", y="count",
        color="grade",
        color_discrete_map=GRADE_COLORS,
    )
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=200,
        showlegend=False,
        xaxis_title="",
        yaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_leads_table(service: LeadService) -> None:
    """Renderiza tabela de leads com filtros."""
    st.markdown("### Leads")

    # Filtros
    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        stage_filter = st.selectbox(
            "Stage", ["Todos"] + list(STAGE_LABELS.values()),
            key="lead_stage_filter",
        )
    with fcol2:
        grade_filter = st.selectbox(
            "Grade", ["Todos", "A", "B", "C", "D", "F"],
            key="lead_grade_filter",
        )
    with fcol3:
        source_filter = st.text_input("Source", key="lead_source_filter")
    with fcol4:
        search = st.text_input("Pesquisar nome/email/phone", key="lead_search")

    # Converter filtros
    stage_val = None
    if stage_filter != "Todos":
        stage_val = next((k for k, v in STAGE_LABELS.items() if v == stage_filter), None)
    grade_val = grade_filter if grade_filter != "Todos" else None
    source_val = source_filter if source_filter else None
    search_val = search if search else None

    result = service.list_leads(
        stage=stage_val, grade=grade_val, source=source_val,
        search=search_val, limit=50,
    )
    leads = result["leads"]
    total = result["total"]

    st.caption(f"{total} leads encontrados")

    if not leads:
        st.info("Nenhum lead encontrado.")
        return

    # Tabela
    rows = []
    for lead in leads:
        budget = ""
        if lead.get("budget_min") or lead.get("budget_max"):
            bmin = f"{lead['budget_min']/1000:.0f}k" if lead.get("budget_min") else "?"
            bmax = f"{lead['budget_max']/1000:.0f}k" if lead.get("budget_max") else "?"
            budget = f"{bmin}-{bmax}€"

        rows.append({
            "Nome": lead["name"],
            "Stage": STAGE_LABELS.get(lead["stage"], lead["stage"]),
            "Score": lead["score"],
            "Grade": lead["grade"],
            "Source": lead.get("source") or "—",
            "Budget": budget,
            "Tipologia": lead.get("preferred_typology") or "—",
            "Interaccoes": lead.get("interactions_count", 0),
            "Criado": lead["created_at"][:10] if isinstance(lead["created_at"], str) else "",
            "_id": lead["id"],
        })

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_id"])

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        },
    )

    # Detalhe de lead seleccionado
    if leads:
        selected_name = st.selectbox(
            "Ver detalhe do lead:",
            ["—"] + [lead["name"] for lead in leads],
            key="lead_detail_select",
        )
        if selected_name != "—":
            selected = next((l for l in leads if l["name"] == selected_name), None)
            if selected:
                _render_lead_detail(service, selected["id"])


def _render_lead_detail(service: LeadService, lead_id: str) -> None:
    """Renderiza detalhe de um lead com timeline."""
    lead = service.get_lead(lead_id)
    if not lead:
        st.error("Lead nao encontrado")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"#### {lead['name']}")
        st.markdown(
            f"**Email:** {lead.get('email') or '—'} | "
            f"**Phone:** {lead.get('phone') or '—'} | "
            f"**Assigned:** {lead.get('assigned_to') or '—'}"
        )

        if lead.get("preferred_locations"):
            st.markdown(f"**Localizacoes:** {', '.join(lead['preferred_locations'])}")
        if lead.get("notes"):
            st.markdown(f"**Notas:** {lead['notes']}")
        if lead.get("tags"):
            tags_html = " ".join(
                f'<span style="background:#E2E8F0; padding:2px 8px; border-radius:4px; '
                f'font-size:0.75rem;">{t}</span>'
                for t in lead["tags"]
            )
            st.markdown(tags_html, unsafe_allow_html=True)

    with col2:
        grade_color = GRADE_COLORS.get(lead.get("grade", "D"), "#94A3B8")
        st.markdown(
            f"""<div style="background:{grade_color}15; border:2px solid {grade_color};
            border-radius:12px; padding:16px; text-align:center;">
            <p style="font-size:2rem; font-weight:700; color:{grade_color}; margin:0;">
            {lead.get('grade', 'D')}</p>
            <p style="font-size:1rem; color:{grade_color}; margin:0;">
            {lead.get('score', 0)} pontos</p>
            </div>""",
            unsafe_allow_html=True,
        )

    # Accoes
    st.markdown("---")
    acol1, acol2, acol3, acol4 = st.columns(4)
    with acol1:
        new_stage = st.selectbox(
            "Mudar stage:", list(STAGE_LABELS.values()),
            index=list(STAGE_LABELS.keys()).index(lead.get("stage", "new")),
            key=f"stage_change_{lead_id}",
        )
        stage_key = next((k for k, v in STAGE_LABELS.items() if v == new_stage), None)
        if stage_key and stage_key != lead.get("stage"):
            if st.button("Aplicar", key=f"apply_stage_{lead_id}"):
                try:
                    service.advance_stage(lead_id, stage_key)
                    st.success(f"Stage alterado para {new_stage}")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    with acol2:
        if st.button("Recalcular Score", key=f"rescore_{lead_id}"):
            service.recalculate_score(lead_id)
            st.success("Score recalculado")
            st.rerun()

    with acol3:
        if st.button("Iniciar Nurture", key=f"nurture_{lead_id}"):
            result = service.start_nurture(lead_id)
            if "error" in result:
                st.warning(result["error"])
            else:
                st.success("Nurture iniciado")

    with acol4:
        if st.button("Ver Matches", key=f"matches_{lead_id}"):
            matches = service.find_matches(lead_id)
            if matches:
                for m in matches[:5]:
                    summary = m.get("listing_summary", {})
                    st.markdown(
                        f"**Score {m['match_score']:.0f}** — "
                        f"{summary.get('municipality', '?')} | "
                        f"{summary.get('typology', '?')} | "
                        f"{summary.get('listing_price', 0)/1000:.0f}k€ | "
                        f"Razoes: {', '.join(m.get('match_reasons', []))}"
                    )
            else:
                st.info("Sem matches encontrados")

    # Timeline
    st.markdown("#### Timeline")
    interactions = service.get_timeline(lead_id)
    if interactions:
        for inter in interactions[:20]:
            icon = {
                "whatsapp_sent": "📤", "whatsapp_received": "📥",
                "email_sent": "📧", "call": "📞", "visit": "🏠",
                "proposal_sent": "📄", "note": "📝", "stage_change": "🔄",
                "score_update": "📊", "auto_nurture": "🤖", "listing_view": "👁",
            }.get(inter.get("type", ""), "•")

            ts = inter.get("created_at", "")
            if isinstance(ts, str) and len(ts) > 16:
                ts = ts[:16]

            content = inter.get("content", "") or inter.get("subject", "") or ""
            if len(content) > 120:
                content = content[:120] + "..."

            st.markdown(
                f"<div style='border-left:2px solid #E2E8F0; padding-left:12px; margin-bottom:8px;'>"
                f"<span style='font-size:0.75rem; color:#94A3B8;'>{ts}</span> "
                f"{icon} <span style='font-size:0.85rem;'>{inter.get('type', '?')}</span>"
                f"<br><span style='font-size:0.8rem; color:#475569;'>{content}</span></div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("Sem interaccoes registadas")


def _render_create_lead(service: LeadService) -> None:
    """Formulario para criar novo lead."""
    with st.expander("Criar Novo Lead", expanded=False):
        with st.form("create_lead_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Nome *")
                email = st.text_input("Email")
                phone = st.text_input("Phone (+351...)")
                source = st.selectbox(
                    "Source",
                    ["habta.eu", "whatsapp", "idealista", "referral", "instagram", "direct"],
                )
            with col2:
                budget_min = st.number_input("Budget Min (€)", min_value=0, value=0, step=10000)
                budget_max = st.number_input("Budget Max (€)", min_value=0, value=0, step=10000)
                typology = st.selectbox("Tipologia", ["", "T0", "T1", "T2", "T3", "T4", "T5+"])
                timeline = st.selectbox(
                    "Timeline",
                    ["", "imediato", "1-3 meses", "3-6 meses", "6+ meses"],
                )

            financing = st.selectbox(
                "Financiamento",
                ["unknown", "cash", "pre_approved", "needs_approval"],
            )
            buyer_type = st.selectbox(
                "Tipo de comprador",
                ["unknown", "end_user", "investor", "golden_visa"],
            )
            notes = st.text_area("Notas")

            submitted = st.form_submit_button("Criar Lead")
            if submitted:
                if not name:
                    st.error("Nome e obrigatorio")
                else:
                    data = {
                        "name": name,
                        "source": source,
                    }
                    if email:
                        data["email"] = email
                    if phone:
                        data["phone"] = phone
                    if budget_min > 0:
                        data["budget_min"] = float(budget_min)
                    if budget_max > 0:
                        data["budget_max"] = float(budget_max)
                    if typology:
                        data["preferred_typology"] = typology
                    if timeline:
                        data["timeline"] = timeline
                    if financing != "unknown":
                        data["financing"] = financing
                    if buyer_type != "unknown":
                        data["buyer_type"] = buyer_type
                    if notes:
                        data["notes"] = notes

                    try:
                        result = service.create_lead(data)
                        st.success(f"Lead criado: {result['name']} (Score: {result['score']}, Grade: {result['grade']})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")


def _render_sync_habta(service: LeadService) -> None:
    """Botao de sync com habta.eu."""
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Sync habta.eu", type="primary"):
            with st.spinner("A sincronizar com habta.eu..."):
                result = service.sync_from_habta()
            st.success(
                f"Sync concluido: {result.get('imported', 0)} importados, "
                f"{result.get('updated', 0)} actualizados, "
                f"{result.get('errors', 0)} erros"
            )
    with col2:
        st.caption("Importa/actualiza leads da tabela contacts do habta.eu (Supabase)")


def page_leads() -> None:
    """Pagina principal do CRM de Leads (M8)."""
    st.markdown(
        '<h2 style="font-family:Cinzel,serif; color:#0F766E; margin-bottom:8px;">'
        'CRM de Leads</h2>'
        '<p style="color:#475569; margin-bottom:24px;">Gestao do pipeline de compradores</p>',
        unsafe_allow_html=True,
    )

    service = _get_service()

    # Metricas
    _render_metrics(service)
    st.markdown("")

    # Pipeline kanban
    st.markdown("### Pipeline")
    _render_pipeline_kanban(service)
    st.markdown("")

    # Graficos
    col1, col2 = st.columns([2, 1])
    with col1:
        _render_charts(service)
    with col2:
        _render_grades_chart(service)

    st.markdown("---")

    # Criar lead + Sync
    ccol1, ccol2 = st.columns([3, 1])
    with ccol1:
        _render_create_lead(service)
    with ccol2:
        _render_sync_habta(service)

    st.markdown("")

    # Tabela de leads
    _render_leads_table(service)
