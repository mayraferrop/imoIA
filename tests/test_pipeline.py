"""Testes para o pipeline orquestrador.

Testa run_pipeline com mocks de todos os serviços.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.run import (
    PipelineResult,
    _enrich_opportunity,
    _filter_noise,
    _prepare_for_classifier,
    run_pipeline,
)


@pytest.fixture
def sample_messages() -> list:
    """Mensagens de exemplo para testes."""
    return [
        {
            "whatsapp_message_id": "m1",
            "sender_id": "351912345678",
            "sender_name": "João",
            "content": "Bom dia a todos!",
            "message_type": "text",
            "timestamp": datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        },
        {
            "whatsapp_message_id": "m2",
            "sender_id": "351918765432",
            "sender_name": "Maria",
            "content": "T2 em Sacavém, 85m2, remodelado, 3º andar com elevador. Preço: 195.000€. Contactar João 912345678",
            "message_type": "text",
            "timestamp": datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
        },
        {
            "whatsapp_message_id": "m3",
            "sender_id": "351911111111",
            "sender_name": "Pedro",
            "content": "Olá",
            "message_type": "text",
            "timestamp": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        },
        {
            "whatsapp_message_id": "m4",
            "sender_id": "351922222222",
            "sender_name": "Ana",
            "content": "URGENTE - Casal em divórcio vende T3 em Almada. 110m2, vista rio. 180.000€ negociáveis.",
            "message_type": "text",
            "timestamp": datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc),
        },
        {
            "whatsapp_message_id": "m5",
            "sender_id": "351933333333",
            "sender_name": "Carlos",
            "content": "Parabéns pelo negócio!",
            "message_type": "text",
            "timestamp": datetime(2024, 1, 1, 14, 0, tzinfo=timezone.utc),
        },
    ]


class TestFilterNoise:
    """Testes para a etapa de filtragem de ruído."""

    def test_removes_short_messages(self) -> None:
        """Remove mensagens com menos de 15 caracteres."""
        messages = [
            {"content": "Olá", "message_type": "text"},
            {"content": "T2 em Sacavém, 85m2, preço bom", "message_type": "text"},
        ]
        result = _filter_noise(messages)
        assert len(result) == 1
        assert result[0]["content"] == "T2 em Sacavém, 85m2, preço bom"

    def test_removes_noise_patterns(self) -> None:
        """Remove mensagens com padrões de ruído (bom dia, parabéns, etc.)."""
        messages = [
            {"content": "Bom dia a todos do grupo!", "message_type": "text"},
            {"content": "Boa tarde, como estão?", "message_type": "text"},
            {"content": "Parabéns pelo excelente negócio!", "message_type": "text"},
            {"content": "T3 em Almada, 180.000€, bom negócio", "message_type": "text"},
        ]
        result = _filter_noise(messages)
        assert len(result) == 1
        assert "Almada" in result[0]["content"]

    def test_removes_non_text_messages(self) -> None:
        """Remove mensagens que não sejam de texto (stickers, media)."""
        messages = [
            {"content": "foto da casa", "message_type": "image"},
            {"content": "T2 em Lisboa, 85m2, 200.000€ bom preço", "message_type": "text"},
            {"content": "sticker engraçado", "message_type": "sticker"},
        ]
        result = _filter_noise(messages)
        assert len(result) == 1

    def test_preserves_valid_messages(self) -> None:
        """Mantém mensagens válidas intactas."""
        messages = [
            {"content": "T2 em Sacavém, 85m2, remodelado. Preço: 195.000€", "message_type": "text"},
            {"content": "Moradia T4 em Cascais, 200m2 + jardim. 420.000€", "message_type": "text"},
        ]
        result = _filter_noise(messages)
        assert len(result) == 2

    def test_empty_input(self) -> None:
        """Retorna lista vazia para input vazio."""
        assert _filter_noise([]) == []


class TestPrepareForClassifier:
    """Testes para a transformação de formato para o classificador."""

    def test_transforms_message_format(self) -> None:
        """Transforma mensagens do pipeline para o formato do classificador."""
        messages = [
            {
                "whatsapp_message_id": "m1",
                "sender_id": "351912345678",
                "sender_name": "João",
                "content": "T2 em Sacavém, 85m2, 195.000€",
                "message_type": "text",
            },
            {
                "whatsapp_message_id": "m2",
                "sender_id": "351918765432",
                "sender_name": "Maria",
                "content": "Moradia T4 em Cascais, 420.000€",
                "message_type": "text",
            },
        ]
        result = _prepare_for_classifier(messages, "Investidores PT")

        assert len(result) == 2
        assert result[0] == {"index": 0, "text": "T2 em Sacavém, 85m2, 195.000€", "group": "Investidores PT"}
        assert result[1] == {"index": 1, "text": "Moradia T4 em Cascais, 420.000€", "group": "Investidores PT"}

    def test_empty_input(self) -> None:
        """Retorna lista vazia para input vazio."""
        assert _prepare_for_classifier([], "Grupo") == []


class TestRunPipeline:
    """Testes para o pipeline completo."""

    @patch("src.pipeline.run._get_whatsapp_client")
    @patch("src.pipeline.run._get_classifier")
    @patch("src.pipeline.run._get_market_services")
    @patch("src.pipeline.run.get_session")
    def test_pipeline_returns_result(
        self,
        mock_session: MagicMock,
        mock_market: MagicMock,
        mock_classifier: MagicMock,
        mock_whatsapp: MagicMock,
    ) -> None:
        """Pipeline retorna PipelineResult com contagens corretas."""
        # Setup WhatsApp mock
        wa_client = MagicMock()
        wa_client.list_active_groups.return_value = [
            {"id": "g1", "name": "Investidores PT"},
        ]
        wa_client.fetch_unread_messages.return_value = [
            {
                "whatsapp_message_id": "m1",
                "sender_id": "351912345678",
                "sender_name": "João",
                "content": "T2 em Sacavém, 85m2, remodelado. Preço: 195.000€. Contactar 912345678",
                "message_type": "text",
                "timestamp": datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            },
        ]
        wa_client.archive_group.return_value = True
        mock_whatsapp.return_value = wa_client

        # Setup classifier mock
        classifier = MagicMock()
        classifier.classify_batch.return_value = [
            MagicMock(
                message_index=0,
                is_opportunity=True,
                confidence=0.85,
                opportunity_type="venda",
                property_type="apartamento",
                location="Sacavém",
                parish=None,
                municipality="Loures",
                district="Lisboa",
                price=195000.0,
                area_m2=85.0,
                bedrooms=2,
                reasoning="Anúncio claro de venda com preço e detalhes",
            ),
        ]
        mock_classifier.return_value = classifier

        # Setup market services mock
        ine_client = MagicMock()
        ine_client.get_median_price.return_value = {"price_m2": 1800.0, "quarter": "2024-Q3"}
        idealista_client = MagicMock()
        idealista_client.search_comparables.return_value = {
            "avg_price_m2": 2100.0,
            "listings_count": 15,
            "comparable_urls": [],
        }
        yield_calc = MagicMock()
        yield_calc.calculate.return_value = MagicMock(
            gross_yield_pct=5.8,
            net_yield_pct=4.2,
            imt=3500.0,
            stamp_duty=1560.0,
            annual_costs=2400.0,
            total_acquisition_cost=200060.0,
        )
        mock_market.return_value = (ine_client, idealista_client, yield_calc)

        # Setup session mock
        session_mock = MagicMock()
        session_ctx = MagicMock()
        session_ctx.__enter__ = MagicMock(return_value=session_mock)
        session_ctx.__exit__ = MagicMock(return_value=False)
        mock_session.return_value = session_ctx

        # Simulate no existing group or message in DB
        session_mock.execute.return_value.scalar_one_or_none.return_value = None

        result = run_pipeline()

        assert isinstance(result, PipelineResult)
        assert result.messages_fetched >= 0
        assert result.groups_processed == 1
        assert isinstance(result.errors, list)

    @patch("src.pipeline.run._get_whatsapp_client")
    @patch("src.pipeline.run.get_session")
    def test_pipeline_handles_no_groups(
        self,
        mock_session: MagicMock,
        mock_whatsapp: MagicMock,
    ) -> None:
        """Pipeline termina normalmente quando não há grupos ativos."""
        wa_client = MagicMock()
        wa_client.list_active_groups.return_value = []
        mock_whatsapp.return_value = wa_client

        session_mock = MagicMock()
        session_ctx = MagicMock()
        session_ctx.__enter__ = MagicMock(return_value=session_mock)
        session_ctx.__exit__ = MagicMock(return_value=False)
        mock_session.return_value = session_ctx

        result = run_pipeline()

        assert result.messages_fetched == 0
        assert result.groups_processed == 0
        assert result.opportunities_found == 0

    @patch("src.pipeline.run._get_whatsapp_client")
    @patch("src.pipeline.run.get_session")
    def test_pipeline_continues_on_group_error(
        self,
        mock_session: MagicMock,
        mock_whatsapp: MagicMock,
    ) -> None:
        """Pipeline continua a processar outros grupos se um falhar."""
        wa_client = MagicMock()
        wa_client.list_active_groups.return_value = [
            {"id": "g1", "name": "Grupo com erro"},
            {"id": "g2", "name": "Grupo OK"},
        ]
        wa_client.fetch_unread_messages.side_effect = [
            Exception("API error"),
            [],
        ]
        mock_whatsapp.return_value = wa_client

        session_mock = MagicMock()
        session_ctx = MagicMock()
        session_ctx.__enter__ = MagicMock(return_value=session_mock)
        session_ctx.__exit__ = MagicMock(return_value=False)
        mock_session.return_value = session_ctx

        result = run_pipeline()

        assert result.groups_processed == 2
        assert len(result.errors) >= 1


class TestPipelineResult:
    """Testes para a dataclass PipelineResult."""

    def test_pipeline_result_creation(self) -> None:
        """PipelineResult pode ser criado com todos os campos."""
        result = PipelineResult(
            messages_fetched=50,
            opportunities_found=5,
            groups_processed=3,
            errors=["Erro no grupo X"],
        )
        assert result.messages_fetched == 50
        assert result.opportunities_found == 5
        assert result.groups_processed == 3
        assert result.errors == ["Erro no grupo X"]

    def test_pipeline_result_empty_errors(self) -> None:
        """PipelineResult aceita lista vazia de erros."""
        result = PipelineResult(
            messages_fetched=0,
            opportunities_found=0,
            groups_processed=0,
            errors=[],
        )
        assert result.errors == []
