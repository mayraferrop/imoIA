"""Testes para o modulo M2 — Pesquisa de Mercado.

Testa:
- CasafariClient (mapeamentos, parsing, graceful fallback)
- MarketService (comparaveis, avaliacao, alertas)
- Integracao com INE (fallback sem CASAFARI)
- Modelos de dados (MarketComparable, PropertyValuation, etc.)
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.modules.m2_market.casafari_client import CasafariClient


# ---------------------------------------------------------------------------
# CasafariClient — mapeamentos
# ---------------------------------------------------------------------------


class TestCasafariClientMapping:
    """Testa mapeamentos de tipos e condicoes."""

    def test_map_property_type_apartamento(self):
        result = CasafariClient.map_property_type("apartamento")
        assert "apartment" in result
        assert "studio" in result
        assert "duplex" in result

    def test_map_property_type_moradia(self):
        result = CasafariClient.map_property_type("moradia")
        assert "house" in result
        assert "villa" in result

    def test_map_property_type_terreno(self):
        result = CasafariClient.map_property_type("terreno")
        assert "plot" in result

    def test_map_property_type_predio(self):
        result = CasafariClient.map_property_type("predio")
        assert "apartment_building" in result

    def test_map_property_type_none(self):
        assert CasafariClient.map_property_type(None) == []

    def test_map_property_type_unknown(self):
        result = CasafariClient.map_property_type("xpto")
        assert result == ["xpto"]

    def test_map_condition_novo(self):
        assert CasafariClient.map_condition("novo") == "new"

    def test_map_condition_renovado(self):
        assert CasafariClient.map_condition("renovado") == "very-good"

    def test_map_condition_usado(self):
        assert CasafariClient.map_condition("usado") == "used"

    def test_map_condition_para_renovar(self):
        assert CasafariClient.map_condition("para_renovar") == "used"

    def test_map_condition_ruina(self):
        assert CasafariClient.map_condition("ruina") == "ruin"

    def test_map_condition_none(self):
        assert CasafariClient.map_condition(None) is None


# ---------------------------------------------------------------------------
# CasafariClient — parsing de alertas
# ---------------------------------------------------------------------------


class TestCasafariClientParsing:
    """Testa parsing de respostas da API CASAFARI."""

    def _sample_alert(self) -> dict:
        """Alerta de exemplo baseado na documentacao CASAFARI."""
        return {
            "alert_id": 412269711,
            "listing_id": 110358519,
            "property_id": 51277418,
            "alert_type": "sale_price",
            "alert_subtype": "price_down",
            "old_value": "549000",
            "new_value": "545000",
            "alert_date": "2021-10-24",
            "property_url": "https://www.casafari.com/home-sale/property-51277418",
            "listing_url": "https://www.idealista.pt/imovel/31407575/",
            "type": "apartment",
            "type_group": "apartment",
            "location": {
                "location_id": 28649,
                "name": "Santa Engrácia",
                "administrative_level": "Localidade",
            },
            "locations_structure": [
                {
                    "location_id": 499,
                    "name": "Portugal",
                    "administrative_level": "País",
                },
                {
                    "location_id": 1599,
                    "name": "Lisbon",
                    "administrative_level": "Distrito",
                },
                {
                    "location_id": 1600,
                    "name": "Lisbon",
                    "administrative_level": "Concelho",
                },
                {
                    "location_id": 1760,
                    "name": "São Vicente",
                    "administrative_level": "Freguesia",
                },
            ],
            "coordinates": {"latitude": 38.7194, "longitude": -9.12209},
            "condition": "used",
            "sale_price": 545000,
            "sale_price_per_sqm": 4192,
            "sale_status": "active",
            "sale_currency": "EUR",
            "total_area": 130,
            "living_area": 128,
            "bedrooms": 3,
            "bathrooms": 2,
            "construction_year": 2015,
            "energy_certificate": "B",
            "features": {
                "floor": "middle",
                "characteristics": ["balcony", "elevator", "garage"],
            },
            "agency": "Helena Almeida Pires",
            "contacts_info": {"phone": "215551538"},
            "description": "Apartamento T3 em São Vicente.",
        }

    def test_parse_alert_basic_fields(self):
        alert = self._sample_alert()
        result = CasafariClient.parse_alert_to_comparable(alert)

        assert result["source"] == "casafari"
        assert result["source_id"] == "51277418"
        assert result["property_type"] == "apartment"
        assert result["bedrooms"] == 3
        assert result["bathrooms"] == 2
        assert result["listing_price"] == 545000
        assert result["price_per_m2"] == 4192
        assert result["gross_area_m2"] == 130
        assert result["useful_area_m2"] == 128
        assert result["condition"] == "used"
        assert result["construction_year"] == 2015
        assert result["energy_certificate"] == "B"
        assert result["currency"] == "EUR"

    def test_parse_alert_location(self):
        alert = self._sample_alert()
        result = CasafariClient.parse_alert_to_comparable(alert)

        assert result["district"] == "Lisbon"
        assert result["municipality"] == "Lisbon"
        assert result["parish"] == "São Vicente"
        assert result["latitude"] == 38.7194
        assert result["longitude"] == -9.12209

    def test_parse_alert_comparison_type_active(self):
        alert = self._sample_alert()
        result = CasafariClient.parse_alert_to_comparable(alert)
        assert result["comparison_type"] == "listing_active"

    def test_parse_alert_comparison_type_sold(self):
        alert = self._sample_alert()
        alert["sale_status"] = "sold"
        alert["alert_subtype"] = "sold"
        result = CasafariClient.parse_alert_to_comparable(alert)
        assert result["comparison_type"] == "listing_sold"

    def test_parse_alert_urls(self):
        alert = self._sample_alert()
        result = CasafariClient.parse_alert_to_comparable(alert)
        assert "casafari.com" in result["source_url"]

    def test_parse_alert_raw_data_preserved(self):
        alert = self._sample_alert()
        result = CasafariClient.parse_alert_to_comparable(alert)
        assert result["raw_data"] == alert


# ---------------------------------------------------------------------------
# CasafariClient — configuracao e fallback
# ---------------------------------------------------------------------------


class TestCasafariClientConfig:
    """Testa configuracao e fallback graceful."""

    @patch("src.modules.m2_market.casafari_client.get_settings")
    def test_is_configured_with_api_token(self, mock_settings):
        settings = MagicMock()
        settings.casafari_api_token = "test-token"
        settings.casafari_username = ""
        settings.casafari_password = ""
        settings.casafari_base_url = "https://api.casafari.com"
        mock_settings.return_value = settings

        client = CasafariClient()
        assert client.is_configured is True

    @patch("src.modules.m2_market.casafari_client.get_settings")
    def test_is_configured_with_credentials(self, mock_settings):
        settings = MagicMock()
        settings.casafari_api_token = ""
        settings.casafari_username = "user@test.com"
        settings.casafari_password = "password"
        settings.casafari_base_url = "https://api.casafari.com"
        mock_settings.return_value = settings

        client = CasafariClient()
        assert client.is_configured is True

    @patch("src.modules.m2_market.casafari_client.get_settings")
    def test_not_configured(self, mock_settings):
        settings = MagicMock()
        settings.casafari_api_token = ""
        settings.casafari_username = ""
        settings.casafari_password = ""
        settings.casafari_base_url = "https://api.casafari.com"
        mock_settings.return_value = settings

        client = CasafariClient()
        assert client.is_configured is False


# ---------------------------------------------------------------------------
# CasafariClient — property detail parsing
# ---------------------------------------------------------------------------


class TestCasafariPropertyDetail:
    """Testa parsing de detalhe de propriedade."""

    def test_parse_property_detail(self):
        data = {
            "property_id": 6256230,
            "property_url": "https://www.casafari.com/home-sale/property-6256230",
            "sale_price": 350000,
            "sale_price_per_sqm": 2800,
            "rent_price": 0,
            "gross_yield": 0,
            "total_area": 125,
            "sale_time_on_market": {
                "date_start": "2020-06-12",
                "date_end": "2020-09-24",
                "days_on_market": 104,
            },
            "sale_price_history": [
                {
                    "date_start": "2020-06-12",
                    "date_end": "2020-08-01",
                    "sale_price_old": 380000,
                    "sale_price_new": 350000,
                },
            ],
            "listings": [
                {
                    "listing_id": 23587829,
                    "source_name": "Idealista",
                    "sale_price": 350000,
                    "agency": "Agency X",
                },
                {
                    "listing_id": 23587830,
                    "source_name": "OLX",
                    "sale_price": 355000,
                    "agency": "Agency Y",
                },
            ],
        }

        result = CasafariClient.parse_property_detail(data)

        assert result["property_id"] == 6256230
        assert result["sale_price"] == 350000
        assert result["days_on_market"] == 104
        assert len(result["price_history"]) == 1
        assert result["price_history"][0]["price_old"] == 380000
        assert result["price_history"][0]["price_new"] == 350000
        assert result["listings_count"] == 2
        assert result["listings_by_source"][0]["source_name"] == "Idealista"


# ---------------------------------------------------------------------------
# MarketService — graceful without CASAFARI
# ---------------------------------------------------------------------------


class TestMarketServiceGraceful:
    """Testa que o servico funciona sem CASAFARI (so INE)."""

    @patch("src.modules.m2_market.service.CasafariClient")
    @patch("src.modules.m2_market.service._get_ine_client")
    def test_find_comparables_without_casafari(self, mock_ine_factory, mock_casafari_cls):
        """Sem CASAFARI configurada retorna lista vazia."""
        mock_client = MagicMock()
        mock_client.is_configured = False
        mock_casafari_cls.return_value = mock_client
        mock_ine_factory.return_value = None

        from src.modules.m2_market.service import MarketService
        svc = MarketService()
        svc._casafari = mock_client

        result = svc.find_comparables(municipality="Lisboa")
        assert result["total"] == 0
        assert result["comparables"] == []


# ---------------------------------------------------------------------------
# Modelos M2
# ---------------------------------------------------------------------------


class TestM2Models:
    """Testa que os modelos M2 sao importaveis e tem os campos correctos."""

    def test_market_comparable_importable(self):
        from src.database.models_v2 import MarketComparable
        assert MarketComparable.__tablename__ == "market_comparables"

    def test_property_valuation_importable(self):
        from src.database.models_v2 import PropertyValuation
        assert PropertyValuation.__tablename__ == "property_valuations"

    def test_market_zone_stats_importable(self):
        from src.database.models_v2 import MarketZoneStats
        assert MarketZoneStats.__tablename__ == "market_zone_stats"

    def test_market_alert_importable(self):
        from src.database.models_v2 import MarketAlert
        assert MarketAlert.__tablename__ == "market_alerts"

    def test_market_comparable_fields(self):
        from src.database.models_v2 import MarketComparable
        cols = {c.name for c in MarketComparable.__table__.columns}
        expected = {
            "id", "tenant_id", "deal_id", "opportunity_id",
            "source", "source_id", "source_url",
            "property_type", "bedrooms", "bathrooms",
            "district", "municipality", "parish",
            "latitude", "longitude", "distance_km",
            "listing_price", "sale_price", "price_per_m2",
            "gross_area_m2", "useful_area_m2",
            "condition", "construction_year",
            "comparison_type", "raw_data",
            "fetched_at", "expires_at", "created_at",
        }
        assert expected.issubset(cols)

    def test_property_valuation_fields(self):
        from src.database.models_v2 import PropertyValuation
        cols = {c.name for c in PropertyValuation.__table__.columns}
        expected = {
            "id", "tenant_id", "deal_id",
            "estimated_value", "estimated_value_low", "estimated_value_high",
            "estimated_price_per_m2", "confidence_score",
            "avg_price_per_m2_zone", "median_price_per_m2_zone",
            "comparables_count", "source", "method",
        }
        assert expected.issubset(cols)

    def test_market_alert_fields(self):
        from src.database.models_v2 import MarketAlert
        cols = {c.name for c in MarketAlert.__table__.columns}
        expected = {
            "id", "tenant_id", "alert_name", "alert_type",
            "districts", "municipalities", "property_types",
            "price_min", "price_max",
            "casafari_feed_id", "is_active",
            "total_triggers", "notify_whatsapp",
        }
        assert expected.issubset(cols)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TestM2Schemas:
    """Testa schemas Pydantic do M2."""

    def test_comparable_search_request_defaults(self):
        from src.modules.m2_market.schemas import ComparableSearchRequest
        req = ComparableSearchRequest()
        assert req.radius_km == 1.0
        assert req.months_back == 12
        assert req.max_results == 20
        assert req.include_sold is True
        assert req.include_active is True

    def test_alert_create_request(self):
        from src.modules.m2_market.schemas import AlertCreateRequest
        req = AlertCreateRequest(
            alert_name="Test Alert",
            alert_type="new_listing",
            districts=["Lisboa"],
            price_max=500000,
        )
        assert req.alert_name == "Test Alert"
        assert req.districts == ["Lisboa"]
        assert req.notify_whatsapp is True

    def test_valuation_request_defaults(self):
        from src.modules.m2_market.schemas import ValuationRequest
        req = ValuationRequest()
        assert req.method == "hybrid"
