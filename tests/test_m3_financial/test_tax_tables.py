"""Testes para tabelas fiscais IMT OE2026."""

from __future__ import annotations

import pytest

from src.modules.m3_financial.calculator import FinancialCalculator
from src.modules.m3_financial.tax_tables import (
    IMT_TABLE_PT_HPP,
    IMT_TABLE_PT_INVESTMENT,
)

calc = FinancialCalculator()


class TestIMTInvestimento:
    """Testes de IMT com tabela de investimento (Tabela III OE2026)."""

    def test_100k(self) -> None:
        """100.000EUR investimento → 1% → IMT = 1.000EUR."""
        assert calc.calc_imt(100_000, IMT_TABLE_PT_INVESTMENT) == 1_000.00

    def test_150k(self) -> None:
        """150.000EUR → 150.000 x 0.05 - 5.427,56 = 2.072,44EUR."""
        assert calc.calc_imt(150_000, IMT_TABLE_PT_INVESTMENT) == 2_072.44

    def test_250k(self) -> None:
        """250.000EUR → 250.000 x 0.07 - 9.394,50 = 8.105,50EUR."""
        assert calc.calc_imt(250_000, IMT_TABLE_PT_INVESTMENT) == 8_105.50

    def test_295k_sacavem(self) -> None:
        """295.000EUR (caso Sacavem) → 295.000 x 0.07 - 9.394,50 = 11.255,50EUR."""
        assert calc.calc_imt(295_000, IMT_TABLE_PT_INVESTMENT) == 11_255.50

    def test_500k(self) -> None:
        """500.000EUR → 500.000 x 0.08 - 12.699,89 = 27.300,11EUR."""
        assert calc.calc_imt(500_000, IMT_TABLE_PT_INVESTMENT) == 27_300.11

    def test_800k(self) -> None:
        """800.000EUR → taxa unica 6% → 48.000EUR."""
        assert calc.calc_imt(800_000, IMT_TABLE_PT_INVESTMENT) == 48_000.00

    def test_2m(self) -> None:
        """2.000.000EUR → taxa unica 7,5% → 150.000EUR."""
        assert calc.calc_imt(2_000_000, IMT_TABLE_PT_INVESTMENT) == 150_000.00


class TestIMTHPP:
    """Testes de IMT com tabela de HPP."""

    def test_100k_hpp_isento(self) -> None:
        """100.000EUR HPP → 0% (isento) → IMT = 0EUR."""
        assert calc.calc_imt(100_000, IMT_TABLE_PT_HPP) == 0.00

    def test_150k_hpp(self) -> None:
        """150.000EUR HPP → 150.000 x 0.05 - 6.363,74 = 1.136,26EUR (OE2026)."""
        assert calc.calc_imt(150_000, IMT_TABLE_PT_HPP) == 1_136.26
