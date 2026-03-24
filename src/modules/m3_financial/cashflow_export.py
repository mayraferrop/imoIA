"""Exportacao de fluxo de caixa M3 para o Cash Flow Pro (Supabase).

Envia os lancamentos do modelo financeiro como entries no Cash Flow Pro
via RPC import_cash_flow_entries. Usa anon key + autenticacao do utilizador.

Logica de datas:
  - CPCV: data da assinatura (cpcv_date do Deal, ou input manual)
  - Escritura: cpcv_date + 60-90 dias (ou escritura_date do Deal)
  - Obra mes 1: dia seguinte a escritura (ou obra_start_date do Deal)
  - Meses seguintes: +30 dias por mes
  - Venda: fim da obra + holding months (ou sale_date do Deal)

Deduplicacao via external_ref (formato: imoia:{model_id}:{periodo}).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger

from src.config import get_settings


def _calc_dates(
    cpcv_date: date,
    escritura_date: Optional[date],
    obra_start_date: Optional[date],
    sale_date: Optional[date],
    renovation_duration_months: int,
    holding_months: int,
) -> Dict[str, date]:
    """Calcula todas as datas do cronograma a partir da data do CPCV.

    Returns:
        Dict com chaves: cpcv, escritura, obra_inicio, meses (lista), venda.
    """
    # Escritura: 60 dias apos CPCV (ou data real do Deal)
    esc = escritura_date or (cpcv_date + timedelta(days=60))

    # Inicio obra: dia seguinte a escritura (ou data real)
    obra_ini = obra_start_date or (esc + timedelta(days=1))

    # Meses de obra + holding
    meses: List[date] = []
    for m in range(holding_months):
        meses.append(obra_ini + timedelta(days=30 * m))

    # Venda: fim do ultimo mes (ou data real)
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
    """
    entries: List[Dict[str, Any]] = []
    mes_idx = 0  # indice para os meses

    for f in flows:
        label = f.get("label", "")
        cat = f.get("categoria", "")
        ref_base = f"imoia:{model_id}:{label.lower().replace(' ', '_')}"

        # Determinar data deste periodo
        if label == "CPCV":
            entry_date = dates["cpcv"]
        elif "Escritura" in label:
            entry_date = dates["escritura"]
        elif label == "VENDA":
            entry_date = dates["venda"]
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
                    entries.append({
                        "entry_type": "expense",
                        "description": f"{label} — {comp['nome']}",
                        "amount": comp["valor"],
                        "currency": "EUR",
                        "main_category": "Aquisição",
                        "subcategory": comp["nome"],
                        "entry_date": entry_date_str,
                        "due_date": entry_date_str,
                        "payment_status": "previsão",
                        "notes": project_name,
                        "external_ref": f"{ref_base}:{j}",
                    })
            else:
                entries.append({
                    "entry_type": "expense",
                    "description": f"{label} — Sinal",
                    "amount": f.get("aquisicao", 0),
                    "currency": "EUR",
                    "main_category": "Aquisição",
                    "subcategory": "Sinal CPCV",
                    "entry_date": entry_date_str,
                    "due_date": entry_date_str,
                    "payment_status": "previsão",
                    "notes": project_name,
                    "external_ref": ref_base,
                })

        elif cat in ("obra", "holding"):
            obra_val = f.get("obra", 0)
            pmt_val = f.get("pmt", 0)
            manut_val = f.get("manut", 0)

            if obra_val > 0:
                entries.append({
                    "entry_type": "expense",
                    "description": f"{label} — Obra (renovacao)",
                    "amount": obra_val,
                    "currency": "EUR",
                    "main_category": "Obra",
                    "subcategory": "Renovação",
                    "entry_date": entry_date_str,
                    "due_date": entry_date_str,
                    "payment_status": "previsão",
                    "notes": project_name,
                    "external_ref": f"{ref_base}:obra",
                })

            if pmt_val > 0:
                juros = f.get("juros", 0)
                amort = f.get("amort", 0)
                entries.append({
                    "entry_type": "expense",
                    "description": f"{label} — Prestacao (juros {juros:.0f} + amort {amort:.0f})",
                    "amount": pmt_val,
                    "currency": "EUR",
                    "main_category": "Financiamento",
                    "subcategory": "Prestação hipoteca",
                    "entry_date": entry_date_str,
                    "due_date": entry_date_str,
                    "payment_status": "previsão",
                    "notes": f"{project_name} | Saldo: {f.get('saldo_devedor', 0):,.0f}",
                    "external_ref": f"{ref_base}:pmt",
                })

            if manut_val > 0:
                entries.append({
                    "entry_type": "expense",
                    "description": f"{label} — Manutencao",
                    "amount": manut_val,
                    "currency": "EUR",
                    "main_category": "Manutenção",
                    "subcategory": "Condomínio e seguro",
                    "entry_date": entry_date_str,
                    "due_date": entry_date_str,
                    "payment_status": "previsão",
                    "notes": project_name,
                    "external_ref": f"{ref_base}:manut",
                })

        elif cat == "venda":
            venda_liq = f.get("venda_liquida", 0)
            comissao = f.get("comissao_venda", 0)
            payoff = f.get("payoff", 0)

            entries.append({
                "entry_type": "income",
                "description": f"Venda — Receita liquida",
                "amount": venda_liq,
                "currency": "EUR",
                "main_category": "Venda",
                "subcategory": "Receita venda",
                "entry_date": entry_date_str,
                "due_date": entry_date_str,
                "payment_status": "previsão",
                "notes": f"{project_name} | Bruto: {f.get('venda_bruta', 0):,.0f}",
                "external_ref": f"{ref_base}:receita",
            })

            if comissao > 0:
                entries.append({
                    "entry_type": "expense",
                    "description": f"Venda — Comissao mediacao + IVA",
                    "amount": comissao,
                    "currency": "EUR",
                    "main_category": "Venda",
                    "subcategory": "Comissão mediação",
                    "entry_date": entry_date_str,
                    "due_date": entry_date_str,
                    "payment_status": "previsão",
                    "notes": project_name,
                    "external_ref": f"{ref_base}:comissao",
                })

            if payoff < 0:
                entries.append({
                    "entry_type": "expense",
                    "description": f"Venda — Liquidacao emprestimo",
                    "amount": abs(payoff),
                    "currency": "EUR",
                    "main_category": "Financiamento",
                    "subcategory": "Payoff hipoteca",
                    "entry_date": entry_date_str,
                    "due_date": entry_date_str,
                    "payment_status": "previsão",
                    "notes": project_name,
                    "external_ref": f"{ref_base}:payoff",
                })

    return entries


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
    cpcv_date: Optional[date] = None,
    deal_id: Optional[str] = None,
    escritura_date: Optional[date] = None,
    obra_start_date: Optional[date] = None,
    sale_date: Optional[date] = None,
    renovation_duration_months: int = 3,
    holding_months: int = 9,
) -> Dict[str, Any]:
    """Exporta fluxo de caixa M3 para o Cash Flow Pro via RPC.

    Datas podem ser passadas directamente (editadas pelo utilizador no modal)
    ou buscadas do Deal. Prioridade: parametro directo > deal > calculado.

    Args:
        flows: Lista de periodos do calc_cash_flow().
        model_id: ID do modelo financeiro.
        project_name: Nome do projecto para as descricoes.
        cpcv_date: Data de assinatura do CPCV.
        deal_id: ID do deal (fallback para datas nao fornecidas).
        escritura_date: Data da escritura (editavel).
        obra_start_date: Data inicio da obra (editavel).
        sale_date: Data prevista de venda (editavel).
        renovation_duration_months: Meses de obra.
        holding_months: Total de meses (obra + holding).

    Returns:
        Dict com inserted_count, skipped_count, entries_preview.
    """
    settings = get_settings()

    if not settings.cashflow_supabase_url or not settings.cashflow_supabase_key:
        raise ValueError("CASHFLOW_SUPABASE_URL e CASHFLOW_SUPABASE_KEY nao configurados no .env")
    if not settings.cashflow_company_id:
        raise ValueError("CASHFLOW_COMPANY_ID nao configurado no .env")
    if not settings.cashflow_user_email or not settings.cashflow_user_password:
        raise ValueError("CASHFLOW_USER_EMAIL e CASHFLOW_USER_PASSWORD nao configurados no .env")

    try:
        from supabase import create_client
    except ImportError:
        raise ValueError("Pacote 'supabase' nao instalado. Execute: pip install supabase")

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
        return {"inserted_count": 0, "skipped_count": 0, "total_entries": 0}

    logger.info(
        f"A exportar {len(entries)} lancamentos para Cash Flow Pro "
        f"(CPCV: {cpcv_date}, Escritura: {dates['escritura']}, "
        f"Venda: {dates['venda']})"
    )

    # Conectar ao Supabase
    supabase = create_client(settings.cashflow_supabase_url, settings.cashflow_supabase_key)
    supabase.auth.sign_in_with_password({
        "email": settings.cashflow_user_email,
        "password": settings.cashflow_user_password,
    })

    # Chamar RPC
    result = supabase.rpc("import_cash_flow_entries", {
        "p_company_id": settings.cashflow_company_id,
        "p_entries": entries,
    }).execute()

    data = result.data if result.data else {}
    inserted = data.get("inserted_count", 0)
    skipped = data.get("skipped_count", 0)

    logger.info(f"Cash Flow Pro: {inserted} inseridos, {skipped} ignorados")

    return {
        "inserted_count": inserted,
        "skipped_count": skipped,
        "skipped_refs": data.get("skipped_refs", []),
        "total_entries": len(entries),
        "dates": {
            "cpcv": cpcv_date.isoformat(),
            "escritura": dates["escritura"].isoformat(),
            "obra_inicio": dates["obra_inicio"].isoformat(),
            "venda": dates["venda"].isoformat(),
        },
    }
