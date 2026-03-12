"""Testes para os módulos de mercado: INE, Idealista, YieldCalculator.

Todos os acessos externos são mockados.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.market.idealista import IdealistaClient
from src.market.ine import INEClient, clear_cache
from src.market.yield_calculator import YieldCalculator, YieldResult


# ==================== INEClient ====================


class TestINEClient:
    """Testes para o cliente INE."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """Limpa o cache antes de cada teste."""
        clear_cache()
        yield
        clear_cache()

    @pytest.fixture
    def mock_ine_response(self):
        """Resposta simulada da API do INE (formato real)."""
        return [{
            "Dados": {
                "2024T3": [
                    {"geocod": "1106", "geodsg": "Lisboa", "valor": "3250.5"},
                    {"geocod": "1312", "geodsg": "Porto", "valor": "2100.0"},
                    {"geocod": "1503", "geodsg": "Almada", "valor": "1850.0"},
                ],
                "2024T2": [
                    {"geocod": "1106", "geodsg": "Lisboa", "valor": "3100.0"},
                    {"geocod": "1312", "geodsg": "Porto", "valor": "2050.0"},
                ],
            }
        }]

    @pytest.fixture
    def ine_client(self, mock_ine_response):
        """Cria um INEClient com HTTP mockado."""
        mock_http = MagicMock(spec=httpx.Client)
        response = MagicMock()
        response.json.return_value = mock_ine_response
        response.raise_for_status = MagicMock()
        mock_http.get.return_value = response

        with patch("src.market.ine.get_settings") as mock_settings:
            settings = MagicMock()
            settings.ine_base_url = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
            mock_settings.return_value = settings
            return INEClient(http_client=mock_http)

    def test_get_median_price_found(self, ine_client):
        """Retorna preço mediano quando município existe."""
        result = ine_client.get_median_price("Lisboa")
        assert result is not None
        assert result["price_m2"] == 3250.5
        assert result["quarter"] == "2024T3"
        assert result["source"] == "INE"

    def test_get_median_price_not_found(self, ine_client):
        """Retorna None quando município não existe."""
        result = ine_client.get_median_price("MunicipioInexistente12345")
        assert result is None

    def test_get_median_price_partial_match(self, ine_client):
        """Encontra município por correspondência parcial."""
        result = ine_client.get_median_price("porto")
        assert result is not None
        assert result["price_m2"] == 2100.0

    def test_cache_hit(self, ine_client):
        """Segunda chamada usa cache."""
        result1 = ine_client.get_median_price("Lisboa")
        result2 = ine_client.get_median_price("Lisboa")
        assert result1 == result2
        # O HTTP get só deve ter sido chamado uma vez (segunda usa cache)
        assert ine_client._http.get.call_count == 1

    def test_http_error_returns_none(self):
        """Retorna None em caso de erro HTTP."""
        mock_http = MagicMock(spec=httpx.Client)
        mock_http.get.side_effect = httpx.HTTPError("Connection error")

        with patch("src.market.ine.get_settings") as mock_settings:
            settings = MagicMock()
            settings.ine_base_url = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
            mock_settings.return_value = settings
            client = INEClient(http_client=mock_http)
            result = client.get_median_price("Lisboa")
            assert result is None


# ==================== IdealistaClient ====================


class TestIdealistaClient:
    """Testes para o cliente Idealista."""

    @pytest.fixture
    def mock_token_response(self):
        """Resposta simulada do endpoint de token."""
        response = MagicMock()
        response.json.return_value = {
            "access_token": "test-bearer-token",
            "expires_in": 3600,
        }
        response.raise_for_status = MagicMock()
        return response

    @pytest.fixture
    def mock_search_response(self):
        """Resposta simulada da pesquisa."""
        response = MagicMock()
        response.json.return_value = {
            "elementList": [
                {"priceByArea": 3200.0, "url": "https://idealista.pt/1"},
                {"priceByArea": 3400.0, "url": "https://idealista.pt/2"},
                {"priceByArea": 3100.0, "url": "https://idealista.pt/3"},
            ],
            "total": 3,
        }
        response.raise_for_status = MagicMock()
        return response

    @pytest.fixture
    def idealista_client(self, mock_token_response, mock_search_response):
        """Cria um IdealistaClient com HTTP mockado."""
        mock_http = MagicMock(spec=httpx.Client)
        mock_http.post.side_effect = [mock_token_response, mock_search_response]

        with patch("src.market.idealista.get_settings") as mock_settings:
            settings = MagicMock()
            settings.idealista_client_id = "test-client-id"
            settings.idealista_client_secret = "test-client-secret"
            settings.idealista_base_url = "https://api.idealista.com/3.5/"
            mock_settings.return_value = settings
            return IdealistaClient(http_client=mock_http)

    def test_search_comparables_returns_data(self, idealista_client):
        """Retorna dados de comparáveis quando pesquisa tem resultados."""
        result = idealista_client.search_comparables("Lisboa", "apartamento", 85.0)
        assert result is not None
        assert "avg_price_m2" in result
        assert "listings_count" in result
        assert "comparable_urls" in result
        assert result["listings_count"] == 3
        assert len(result["comparable_urls"]) == 3

    def test_search_comparables_avg_price(self, idealista_client):
        """Calcula preço médio por m2 corretamente."""
        result = idealista_client.search_comparables("Lisboa", "apartamento", 85.0)
        expected_avg = round((3200.0 + 3400.0 + 3100.0) / 3, 2)
        assert result["avg_price_m2"] == expected_avg

    def test_no_credentials_returns_none(self):
        """Retorna None silenciosamente sem credenciais."""
        with patch("src.market.idealista.get_settings") as mock_settings:
            settings = MagicMock()
            settings.idealista_client_id = ""
            settings.idealista_client_secret = ""
            mock_settings.return_value = settings

            client = IdealistaClient()
            result = client.search_comparables("Lisboa", "apartamento", 85.0)
            assert result is None

    def test_empty_results_returns_none(self, mock_token_response):
        """Retorna None quando não há resultados."""
        empty_response = MagicMock()
        empty_response.json.return_value = {"elementList": [], "total": 0}
        empty_response.raise_for_status = MagicMock()

        mock_http = MagicMock(spec=httpx.Client)
        mock_http.post.side_effect = [mock_token_response, empty_response]

        with patch("src.market.idealista.get_settings") as mock_settings:
            settings = MagicMock()
            settings.idealista_client_id = "test-id"
            settings.idealista_client_secret = "test-secret"
            settings.idealista_base_url = "https://api.idealista.com/3.5/"
            mock_settings.return_value = settings

            client = IdealistaClient(http_client=mock_http)
            result = client.search_comparables("Lisboa", "apartamento", 85.0)
            assert result is None

    def test_http_error_returns_none(self):
        """Retorna None em caso de erro HTTP."""
        mock_http = MagicMock(spec=httpx.Client)
        mock_http.post.side_effect = httpx.HTTPError("Connection error")

        with patch("src.market.idealista.get_settings") as mock_settings:
            settings = MagicMock()
            settings.idealista_client_id = "test-id"
            settings.idealista_client_secret = "test-secret"
            settings.idealista_base_url = "https://api.idealista.com/3.5/"
            mock_settings.return_value = settings

            client = IdealistaClient(http_client=mock_http)
            result = client.search_comparables("Lisboa", "apartamento", 85.0)
            assert result is None


# ==================== YieldCalculator ====================


class TestYieldCalculator:
    """Testes para a calculadora de yield."""

    @pytest.fixture
    def calculator(self):
        """Cria uma instância de YieldCalculator."""
        return YieldCalculator()

    def test_returns_yield_result(self, calculator):
        """Retorna uma instância de YieldResult."""
        result = calculator.calculate(200_000, 900)
        assert isinstance(result, YieldResult)

    def test_gross_yield_calculation(self, calculator):
        """Calcula yield bruto corretamente."""
        result = calculator.calculate(200_000, 1000)
        # Yield bruto = (1000 * 12) / 200000 * 100 = 6.0%
        assert result.gross_yield_pct == 6.0

    def test_net_yield_lower_than_gross(self, calculator):
        """Yield líquido é sempre menor que o bruto."""
        result = calculator.calculate(200_000, 1000)
        assert result.net_yield_pct < result.gross_yield_pct

    def test_imt_tier_1(self, calculator):
        """IMT correto para imóveis até 101.917€."""
        result = calculator.calculate(100_000, 500)
        assert result.imt == 1000.0  # 1% de 100.000

    def test_imt_tier_2(self, calculator):
        """IMT correto para imóveis entre 101.917€ e 139.412€."""
        result = calculator.calculate(120_000, 600)
        assert result.imt == 2400.0  # 2% de 120.000

    def test_imt_tier_3(self, calculator):
        """IMT correto para imóveis entre 139.412€ e 190.086€."""
        result = calculator.calculate(180_000, 900)
        assert result.imt == 9000.0  # 5% de 180.000

    def test_imt_tier_4(self, calculator):
        """IMT correto para imóveis entre 190.086€ e 316.772€."""
        result = calculator.calculate(250_000, 1200)
        assert result.imt == 17500.0  # 7% de 250.000

    def test_imt_tier_5(self, calculator):
        """IMT correto para imóveis entre 316.772€ e 633.453€."""
        result = calculator.calculate(500_000, 2500)
        assert result.imt == 40000.0  # 8% de 500.000

    def test_imt_tier_6(self, calculator):
        """IMT correto para imóveis acima de 633.453€."""
        result = calculator.calculate(700_000, 3500)
        assert result.imt == 42000.0  # 6% de 700.000 (taxa única)

    def test_stamp_duty(self, calculator):
        """Imposto de selo calculado corretamente (0.8%)."""
        result = calculator.calculate(200_000, 1000)
        assert result.stamp_duty == 1600.0  # 0.8% de 200.000

    def test_total_acquisition_cost(self, calculator):
        """Custo total de aquisição inclui todos os componentes."""
        price = 200_000
        result = calculator.calculate(price, 1000)

        imt = price * 0.07  # Tier 4: 190.086-316.772 → 7%
        stamp_duty = price * 0.008
        notary = 1500.0
        lawyer = price * 0.015
        expected = price + imt + stamp_duty + notary + lawyer

        assert result.total_acquisition_cost == round(expected, 2)

    def test_zero_price_returns_zero_yields(self, calculator):
        """Preço zero retorna yields zero."""
        result = calculator.calculate(0, 1000)
        assert result.gross_yield_pct == 0.0
        assert result.net_yield_pct == 0.0

    def test_zero_rent_returns_zero_yields(self, calculator):
        """Renda zero retorna yields zero."""
        result = calculator.calculate(200_000, 0)
        assert result.gross_yield_pct == 0.0
        assert result.net_yield_pct == 0.0

    def test_annual_costs_positive(self, calculator):
        """Custos anuais são positivos."""
        result = calculator.calculate(200_000, 1000)
        assert result.annual_costs > 0

    def test_realistic_scenario(self, calculator):
        """Cenário realista: T2 em Lisboa a 200k com renda de 900€/mês."""
        result = calculator.calculate(200_000, 900)

        # Yield bruto esperado: (900 * 12) / 200000 * 100 = 5.4%
        assert result.gross_yield_pct == 5.4

        # Yield líquido deve ser positivo mas menor que bruto
        assert 0 < result.net_yield_pct < result.gross_yield_pct

        # IMT para 200.000€ (tier 4: 7%)
        assert result.imt == 14000.0

        # Stamp duty
        assert result.stamp_duty == 1600.0
