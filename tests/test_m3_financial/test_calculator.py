"""Testes para o FinancialCalculator com cenarios reais."""

from __future__ import annotations

import pytest

from src.modules.m3_financial.calculator import (
    FinancialCalculator,
    FinancialInput,
)

calc = FinancialCalculator()


class TestCasoSacavem:
    """Caso 1: Predio em Sacavem — 2 unidades, financiamento bancario.

    Compra: 295.000EUR, Obra: 98.400EUR, Venda: 500.000EUR
    Financiamento: 75% (221.250EUR), TAN 2.73%, 30 anos
    Retencao: 3m obra + 6m venda = 9 meses
    """

    @pytest.fixture()
    def result(self):
        inp = FinancialInput(
            purchase_price=295_000,
            country="PT",
            financing_type="mortgage",
            loan_amount=221_250,
            interest_rate_pct=2.73,
            loan_term_months=360,
            renovation_budget=98_400,
            renovation_contingency_pct=0,
            renovation_duration_months=3,
            estimated_sale_price=500_000,
            comissao_venda_pct=6.15,
            additional_holding_months=6,
            monthly_condominio=100,
            annual_insurance=0,
            roi_target_pct=15,
        )
        return calc.calculate(inp)

    def test_imt(self, result) -> None:
        """IMT deve ser 11.255,50EUR (escalao 330.539, tabela OE2026)."""
        assert result.imt == 11_255.50

    def test_imposto_selo(self, result) -> None:
        """IS deve ser 2.360EUR (0,8% de 295k)."""
        assert result.imposto_selo == 2_360.00

    def test_monthly_payment(self, result) -> None:
        """PMT mensal deve ser ~900,89EUR."""
        assert abs(result.monthly_payment - 900.89) < 1.0

    def test_bank_fees(self, result) -> None:
        """Custos hipoteca = 1.441 fixos + IS 0,6% de 221.250."""
        # IS = 221.250 * 0.006 = 1.327,50
        # Total = 1.441 + 1.327,50 = 2.768,50
        assert abs(result.bank_fees - 2_768.50) < 1.0

    def test_payoff_at_sale(self, result) -> None:
        """Payoff no mes 9 deve ser ~217.639EUR."""
        assert abs(result.payoff_at_sale - 217_639) < 200

    def test_venda_liquida(self, result) -> None:
        """Venda liquida = 500k - 6,15% = 469.250EUR."""
        venda_liq = 500_000 * (1 - 0.0615)
        assert abs(result.caixa_closing - (venda_liq - result.payoff_at_sale)) < 100

    def test_roi_positive(self, result) -> None:
        """ROI anualizado deve ser positivo e superior a 15%."""
        assert result.roi_pct > 15

    def test_go_nogo(self, result) -> None:
        """Decisao deve ser 'go' com ROI > 15%."""
        assert result.go_nogo == "go"
        assert result.meets_criteria is True

    def test_moic_above_1(self, result) -> None:
        """MOIC deve ser superior a 1 (lucro positivo)."""
        assert result.moic > 1.0

    def test_net_profit_positive(self, result) -> None:
        """Lucro liquido deve ser positivo."""
        assert result.net_profit > 0


class TestCasoBrasil:
    """Caso 2: Moradia no Brasil — cash, flip."""

    @pytest.fixture()
    def result(self):
        inp = FinancialInput(
            purchase_price=500_000,
            country="BR",
            renovation_budget=100_000,
            estimated_sale_price=800_000,
            itbi_pct=0.03,
            additional_holding_months=3,
            renovation_duration_months=6,
        )
        return calc.calculate(inp)

    def test_itbi(self, result) -> None:
        """ITBI deve ser 15.000 (3% de 500k)."""
        assert result.itbi == 15_000

    def test_capital_gains_tax(self, result) -> None:
        """IR deve ser 15% sobre ganho de capital."""
        # Ganho = 800k - 500k = 300k → 15% → 45.000
        assert abs(result.capital_gains_tax - 45_000) < 100

    def test_net_profit_positive(self, result) -> None:
        """Deve ter lucro positivo."""
        assert result.net_profit > 0


class TestCasoFinanciamento:
    """Caso 3: Apartamento PT com financiamento — mortgage."""

    @pytest.fixture()
    def result(self):
        inp = FinancialInput(
            purchase_price=200_000,
            country="PT",
            financing_type="mortgage",
            loan_amount=140_000,
            interest_rate_pct=3.3,
            loan_term_months=240,
            renovation_budget=30_000,
            estimated_sale_price=300_000,
            additional_holding_months=3,
            renovation_duration_months=4,
        )
        return calc.calculate(inp)

    def test_ltv(self, result) -> None:
        """LTV deve ser 70%."""
        assert result.ltv_pct == 70.0

    def test_monthly_payment_positive(self, result) -> None:
        """Prestacao mensal deve ser positiva."""
        assert result.monthly_payment > 0

    def test_bank_fees(self, result) -> None:
        """Custos bancarios devem ser positivos."""
        assert result.bank_fees > 0

    def test_roi_positive(self, result) -> None:
        """ROI deve ser positivo."""
        assert result.roi_pct > 0


class TestCashFlow:
    """Testa o fluxo de caixa mensal."""

    def test_cash_flow_structure(self) -> None:
        """Fluxo de caixa deve ter CPCV, Escritura, Meses e VENDA."""
        inp = FinancialInput(
            purchase_price=200_000,
            country="PT",
            renovation_budget=30_000,
            estimated_sale_price=280_000,
            renovation_duration_months=3,
            additional_holding_months=2,
        )
        result = calc.calculate(inp)
        cf = calc.calc_cash_flow(inp, result)

        assert "flows" in cf
        assert "pico_caixa_necessario" in cf
        assert "saldo_final" in cf

        flows = cf["flows"]
        assert flows[0]["label"] == "CPCV"
        assert "Escritura" in flows[1]["label"]
        assert flows[-1]["label"] == "VENDA"

        # Pico de caixa deve ser positivo
        assert cf["pico_caixa_necessario"] > 0

    def test_cash_flow_saldo_final_matches_profit(self) -> None:
        """Saldo final do fluxo de caixa deve ser proximo do lucro."""
        inp = FinancialInput(
            purchase_price=150_000,
            country="PT",
            renovation_budget=20_000,
            estimated_sale_price=220_000,
            renovation_duration_months=3,
            additional_holding_months=3,
        )
        result = calc.calculate(inp)
        cf = calc.calc_cash_flow(inp, result)

        # O saldo final do fluxo deve ser proximo do gross_profit
        # (diferenca inclui contingencia de obra e mais-valias fiscais)
        assert abs(cf["saldo_final"] - result.gross_profit) < 5_000
