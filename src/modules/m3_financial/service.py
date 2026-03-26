"""Servico M3 — orquestra calculos financeiros e persiste resultados."""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import select

from datetime import datetime

from src.database.db import get_session
from src.database.models_v2 import (
    CashflowProjection,
    FinancialModel,
    PaymentCondition,
    Property,
    Tenant,
)
from src.modules.m3_financial.calculator import (
    FinancialCalculator,
    FinancialInput,
    FinancialResult,
)


class FinancialService:
    """Servico de negocio para o modulo M3."""

    def __init__(self) -> None:
        self.calculator = FinancialCalculator()

    def create_model(
        self,
        property_id: str,
        input_data: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cria um modelo financeiro para uma propriedade.

        Args:
            property_id: ID da Property.
            input_data: Dados de entrada para o calculo.
            tenant_id: ID do tenant (se None, usa default).

        Returns:
            Dict com resultado completo do calculo + id do modelo.
        """
        with get_session() as session:
            prop = session.get(Property, property_id)
            if prop is None:
                raise ValueError(f"Property {property_id} nao encontrada")

            if tenant_id is None:
                tenant_id = prop.tenant_id

            # Preencher input com dados da propriedade se nao fornecidos
            if "purchase_price" not in input_data or input_data["purchase_price"] == 0:
                if prop.asking_price:
                    input_data["purchase_price"] = prop.asking_price

            if "country" not in input_data and prop.country:
                input_data["country"] = prop.country

            # Filtrar campos validos para FinancialInput
            valid_fields = {f.name for f in dataclasses.fields(FinancialInput)}
            filtered = {k: v for k, v in input_data.items() if k in valid_fields}

            fin_input = FinancialInput(**filtered)
            result = self.calculator.calculate(fin_input)

            # Persistir como FinancialModel
            model = FinancialModel(
                id=str(uuid4()),
                tenant_id=tenant_id,
                property_id=property_id,
                scenario_name=fin_input.scenario_name,
                country=fin_input.country,
                entity_structure=fin_input.entity_structure,
                imt_resale_regime=fin_input.imt_resale_regime,
                purchase_price=result.purchase_price,
                imt=result.imt,
                imposto_selo=result.imposto_selo,
                notario_registo=result.notario_registo,
                comissao_compra=result.comissao_compra,
                imt_2=result.imt_2,
                imt_2_original=result.imt_2_original,
                is_2=result.is_2,
                escritura_2=result.escritura_2,
                total_acquisition_cost_2=result.total_acquisition_cost_2,
                total_acquisition_cost=result.total_acquisition_cost,
                itbi=result.itbi,
                escritura_registro_br=result.escritura_registro_br,
                renovation_budget=result.renovation_budget,
                renovation_contingency_pct=fin_input.renovation_contingency_pct,
                renovation_total=result.renovation_total,
                renovation_duration_months=fin_input.renovation_duration_months,
                financing_type=result.financing_type,
                loan_amount=result.loan_amount,
                ltv_pct=result.ltv_pct,
                interest_rate_pct=result.interest_rate_pct,
                monthly_payment=result.monthly_payment,
                total_interest=result.total_interest,
                bank_fees=result.bank_fees,
                bank_fees_detail=result.bank_fees_detail,
                holding_months=result.holding_months,
                total_holding_cost=result.total_holding_cost,
                estimated_sale_price=result.estimated_sale_price,
                comissao_venda_pct=fin_input.comissao_venda_pct,
                comissao_venda=result.comissao_venda,
                total_sale_costs=result.total_sale_costs,
                deductible_expenses=result.deductible_expenses,
                taxable_gain_50pct=result.taxable_gain,
                estimated_irs_rate_pct=result.estimated_irs_rate_pct,
                capital_gains_tax_pt=result.capital_gains_detail.get("imposto", 0) if result.entity_structure == "pf_only" else 0,
                capital_gains_tax=result.capital_gains_tax,
                irc_taxable_income=result.irc_taxable_income,
                irc_rate_pct=result.irc_rate_pct,
                irc_estimated=result.irc_estimated,
                derrama_estimated=result.derrama_estimated,
                total_corporate_tax=result.total_corporate_tax,
                total_investment=result.total_investment,
                total_costs=result.total_costs,
                gross_profit=result.gross_profit,
                net_profit=result.net_profit,
                roi_pct=result.roi_pct,
                roi_simple_pct=result.roi_simple_pct,
                roi_annualized_pct=result.roi_annualized_pct,
                cash_on_cash_return_pct=result.cash_on_cash_return_pct,
                moic=result.moic,
                payoff_at_sale=result.payoff_at_sale,
                caixa_closing=result.caixa_closing,
                mao=result.mao,
                floor_price=result.floor_price,
                margin_of_safety_pct=result.margin_of_safety_pct,
                roi_target_pct=fin_input.roi_target_pct,
                meets_criteria=result.meets_criteria,
                go_nogo=result.go_nogo,
                raw_calculations=result.capital_gains_detail,
                status="calculated",
            )
            session.add(model)
            session.flush()

            logger.info(
                f"FinancialModel {model.id} criado para Property {property_id} "
                f"— cenario={fin_input.scenario_name}, ROI={result.roi_pct}%, "
                f"go_nogo={result.go_nogo}"
            )

            return {
                "model_id": model.id,
                **self._result_to_dict(result),
            }

    def create_scenarios(
        self,
        property_id: str,
        base_input: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cria 3 cenarios automaticos: base, optimista, pessimista."""
        scenarios: Dict[str, Any] = {}

        # Base
        base_input["scenario_name"] = "base"
        scenarios["base"] = self.create_model(
            property_id, dict(base_input), tenant_id
        )

        # Optimista: -10% custos obra, +10% venda, -1 mes holding
        opt_input = dict(base_input)
        opt_input["scenario_name"] = "optimista"
        opt_input["renovation_budget"] = base_input.get(
            "renovation_budget", 0
        ) * 0.90
        opt_input["estimated_sale_price"] = base_input.get(
            "estimated_sale_price", 0
        ) * 1.10
        opt_input["additional_holding_months"] = max(
            base_input.get("additional_holding_months", 3) - 1, 1
        )
        scenarios["optimista"] = self.create_model(
            property_id, opt_input, tenant_id
        )

        # Pessimista: +20% custos obra, -10% venda, +3 meses holding
        pess_input = dict(base_input)
        pess_input["scenario_name"] = "pessimista"
        pess_input["renovation_budget"] = base_input.get(
            "renovation_budget", 0
        ) * 1.20
        pess_input["estimated_sale_price"] = base_input.get(
            "estimated_sale_price", 0
        ) * 0.90
        pess_input["additional_holding_months"] = base_input.get(
            "additional_holding_months", 3
        ) + 3
        scenarios["pessimista"] = self.create_model(
            property_id, pess_input, tenant_id
        )

        return scenarios

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Busca um modelo financeiro por ID."""
        with get_session() as session:
            model = session.get(FinancialModel, model_id)
            if model is None:
                return None
            return self._model_to_dict(model)

    def list_by_property(self, property_id: str) -> list:
        """Lista todos os modelos financeiros de uma propriedade."""
        with get_session() as session:
            models = session.execute(
                select(FinancialModel)
                .where(FinancialModel.property_id == property_id)
                .order_by(FinancialModel.created_at.desc())
            ).scalars().all()
            return [self._model_to_dict(m) for m in models]

    def calculate_mao(self, arv: float, renovation_total: float) -> Dict[str, Any]:
        """Calcula MAO (Maximum Allowable Offer) — regra dos 70%."""
        mao_70 = max(arv * 0.70 - renovation_total, 0)
        mao_65 = max(arv * 0.65 - renovation_total, 0)
        mao_60 = max(arv * 0.60 - renovation_total, 0)
        return {
            "arv": arv,
            "renovation_total": renovation_total,
            "mao_70pct": round(mao_70, 2),
            "mao_65pct": round(mao_65, 2),
            "mao_60pct": round(mao_60, 2),
            "nota": "70% mercados activos, 65% normais, 60% lentos",
        }

    def calculate_floor_price(
        self,
        total_investment: float,
        roi_target_pct: float,
        comissao_venda_pct: float = 6.15,
    ) -> Dict[str, Any]:
        """Calcula preco minimo de venda para atingir ROI target."""
        target_profit = total_investment * (roi_target_pct / 100)
        net_of_commission = 1 - (comissao_venda_pct / 100)
        floor = (
            (total_investment + target_profit) / net_of_commission
            if net_of_commission > 0
            else 0
        )
        return {
            "total_investment": total_investment,
            "roi_target_pct": roi_target_pct,
            "floor_price": round(floor, 2),
            "profit_at_floor": round(target_profit, 2),
        }

    def save_scenario_with_conditions(
        self,
        request_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Salva cenario financeiro com condicoes de pagamento e gera projecao.

        Fluxo:
        1. Cria Property se nao existir
        2. Cria FinancialModel com calculo completo
        3. Cria PaymentCondition com tranches
        4. Gera e persiste CashflowProjection (fluxo mensal)
        """
        property_id = request_data.pop("property_id", None)
        cpcv_date_str = request_data.pop("cpcv_date", "")
        escritura_date_str = request_data.pop("escritura_date", "")
        tranches_data = request_data.pop("tranches", [])

        with get_session() as session:
            # 1. Garantir tenant
            tenant = session.execute(
                select(Tenant).where(Tenant.slug == "default")
            ).scalar_one_or_none()
            tenant_id = tenant.id if tenant else None

            # 2. Criar Property se necessario
            if not property_id:
                prop = Property(
                    tenant_id=tenant_id,
                    property_type="apartamento",
                    asking_price=request_data.get("purchase_price"),
                    municipality=request_data.get("municipality", "Simulacao"),
                    source="manual",
                    status="lead",
                    notes="Criado pelo simulador M3 com condicoes de pagamento",
                )
                session.add(prop)
                session.flush()
                property_id = prop.id

            # 3. Calcular modelo financeiro
            # Converter tranches para cpcv_parcelas
            cpcv_parcelas = []
            for t in tranches_data:
                if isinstance(t, dict):
                    cpcv_parcelas.append({
                        "pct": t.get("pct", 0),
                        "dias": t.get("dias_apos_cpcv", 0),
                    })

            valid_fields = {f.name for f in dataclasses.fields(FinancialInput)}
            filtered = {k: v for k, v in request_data.items() if k in valid_fields}
            if cpcv_parcelas:
                filtered["cpcv_parcelas"] = cpcv_parcelas

            fin_input = FinancialInput(**filtered)
            result = self.calculator.calculate(fin_input)
            cash_flow = self.calculator.calc_cash_flow(fin_input, result)

            # Injectar TIR
            tir = cash_flow.get("tir_anual_pct", 0)
            result.tir_anual_pct = tir
            if tir > 0 and tir >= fin_input.roi_target_pct:
                result.go_nogo = "go"
                result.meets_criteria = True
            elif tir > 0 and tir >= fin_input.roi_target_pct * 0.7:
                result.go_nogo = "marginal"
            elif tir > 0:
                result.go_nogo = "no_go"

            # 4. Persistir FinancialModel
            result_dict = dataclasses.asdict(result)
            model = FinancialModel(
                tenant_id=tenant_id,
                property_id=property_id,
                **{
                    k: v
                    for k, v in result_dict.items()
                    if hasattr(FinancialModel, k) and k not in ("warnings",)
                },
            )
            model.scenario_name = request_data.get("scenario_name", "base")
            model.status = "calculated"
            session.add(model)
            session.flush()

            # 5. Persistir PaymentCondition
            cpcv_dt = datetime.fromisoformat(cpcv_date_str) if cpcv_date_str else datetime.now()
            escrit_dt = datetime.fromisoformat(escritura_date_str) if escritura_date_str else datetime.now()

            payment_cond = PaymentCondition(
                tenant_id=tenant_id,
                financial_model_id=model.id,
                cpcv_date=cpcv_dt,
                escritura_date=escrit_dt,
                tranches=[t if isinstance(t, dict) else t.dict() for t in tranches_data],
            )
            session.add(payment_cond)

            # 6. Persistir CashflowProjection (cada linha do fluxo)
            flows = cash_flow.get("flows", [])
            for i, f in enumerate(flows):
                proj = CashflowProjection(
                    tenant_id=tenant_id,
                    financial_model_id=model.id,
                    mes=i,
                    periodo_label=f.get("label", ""),
                    categoria=f.get("categoria", ""),
                    saidas_projetado=f.get("saidas", f.get("aquisicao", 0)),
                    pmt_projetado=f.get("pmt", 0),
                    manutencao_projetado=f.get("manut", 0),
                    payoff_projetado=abs(f.get("payoff", 0)) if f.get("payoff", 0) < 0 else 0,
                    fluxo_projetado=f.get("fluxo", 0),
                    acumulado_projetado=f.get("acumulado", 0),
                )
                session.add(proj)

            session.flush()

            logger.info(
                f"Cenario salvo: model={model.id}, payment={payment_cond.id}, "
                f"projections={len(flows)}"
            )

            return {
                "model_id": model.id,
                "payment_condition_id": payment_cond.id,
                "projections_count": len(flows),
                "property_id": property_id,
                **result_dict,
                "cash_flow": cash_flow,
            }

    def get_projections(self, model_id: str) -> Dict[str, Any]:
        """Busca projecoes financeiras de um modelo."""
        with get_session() as session:
            projs = session.execute(
                select(CashflowProjection)
                .where(CashflowProjection.financial_model_id == model_id)
                .order_by(CashflowProjection.mes)
            ).scalars().all()

            cond = session.execute(
                select(PaymentCondition)
                .where(PaymentCondition.financial_model_id == model_id)
            ).scalar_one_or_none()

            return {
                "model_id": model_id,
                "payment_condition": {
                    "cpcv_date": cond.cpcv_date.isoformat() if cond else None,
                    "escritura_date": cond.escritura_date.isoformat() if cond else None,
                    "tranches": cond.tranches if cond else [],
                } if cond else None,
                "projections": [
                    {
                        "mes": p.mes,
                        "periodo_label": p.periodo_label,
                        "categoria": p.categoria,
                        "fluxo_projetado": p.fluxo_projetado,
                        "acumulado_projetado": p.acumulado_projetado,
                        "fluxo_real": p.fluxo_real,
                        "acumulado_real": p.acumulado_real,
                    }
                    for p in projs
                ],
            }

    def delete_model(self, model_id: str) -> bool:
        """Exclui modelo financeiro e dados associados."""
        with get_session() as session:
            model = session.get(FinancialModel, model_id)
            if not model:
                return False

            # Excluir projecções associadas
            session.execute(
                select(CashflowProjection)
                .where(CashflowProjection.financial_model_id == model_id)
            )
            for proj in session.execute(
                select(CashflowProjection).where(CashflowProjection.financial_model_id == model_id)
            ).scalars().all():
                session.delete(proj)

            # Excluir condições de pagamento
            for cond in session.execute(
                select(PaymentCondition).where(PaymentCondition.financial_model_id == model_id)
            ).scalars().all():
                session.delete(cond)

            # Excluir modelo
            session.delete(model)
            logger.info(f"Modelo financeiro excluido: {model_id}")
            return True

    @staticmethod
    def _result_to_dict(result: FinancialResult) -> Dict[str, Any]:
        """Converte FinancialResult para dicionario serializavel."""
        return dataclasses.asdict(result)

    @staticmethod
    def _model_to_dict(model: FinancialModel) -> Dict[str, Any]:
        """Converte FinancialModel ORM para dicionario."""
        return {
            "id": model.id,
            "property_id": model.property_id,
            "scenario_name": model.scenario_name,
            "country": model.country,
            "purchase_price": model.purchase_price,
            "imt": model.imt,
            "imposto_selo": model.imposto_selo,
            "total_acquisition_cost": model.total_acquisition_cost,
            "renovation_total": model.renovation_total,
            "financing_type": model.financing_type,
            "loan_amount": model.loan_amount,
            "monthly_payment": model.monthly_payment,
            "bank_fees": model.bank_fees,
            "holding_months": model.holding_months,
            "total_holding_cost": model.total_holding_cost,
            "estimated_sale_price": model.estimated_sale_price,
            "comissao_venda": model.comissao_venda,
            "capital_gains_tax": model.capital_gains_tax,
            "total_investment": model.total_investment,
            "net_profit": model.net_profit,
            "roi_pct": model.roi_pct,
            "roi_simple_pct": model.roi_simple_pct,
            "moic": model.moic,
            "payoff_at_sale": model.payoff_at_sale,
            "caixa_closing": model.caixa_closing,
            "mao": model.mao,
            "floor_price": model.floor_price,
            "margin_of_safety_pct": model.margin_of_safety_pct,
            "meets_criteria": model.meets_criteria,
            "go_nogo": model.go_nogo,
            "status": model.status,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }
