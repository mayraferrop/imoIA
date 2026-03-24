"""Testes para os endpoints do M3 — Motor Financeiro."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


class TestQuickIMT:
    """Testes para POST /api/v1/financial/quick-imt."""

    def test_100k_investimento(self) -> None:
        """100k investimento → IMT = 1.000EUR."""
        resp = client.post(
            "/api/v1/financial/quick-imt",
            json={"value": 100_000, "country": "PT", "is_hpp": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imt"] == 1_000.00
        assert data["imposto_selo"] == 800.00

    def test_295k_investimento(self) -> None:
        """295k investimento → IMT = 11.255,50EUR."""
        resp = client.post(
            "/api/v1/financial/quick-imt",
            json={"value": 295_000, "country": "PT", "is_hpp": False},
        )
        assert resp.status_code == 200
        assert resp.json()["imt"] == 11_255.50

    def test_100k_hpp_isento(self) -> None:
        """100k HPP → IMT = 0EUR (isento)."""
        resp = client.post(
            "/api/v1/financial/quick-imt",
            json={"value": 100_000, "country": "PT", "is_hpp": True},
        )
        assert resp.status_code == 200
        assert resp.json()["imt"] == 0.00

    def test_brasil_itbi(self) -> None:
        """500k Brasil → ITBI = 15.000."""
        resp = client.post(
            "/api/v1/financial/quick-imt",
            json={"value": 500_000, "country": "BR"},
        )
        assert resp.status_code == 200
        assert resp.json()["itbi"] == 15_000.00


class TestMAO:
    """Testes para POST /api/v1/financial/mao."""

    def test_mao_basic(self) -> None:
        """MAO = 500k x 0.70 - 100k = 250k."""
        resp = client.post(
            "/api/v1/financial/mao",
            json={"arv": 500_000, "renovation_total": 100_000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mao_70pct"] == 250_000.00
        assert data["mao_65pct"] == 225_000.00
        assert data["mao_60pct"] == 200_000.00


class TestFloorPrice:
    """Testes para POST /api/v1/financial/floor-price."""

    def test_floor_basic(self) -> None:
        """Floor price para 200k investido com 15% target."""
        resp = client.post(
            "/api/v1/financial/floor-price",
            json={
                "total_investment": 200_000,
                "roi_target_pct": 15,
                "comissao_venda_pct": 6.15,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["floor_price"] > 200_000
        assert data["profit_at_floor"] == 30_000.00
