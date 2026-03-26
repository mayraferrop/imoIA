"""Exportacao de fluxo de caixa M3 para o Cash Flow Pro (Supabase).

Envia os lancamentos do modelo financeiro como entries no Cash Flow Pro
via edge function import_external_entries. Usa anon key + auth do utilizador.

Logica de datas:
  - CPCV: data da assinatura (cpcv_date do Deal, ou input manual)
  - Escritura: cpcv_date + 60-90 dias (ou escritura_date do Deal)
  - Obra mes 1: dia seguinte a escritura (ou obra_start_date do Deal)
  - Meses seguintes: +30 dias por mes
  - Venda: fim da obra + holding months (ou sale_date do Deal)

Deduplicacao via external_ref (formato: imoia:{model_id}:{periodo}).
Categorias mapeadas para o plano de contas CashFlow Pro.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.config import get_settings

# Mapeamento imoIA -> CashFlow Pro (plano de contas)
CATEGORY_MAP: Dict[str, Dict[str, str]] = {
    # Aquisicao
    "sinal":       {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "Aquisição do Imóvel",      "budget": "Custos dos Produtos / Serviços"},
    "equity":      {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "Aquisição do Imóvel",      "budget": "Custos dos Produtos / Serviços"},
    "imt":         {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "IMT, IS, Notário",         "budget": "Impostos pagos"},
    "is":          {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "IMT, IS, Notário",         "budget": "Impostos pagos"},
    "notario":     {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "IMT, IS, Notário",         "budget": "Custos dos Produtos / Serviços"},
    # Obra
    "obra":        {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "Reformas / Reabilitação",  "budget": "Custos dos Produtos / Serviços"},
    "consumos_obra": {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "Contas de Consumo",      "budget": "Custos dos Produtos / Serviços"},
    # Manutencao
    "condominio":  {"cat": "Despesas Operacionais",          "sub": "Seguros e Condomínios",    "budget": "Custos dos Produtos / Serviços"},
    "seguro":      {"cat": "Despesas Operacionais",          "sub": "Seguros e Condomínios",    "budget": "Custos dos Produtos / Serviços"},
    "consumos_holding": {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "Contas de Consumo",   "budget": "Custos dos Produtos / Serviços"},
    # Financiamento
    "juros":       {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "Juros Capitalizados",      "budget": "Custos dos Produtos / Serviços"},
    "amortizacao": {"cat": "Contas a pagar (C/P)",           "sub": "Empréstimos Bancários — Curto Prazo", "budget": "Amortização de empréstimos"},
    "payoff":      {"cat": "Contas a pagar (C/P)",           "sub": "Empréstimos Bancários — Curto Prazo", "budget": "Amortização de empréstimos"},
    "penalizacao": {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "Encargos Bancários e Taxas", "budget": "Custos dos Produtos / Serviços"},
    # Venda
    "receita":     {"cat": "Receita de Revenda de Imóveis",  "sub": "Receita de Venda de Imóveis", "budget": "Receitas Operacionais"},
    "comissao":    {"cat": "Custo do Imóvel Vendido (COGS)", "sub": "Comissão de Compra/Venda", "budget": "Custos dos Produtos / Serviços"},
    # Reembolso
    "reembolso_imt": {"cat": "Receita de Revenda de Imóveis", "sub": "Reembolso de IMT de Revenda", "budget": "Outras Receitas não operacionais"},
}

# Mapeamento de nomes de componentes do calculator para chaves do CATEGORY_MAP
_COMP_NAME_MAP: Dict[str, str] = {
    "Equity restante": "equity",
    "IMT": "imt",
    "Imposto de Selo": "is",
    "Notario e Registo": "notario",
    "Comissao compra": "comissao",
    "Custos hipoteca": "penalizacao",
    "IMT 2a transmissao": "imt",
    "IMT 2a transmissao (devolvido)": "reembolso_imt",
}


def _cat(key: str) -> Dict[str, str]:
    """Retorna main_category, subcategory e budget_category para uma chave."""
    m = CATEGORY_MAP.get(key, CATEGORY_MAP["sinal"])
    return {
        "main_category": m["cat"],
        "subcategory": m["sub"],
        "budget_category": m["budget"],
    }


def _make_entry(
    entry_type: str,
    description: str,
    amount: float,
    cat_key: str,
    entry_date_str: str,
    project_name: str,
    external_ref: str,
    notes: str = "",
) -> Dict[str, Any]:
    """Cria um entry para o CashFlow Pro com categorias mapeadas."""
    cats = _cat(cat_key)
    return {
        "entry_type": entry_type,
        "description": description,
        "amount": amount,
        "currency": "EUR",
        "main_category": cats["main_category"],
        "subcategory": cats["subcategory"],
        "budget_category": cats["budget_category"],
        "entry_date": entry_date_str,
        "due_date": entry_date_str,
        "payment_status": "previsão",
        "notes": notes or project_name,
        "external_ref": external_ref,
    }


def _calc_dates(
    cpcv_date: date,
    escritura_date: Optional[date],
    obra_start_date: Optional[date],
    sale_date: Optional[date],
    renovation_duration_months: int,
    holding_months: int,
) -> Dict[str, date]:
    """Calcula todas as datas do cronograma a partir da data do CPCV."""
    esc = escritura_date or (cpcv_date + timedelta(days=60))
    obra_ini = obra_start_date or (esc + timedelta(days=1))

    meses: List[date] = []
    for m in range(holding_months):
        meses.append(obra_ini + timedelta(days=30 * m))

    venda = sale_date or (obra_ini + timedelta(days=30 * holding_months))

    return {
        "cpcv": cpcv_date,
        "escritura": esc,
        "obra_inicio": obra_ini,
        "meses": meses,
        "venda": venda,
    }


def _build_entries(
    flows: List[Dict[str, Any]],
    model_id: str,
    project_name: str,
    dates: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Converte flows do M3 em entries para o Cash Flow Pro.

    Cada componente vira um lancamento separado (IMT, IS, Notario, etc.).
    Juros e amortizacao sao lancamentos separados.
    """
    entries: List[Dict[str, Any]] = []
    mes_idx = 0

    for f in flows:
        label = f.get("label", "")
        cat = f.get("categoria", "")
        ref_base = f"imoia:{model_id}:{label.lower().replace(' ', '_')}"

        # Determinar data deste periodo
        if label == "CPCV" or label.startswith("CPCV "):
            entry_date = dates["cpcv"]
        elif "Escritura" in label:
            entry_date = dates["escritura"]
        elif label == "VENDA":
            entry_date = dates["venda"]
        elif label == "Reembolso IMT":
            entry_date = dates["venda"] + timedelta(days=365)
        elif label.startswith("Mes"):
            if mes_idx < len(dates["meses"]):
                entry_date = dates["meses"][mes_idx]
            else:
                entry_date = dates["venda"] - timedelta(days=30)
            mes_idx += 1
        else:
            entry_date = dates["cpcv"]

        entry_date_str = entry_date.isoformat()

        if cat == "aquisicao":
            componentes = f.get("componentes", [])
            if componentes:
                for j, comp in enumerate(componentes):
                    nome = comp["nome"]
                    cat_key = _COMP_NAME_MAP.get(nome, "sinal")
                    entries.append(_make_entry(
                        entry_type="expense",
                        description=f"{label} — {nome}",
                        amount=comp["valor"],
                        cat_key=cat_key,
                        entry_date_str=entry_date_str,
                        project_name=project_name,
                        external_ref=f"{ref_base}:{j}",
                    ))
            else:
                # CPCV sem componentes = sinal
                entries.append(_make_entry(
                    entry_type="expense",
                    description=f"{label} — Sinal",
                    amount=f.get("aquisicao", 0),
                    cat_key="sinal",
                    entry_date_str=entry_date_str,
                    project_name=project_name,
                    external_ref=ref_base,
                ))

        elif cat in ("obra", "holding"):
            obra_val = f.get("obra", 0)
            juros = f.get("juros", 0)
            amort = f.get("amort", 0)
            manut_val = f.get("manut", 0)
            consumos_val = f.get("consumos", 0)
            # manut inclui consumos — subtrair para nao duplicar
            manut_sem_consumos = manut_val - consumos_val

            if obra_val > 0:
                entries.append(_make_entry(
                    entry_type="expense",
                    description=f"{label} — Obra (renovação)",
                    amount=obra_val,
                    cat_key="obra",
                    entry_date_str=entry_date_str,
                    project_name=project_name,
                    external_ref=f"{ref_base}:obra",
                ))

            # Juros e amortizacao separados (em vez de PMT unico)
            if juros > 0:
                entries.append(_make_entry(
                    entry_type="expense",
                    description=f"{label} — Juros hipoteca",
                    amount=juros,
                    cat_key="juros",
                    entry_date_str=entry_date_str,
                    project_name=project_name,
                    external_ref=f"{ref_base}:juros",
                    notes=f"{project_name} | Saldo: {f.get('saldo_devedor', 0):,.0f}",
                ))

            if amort > 0:
                entries.append(_make_entry(
                    entry_type="expense",
                    description=f"{label} — Amortização hipoteca",
                    amount=amort,
                    cat_key="amortizacao",
                    entry_date_str=entry_date_str,
                    project_name=project_name,
                    external_ref=f"{ref_base}:amort",
                    notes=f"{project_name} | Saldo: {f.get('saldo_devedor', 0):,.0f}",
                ))

            if manut_sem_consumos > 0:
                entries.append(_make_entry(
                    entry_type="expense",
                    description=f"{label} — Condomínio e seguro",
                    amount=round(manut_sem_consumos, 2),
                    cat_key="condominio",
                    entry_date_str=entry_date_str,
                    project_name=project_name,
                    external_ref=f"{ref_base}:manut",
                ))

            if consumos_val > 0:
                consumos_key = "consumos_obra" if cat == "obra" else "consumos_holding"
                entries.append(_make_entry(
                    entry_type="expense",
                    description=f"{label} — Contas de consumo",
                    amount=consumos_val,
                    cat_key=consumos_key,
                    entry_date_str=entry_date_str,
                    project_name=project_name,
                    external_ref=f"{ref_base}:consumos",
                ))

        elif cat == "venda":
            venda_liq = f.get("venda_liquida", 0)
            comissao = f.get("comissao_venda", 0)
            payoff = f.get("payoff", 0)

            entries.append(_make_entry(
                entry_type="income",
                description="Venda — Receita líquida",
                amount=venda_liq,
                cat_key="receita",
                entry_date_str=entry_date_str,
                project_name=project_name,
                external_ref=f"{ref_base}:receita",
                notes=f"{project_name} | Bruto: {f.get('venda_bruta', 0):,.0f}",
            ))

            if comissao > 0:
                entries.append(_make_entry(
                    entry_type="expense",
                    description="Venda — Comissão mediação + IVA",
                    amount=comissao,
                    cat_key="comissao",
                    entry_date_str=entry_date_str,
                    project_name=project_name,
                    external_ref=f"{ref_base}:comissao",
                ))

            if payoff < 0:
                entries.append(_make_entry(
                    entry_type="expense",
                    description="Venda — Liquidação empréstimo",
                    amount=abs(payoff),
                    cat_key="payoff",
                    entry_date_str=entry_date_str,
                    project_name=project_name,
                    external_ref=f"{ref_base}:payoff",
                ))

        elif cat == "reembolso":
            componentes = f.get("componentes", [])
            for j, comp in enumerate(componentes):
                entries.append(_make_entry(
                    entry_type="income",
                    description=f"Reembolso IMT — {comp['nome']}",
                    amount=comp["valor"],
                    cat_key="reembolso_imt",
                    entry_date_str=entry_date_str,
                    project_name=project_name,
                    external_ref=f"{ref_base}:{j}",
                ))

    return entries


def _get_cfp_jwt(settings: Any) -> str:
    """Autentica no Supabase e retorna o JWT."""
    auth_url = f"{settings.cashflow_supabase_url}/auth/v1/token?grant_type=password"
    auth_resp = httpx.post(
        auth_url,
        headers={
            "apikey": settings.cashflow_supabase_key,
            "Content-Type": "application/json",
        },
        json={
            "email": settings.cashflow_user_email,
            "password": settings.cashflow_user_password,
        },
        timeout=15,
    )
    if auth_resp.status_code != 200:
        raise ValueError(f"Falha na autenticacao Cash Flow Pro: {auth_resp.text}")
    return auth_resp.json()["access_token"]


def list_cfp_projects() -> List[Dict[str, str]]:
    """Lista projectos do CashFlow Pro para o dropdown."""
    settings = get_settings()
    if not settings.cashflow_supabase_url or not settings.cashflow_company_id:
        return []

    jwt_token = _get_cfp_jwt(settings)
    url = (
        f"{settings.cashflow_supabase_url}/functions/v1/"
        f"make-server-36aa765f/integrations/projects"
        f"?company_id={settings.cashflow_company_id}"
    )
    resp = httpx.get(
        url,
        headers={"Authorization": f"Bearer {jwt_token}"},
        timeout=15,
    )
    if resp.status_code != 200:
        logger.warning(f"Falha ao listar projectos CFP: {resp.text}")
        return []
    return resp.json()


def get_deal_dates(deal_id: str) -> Optional[Dict[str, Any]]:
    """Busca datas reais de um Deal (CPCV, escritura, obra, venda)."""
    try:
        from src.database.db import get_session
        from src.database.models_v2 import Deal
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                return None
            return {
                "cpcv_date": deal.cpcv_date.date() if deal.cpcv_date else None,
                "escritura_date": deal.escritura_date.date() if deal.escritura_date else None,
                "obra_start_date": deal.obra_start_date.date() if deal.obra_start_date else None,
                "sale_date": deal.sale_date.date() if deal.sale_date else None,
                "title": deal.title,
            }
    except Exception:
        return None


def export_to_cashflow_pro(
    flows: List[Dict[str, Any]],
    model_id: str,
    project_name: str = "Simulacao",
    project_id: Optional[str] = None,
    cpcv_date: Optional[date] = None,
    deal_id: Optional[str] = None,
    escritura_date: Optional[date] = None,
    obra_start_date: Optional[date] = None,
    sale_date: Optional[date] = None,
    renovation_duration_months: int = 3,
    holding_months: int = 9,
) -> Dict[str, Any]:
    """Exporta fluxo de caixa M3 para o Cash Flow Pro via edge function.

    Args:
        flows: Lista de periodos do calc_cash_flow().
        model_id: ID do modelo financeiro.
        project_name: Nome do projecto para as descricoes.
        project_id: ID do projecto no CashFlow Pro (seleccionado pelo utilizador).
        cpcv_date: Data de assinatura do CPCV.
        deal_id: ID do deal (fallback para datas nao fornecidas).
        escritura_date: Data da escritura (editavel).
        obra_start_date: Data inicio da obra (editavel).
        sale_date: Data prevista de venda (editavel).
        renovation_duration_months: Meses de obra.
        holding_months: Total de meses (obra + holding).

    Returns:
        Dict com inserted_count, updated_count, skipped_count, errors.
    """
    settings = get_settings()

    if not settings.cashflow_supabase_url or not settings.cashflow_supabase_key:
        raise ValueError("CASHFLOW_SUPABASE_URL e CASHFLOW_SUPABASE_KEY nao configurados no .env")
    if not settings.cashflow_company_id:
        raise ValueError("CASHFLOW_COMPANY_ID nao configurado no .env")
    if not settings.cashflow_user_email or not settings.cashflow_user_password:
        raise ValueError("CASHFLOW_USER_EMAIL e CASHFLOW_USER_PASSWORD nao configurados no .env")

    # Resolver datas: parametro directo > deal > calculado
    deal_dates = None
    if deal_id:
        deal_dates = get_deal_dates(deal_id)

    if not escritura_date:
        escritura_date = deal_dates["escritura_date"] if deal_dates and deal_dates.get("escritura_date") else None
    if not obra_start_date:
        obra_start_date = deal_dates["obra_start_date"] if deal_dates and deal_dates.get("obra_start_date") else None
    if not sale_date:
        sale_date = deal_dates["sale_date"] if deal_dates and deal_dates.get("sale_date") else None

    if not cpcv_date:
        if deal_dates and deal_dates.get("cpcv_date"):
            cpcv_date = deal_dates["cpcv_date"]
        else:
            cpcv_date = date.today()

    if deal_dates and deal_dates.get("title") and project_name == "Simulacao":
        project_name = deal_dates["title"]

    dates = _calc_dates(
        cpcv_date=cpcv_date,
        escritura_date=escritura_date,
        obra_start_date=obra_start_date,
        sale_date=sale_date,
        renovation_duration_months=renovation_duration_months,
        holding_months=holding_months,
    )

    # Montar entries
    entries = _build_entries(flows, model_id, project_name, dates)
    if not entries:
        return {"inserted_count": 0, "updated_count": 0, "skipped_count": 0, "total_entries": 0}

    logger.info(
        f"A exportar {len(entries)} lancamentos para Cash Flow Pro "
        f"(CPCV: {cpcv_date}, Escritura: {dates['escritura']}, "
        f"Venda: {dates['venda']})"
    )

    # Autenticar e chamar edge function
    jwt_token = _get_cfp_jwt(settings)

    import_url = f"{settings.cashflow_supabase_url}/functions/v1/make-server-36aa765f/integrations/import"
    payload: Dict[str, Any] = {
        "company_id": settings.cashflow_company_id,
        "source": "imoia",
        "entries": entries,
    }
    if project_id:
        payload["project_id"] = project_id

    import_resp = httpx.post(
        import_url,
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if import_resp.status_code != 200:
        raise ValueError(f"Erro na importacao Cash Flow Pro: {import_resp.text}")

    data = import_resp.json()
    inserted = data.get("inserted", 0)
    updated = data.get("updated", 0)
    skipped = data.get("skipped", 0)

    logger.info(f"Cash Flow Pro: {inserted} inseridos, {updated} actualizados, {skipped} ignorados")

    return {
        "inserted_count": inserted,
        "updated_count": updated,
        "skipped_count": skipped,
        "errors": data.get("errors", []),
        "total_entries": len(entries),
        "dates": {
            "cpcv": cpcv_date.isoformat(),
            "escritura": dates["escritura"].isoformat(),
            "obra_inicio": dates["obra_inicio"].isoformat(),
            "venda": dates["venda"].isoformat(),
        },
    }
