"""Motor de calculo financeiro para investimento imobiliario.

Suporta Portugal e Brasil com parametros fiscais distintos.
Suporta 3 estruturas de operacao: PF+JP, so PF, so JP.
Calcula custos de aquisicao, obra, financiamento, holding, venda,
impostos (informativos), ROI anualizado (CAGR), MAO e decisao go/no-go.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.modules.m3_financial.tax_tables import (
    BANK_FEES_PT,
    CONDOMINIO_DEFAULT_MONTHLY,
    COEF_DESVALORIZACAO_DEFAULT,
    CUSTOS_NOTARIO_REGISTO_PT,
    EURIBOR_12M_REFERENCE,
    ESCRITURA_REGISTRO_ESTIMATE_BRL,
    IMI_RATE_DEFAULT,
    IMPOSTO_SELO_ADICIONAL_THRESHOLD,
    IMPOSTO_SELO_PCT,
    IMT_TABLE_PT_HPP,
    IMT_TABLE_PT_INVESTMENT,
    IR_GAIN_BRACKETS_BR,
    IRS_BRACKETS_PT_2026,
    ISENCAO_IMOVEL_UNICO_BRL,
    ITBI_DEFAULT_PCT,
    LTV_MAX_INVESTMENT,
    MAIS_VALIAS_INCLUSAO_PCT,
    SEGURO_DEFAULT_ANNUAL,
    SPREAD_TYPICAL_REFERENCE,
    VPT_ESTIMATE_PCT,
)


@dataclass
class FinancialInput:
    """Dados de entrada para o calculo financeiro."""

    # Obrigatorios
    purchase_price: float = 0
    country: str = "PT"

    # Estrutura da operacao
    entity_structure: str = "pf_jp"  # pf_jp, pf_only, jp_only
    imt_resale_regime: str = "none"  # none, reembolso, isencao

    # Obra
    renovation_budget: float = 0
    renovation_contingency_pct: float = 15
    renovation_duration_months: int = 6

    # Financiamento (default: cash)
    financing_type: str = "cash"  # cash ou mortgage
    loan_amount: float = 0  # override directo (se > 0, ignora percentagens)
    loan_pct_purchase: float = 0  # % do preco compra financiado (0-90)
    loan_pct_renovation: float = 0  # % da obra financiada (0-100)
    interest_rate_pct: float = 0
    spread_pct: float = 0
    euribor_pct: float = EURIBOR_12M_REFERENCE
    loan_term_months: int = 240

    # Venda
    estimated_sale_price: float = 0
    comissao_venda_pct: float = 6.15

    # Holding
    additional_holding_months: int = 3
    monthly_condominio: float = CONDOMINIO_DEFAULT_MONTHLY
    annual_insurance: float = SEGURO_DEFAULT_ANNUAL

    # Comissao de compra
    comissao_compra_pct: float = 0

    # CPCV parcelado — lista de parcelas [{pct: float, dias: int}]
    # Default: 1 parcela de 10% no acto
    # Exemplo Sacavem: [{"pct": 5, "dias": 0}, {"pct": 5, "dias": 30}]
    cpcv_parcelas: list = None  # None = default 10% unico

    # Mais-valias (so relevante para pf_only)
    is_resident: bool = True
    estimated_annual_income: float = 0
    devaluation_coefficient: float = COEF_DESVALORIZACAO_DEFAULT
    renovation_with_invoice_pct: float = 100

    # Go/no-go
    roi_target_pct: float = 15.0
    holding_max_months: int = 12

    # Brasil especifico
    itbi_pct: float = ITBI_DEFAULT_PCT
    is_unico_imovel_br: bool = False
    valor_imovel_unico_br: float = 0

    # Cenario
    scenario_name: str = "base"


@dataclass
class FinancialResult:
    """Resultado completo do calculo financeiro."""

    # Aquisicao — 1a escritura (vendedor → PF ou vendedor → JP)
    purchase_price: float = 0
    imt: float = 0
    imposto_selo: float = 0
    notario_registo: float = 0
    comissao_compra: float = 0
    total_acquisition_cost: float = 0

    # 2a escritura — PF → JP (so quando entity_structure = "pf_jp")
    imt_2: float = 0
    imt_2_original: float = 0  # IMT que SERIA pago (ref. poupanca)
    is_2: float = 0
    escritura_2: float = 0
    total_acquisition_cost_2: float = 0

    # Brasil
    itbi: float = 0
    escritura_registro_br: float = 0

    # Obra
    renovation_budget: float = 0
    renovation_contingency: float = 0
    renovation_total: float = 0

    # Financiamento
    financing_type: str = "cash"
    loan_amount: float = 0
    ltv_pct: float = 0
    interest_rate_pct: float = 0
    monthly_payment: float = 0
    total_interest: float = 0
    bank_fees: float = 0
    bank_fees_detail: Dict[str, Any] = field(default_factory=dict)

    # Holding
    holding_months: int = 0
    total_holding_cost: float = 0
    holding_detail: Dict[str, Any] = field(default_factory=dict)

    # Venda
    estimated_sale_price: float = 0
    comissao_venda: float = 0
    other_sale_costs: float = 0
    total_sale_costs: float = 0

    # Fiscal — IRS (pf_only)
    deductible_expenses: float = 0
    taxable_gain: float = 0
    estimated_irs_rate_pct: float = 0
    capital_gains_tax: float = 0
    capital_gains_detail: Dict[str, Any] = field(default_factory=dict)

    # Fiscal — IRC (pf_jp ou jp_only)
    irc_taxable_income: float = 0
    irc_rate_pct: float = 21.0
    irc_estimated: float = 0
    derrama_estimated: float = 0
    total_corporate_tax: float = 0

    # Resultados
    total_investment: float = 0
    total_costs: float = 0
    gross_profit: float = 0
    net_profit: float = 0
    roi_pct: float = 0
    roi_simple_pct: float = 0
    roi_annualized_pct: float = 0
    tir_anual_pct: float = 0
    cash_on_cash_return_pct: float = 0
    moic: float = 0
    payoff_at_sale: float = 0
    caixa_closing: float = 0

    # Go/no-go
    mao: float = 0
    floor_price: float = 0
    margin_of_safety_pct: float = 0
    meets_criteria: bool = False
    go_nogo: str = "pending"

    # Meta
    entity_structure: str = "pf_jp"
    imt_resale_regime: str = "none"
    warnings: List[str] = field(default_factory=list)
    country: str = "PT"
    scenario_name: str = "base"


class FinancialCalculator:
    """Motor de calculo financeiro para fix and flip."""

    def calculate(self, inp: FinancialInput) -> FinancialResult:
        """Executa o calculo financeiro completo."""
        result = FinancialResult(
            country=inp.country,
            scenario_name=inp.scenario_name,
            entity_structure=inp.entity_structure,
            imt_resale_regime=inp.imt_resale_regime,
        )
        result.purchase_price = inp.purchase_price

        # jp_only forca cash (banco nao empresta a empresa para flip)
        if inp.entity_structure == "jp_only":
            inp.financing_type = "cash"
            inp.loan_amount = 0

        if inp.country == "PT":
            self._calc_acquisition_pt(inp, result)
        elif inp.country == "BR":
            self._calc_acquisition_br(inp, result)

        self._calc_renovation(inp, result)

        if inp.financing_type != "cash":
            self._calc_financing(inp, result)

        self._calc_holding(inp, result)
        self._calc_sale_costs(inp, result)
        self._calc_results(inp, result)
        self._calc_tax_info(inp, result)
        self._calc_go_nogo(inp, result)

        return result

    # --- AQUISICAO PORTUGAL ---

    def _calc_acquisition_pt(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula custos de aquisicao em Portugal.

        Suporta 3 estruturas:
        - pf_jp: 2 escrituras (vendedor→PF + PF→JP), duplo IMT+IS
        - pf_only: 1 escritura (vendedor→PF)
        - jp_only: 1 escritura (vendedor→JP)
        """
        price = inp.purchase_price

        # Escritura 1 — vendedor → PF (ou vendedor → JP se jp_only)
        res.imt = self.calc_imt(price, IMT_TABLE_PT_INVESTMENT)

        # jp_only pode beneficiar de regime IMT revenda na unica escritura
        if inp.entity_structure == "jp_only" and inp.imt_resale_regime in (
            "reembolso",
            "isencao",
        ):
            res.imt_2_original = res.imt  # guardar ref. de poupanca
            res.imt = 0

        res.imposto_selo = round(price * IMPOSTO_SELO_PCT, 2)
        if price > IMPOSTO_SELO_ADICIONAL_THRESHOLD:
            res.imposto_selo += round(price * 0.01, 2)

        res.notario_registo = CUSTOS_NOTARIO_REGISTO_PT
        res.comissao_compra = round(price * (inp.comissao_compra_pct / 100), 2)

        total_1 = (
            price
            + res.imt
            + res.imposto_selo
            + res.notario_registo
            + res.comissao_compra
        )

        # Escritura 2 — PF → JP (so quando pf_jp)
        if inp.entity_structure == "pf_jp":
            imt_2_full = self.calc_imt(price, IMT_TABLE_PT_INVESTMENT)

            if inp.imt_resale_regime == "isencao":
                # Isencao: nao paga IMT na escritura
                res.imt_2 = 0
                res.imt_2_original = imt_2_full
            elif inp.imt_resale_regime == "reembolso":
                # Reembolso: paga IMT na escritura, recupera 12 meses depois
                res.imt_2 = imt_2_full
                res.imt_2_original = imt_2_full
            else:
                # Sem beneficio: paga IMT normal
                res.imt_2 = imt_2_full
                res.imt_2_original = imt_2_full

            # IS paga-se SEMPRE (nao e isento pelo Art. 7)
            res.is_2 = round(price * IMPOSTO_SELO_PCT, 2)
            res.escritura_2 = CUSTOS_NOTARIO_REGISTO_PT

            res.total_acquisition_cost_2 = round(
                res.imt_2 + res.is_2 + res.escritura_2, 2
            )

            # Warning se reembolso e holding > 12 meses
            total_months = (
                inp.renovation_duration_months + inp.additional_holding_months
            )
            if (
                inp.imt_resale_regime == "reembolso"
                and total_months > 12
            ):
                res.warnings.append(
                    f"Retencao de {total_months} meses excede 1 ano — "
                    f"perdera direito ao reembolso de IMT "
                    f"({res.imt_2_original:,.2f}EUR)"
                )

        res.total_acquisition_cost = round(
            total_1 + res.total_acquisition_cost_2, 2
        )

    @staticmethod
    def calc_imt(
        value: float, table: list[tuple[float, float, float | None]]
    ) -> float:
        """Calcula IMT com base na tabela progressiva OE2026."""
        for limit, rate, deduction in table:
            if value <= limit:
                if deduction is None:
                    return round(value * rate, 2)
                return round(value * rate - deduction, 2)
        return round(value * 0.075, 2)

    # --- AQUISICAO BRASIL ---

    def _calc_acquisition_br(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula custos de aquisicao no Brasil."""
        price = inp.purchase_price
        res.itbi = price * inp.itbi_pct
        res.escritura_registro_br = ESCRITURA_REGISTRO_ESTIMATE_BRL
        res.total_acquisition_cost = price + res.itbi + res.escritura_registro_br

    # --- OBRA ---

    def _calc_renovation(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula custos de obra com contingencia."""
        res.renovation_budget = inp.renovation_budget
        res.renovation_contingency = inp.renovation_budget * (
            inp.renovation_contingency_pct / 100
        )
        res.renovation_total = inp.renovation_budget + res.renovation_contingency

    # --- FINANCIAMENTO ---

    def _calc_financing(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula custos de financiamento bancario."""
        res.financing_type = inp.financing_type

        # Calcular emprestimo: override directo ou via percentagens
        if inp.loan_amount > 0:
            res.loan_amount = inp.loan_amount
        elif inp.loan_pct_purchase > 0 or inp.loan_pct_renovation > 0:
            loan_purchase = inp.purchase_price * (inp.loan_pct_purchase / 100)
            loan_reno = res.renovation_total * (inp.loan_pct_renovation / 100)
            res.loan_amount = round(loan_purchase + loan_reno, 2)
        else:
            # Sem financiamento (cash) — loan_amount fica 0
            res.loan_amount = 0

        res.ltv_pct = (
            (res.loan_amount / inp.purchase_price) * 100
            if inp.purchase_price > 0
            else 0
        )

        if inp.interest_rate_pct > 0:
            res.interest_rate_pct = inp.interest_rate_pct
        else:
            euribor = (
                inp.euribor_pct if inp.euribor_pct > 0 else EURIBOR_12M_REFERENCE
            )
            spread = (
                inp.spread_pct if inp.spread_pct > 0 else SPREAD_TYPICAL_REFERENCE
            )
            res.interest_rate_pct = (euribor + spread) * 100

        monthly_rate = (res.interest_rate_pct / 100) / 12
        n = inp.loan_term_months
        if monthly_rate > 0 and n > 0:
            res.monthly_payment = round(
                res.loan_amount
                * (monthly_rate * (1 + monthly_rate) ** n)
                / ((1 + monthly_rate) ** n - 1),
                2,
            )
        elif n > 0:
            res.monthly_payment = round(res.loan_amount / n, 2)

        # Custos bancarios (Portugal)
        if inp.country == "PT":
            fees = BANK_FEES_PT
            fixed_fees = (
                fees["dossier"]
                + fees["avaliacao"]
                + fees["registo_hipoteca"]
                + fees["outros"]
            )
            is_fee = round(res.loan_amount * fees["is_pct"], 2)
            res.bank_fees_detail = {
                "dossier": fees["dossier"],
                "avaliacao": fees["avaliacao"],
                "registo_hipoteca": fees["registo_hipoteca"],
                "outros": fees["outros"],
                "is_emprestimo": is_fee,
            }
            res.bank_fees = round(fixed_fees + is_fee, 2)

    # --- HOLDING COSTS ---

    def _calc_holding(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula custos de detencao durante a obra + venda."""
        res.holding_months = (
            inp.renovation_duration_months + inp.additional_holding_months
        )

        monthly_imi = 0.0
        if inp.country == "PT":
            vpt_estimate = inp.purchase_price * VPT_ESTIMATE_PCT
            monthly_imi = (vpt_estimate * IMI_RATE_DEFAULT) / 12

        monthly_total = (
            inp.monthly_condominio
            + (inp.annual_insurance / 12)
            + monthly_imi
        )

        res.total_holding_cost = round(monthly_total * res.holding_months, 2)
        res.holding_detail = {
            "meses": res.holding_months,
            "condominio_mensal": inp.monthly_condominio,
            "seguro_mensal": round(inp.annual_insurance / 12, 2),
            "imi_mensal": round(monthly_imi, 2),
            "total_mensal": round(monthly_total, 2),
        }

    # --- CUSTOS DE VENDA ---

    def _calc_sale_costs(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula custos de venda."""
        res.estimated_sale_price = inp.estimated_sale_price
        res.comissao_venda = round(
            inp.estimated_sale_price * (inp.comissao_venda_pct / 100), 2
        )
        res.other_sale_costs = 500
        res.total_sale_costs = round(
            res.comissao_venda + res.other_sale_costs, 2
        )

    # --- INFORMACAO FISCAL (informativa, NAO subtrai do lucro) ---

    def _calc_tax_info(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula impostos informativos baseado na entity_structure.

        NUNCA subtrai do lucro cash. Serve para planeamento fiscal.
        """
        if inp.country != "PT":
            # Brasil: manter calculo existente de mais-valias
            self._calc_capital_gains_br(inp, res)
            return

        if inp.entity_structure == "pf_only":
            # PF vende directamente → mais-valias IRS
            self._calc_capital_gains_pt(inp, res)

        elif inp.entity_structure in ("pf_jp", "jp_only"):
            # Lucro na JP → IRC 21% + derrama
            revenue = inp.estimated_sale_price

            if inp.entity_structure == "pf_jp":
                cost_of_acquisition = inp.purchase_price
                cost_of_transfer = res.total_acquisition_cost_2
            else:
                cost_of_acquisition = inp.purchase_price
                cost_of_transfer = 0

            cost_of_renovation = inp.renovation_budget
            cost_of_sale = res.comissao_venda
            cost_of_financing = res.monthly_payment * res.holding_months
            cost_of_maintenance = inp.monthly_condominio * res.holding_months

            total_costs_jp = (
                cost_of_acquisition
                + cost_of_transfer
                + cost_of_renovation
                + cost_of_sale
                + cost_of_financing
                + cost_of_maintenance
            )

            taxable_income = max(revenue - total_costs_jp, 0)

            res.irc_taxable_income = round(taxable_income, 2)
            res.irc_rate_pct = 21.0
            res.irc_estimated = round(taxable_income * 0.21, 2)
            res.derrama_estimated = round(taxable_income * 0.015, 2)
            res.total_corporate_tax = round(
                res.irc_estimated + res.derrama_estimated, 2
            )

            res.capital_gains_detail = {
                "entity": "JP",
                "receita": revenue,
                "custos_totais": round(total_costs_jp, 2),
                "lucro_tributavel": round(taxable_income, 2),
                "irc_21pct": res.irc_estimated,
                "derrama_1_5pct": res.derrama_estimated,
                "total_imposto": res.total_corporate_tax,
                "pf_mais_valias": 0,
            }

    # --- MAIS-VALIAS PORTUGAL (so para pf_only) ---

    def _calc_capital_gains_pt(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula mais-valias imobiliarias em Portugal (PF)."""
        renovation_deductible = inp.renovation_budget * (
            inp.renovation_with_invoice_pct / 100
        )
        res.deductible_expenses = (
            res.imt
            + res.imposto_selo
            + res.notario_registo
            + res.comissao_compra
            + renovation_deductible
            + res.comissao_venda
        )

        adjusted_purchase = inp.purchase_price * inp.devaluation_coefficient
        gain = (
            inp.estimated_sale_price - adjusted_purchase - res.deductible_expenses
        )
        gain = max(gain, 0)

        taxable = gain * MAIS_VALIAS_INCLUSAO_PCT
        res.taxable_gain = taxable

        if taxable > 0:
            total_income = inp.estimated_annual_income + taxable
            tax_on_total = self._calc_irs_pt(total_income)
            tax_without_gain = self._calc_irs_pt(inp.estimated_annual_income)
            res.capital_gains_tax = round(tax_on_total - tax_without_gain, 2)

            if taxable > 0:
                res.estimated_irs_rate_pct = round(
                    (res.capital_gains_tax / taxable) * 100, 2
                )

        res.capital_gains_detail = {
            "entity": "PF",
            "mais_valia_bruta": inp.estimated_sale_price - inp.purchase_price,
            "despesas_dedutiveis": res.deductible_expenses,
            "mais_valia_liquida": gain,
            "50pct_tributavel": taxable,
            "taxa_efectiva_pct": res.estimated_irs_rate_pct,
            "imposto": res.capital_gains_tax,
        }

    @staticmethod
    def _calc_irs_pt(taxable_income: float) -> float:
        """Calcula IRS progressivo portugues (simplificado)."""
        if taxable_income <= 0:
            return 0
        tax = 0.0
        prev_limit = 0.0
        for limit, rate in IRS_BRACKETS_PT_2026:
            bracket_income = min(taxable_income, limit) - prev_limit
            if bracket_income > 0:
                tax += bracket_income * rate
            if taxable_income <= limit:
                break
            prev_limit = limit
        return round(tax, 2)

    # --- MAIS-VALIAS BRASIL ---

    def _calc_capital_gains_br(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula ganho de capital no Brasil."""
        gain = max(inp.estimated_sale_price - inp.purchase_price, 0)

        if (
            inp.is_unico_imovel_br
            and inp.estimated_sale_price <= ISENCAO_IMOVEL_UNICO_BRL
        ):
            res.capital_gains_tax = 0
            res.capital_gains_detail = {
                "isento": True,
                "motivo": "imovel unico ate R$440k",
            }
            return

        tax = 0.0
        prev_limit = 0.0
        applied_rate = 0.0
        for limit, rate in IR_GAIN_BRACKETS_BR:
            bracket = min(gain, limit) - prev_limit
            if bracket > 0:
                tax += bracket * rate
                applied_rate = rate
            if gain <= limit:
                break
            prev_limit = limit

        res.capital_gains_tax = round(tax, 2)
        res.capital_gains_detail = {
            "ganho_capital": gain,
            "taxa_aplicada_pct": applied_rate * 100,
            "imposto": round(tax, 2),
        }

    # --- RESULTADOS FINAIS ---

    def _calc_results(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Calcula metricas finais de retorno.

        Metodologia (optica de caixa):
        - Equity = preco_compra - emprestimo
        - Caixa investido = equity + custos_compra_1 + custos_compra_2
          + custos_hipoteca + obra + prestacoes + manutencao
        - Caixa no closing = venda_liquida - payoff_emprestimo
        - Lucro = caixa_closing - caixa_investido
        - ROI = CAGR: (1 + lucro/caixa)^(12/meses) - 1
        """
        equity = inp.purchase_price - res.loan_amount

        custos_compra_1 = (
            res.imt
            + res.imposto_selo
            + res.notario_registo
            + res.comissao_compra
            + res.itbi
            + res.escritura_registro_br
        )

        custos_compra_2 = res.total_acquisition_cost_2

        # Manutencao mensal = condominio + seguro + IMI (PT)
        monthly_imi = 0.0
        if inp.country == "PT":
            vpt_estimate = inp.purchase_price * VPT_ESTIMATE_PCT
            monthly_imi = (vpt_estimate * IMI_RATE_DEFAULT) / 12
        monthly_maintenance = (
            inp.monthly_condominio + inp.annual_insurance / 12 + monthly_imi
        )

        res.total_investment = round(
            equity
            + custos_compra_1
            + custos_compra_2
            + res.bank_fees
            + res.renovation_total
            + (res.monthly_payment * res.holding_months)
            + (monthly_maintenance * res.holding_months),
            2,
        )

        # Payoff — saldo devedor no mes da venda
        monthly_rate = (
            (res.interest_rate_pct / 100) / 12
            if res.interest_rate_pct > 0
            else 0
        )
        saldo = res.loan_amount
        for _ in range(res.holding_months):
            if saldo <= 0:
                break
            juros = saldo * monthly_rate
            amort = res.monthly_payment - juros
            saldo = max(saldo - amort, 0)
        res.payoff_at_sale = round(saldo, 2)

        # Venda liquida
        venda_liquida = inp.estimated_sale_price * (
            1 - inp.comissao_venda_pct / 100
        )

        # Caixa no closing
        res.caixa_closing = round(venda_liquida - res.payoff_at_sale, 2)

        # Total costs (para referencia, sem impostos)
        res.total_costs = round(
            custos_compra_1
            + custos_compra_2
            + res.bank_fees
            + res.renovation_total
            + res.total_holding_cost
            + res.total_sale_costs
            + (res.monthly_payment * res.holding_months),
            2,
        )

        # Lucro cash = caixa no closing - caixa investido
        # Impostos pagam-se a parte (IRS ou IRC), nao saem do caixa no closing
        # No regime reembolso, o IMT 2 volta 12 meses depois — somar ao lucro
        imt_reembolso = 0.0
        if inp.imt_resale_regime == "reembolso" and inp.entity_structure == "pf_jp":
            imt_reembolso = res.imt_2
        elif inp.imt_resale_regime == "reembolso" and inp.entity_structure == "jp_only":
            imt_reembolso = res.imt_2_original

        res.gross_profit = round(
            res.caixa_closing - res.total_investment + imt_reembolso, 2
        )
        res.net_profit = res.gross_profit

        # ROI — CAGR anualizado
        if res.total_investment > 0 and res.holding_months > 0:
            raw_return = res.net_profit / res.total_investment
            res.roi_simple_pct = round(raw_return * 100, 2)

            if 1 + raw_return > 0:
                res.roi_pct = round(
                    (
                        (1 + raw_return) ** (12 / res.holding_months) - 1
                    )
                    * 100,
                    2,
                )
            else:
                res.roi_pct = -100.0

            res.roi_annualized_pct = res.roi_pct

            # MOIC — inclui reembolso IMT para consistencia com net_profit
            retorno_total = res.caixa_closing + imt_reembolso
            res.moic = round(retorno_total / res.total_investment, 2)

            # ROI equity = lucro / capital proprio investido
            # equity_real = total_investment - loan (dinheiro que sai do bolso)
            equity_real = res.total_investment - res.loan_amount
            if equity_real > 0:
                res.cash_on_cash_return_pct = round(
                    (res.net_profit / equity_real) * 100, 2
                )

        # Warnings
        if res.net_profit < 0:
            res.warnings.append(
                "Prejuizo — o negocio nao cobre os custos"
            )
        if res.holding_months > inp.holding_max_months:
            res.warnings.append(
                f"Retencao ({res.holding_months}m) excede maximo "
                f"({inp.holding_max_months}m)"
            )
        if inp.estimated_sale_price <= 0:
            res.warnings.append(
                "Preco de venda nao definido — resultados incompletos"
            )
        if inp.entity_structure == "jp_only":
            res.warnings.append(
                "Sem financiamento bancario — JP compra a cash"
            )

    # --- FLUXO DE CAIXA MENSAL ---

    def calc_cash_flow(
        self, inp: FinancialInput, res: FinancialResult
    ) -> Dict[str, Any]:
        """Gera o fluxo de caixa mes a mes.

        Ordem do fluxo (estrutura pf_jp):
          CPCV (N parcelas) → Escritura 1 (V→PF) → Meses obra/holding →
          Escritura 2 (PF→JP, 1 mes antes da venda) → VENDA →
          (12 meses depois da Escritura 2: Reembolso IMT se aplicavel)
        """
        flows: List[Dict[str, Any]] = []
        acum = 0.0

        # --- CPCV (parcelado ou unico) ---
        parcelas = inp.cpcv_parcelas
        if not parcelas:
            parcelas = [{"pct": 10.0, "dias": 0}]

        cpcv_total = 0.0
        for idx, parcela in enumerate(parcelas):
            pct = parcela.get("pct", 10)
            val = round(inp.purchase_price * (pct / 100), 2)
            cpcv_total += val
            acum -= val
            n_label = f" {idx + 1}/{len(parcelas)}" if len(parcelas) > 1 else ""
            flows.append({
                "label": f"CPCV{n_label}",
                "categoria": "aquisicao",
                "descricao": f"Sinal {pct}% do preco de compra ({parcela.get('dias', 0)}d)",
                "aquisicao": val,
                "obra": 0,
                "saidas": val,
                "fluxo": round(-val, 2),
                "acumulado": round(acum, 2),
            })

        # --- Escritura 1 (Vendedor → PF ou Vendedor → JP) ---
        equity = inp.purchase_price - res.loan_amount
        custos_compra_1 = (
            res.imt + res.imposto_selo + res.notario_registo + res.comissao_compra
        )
        escritura_cash = equity - cpcv_total + custos_compra_1 + res.bank_fees

        label_esc1 = (
            "Escritura 1 (V→PF)" if inp.entity_structure == "pf_jp" else "Escritura"
        )
        componentes_esc1 = []
        if equity - cpcv_total > 0:
            componentes_esc1.append({"nome": "Equity restante", "valor": round(equity - cpcv_total, 2)})
        if res.imt > 0:
            componentes_esc1.append({"nome": "IMT", "valor": round(res.imt, 2)})
        if res.imposto_selo > 0:
            componentes_esc1.append({"nome": "Imposto de Selo", "valor": round(res.imposto_selo, 2)})
        if res.notario_registo > 0:
            componentes_esc1.append({"nome": "Notario e Registo", "valor": round(res.notario_registo, 2)})
        if res.comissao_compra > 0:
            componentes_esc1.append({"nome": "Comissao compra", "valor": round(res.comissao_compra, 2)})
        if res.bank_fees > 0:
            componentes_esc1.append({"nome": "Custos hipoteca", "valor": round(res.bank_fees, 2)})

        acum -= escritura_cash
        flows.append({
            "label": label_esc1,
            "categoria": "aquisicao",
            "descricao": " | ".join(f"{c['nome']}: {c['valor']:,.0f}" for c in componentes_esc1),
            "componentes": componentes_esc1,
            "aquisicao": round(escritura_cash, 2),
            "obra": 0,
            "saidas": round(escritura_cash, 2),
            "fluxo": round(-escritura_cash, 2),
            "acumulado": round(acum, 2),
        })

        # --- Meses (obra + holding) ---
        reno_per_month = (
            inp.renovation_budget / max(inp.renovation_duration_months, 1)
        )
        monthly_rate = (
            (res.interest_rate_pct / 100) / 12 if res.interest_rate_pct > 0 else 0
        )
        saldo = res.loan_amount
        # Manutencao mensal inclui IMI (consistente com _calc_holding)
        monthly_imi_cf = 0.0
        if inp.country == "PT":
            vpt_est = inp.purchase_price * VPT_ESTIMATE_PCT
            monthly_imi_cf = (vpt_est * IMI_RATE_DEFAULT) / 12
        manut_mensal = inp.monthly_condominio + inp.annual_insurance / 12 + monthly_imi_cf

        for m in range(1, res.holding_months + 1):
            obra_val = reno_per_month if m <= inp.renovation_duration_months else 0
            juros = saldo * monthly_rate
            amort = res.monthly_payment - juros if res.monthly_payment > 0 else 0
            saldo = max(saldo - amort, 0)
            fluxo_mes = -(obra_val + res.monthly_payment + manut_mensal)
            acum += fluxo_mes

            fase = "obra" if m <= inp.renovation_duration_months else "holding"
            desc_parts = []
            if obra_val > 0:
                desc_parts.append(f"Obra: {obra_val:,.0f}")
            if res.monthly_payment > 0:
                desc_parts.append(f"PMT: {res.monthly_payment:,.0f} (juros {juros:,.0f} + amort {amort:,.0f})")
            if manut_mensal > 0:
                desc_parts.append(f"Manut: {manut_mensal:,.0f}")

            flows.append({
                "label": f"Mes {m}",
                "categoria": fase,
                "descricao": " | ".join(desc_parts),
                "obra": round(obra_val, 2),
                "aquisicao": 0,
                "saidas": round(obra_val, 2),
                "saldo_devedor": round(saldo + amort, 2),
                "juros": round(juros, 2),
                "amort": round(amort, 2),
                "payoff": round(saldo, 2),
                "pmt": round(res.monthly_payment, 2),
                "manut": round(manut_mensal, 2),
                "fluxo": round(fluxo_mes, 2),
                "acumulado": round(acum, 2),
            })

        # --- Escritura 2 (PF → JP) — 1 mes antes da venda (so pf_jp) ---
        has_escritura_2 = (
            inp.entity_structure == "pf_jp" and res.total_acquisition_cost_2 > 0
        )
        if has_escritura_2:
            componentes_esc2 = []
            if res.imt_2 > 0:
                componentes_esc2.append({"nome": "IMT 2a transmissao", "valor": round(res.imt_2, 2)})
            if res.is_2 > 0:
                componentes_esc2.append({"nome": "Imposto de Selo", "valor": round(res.is_2, 2)})
            if res.escritura_2 > 0:
                componentes_esc2.append({"nome": "Notario e Registo", "valor": round(res.escritura_2, 2)})

            acum -= res.total_acquisition_cost_2
            flows.append({
                "label": "Escritura 2 (PF→JP)",
                "categoria": "aquisicao",
                "descricao": "Transferencia PF→JP ao custo, 1 mes antes da venda",
                "componentes": componentes_esc2,
                "aquisicao": round(res.total_acquisition_cost_2, 2),
                "obra": 0,
                "saidas": round(res.total_acquisition_cost_2, 2),
                "fluxo": round(-res.total_acquisition_cost_2, 2),
                "acumulado": round(acum, 2),
            })

        # --- VENDA ---
        venda_liq = inp.estimated_sale_price * (1 - inp.comissao_venda_pct / 100)
        comissao_venda = inp.estimated_sale_price * (inp.comissao_venda_pct / 100)
        caixa_closing = venda_liq - saldo
        acum += caixa_closing
        flows.append({
            "label": "VENDA",
            "categoria": "venda",
            "descricao": f"Venda bruta: {inp.estimated_sale_price:,.0f} | Comissao: -{comissao_venda:,.0f} | Payoff: -{saldo:,.0f}",
            "obra": 0,
            "aquisicao": 0,
            "saidas": 0,
            "payoff": round(-saldo, 2),
            "venda_bruta": round(inp.estimated_sale_price, 2),
            "comissao_venda": round(comissao_venda, 2),
            "venda_liquida": round(venda_liq, 2),
            "fluxo": round(caixa_closing, 2),
            "acumulado": round(acum, 2),
        })

        # --- Reembolso IMT (12 meses apos Escritura 2) ---
        if inp.imt_resale_regime == "reembolso" and has_escritura_2 and res.imt_2 > 0:
            imt_reembolso = res.imt_2
            acum += imt_reembolso
            flows.append({
                "label": "Reembolso IMT",
                "categoria": "reembolso",
                "descricao": f"Devolucao IMT Art. 7 CIMT — 12 meses apos Escritura 2",
                "componentes": [{"nome": "IMT 2a transmissao (devolvido)", "valor": round(imt_reembolso, 2)}],
                "aquisicao": 0,
                "obra": 0,
                "saidas": 0,
                "fluxo": round(imt_reembolso, 2),
                "acumulado": round(acum, 2),
            })

        pico_investido = abs(min(f["acumulado"] for f in flows))

        # Calcular TIR sobre os fluxos mensais
        tir_anual = self._calc_tir(flows)

        return {
            "flows": flows,
            "pico_caixa_necessario": round(pico_investido, 2),
            "saldo_final": round(acum, 2),
            "tir_anual_pct": tir_anual,
        }

    @staticmethod
    def _calc_tir(flows: list[dict]) -> float:
        """Calcula TIR anual via Newton-Raphson sobre fluxos mensais.

        A TIR e a taxa mensal r que faz NPV = sum(fluxo_t / (1+r)^t) = 0.
        Retorna a taxa anualizada: (1 + r_mensal)^12 - 1, em percentagem.
        """
        # Extrair fluxos com indice mensal
        fluxos = []
        for i, f in enumerate(flows):
            valor = f.get("fluxo", 0)
            if valor != 0:
                fluxos.append((i, valor))

        if len(fluxos) < 2:
            return 0.0

        # Verificar se ha pelo menos uma saida e uma entrada
        tem_negativo = any(v < 0 for _, v in fluxos)
        tem_positivo = any(v > 0 for _, v in fluxos)
        if not tem_negativo or not tem_positivo:
            return 0.0

        # Newton-Raphson
        r = 0.02  # chute inicial: 2% ao mes
        for _ in range(1000):
            npv = 0.0
            derivada = 0.0
            for t, valor in fluxos:
                divisor = (1 + r) ** t
                if divisor == 0:
                    break
                npv += valor / divisor
                derivada -= t * valor / (divisor * (1 + r))

            if abs(npv) < 0.01:
                break

            if abs(derivada) < 1e-12:
                break

            passo = npv / derivada
            r -= passo

            # Limites de seguranca
            if r <= -1:
                r = -0.99
            if r > 10:
                r = 10.0

        # Anualizar: (1 + r_mensal)^12 - 1
        try:
            tir_anual = ((1 + r) ** 12 - 1) * 100
        except (OverflowError, ValueError):
            tir_anual = 0.0

        return round(tir_anual, 2)

    # --- GO / NO-GO ---

    def _calc_go_nogo(
        self, inp: FinancialInput, res: FinancialResult
    ) -> None:
        """Determina decisao go/no-go automatica."""
        # MAO — regra dos 70%
        if inp.estimated_sale_price > 0:
            res.mao = round(
                inp.estimated_sale_price * 0.70 - res.renovation_total, 2
            )
        else:
            res.mao = 0

        # Floor price — preco minimo de venda para ROI target
        target_profit = res.total_investment * (inp.roi_target_pct / 100)
        net_of_commission = 1 - (inp.comissao_venda_pct / 100)
        if net_of_commission > 0:
            res.floor_price = round(
                (res.total_investment + target_profit)
                / net_of_commission,
                2,
            )

        # Margem de seguranca
        if inp.estimated_sale_price > 0 and res.floor_price > 0:
            res.margin_of_safety_pct = round(
                (inp.estimated_sale_price - res.floor_price)
                / inp.estimated_sale_price
                * 100,
                2,
            )

        # Decisao
        res.meets_criteria = res.roi_pct >= inp.roi_target_pct
        if res.roi_pct >= inp.roi_target_pct:
            res.go_nogo = "go"
        elif res.roi_pct >= inp.roi_target_pct * 0.7:
            res.go_nogo = "marginal"
        else:
            res.go_nogo = "no_go"
