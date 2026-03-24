"""Maquina de estados do Deal Pipeline.

Define estrategias de investimento e mediacao, estados, transicoes validas
e rotas sugeridas por estrategia. Agnostico a base de dados.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Estrategias suportadas (investimento + mediacao)
# ---------------------------------------------------------------------------

INVESTMENT_STRATEGIES: Dict[str, Dict[str, Any]] = {
    # === Investimento ===
    "fix_and_flip": {
        "label": "Fix and Flip",
        "description": "Comprar, renovar, vender com lucro",
        "phases": ["aquisicao", "obra", "venda"],
        "exit": "venda",
        "icon": "\U0001f528",
        "role": "investidor",
    },
    "buy_and_hold": {
        "label": "Buy and Hold (Arrendamento)",
        "description": "Comprar (com ou sem obra) e arrendar a longo prazo",
        "phases": ["aquisicao", "obra_opcional", "arrendamento"],
        "exit": "arrendamento",
        "icon": "\U0001f3e0",
        "role": "investidor",
    },
    "brrrr": {
        "label": "BRRRR",
        "description": "Buy, Rehab, Rent, Refinance, Repeat",
        "phases": ["aquisicao", "obra", "arrendamento", "refinanciamento"],
        "exit": "arrendamento",
        "icon": "\U0001f504",
        "role": "investidor",
    },
    "revenda_sem_obra": {
        "label": "Compra e Revenda (sem obra)",
        "description": "Comprar abaixo do mercado, revender sem renovar",
        "phases": ["aquisicao", "venda"],
        "exit": "venda",
        "icon": "\U0001f4b0",
        "role": "investidor",
    },
    "alojamento_local": {
        "label": "Alojamento Local (AL)",
        "description": "Comprar, mobilar, licenciar como AL, explorar",
        "phases": ["aquisicao", "obra_opcional", "licenciamento_al", "operacao_al"],
        "exit": "operacao_al",
        "icon": "\U0001f3d6\ufe0f",
        "role": "investidor",
    },
    "desenvolvimento": {
        "label": "Desenvolvimento / Construcao",
        "description": "Comprar terreno ou ruina, construir de raiz",
        "phases": ["aquisicao", "licenciamento_obra", "construcao", "venda_ou_arrendamento"],
        "exit": "venda",
        "icon": "\U0001f3d7\ufe0f",
        "role": "investidor",
    },
    "wholesale": {
        "label": "Wholesale (Cessao)",
        "description": "Encontrar negocio, assinar CPCV, ceder posicao contratual",
        "phases": ["aquisicao_parcial", "cessao"],
        "exit": "cessao",
        "icon": "\U0001f4cb",
        "role": "investidor",
    },
    # === Mediacao ===
    "mediacao_venda": {
        "label": "Mediacao — Venda",
        "description": "Representar vendedor ou listar imovel para venda. Comissao na escritura.",
        "phases": ["angariacao", "marketing", "leads_visitas", "negociacao_venda"],
        "exit": "escritura_venda",
        "icon": "\U0001f3ea",
        "role": "mediador",
    },
    "mediacao_arrendamento": {
        "label": "Mediacao — Arrendamento",
        "description": "Encontrar inquilino para imovel. Comissao na assinatura do contrato.",
        "phases": ["angariacao", "marketing", "leads_visitas", "contrato_arrendamento"],
        "exit": "arrendamento",
        "icon": "\U0001f511",
        "role": "mediador",
    },
    "mediacao_compra": {
        "label": "Mediacao — Comprador",
        "description": "Representar comprador na procura e aquisicao de imovel.",
        "phases": ["procura", "visitas", "negociacao_compra"],
        "exit": "escritura_compra",
        "icon": "\U0001f50d",
        "role": "mediador",
    },
}

# ---------------------------------------------------------------------------
# Todos os estados possiveis do deal
# ---------------------------------------------------------------------------

DEAL_STATUSES = [
    # Fase inicial
    "lead",
    "oportunidade",
    "analise",
    # Fase de aquisicao
    "proposta",
    "negociacao",
    "cpcv_compra",
    "due_diligence",
    "financiamento",
    "escritura_compra",
    # Fase de obra
    "obra",
    # Fase de arrendamento
    "arrendamento",
    # Fase de refinanciamento
    "refinanciamento",
    # Fase de venda
    "em_venda",
    "cpcv_venda",
    "escritura_venda",
    # Fase de cessao
    "cessao",
    # === Mediacao ===
    "angariacao",
    "cma",
    "acordo_mediacao",
    "marketing_activo",
    "com_leads",
    "visitas_agendadas",
    "proposta_recebida",
    "em_partilha",
    # Estados terminais
    "concluido",
    "descartado",
    "em_pausa",
]

# ---------------------------------------------------------------------------
# Transicoes validas — agnosticas a estrategia
# ---------------------------------------------------------------------------

DEAL_TRANSITIONS: Dict[str, List[str]] = {
    # === Investimento ===
    "lead": ["oportunidade", "angariacao", "descartado"],
    "oportunidade": ["analise", "proposta", "descartado"],
    "analise": ["proposta", "descartado"],
    "proposta": ["negociacao", "cpcv_compra", "descartado"],
    "negociacao": ["cpcv_compra", "proposta", "descartado"],
    "cpcv_compra": ["due_diligence", "financiamento", "escritura_compra", "cessao", "descartado"],
    "due_diligence": ["financiamento", "escritura_compra", "descartado"],
    "financiamento": ["escritura_compra", "descartado"],
    "escritura_compra": ["obra", "em_venda", "arrendamento", "concluido"],
    "obra": ["em_venda", "arrendamento", "concluido"],
    "arrendamento": ["refinanciamento", "em_venda", "em_pausa", "concluido"],
    "refinanciamento": ["arrendamento", "concluido"],
    "em_venda": ["cpcv_venda", "arrendamento", "em_pausa"],
    "cpcv_venda": ["escritura_venda", "em_venda"],
    "escritura_venda": ["concluido"],
    "cessao": ["concluido", "descartado"],
    # === Mediacao ===
    "angariacao": ["cma", "acordo_mediacao", "descartado"],
    "cma": ["acordo_mediacao", "descartado"],
    "acordo_mediacao": ["marketing_activo", "descartado"],
    "marketing_activo": ["com_leads", "em_partilha", "descartado"],
    "com_leads": ["visitas_agendadas", "marketing_activo"],
    "visitas_agendadas": ["proposta_recebida", "com_leads"],
    "proposta_recebida": ["negociacao", "visitas_agendadas"],
    "em_partilha": ["com_leads", "visitas_agendadas", "descartado"],
    # === Terminais ===
    "em_pausa": ["oportunidade", "analise", "proposta", "em_venda", "arrendamento", "marketing_activo", "descartado"],
    "descartado": ["lead"],
}

# ---------------------------------------------------------------------------
# Rota sugerida por estrategia (para dashboard mostrar progresso)
# ---------------------------------------------------------------------------

STRATEGY_ROUTES: Dict[str, List[str]] = {
    # === Investimento ===
    "fix_and_flip": [
        "lead", "oportunidade", "analise", "proposta", "negociacao",
        "cpcv_compra", "due_diligence", "financiamento", "escritura_compra",
        "obra", "em_venda", "cpcv_venda", "escritura_venda", "concluido",
    ],
    "buy_and_hold": [
        "lead", "oportunidade", "analise", "proposta", "negociacao",
        "cpcv_compra", "due_diligence", "financiamento", "escritura_compra",
        "arrendamento", "concluido",
    ],
    "brrrr": [
        "lead", "oportunidade", "analise", "proposta", "negociacao",
        "cpcv_compra", "due_diligence", "financiamento", "escritura_compra",
        "obra", "arrendamento", "refinanciamento", "concluido",
    ],
    "revenda_sem_obra": [
        "lead", "oportunidade", "analise", "proposta", "negociacao",
        "cpcv_compra", "due_diligence", "financiamento", "escritura_compra",
        "em_venda", "cpcv_venda", "escritura_venda", "concluido",
    ],
    "alojamento_local": [
        "lead", "oportunidade", "analise", "proposta", "negociacao",
        "cpcv_compra", "due_diligence", "financiamento", "escritura_compra",
        "obra", "arrendamento", "concluido",
    ],
    "desenvolvimento": [
        "lead", "oportunidade", "analise", "proposta", "negociacao",
        "cpcv_compra", "due_diligence", "financiamento", "escritura_compra",
        "obra", "em_venda", "cpcv_venda", "escritura_venda", "concluido",
    ],
    "wholesale": [
        "lead", "oportunidade", "analise", "proposta", "negociacao",
        "cpcv_compra", "cessao", "concluido",
    ],
    # === Mediacao ===
    "mediacao_venda": [
        "lead", "angariacao", "cma", "acordo_mediacao",
        "marketing_activo", "com_leads", "visitas_agendadas",
        "proposta_recebida", "negociacao", "cpcv_compra",
        "escritura_compra", "concluido",
    ],
    "mediacao_arrendamento": [
        "lead", "angariacao", "cma", "acordo_mediacao",
        "marketing_activo", "com_leads", "visitas_agendadas",
        "proposta_recebida", "negociacao",
        "arrendamento", "concluido",
    ],
    "mediacao_compra": [
        "lead", "oportunidade", "analise",
        "visitas_agendadas", "proposta",
        "negociacao", "cpcv_compra", "due_diligence",
        "financiamento", "escritura_compra", "concluido",
    ],
}

# ---------------------------------------------------------------------------
# Labels e cores para o dashboard
# ---------------------------------------------------------------------------

STATUS_CONFIG: Dict[str, Dict[str, str]] = {
    "lead": {"label": "Lead", "color": "#9CA3AF", "icon": "\U0001f4e5"},
    "oportunidade": {"label": "Oportunidade", "color": "#60A5FA", "icon": "\U0001f50d"},
    "analise": {"label": "Em analise", "color": "#818CF8", "icon": "\U0001f4ca"},
    "proposta": {"label": "Proposta", "color": "#F59E0B", "icon": "\U0001f4dd"},
    "negociacao": {"label": "Negociacao", "color": "#F97316", "icon": "\U0001f91d"},
    "cpcv_compra": {"label": "CPCV Compra", "color": "#EF4444", "icon": "\u270d\ufe0f"},
    "due_diligence": {"label": "Due Diligence", "color": "#EC4899", "icon": "\U0001f50e"},
    "financiamento": {"label": "Financiamento", "color": "#8B5CF6", "icon": "\U0001f3e6"},
    "escritura_compra": {"label": "Escritura Compra", "color": "#10B981", "icon": "\U0001f3db\ufe0f"},
    "obra": {"label": "Obra", "color": "#06B6D4", "icon": "\U0001f528"},
    "arrendamento": {"label": "Arrendamento", "color": "#14B8A6", "icon": "\U0001f3e0"},
    "refinanciamento": {"label": "Refinanciamento", "color": "#A78BFA", "icon": "\U0001f504"},
    "em_venda": {"label": "Em Venda", "color": "#F472B6", "icon": "\U0001f3f7\ufe0f"},
    "cpcv_venda": {"label": "CPCV Venda", "color": "#FB923C", "icon": "\u270d\ufe0f"},
    "escritura_venda": {"label": "Escritura Venda", "color": "#22C55E", "icon": "\U0001f3db\ufe0f"},
    "cessao": {"label": "Cessao", "color": "#94A3B8", "icon": "\U0001f4cb"},
    # === Mediacao ===
    "angariacao": {"label": "Angariacao", "color": "#6366F1", "icon": "\U0001f4de"},
    "cma": {"label": "CMA", "color": "#8B5CF6", "icon": "\U0001f4ca"},
    "acordo_mediacao": {"label": "Acordo Mediacao", "color": "#A855F7", "icon": "\U0001f4c4"},
    "marketing_activo": {"label": "Marketing Activo", "color": "#EC4899", "icon": "\U0001f4e3"},
    "com_leads": {"label": "Com Leads", "color": "#F97316", "icon": "\U0001f4e5"},
    "visitas_agendadas": {"label": "Visitas Agendadas", "color": "#EAB308", "icon": "\U0001f697"},
    "proposta_recebida": {"label": "Proposta Recebida", "color": "#22C55E", "icon": "\U0001f4b0"},
    "em_partilha": {"label": "Em Partilha", "color": "#06B6D4", "icon": "\U0001f91d"},
    # === Terminais ===
    "concluido": {"label": "Concluido", "color": "#6B7280", "icon": "\u2705"},
    "descartado": {"label": "Descartado", "color": "#374151", "icon": "\u274c"},
    "em_pausa": {"label": "Em Pausa", "color": "#D1D5DB", "icon": "\u23f8\ufe0f"},
}

# ---------------------------------------------------------------------------
# Tasks automaticas por estado
# ---------------------------------------------------------------------------

AUTO_TASKS: Dict[str, List[Dict[str, str]]] = {
    # === Investimento ===
    "cpcv_compra": [
        {"title": "Entregar sinal", "priority": "high"},
        {"title": "Obter certidao predial", "priority": "high"},
        {"title": "Agendar reforco", "priority": "medium"},
    ],
    # due_diligence: gerido pelo M5 (DueDiligenceService.generate_checklist)
    "financiamento": [
        {"title": "Submeter pedido ao banco", "priority": "high"},
        {"title": "Follow-up banco (1 semana)", "priority": "medium"},
    ],
    "escritura_compra": [
        {"title": "Pagar IMT/IS (guias 48h antes)", "priority": "high"},
        {"title": "Marcar Casa Pronta / notario", "priority": "high"},
    ],
    "obra": [
        {"title": "Comunicacao previa a camara", "priority": "high"},
        {"title": "Reuniao com empreiteiro", "priority": "high"},
    ],
    "em_venda": [
        {"title": "Publicar Idealista", "priority": "high"},
        {"title": "Publicar Facebook Marketplace", "priority": "medium"},
        {"title": "Fotos profissionais", "priority": "high"},
    ],
    "arrendamento": [
        {"title": "Publicar anuncio de arrendamento", "priority": "high"},
        {"title": "Redigir contrato de arrendamento", "priority": "medium"},
        {"title": "Registar contrato nas Financas", "priority": "medium"},
    ],
    # === Mediacao ===
    "angariacao": [
        {"title": "Visitar imovel", "priority": "high"},
        {"title": "Fotografar imovel", "priority": "high"},
        {"title": "Pedir documentacao ao proprietario", "priority": "medium"},
    ],
    "cma": [
        {"title": "Pesquisar comparaveis", "priority": "high"},
        {"title": "Preparar relatorio CMA", "priority": "high"},
        {"title": "Apresentar CMA ao proprietario", "priority": "medium"},
    ],
    "acordo_mediacao": [
        {"title": "Assinar CMI (contrato mediacao)", "priority": "high"},
        {"title": "Definir preco de venda", "priority": "high"},
        {"title": "Recolher chaves", "priority": "medium"},
    ],
    "marketing_activo": [
        {"title": "Publicar Idealista", "priority": "high"},
        {"title": "Publicar nos grupos WhatsApp", "priority": "medium"},
        {"title": "Criar peca redes sociais", "priority": "medium"},
    ],
    "com_leads": [
        {"title": "Qualificar leads", "priority": "high"},
        {"title": "Agendar visitas", "priority": "high"},
    ],
    "visitas_agendadas": [
        {"title": "Preparar imovel para visita", "priority": "high"},
        {"title": "Follow-up pos-visita", "priority": "medium"},
    ],
    "proposta_recebida": [
        {"title": "Apresentar proposta ao proprietario", "priority": "high"},
        {"title": "Negociar condicoes", "priority": "medium"},
    ],
}

# ---------------------------------------------------------------------------
# Funcoes da maquina de estados
# ---------------------------------------------------------------------------


def can_transition(current: str, target: str) -> bool:
    """Verifica se a transicao entre dois estados e valida."""
    return target in DEAL_TRANSITIONS.get(current, [])


def get_next_statuses(current: str, strategy: Optional[str] = None) -> List[str]:
    """Retorna proximos estados possiveis, filtrados pela rota da estrategia."""
    all_next = DEAL_TRANSITIONS.get(current, [])
    if not strategy or strategy not in STRATEGY_ROUTES:
        return all_next

    route = STRATEGY_ROUTES[strategy]
    # Manter estados da rota + estados terminais/pausa (sempre disponiveis)
    terminal = {"concluido", "descartado", "em_pausa"}
    return [s for s in all_next if s in route or s in terminal]


def get_progress_pct(current: str, strategy: str) -> float:
    """Calcula percentagem de conclusao na rota da estrategia."""
    route = STRATEGY_ROUTES.get(strategy)
    if not route or current not in route:
        if current in ("concluido",):
            return 100.0
        if current in ("descartado", "em_pausa"):
            return 0.0
        return 0.0

    idx = route.index(current)
    return round((idx / (len(route) - 1)) * 100, 1)


def get_strategy_info(strategy: str) -> Optional[Dict[str, Any]]:
    """Retorna informacao completa de uma estrategia."""
    info = INVESTMENT_STRATEGIES.get(strategy)
    if not info:
        return None
    return {
        **info,
        "key": strategy,
        "route": STRATEGY_ROUTES.get(strategy, []),
    }


def get_all_strategies(role: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna estrategias com as suas rotas, opcionalmente filtradas por role."""
    result = []
    for key, info in INVESTMENT_STRATEGIES.items():
        if role and info.get("role", "investidor") != role:
            continue
        result.append({**info, "key": key, "route": STRATEGY_ROUTES.get(key, [])})
    return result


def get_all_statuses() -> List[Dict[str, Any]]:
    """Retorna todos os estados com labels e cores."""
    return [
        {"key": status, **STATUS_CONFIG.get(status, {"label": status, "color": "#666", "icon": ""})}
        for status in DEAL_STATUSES
    ]


def is_mediation_strategy(strategy: str) -> bool:
    """Verifica se a estrategia e de mediacao."""
    info = INVESTMENT_STRATEGIES.get(strategy, {})
    return info.get("role") == "mediador"
