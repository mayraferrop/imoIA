"""Design tokens partilhados do dashboard ImoIA.

Modulo central de constantes visuais, cores, formatadores e componentes HTML
reutilizaveis. Substitui as cores e estilos hardcoded espalhados pelos
ficheiros do dashboard, garantindo coerencia visual.

Design system: Light Mode + Teal/Blue + Cinzel/Josefin Sans.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Paleta de Cores
# ---------------------------------------------------------------------------

COLORS: Dict[str, str] = {
    # Marca principal (teal)
    "primary": "#0F766E",        # teal-700
    "primary_light": "#14B8A6",  # teal-500
    "primary_bg": "#F0FDFA",     # teal-50
    # Call-to-action
    "cta": "#0369A1",            # blue-700
    # Fundos
    "bg": "#FFFFFF",
    "bg_card": "#F8FAFC",        # slate-50
    "bg_hover": "#F1F5F9",       # slate-100
    # Texto
    "text": "#1E293B",           # slate-800
    "text_secondary": "#475569", # slate-600
    "text_muted": "#94A3B8",     # slate-400
    # Semanticas
    "success": "#16A34A",        # green-600
    "warning": "#D97706",        # amber-600
    "danger": "#DC2626",         # red-600
    "info": "#2563EB",           # blue-600
    "purple": "#7C3AED",        # violet-600
    # Contornos
    "border": "#E2E8F0",        # slate-200
    "border_hover": "#CBD5E1",  # slate-300
}

# ---------------------------------------------------------------------------
# Cores por Grade (A-F)
# ---------------------------------------------------------------------------

GRADE_COLORS: Dict[str, str] = {
    "A": "#16A34A",  # green-600 — excelente
    "B": "#14B8A6",  # teal-500  — bom
    "C": "#D97706",  # amber-600 — medio
    "D": "#94A3B8",  # slate-400 — fraco
    "F": "#DC2626",  # red-600   — rejeitar
}

# ---------------------------------------------------------------------------
# Cores por Status (oportunidades)
# ---------------------------------------------------------------------------

STATUS_COLORS: Dict[str, str] = {
    "nova": COLORS["info"],
    "analisada": COLORS["warning"],
    "interessante": COLORS["success"],
    "descartada": COLORS["danger"],
    "contactada": COLORS["purple"],
}

# ---------------------------------------------------------------------------
# Cores por Stage (pipeline de leads)
# ---------------------------------------------------------------------------

STAGE_COLORS: Dict[str, str] = {
    "new": "#94A3B8",
    "contacted": "#2563EB",
    "qualified": "#7C3AED",
    "visit": "#D97706",
    "proposal": "#0F766E",
    "negotiation": "#14B8A6",
    "closed_won": "#16A34A",
    "closed_lost": "#DC2626",
}

STAGE_LABELS: Dict[str, str] = {
    "new": "Novo",
    "contacted": "Contactado",
    "qualified": "Qualificado",
    "visit": "Visita",
    "proposal": "Proposta",
    "negotiation": "Negociacao",
    "closed_won": "Ganho",
    "closed_lost": "Perdido",
}

# ---------------------------------------------------------------------------
# Labels de Tipos de Oportunidade (PT-PT)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Tipos de Imovel
# ---------------------------------------------------------------------------

PROPERTY_TYPES = [
    "apartamento", "moradia", "terreno", "predio",
    "loja", "armazem", "escritorio",
]

# ---------------------------------------------------------------------------
# Icones SVG inline (sem emojis — best practice UI/UX)
# ---------------------------------------------------------------------------

ICONS: Dict[str, str] = {
    "dashboard": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="3" width="7" height="7"/>'
        '<rect x="14" y="3" width="7" height="7"/>'
        '<rect x="3" y="14" width="7" height="7"/>'
        '<rect x="14" y="14" width="7" height="7"/></svg>'
    ),
    "pipeline": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'
    ),
    "config": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42'
        'M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
    ),
    "groups": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
    ),
    "home": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
        '<polyline points="9 22 9 12 15 12 15 22"/></svg>'
    ),
    "area": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<path d="M3 9h18M9 3v18"/></svg>'
    ),
    "bed": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<path d="M2 4v16"/><path d="M22 4v16"/>'
        '<path d="M2 12h20"/><path d="M2 8h20"/></svg>'
    ),
    "tag": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10'
        'l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>'
    ),
}


# ---------------------------------------------------------------------------
# Funcoes de Formatacao
# ---------------------------------------------------------------------------


def fmt_eur(value: Optional[float]) -> str:
    """Formata um valor numerico como preco em euros.

    Exemplos:
        >>> fmt_eur(295000)
        '295.000 EUR'
        >>> fmt_eur(None)
        'N/D'
    """
    if value is None:
        return "N/D"
    return f"{value:,.0f} EUR".replace(",", ".")


def fmt_pct(value: Optional[float], decimals: int = 1) -> str:
    """Formata um valor numerico como percentagem.

    Args:
        value: Valor decimal (0.15 = 15%) ou ja em percentagem (15.0).
               Se |value| < 1 assume-se decimal, caso contrario percentagem.
        decimals: Casas decimais a apresentar.

    Exemplos:
        >>> fmt_pct(0.153)
        '15.3%'
        >>> fmt_pct(15.3)
        '15.3%'
        >>> fmt_pct(None)
        'N/D'
    """
    if value is None:
        return "N/D"
    # Se o valor absoluto for menor que 1, assumimos que e decimal (0.15 = 15%)
    pct = value * 100 if abs(value) < 1 else value
    return f"{pct:.{decimals}f}%"


# ---------------------------------------------------------------------------
# Componentes HTML Reutilizaveis
# ---------------------------------------------------------------------------


def grade_badge_html(grade: Optional[str], score: Optional[int] = None) -> str:
    """Gera HTML de badge para um deal grade (A-F) com cor correspondente.

    Args:
        grade: Letra do grade (A, B, C, D, F) ou None.
        score: Pontuacao numerica opcional a apresentar ao lado do grade.

    Returns:
        String HTML com o badge estilizado.
    """
    if not grade:
        return (
            '<span style="background:#F1F5F9; color:#94A3B8; '
            'padding:2px 10px; border-radius:6px; font-size:0.8rem; '
            'font-weight:600;">N/D</span>'
        )
    color = GRADE_COLORS.get(grade, "#94A3B8")
    score_text = f" ({score})" if score is not None else ""
    return (
        f'<span style="background:{color}15; color:{color}; '
        f'border:1px solid {color}40; padding:2px 10px; border-radius:6px; '
        f'font-size:0.8rem; font-weight:700;">{grade}{score_text}</span>'
    )


def render_property_card(opp: Dict[str, Any]) -> str:
    """Gera HTML de um card de propriedade/oportunidade.

    O card tem borda lateral colorida conforme o grade, linha de icones
    (tipo, area, quartos) e preco formatado.

    Args:
        opp: Dicionario com campos da oportunidade. Campos esperados:
            - deal_grade (str|None): grade A-F
            - deal_score (int|None): pontuacao 0-100
            - opportunity_type (str|None): tipo da oportunidade
            - municipality (str|None): municipio
            - district (str|None): distrito
            - price (float|None): preco em euros
            - area_m2 (float|None): area em m2
            - bedrooms (int|None): numero de quartos
            - property_type (str|None): tipo de imovel
            - status (str|None): status actual

    Returns:
        String HTML com o card completo.
    """
    grade = opp.get("deal_grade")
    border_color = GRADE_COLORS.get(grade, COLORS["border"]) if grade else COLORS["border"]
    score = opp.get("deal_score")

    # Cabecalho: localizacao + badge
    municipality = opp.get("municipality") or "Local desconhecido"
    district = opp.get("district") or ""
    location = f"{municipality}, {district}" if district else municipality

    # Tipo de oportunidade
    opp_type = opp.get("opportunity_type") or ""
    type_label = OPPORTUNITY_TYPE_LABELS.get(opp_type, opp_type.replace("_", " ").title() if opp_type else "")

    # Preco
    price_html = fmt_eur(opp.get("price"))

    # Icones de detalhes (tipo imovel, area, quartos)
    details_parts = []
    prop_type = opp.get("property_type")
    if prop_type:
        details_parts.append(
            f'{ICONS["tag"]} <span style="font-size:0.8rem; color:{COLORS["text_secondary"]};">'
            f'{prop_type.capitalize()}</span>'
        )
    area = opp.get("area_m2")
    if area:
        details_parts.append(
            f'{ICONS["area"]} <span style="font-size:0.8rem; color:{COLORS["text_secondary"]};">'
            f'{area:.0f} m2</span>'
        )
    bedrooms = opp.get("bedrooms")
    if bedrooms:
        details_parts.append(
            f'{ICONS["bed"]} <span style="font-size:0.8rem; color:{COLORS["text_secondary"]};">'
            f'T{bedrooms}</span>'
        )
    details_html = " &nbsp;&middot;&nbsp; ".join(details_parts) if details_parts else ""

    # Status badge
    status = opp.get("status") or ""
    status_color = STATUS_COLORS.get(status, COLORS["text_muted"])
    status_html = (
        f'<span style="background:{status_color}15; color:{status_color}; '
        f'padding:1px 8px; border-radius:4px; font-size:0.75rem; '
        f'font-weight:500;">{status.capitalize()}</span>'
    ) if status else ""

    return f"""
    <div style="background:{COLORS['bg']}; border:1px solid {COLORS['border']};
        border-left:4px solid {border_color}; border-radius:12px;
        padding:16px 20px; margin-bottom:10px;
        transition:all 200ms ease; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
        <div style="display:flex; justify-content:space-between; align-items:center;
            margin-bottom:8px;">
            <span style="font-family:'Josefin Sans',sans-serif; font-size:1rem;
                font-weight:600; color:{COLORS['text']};">{location}</span>
            <span>{grade_badge_html(grade, score)}</span>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center;
            margin-bottom:6px;">
            <span style="font-size:0.8rem; color:{COLORS['primary']}; font-weight:500;">
                {type_label}</span>
            {status_html}
        </div>
        <div style="display:flex; align-items:center; gap:4px; margin-bottom:8px;">
            {details_html}
        </div>
        <div style="font-family:'Cinzel',serif; font-size:1.15rem; font-weight:700;
            color:{COLORS['primary']};">
            {price_html}
        </div>
    </div>
    """


def render_empty_state(
    title: str,
    description: str,
    action_label: Optional[str] = None,
) -> str:
    """Gera HTML para um estado vazio (sem dados).

    Args:
        title: Titulo principal.
        description: Texto descritivo.
        action_label: Texto opcional para uma sugestao de accao.

    Returns:
        String HTML com o empty state.
    """
    action_html = ""
    if action_label:
        action_html = (
            f'<p style="margin-top:12px;">'
            f'<span style="background:{COLORS["primary"]}; color:white; '
            f'padding:8px 20px; border-radius:8px; font-size:0.85rem; '
            f'font-weight:500; cursor:pointer;">{action_label}</span></p>'
        )

    return f"""
    <div class="empty-state" style="text-align:center; padding:60px 20px;
        color:#64748B;">
        <h3 style="font-family:'Cinzel',serif; color:{COLORS['text_secondary']} !important;
            font-size:1.3rem !important; margin-bottom:8px !important;">
            {title}</h3>
        <p style="font-family:'Josefin Sans',sans-serif; font-size:0.95rem;
            color:{COLORS['text_muted']};">
            {description}</p>
        {action_html}
    </div>
    """


def render_kpi_metric(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: str = "normal",
) -> str:
    """Gera HTML para um card de metrica KPI.

    Args:
        label: Etiqueta superior (ex: "Total Oportunidades").
        value: Valor principal formatado (ex: "82").
        delta: Texto de variacao opcional (ex: "+12 esta semana").
        delta_color: Cor da variacao — "normal" (primary), "success",
            "warning", "danger", ou codigo hex directo.

    Returns:
        String HTML com o card de metrica.
    """
    # Resolver cor do delta
    color_map = {
        "normal": COLORS["primary"],
        "success": COLORS["success"],
        "warning": COLORS["warning"],
        "danger": COLORS["danger"],
        "inverse": COLORS["danger"],
    }
    resolved_color = color_map.get(delta_color, delta_color)

    delta_html = ""
    if delta:
        delta_html = (
            f'<p style="font-family:\'Josefin Sans\',sans-serif; font-size:0.8rem; '
            f'color:{resolved_color}; margin:4px 0 0 0;">{delta}</p>'
        )

    return f"""
    <div class="metric-card" style="background:{COLORS['bg']}; border:1px solid {COLORS['border']};
        border-radius:14px; padding:20px 24px;
        transition:all 200ms ease; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
        <p class="metric-label" style="font-family:'Josefin Sans',sans-serif;
            font-size:0.85rem; color:{COLORS['text_muted']};
            text-transform:uppercase; letter-spacing:0.1em; margin:0 0 4px 0;">
            {label}</p>
        <p class="metric-value" style="font-family:'Cinzel',serif;
            font-size:2rem; font-weight:700; color:{COLORS['primary']};
            line-height:1.2; margin:0;">
            {value}</p>
        {delta_html}
    </div>
    """


# ---------------------------------------------------------------------------
# CSS Global — Design System
# ---------------------------------------------------------------------------

GLOBAL_CSS: str = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Josefin+Sans:wght@300;400;500;600;700&display=swap');

    /* ---- Tipografia base ---- */
    .main h1, .main h2, .main h3 {
        font-family: 'Cinzel', serif !important;
        color: #1E293B !important;
        letter-spacing: 0.02em;
    }
    .main p, .main span, .main div, .main label {
        font-family: 'Josefin Sans', sans-serif !important;
    }

    /* ---- Navegacao lateral ---- */
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

    /* ---- Cards de metrica ---- */
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

    /* ---- Cards de oportunidade ---- */
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

    /* ---- Badges ---- */
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
    .badge-confidence-mid  { background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }
    .badge-confidence-low  { background: #F1F5F9; color: #64748B; border: 1px solid #E2E8F0; }
    .badge-status-nova         { background: #DBEAFE; color: #1D4ED8; border: 1px solid #BFDBFE; }
    .badge-status-interessante { background: #DCFCE7; color: #15803D; border: 1px solid #BBF7D0; }
    .badge-status-descartada   { background: #FEE2E2; color: #B91C1C; border: 1px solid #FECACA; }
    .badge-status-contactada   { background: #EDE9FE; color: #6D28D9; border: 1px solid #DDD6FE; }
    .badge-status-analisada    { background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }

    /* ---- Titulos de seccao ---- */
    .section-title {
        font-family: 'Cinzel', serif;
        font-size: 1.4rem;
        color: #1E293B;
        margin: 24px 0 16px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #14B8A640;
    }

    /* ---- Cards de configuracao ---- */
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

    /* ---- Info / Warning boxes ---- */
    .info-box {
        background: #F0FDFA;
        border: 1px solid #99F6E4;
        border-radius: 10px;
        padding: 16px 20px;
        color: #0F766E;
        font-family: 'Josefin Sans', sans-serif;
        font-size: 0.9rem;
    }
    .warn-box {
        background: #FFFBEB;
        border: 1px solid #FDE68A;
        border-radius: 10px;
        padding: 16px 20px;
        color: #B45309;
        font-family: 'Josefin Sans', sans-serif;
        font-size: 0.9rem;
    }

    /* ---- Empty state ---- */
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

    /* ---- Plotly overrides ---- */
    .js-plotly-plot .plotly .modebar { display: none !important; }

    /* ---- Streamlit overrides (light theme) ---- */
    .stExpander {
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        background: #FFFFFF !important;
    }
    .stExpander:hover {
        border-color: #CBD5E1 !important;
    }
</style>
"""
