"""Pagina M9 — Fecho + P&L no dashboard Streamlit.

Inclui: closing workflow, P&L comparativo, portfolio e relatorio fiscal.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from loguru import logger

from src.modules.m9_closing.service import ClosingService, PnLService

# Cores consistentes com o design system
COLORS = {
    "primary": "#0F766E",
    "primary_light": "#14B8A6",
    "success": "#16A34A",
    "warning": "#D97706",
    "danger": "#DC2626",
    "info": "#2563EB",
    "text_primary": "#1E293B",
    "text_secondary": "#475569",
    "bg_card": "#F8FAFC",
    "border": "#E2E8F0",
}

CLOSING_STATUS_LABELS = {
    "pending": ("Pendente", "#9CA3AF"),
    "imt_paid": ("IMT Pago", "#F59E0B"),
    "deed_scheduled": ("Escritura Agendada", "#3B82F6"),
    "deed_done": ("Escritura Realizada", "#8B5CF6"),
    "registered": ("Registado", "#06B6D4"),
    "completed": ("Concluido", "#16A34A"),
    "cancelled": ("Cancelado", "#EF4444"),
}


def page_closing() -> None:
    """Pagina principal M9 — Fecho + P&L."""
    st.markdown(
        '<h1 style="font-family:Cinzel,serif; color:#0F766E;">M9 — Fecho + P&L</h1>',
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "Processos de Fecho",
        "P&L Comparativo",
        "Portfolio",
        "Relatorio Fiscal",
    ])

    with tab1:
        _render_closing_tab()

    with tab2:
        _render_pnl_tab()

    with tab3:
        _render_portfolio_tab()

    with tab4:
        _render_fiscal_tab()


# ---------------------------------------------------------------------------
# Tab 1: Processos de Fecho
# ---------------------------------------------------------------------------


def _render_closing_tab() -> None:
    """Renderiza tab de processos de fecho."""
    closing_service = ClosingService()

    closings = closing_service.list_closings()

    if not closings:
        st.info("Nenhum processo de fecho encontrado. Crie um via API.")
        return

    for closing in closings:
        _render_closing_card(closing, closing_service)


def _render_closing_card(closing: Dict[str, Any], service: ClosingService) -> None:
    """Renderiza card de um processo de fecho."""
    status = closing["status"]
    label, color = CLOSING_STATUS_LABELS.get(status, (status, "#6B7280"))
    closing_type = "Compra" if closing["closing_type"] == "compra" else "Venda"

    with st.expander(
        f"{closing_type} — {label} — {closing.get('transaction_price', 'N/A')} EUR",
        expanded=False,
    ):
        # Barra de progresso
        steps = ["pending", "imt_paid", "deed_scheduled", "deed_done", "registered", "completed"]
        if status in steps:
            current_idx = steps.index(status)
            progress = (current_idx) / (len(steps) - 1)
        else:
            progress = 0
        st.progress(progress, text=f"Progresso: {label}")

        # Datas-chave
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("CPCV", closing.get("cpcv_date", "—") or "—")
        with col2:
            st.metric("Escritura", closing.get("deed_actual_date", "—") or "—")
        with col3:
            st.metric("Registo", closing.get("registration_date", "—") or "—")

        # Alertas de guias fiscais
        _render_tax_alerts(closing)

        # Checklist
        st.markdown("**Checklist**")
        checklist = closing.get("checklist", {})
        progress_info = closing.get("checklist_progress", {})
        st.caption(
            f"{progress_info.get('done', 0)}/{progress_info.get('total', 0)} "
            f"({progress_info.get('pct', 0)}%)"
        )

        for key, item in sorted(
            checklist.items(), key=lambda x: x[1].get("order", 99)
        ):
            done = item.get("done", False)
            icon = "+" if done else " "
            st.markdown(f"- [{icon}] {item.get('label', key)}")


def _render_tax_alerts(closing: Dict[str, Any]) -> None:
    """Renderiza alertas de validade de guias fiscais."""
    now = datetime.utcnow()

    for guide_type, prefix in [("IMT", "imt"), ("IS", "is")]:
        expires_str = closing.get(f"{prefix}_guide_expires_at")
        if not expires_str:
            continue

        try:
            expires = datetime.fromisoformat(expires_str)
        except (ValueError, TypeError):
            continue

        remaining = expires - now
        hours_left = remaining.total_seconds() / 3600

        if hours_left < 0:
            st.error(f"Guia {guide_type} EXPIRADA!")
        elif hours_left < 12:
            st.warning(
                f"Guia {guide_type} expira em {hours_left:.0f}h — "
                f"renovar antes da escritura!"
            )
        else:
            st.success(f"Guia {guide_type}: {hours_left:.0f}h restantes")


# ---------------------------------------------------------------------------
# Tab 2: P&L Comparativo
# ---------------------------------------------------------------------------


def _render_pnl_tab() -> None:
    """Renderiza tab de P&L comparativo (estimado vs real)."""
    pnl_service = PnLService()

    summary = pnl_service.get_portfolio_summary()
    deals = summary.get("deals", [])

    if not deals:
        st.info("Nenhum P&L calculado. Use POST /api/v1/pnl/{deal_id}/calculate.")
        return

    # Selector de deal
    deal_options = {
        d["deal_id"]: f"{d.get('property_name', 'N/A')} — {d['deal_id'][:8]}"
        for d in deals
    }
    selected_deal = st.selectbox(
        "Seleccione um deal",
        options=list(deal_options.keys()),
        format_func=lambda x: deal_options[x],
    )

    if not selected_deal:
        return

    pnl = pnl_service.get_pnl(selected_deal)
    if not pnl:
        st.warning("P&L nao encontrado para este deal.")
        return

    # Tabela Estimado vs Real
    st.markdown("### Estimado vs Real")

    comparison_data = [
        ("Preco Compra", pnl.get("purchase_price", 0), pnl.get("purchase_price", 0)),
        ("IMT + IS", pnl.get("imt_cost", 0) + pnl.get("is_cost", 0),
         pnl.get("imt_cost", 0) + pnl.get("is_cost", 0)),
        ("Obra", pnl.get("renovation_budget", 0), pnl.get("renovation_actual", 0)),
        ("Financiamento", pnl.get("loan_setup_costs", 0) + pnl.get("total_interest_paid", 0),
         pnl.get("loan_setup_costs", 0) + pnl.get("total_interest_paid", 0)),
        ("Preco Venda", pnl.get("sale_price", 0), pnl.get("sale_price", 0)),
        ("Comissao Venda", pnl.get("sale_commission", 0), pnl.get("sale_commission", 0)),
        ("Lucro Liquido", pnl.get("estimated_profit", 0), pnl.get("net_profit", 0)),
        ("ROI (%)", pnl.get("estimated_roi_pct", 0), pnl.get("roi_annualized_pct", 0)),
    ]

    df = pd.DataFrame(comparison_data, columns=["Item", "Estimado", "Real"])
    df["Desvio"] = df["Real"] - df["Estimado"]
    df["Desvio %"] = df.apply(
        lambda r: round(r["Desvio"] / r["Estimado"] * 100, 1) if r["Estimado"] else 0,
        axis=1,
    )

    st.dataframe(
        df.style.applymap(
            lambda v: "color: green" if v > 0 else ("color: red" if v < 0 else ""),
            subset=["Desvio", "Desvio %"],
        ),
        use_container_width=True,
        hide_index=True,
    )

    # Metricas principais
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "ROI Anualizado",
            f"{pnl.get('roi_annualized_pct', 0):.1f}%",
            delta=f"{pnl.get('roi_variance_pct', 0):+.1f}%",
        )
    with col2:
        st.metric("MOIC", f"{pnl.get('moic', 0):.2f}x")
    with col3:
        st.metric(
            "Lucro Liquido",
            f"{pnl.get('net_profit', 0):,.0f} EUR",
            delta=f"{pnl.get('profit_variance', 0):+,.0f}",
        )
    with col4:
        st.metric("Margem", f"{pnl.get('profit_margin_pct', 0):.1f}%")


# ---------------------------------------------------------------------------
# Tab 3: Portfolio
# ---------------------------------------------------------------------------


def _render_portfolio_tab() -> None:
    """Renderiza tab de portfolio agregado."""
    pnl_service = PnLService()
    summary = pnl_service.get_portfolio_summary()

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Deals Fechados", summary.get("total_deals", 0))
    with col2:
        st.metric("Total Investido", f"{summary.get('total_invested', 0):,.0f} EUR")
    with col3:
        st.metric("Lucro Total", f"{summary.get('total_profit', 0):,.0f} EUR")
    with col4:
        st.metric("ROI Medio", f"{summary.get('avg_roi_pct', 0):.1f}%")

    deals = summary.get("deals", [])
    if not deals:
        st.info("Nenhum deal com P&L calculado.")
        return

    # Grafico ROI por deal
    st.markdown("### ROI por Deal")
    df = pd.DataFrame(deals)
    if not df.empty and "roi_annualized_pct" in df.columns:
        fig = px.bar(
            df,
            x="deal_id",
            y="roi_annualized_pct",
            color="roi_annualized_pct",
            color_continuous_scale=["#EF4444", "#F59E0B", "#16A34A"],
            labels={"roi_annualized_pct": "ROI Anualizado (%)", "deal_id": "Deal"},
        )
        fig.update_layout(
            showlegend=False,
            xaxis_tickangle=-45,
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Tabela de deals
    st.markdown("### Detalhe por Deal")
    display_cols = [
        "property_name", "purchase_price", "sale_price",
        "net_profit", "roi_annualized_pct", "moic", "holding_months", "status",
    ]
    existing_cols = [c for c in display_cols if c in df.columns]
    if existing_cols:
        st.dataframe(df[existing_cols], use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Tab 4: Relatorio Fiscal
# ---------------------------------------------------------------------------


def _render_fiscal_tab() -> None:
    """Renderiza tab de relatorio fiscal anual."""
    pnl_service = PnLService()

    current_year = datetime.now().year
    year = st.selectbox("Ano Fiscal", options=list(range(current_year, 2020, -1)))

    report = pnl_service.generate_fiscal_report(year)

    # KPIs fiscais
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Mais-Valias Totais", f"{report.get('total_capital_gains', 0):,.0f} EUR")
    with col2:
        st.metric("Despesas Dedutiveis", f"{report.get('total_deductible_expenses', 0):,.0f} EUR")
    with col3:
        st.metric("Base Tributavel (50%)", f"{report.get('taxable_amount', 0):,.0f} EUR")
    with col4:
        st.metric("Imposto Estimado", f"{report.get('estimated_tax', 0):,.0f} EUR")

    deals = report.get("deals", [])
    if deals:
        st.markdown("### Detalhe por Deal")
        df = pd.DataFrame(deals)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(f"Nenhum deal com P&L em {year}.")
