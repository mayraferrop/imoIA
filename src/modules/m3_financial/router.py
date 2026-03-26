"""Endpoints M3 — Motor Financeiro.

POST /api/v1/financial/                        — Criar modelo financeiro
POST /api/v1/financial/scenarios/{property_id}  — Criar 3 cenarios automaticos
GET  /api/v1/financial/{model_id}              — Obter modelo
GET  /api/v1/financial/property/{property_id}  — Listar modelos de uma propriedade
POST /api/v1/financial/simulate                 — Simular sem persistir
POST /api/v1/financial/mao                     — Calcular MAO (regra 70%)
POST /api/v1/financial/floor-price             — Calcular preco minimo de venda
POST /api/v1/financial/quick-imt               — Calculo rapido de IMT/IS
GET  /api/v1/financial/{model_id}/cash-flow    — Fluxo de caixa mensal
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException

from src.modules.m3_financial.calculator import (
    FinancialCalculator,
    FinancialInput,
)
from src.modules.m3_financial.schemas import (
    FinancialModelCreateRequest,
    FloorPriceRequest,
    MAORequest,
    QuickIMTRequest,
    ScenarioSaveRequest,
)
from src.modules.m3_financial.service import FinancialService
from src.modules.m3_financial.tax_tables import (
    IMT_TABLE_PT_HPP,
    IMT_TABLE_PT_INVESTMENT,
    IMPOSTO_SELO_PCT,
    ITBI_DEFAULT_PCT,
)

router = APIRouter()
service = FinancialService()
calculator = FinancialCalculator()


@router.post("/", summary="Criar modelo financeiro")
async def create_financial_model(
    property_id: str, request: FinancialModelCreateRequest
) -> Dict[str, Any]:
    """Cria um modelo financeiro completo para uma propriedade."""
    try:
        result = service.create_model(property_id, request.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/scenarios/{property_id}", summary="Criar 3 cenarios automaticos"
)
async def create_scenarios(
    property_id: str, request: FinancialModelCreateRequest
) -> Dict[str, Any]:
    """Cria cenarios base, optimista e pessimista automaticamente."""
    try:
        return service.create_scenarios(property_id, request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/debug-supabase", summary="Debug Supabase connection")
async def debug_supabase() -> Dict[str, Any]:
    """Debug: verifica se o backend consegue ligar ao Supabase REST."""
    import os
    from src.database.supabase_rest import _url, _key, _get
    url = _url()
    key = _key()
    try:
        result = _get("financial_models", "select=id&limit=1")
        return {"url": url[:30] + "..." if url else "EMPTY", "key_len": len(key), "test_result": result}
    except Exception as e:
        return {"url": url[:30] + "..." if url else "EMPTY", "key_len": len(key), "error": str(e)}


@router.get("/scenarios", summary="Listar cenarios salvos")
async def list_scenarios() -> list:
    """Lista todos os cenarios financeiros salvos via Supabase REST."""
    from src.database.supabase_rest import list_scenarios as supa_list
    return supa_list()


@router.get("/cashflow-pro/projects", summary="Listar projectos CashFlow Pro")
async def list_cashflow_pro_projects() -> List[Dict[str, str]]:
    """Lista projectos do CashFlow Pro para o dropdown de exportacao."""
    try:
        from src.modules.m3_financial.cashflow_export import list_cfp_projects
        return list_cfp_projects()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar projectos: {str(e)}")


@router.get("/{model_id}", summary="Obter modelo financeiro")
async def get_financial_model(model_id: str) -> Dict[str, Any]:
    """Retorna detalhe de um modelo financeiro."""
    result = service.get_model(model_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Modelo nao encontrado")
    return result


@router.get(
    "/property/{property_id}",
    summary="Listar modelos de uma propriedade",
)
async def list_by_property(property_id: str) -> list:
    """Lista todos os modelos financeiros de uma propriedade."""
    return service.list_by_property(property_id)


@router.delete("/{model_id}", summary="Excluir modelo financeiro")
async def delete_financial_model(model_id: str) -> Dict[str, Any]:
    """Exclui modelo financeiro e dados associados (condições, projecções)."""
    try:
        result = service.delete_model(model_id)
        if not result:
            raise HTTPException(status_code=404, detail="Modelo não encontrado")
        return {"deleted": True, "model_id": model_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulate", summary="Simular modelo financeiro sem persistir")
async def simulate_financial_model(
    request: FinancialModelCreateRequest,
) -> Dict[str, Any]:
    """Calcula modelo financeiro completo sem criar Property nem persistir.

    Util para simulacoes rapidas no dashboard sem poluir a BD.
    """
    valid_fields = {f.name for f in dataclasses.fields(FinancialInput)}
    filtered = {k: v for k, v in request.model_dump().items() if k in valid_fields}
    fin_input = FinancialInput(**filtered)
    result = calculator.calculate(fin_input)
    cash_flow = calculator.calc_cash_flow(fin_input, result)
    # Injectar TIR calculada pelo cash flow no resultado
    tir = cash_flow.get("tir_anual_pct", 0)
    result.tir_anual_pct = tir
    # Recalcular go/no-go com base na TIR (mais preciso que ROI CAGR)
    if tir > 0:
        if tir >= fin_input.roi_target_pct:
            result.go_nogo = "go"
            result.meets_criteria = True
        elif tir >= fin_input.roi_target_pct * 0.7:
            result.go_nogo = "marginal"
            result.meets_criteria = False
        else:
            result.go_nogo = "no_go"
            result.meets_criteria = False
    return {
        "model_id": None,
        **dataclasses.asdict(result),
        "cash_flow": cash_flow,
    }


@router.post("/mao", summary="Calcular MAO — Maximum Allowable Offer")
async def calculate_mao(request: MAORequest) -> Dict[str, Any]:
    """Regra dos 70%: MAO = ARV x 0.70 - Custo de Obra."""
    return service.calculate_mao(request.arv, request.renovation_total)


@router.post("/floor-price", summary="Calcular preco minimo de venda")
async def calculate_floor_price(
    request: FloorPriceRequest,
) -> Dict[str, Any]:
    """Preco minimo para atingir o ROI target."""
    return service.calculate_floor_price(
        request.total_investment,
        request.roi_target_pct,
        request.comissao_venda_pct,
    )


@router.post("/quick-imt", summary="Calculo rapido de IMT")
async def quick_imt(request: QuickIMTRequest) -> Dict[str, Any]:
    """Calcula IMT sem criar modelo completo. Util para triagem rapida."""
    if request.country == "PT":
        table = IMT_TABLE_PT_HPP if request.is_hpp else IMT_TABLE_PT_INVESTMENT
        imt = calculator.calc_imt(request.value, table)
        is_val = round(request.value * IMPOSTO_SELO_PCT, 2)
        return {
            "valor": request.value,
            "imt": imt,
            "imposto_selo": is_val,
            "total_impostos": round(imt + is_val, 2),
            "tabela": "HPP" if request.is_hpp else "Investimento",
            "nota": "Valores OE2026",
        }
    elif request.country == "BR":
        itbi = round(request.value * ITBI_DEFAULT_PCT, 2)
        return {
            "valor": request.value,
            "itbi": itbi,
            "itbi_pct": ITBI_DEFAULT_PCT * 100,
            "nota": "ITBI default 3% — varia por municipio",
        }
    raise HTTPException(status_code=400, detail="Pais nao suportado")


@router.get(
    "/{model_id}/cash-flow", summary="Fluxo de caixa mensal"
)
async def get_cash_flow(model_id: str) -> Dict[str, Any]:
    """Retorna o fluxo de caixa mes a mes.

    Mostra quanto sai do bolso em cada periodo,
    o pico maximo de capital necessario, e o saldo final.
    Equivalente a aba '02_Fluxo' do Excel.
    """
    from src.database.db import get_session
    from src.database.models_v2 import FinancialModel

    with get_session() as session:
        model = session.get(FinancialModel, model_id)
        if model is None:
            raise HTTPException(
                status_code=404, detail="Modelo nao encontrado"
            )

        # Reconstruir input a partir do modelo persistido
        inp = FinancialInput(
            purchase_price=model.purchase_price or 0,
            country=model.country or "PT",
            entity_structure=model.entity_structure or "pf_jp",
            imt_resale_regime=model.imt_resale_regime or "none",
            renovation_budget=model.renovation_budget,
            renovation_contingency_pct=model.renovation_contingency_pct,
            renovation_duration_months=model.renovation_duration_months,
            financing_type=model.financing_type or "cash",
            loan_amount=model.loan_amount,
            interest_rate_pct=model.interest_rate_pct,
            loan_term_months=model.loan_term_months,
            estimated_sale_price=model.estimated_sale_price,
            comissao_venda_pct=model.comissao_venda_pct,
            additional_holding_months=max(
                model.holding_months - model.renovation_duration_months, 0
            ),
            monthly_condominio=model.monthly_condominio,
            annual_insurance=model.monthly_insurance * 12,
            monthly_consumos=getattr(model, "monthly_consumos", 0) or 0,
            comissao_compra_pct=model.comissao_compra_pct,
        )

        # Reconstruir result parcial necessario para cash flow
        from src.modules.m3_financial.calculator import FinancialResult

        res = FinancialResult(
            entity_structure=model.entity_structure or "pf_jp",
            imt=model.imt,
            imposto_selo=model.imposto_selo,
            notario_registo=model.notario_registo,
            comissao_compra=model.comissao_compra,
            total_acquisition_cost_2=model.total_acquisition_cost_2,
            bank_fees=model.bank_fees,
            interest_rate_pct=model.interest_rate_pct,
            loan_amount=model.loan_amount,
            monthly_payment=model.monthly_payment,
            holding_months=model.holding_months,
        )

        return calculator.calc_cash_flow(inp, res)


@router.post("/{model_id}/export-cashflow", summary="Exportar para CashFlow Pro")
async def export_to_cashflow_pro(
    model_id: str,
    project_id: Optional[str] = Body(None, embed=True),
) -> Dict[str, Any]:
    """Exporta fluxo de caixa para o Cash Flow Pro externo."""
    try:
        from src.modules.m3_financial.cashflow_export import export_to_cashflow_pro as do_export

        # Buscar modelo e recalcular cash flow
        model_data = service.get_model(model_id)
        if not model_data:
            raise HTTPException(status_code=404, detail="Modelo nao encontrado")

        # Reconstruir input e calcular cash flow
        valid_fields = {f.name for f in dataclasses.fields(FinancialInput)}
        filtered = {k: v for k, v in model_data.items() if k in valid_fields}
        fin_input = FinancialInput(**filtered)
        result = calculator.calculate(fin_input)
        cash_flow = calculator.calc_cash_flow(fin_input, result)

        # Buscar datas das payment conditions
        projections = service.get_projections(model_id)
        cpcv_date = None
        escritura_date = None
        if projections and projections.get("payment_condition"):
            from datetime import date as date_type
            pc = projections["payment_condition"]
            if pc.get("cpcv_date"):
                cpcv_date = date_type.fromisoformat(pc["cpcv_date"][:10])
            if pc.get("escritura_date"):
                escritura_date = date_type.fromisoformat(pc["escritura_date"][:10])

        export_result = do_export(
            flows=cash_flow.get("flows", []),
            model_id=model_id,
            project_name=model_data.get("scenario_name", "ImoIA"),
            project_id=project_id,
            cpcv_date=cpcv_date,
            escritura_date=escritura_date,
            renovation_duration_months=fin_input.renovation_duration_months,
            holding_months=result.holding_months,
        )
        return export_result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na exportacao: {str(e)}")


@router.post("/save-scenario", summary="Salvar cenario com condicoes de pagamento")
async def save_scenario(request: ScenarioSaveRequest) -> Dict[str, Any]:
    """Salva cenario financeiro completo via Supabase REST.

    Cria FinancialModel + PaymentCondition + CashflowProjection.
    """
    try:
        from uuid import uuid4
        from src.database import supabase_rest as supa

        data = request.model_dump()
        property_id = data.pop("property_id", None)
        cpcv_date_str = data.pop("cpcv_date", "")
        escritura_date_str = data.pop("escritura_date", "")
        tranches_data = data.pop("tranches", [])
        if isinstance(tranches_data, list):
            tranches_data = [t if isinstance(t, dict) else t for t in tranches_data]

        if not property_id:
            raise ValueError("Seleccione um imóvel para vincular o cenário.")

        tenant_id = supa.ensure_tenant()

        # Calcular modelo financeiro
        cpcv_parcelas = []
        for t in tranches_data:
            if isinstance(t, dict):
                cpcv_parcelas.append({"pct": t.get("pct", 0), "dias": t.get("dias_apos_cpcv", 0)})

        valid_fields = {f.name for f in dataclasses.fields(FinancialInput)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        if cpcv_parcelas:
            filtered["cpcv_parcelas"] = cpcv_parcelas

        fin_input = FinancialInput(**filtered)
        result = calculator.calculate(fin_input)
        cash_flow = calculator.calc_cash_flow(fin_input, result)

        tir = cash_flow.get("tir_anual_pct", 0)
        result.tir_anual_pct = tir
        if tir > 0 and tir >= fin_input.roi_target_pct:
            result.go_nogo = "go"
            result.meets_criteria = True
        elif tir > 0 and tir >= fin_input.roi_target_pct * 0.7:
            result.go_nogo = "marginal"
        elif tir > 0:
            result.go_nogo = "no_go"

        result_dict = dataclasses.asdict(result)
        model_id = str(uuid4())

        # Persistir no Supabase via REST
        model_row = {
            "id": model_id,
            "tenant_id": tenant_id,
            "property_id": property_id,
            "scenario_name": data.get("scenario_name", "base"),
            "status": "calculated",
            **{k: v for k, v in result_dict.items()
               if k not in ("warnings", "holding_detail", "bank_fees_detail")
               and not isinstance(v, (dict, list))},
        }
        supa.save_financial_model(model_row)

        payment_id = str(uuid4())
        supa.save_payment_condition({
            "id": payment_id,
            "tenant_id": tenant_id,
            "financial_model_id": model_id,
            "cpcv_date": cpcv_date_str or None,
            "escritura_date": escritura_date_str or None,
            "tranches": tranches_data,
        })

        flows = cash_flow.get("flows", [])
        projections = []
        for i, f in enumerate(flows):
            projections.append({
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "financial_model_id": model_id,
                "mes": i,
                "periodo_label": f.get("label", ""),
                "categoria": f.get("categoria", ""),
                "saidas_projetado": f.get("saidas", f.get("aquisicao", 0)),
                "pmt_projetado": f.get("pmt", 0),
                "manutencao_projetado": f.get("manut", 0),
                "payoff_projetado": abs(f.get("payoff", 0)) if f.get("payoff", 0) < 0 else 0,
                "fluxo_projetado": f.get("fluxo", 0),
                "acumulado_projetado": f.get("acumulado", 0),
            })
        supa.save_projections(projections)

        return {
            "model_id": model_id,
            "payment_condition_id": payment_id,
            "projections_count": len(flows),
            "property_id": property_id,
            **result_dict,
            "cash_flow": cash_flow,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar: {str(e)}")


@router.get("/{model_id}/projections", summary="Buscar projecao financeira")
async def get_projections(model_id: str) -> Dict[str, Any]:
    """Retorna projecao financeira mensal (projetado vs real) via Supabase REST."""
    from src.database.supabase_rest import get_projections as supa_proj
    result = supa_proj(model_id)
    if not result or not result.get("projections"):
        raise HTTPException(status_code=404, detail="Modelo nao encontrado")
    return result
