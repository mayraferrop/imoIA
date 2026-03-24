"""Calculadora de yield para investimento imobiliário em Portugal.

Calcula yield bruto e líquido, incluindo todos os custos de aquisição
e custos anuais específicos do mercado português.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class YieldResult:
    """Resultado do cálculo de yield."""

    gross_yield_pct: float
    net_yield_pct: float
    imt: float
    stamp_duty: float
    annual_costs: float
    total_acquisition_cost: float


class YieldCalculator:
    """Calculadora de yield para investimento imobiliário em Portugal."""

    # Custos fixos estimados
    NOTARY_REGISTRY_COST = 1500.0  # Notário + registo
    LAWYER_RATE = 0.015  # 1.5% do valor de compra
    STAMP_DUTY_RATE = 0.008  # 0.8% imposto de selo
    IMI_RATE = 0.0035  # 0.35% do VPT
    VPT_RATIO = 0.60  # VPT = 60% do valor de compra
    CONDO_MONTHLY = 50.0  # Condomínio mensal estimado
    MAINTENANCE_RATE = 0.05  # 5% da renda anual
    INSURANCE_ANNUAL = 300.0  # Seguro anual
    IRS_RATE = 0.28  # 28% taxa autónoma sobre rendas
    VACANCY_RATE = 0.08  # 8% vacância

    def calculate(
        self,
        purchase_price: float,
        monthly_rent: float,
        municipality: Optional[str] = "Lisboa",
    ) -> YieldResult:
        """Calcula yield bruto e líquido de um investimento.

        Args:
            purchase_price: Preço de compra em euros.
            monthly_rent: Renda mensal estimada em euros.
            municipality: Município (para referência futura).

        Returns:
            YieldResult com yields e custos detalhados.
        """
        if purchase_price <= 0 or monthly_rent <= 0:
            logger.warning("Preço ou renda inválidos para cálculo de yield")
            return YieldResult(
                gross_yield_pct=0.0,
                net_yield_pct=0.0,
                imt=0.0,
                stamp_duty=0.0,
                annual_costs=0.0,
                total_acquisition_cost=0.0,
            )

        # Custos de aquisição
        imt = self._calculate_imt(purchase_price)
        stamp_duty = purchase_price * self.STAMP_DUTY_RATE
        lawyer = purchase_price * self.LAWYER_RATE
        total_acquisition = (
            purchase_price + imt + stamp_duty + self.NOTARY_REGISTRY_COST + lawyer
        )

        # Rendimento anual bruto
        annual_rent = monthly_rent * 12

        # Yield bruto
        gross_yield = (annual_rent / purchase_price) * 100

        # Custos anuais
        vpt = purchase_price * self.VPT_RATIO
        imi = vpt * self.IMI_RATE
        condo = self.CONDO_MONTHLY * 12
        maintenance = annual_rent * self.MAINTENANCE_RATE
        vacancy_cost = annual_rent * self.VACANCY_RATE
        effective_rent = annual_rent - vacancy_cost
        irs = effective_rent * self.IRS_RATE

        annual_costs = imi + condo + maintenance + self.INSURANCE_ANNUAL + irs + vacancy_cost

        # Yield líquido
        net_income = effective_rent - imi - condo - maintenance - self.INSURANCE_ANNUAL - irs
        net_yield = (net_income / total_acquisition) * 100

        result = YieldResult(
            gross_yield_pct=round(gross_yield, 2),
            net_yield_pct=round(net_yield, 2),
            imt=round(imt, 2),
            stamp_duty=round(stamp_duty, 2),
            annual_costs=round(annual_costs, 2),
            total_acquisition_cost=round(total_acquisition, 2),
        )

        logger.debug(
            f"Yield calculado para {municipality}: bruto={result.gross_yield_pct}%, "
            f"líquido={result.net_yield_pct}%, aquisição={result.total_acquisition_cost}€"
        )

        return result

    @staticmethod
    def _calculate_imt(price: float) -> float:
        """Calcula o IMT (Imposto Municipal sobre Transmissões).

        Tabela progressiva para habitação secundária/investimento em Portugal.

        Args:
            price: Preço de compra em euros.

        Returns:
            Valor do IMT em euros.
        """
        if price <= 101_917:
            return price * 0.01
        elif price <= 139_412:
            return price * 0.02
        elif price <= 190_086:
            return price * 0.05
        elif price <= 316_772:
            return price * 0.07
        elif price <= 633_453:
            return price * 0.08
        else:
            return price * 0.06
