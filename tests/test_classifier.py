"""Testes para o classificador de oportunidades imobiliárias.

Testa o OpportunityClassifier com mock da API Anthropic,
incluindo os dados de teste definidos no CLAUDE.md.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer.classifier import OpportunityClassifier, OpportunityResult
from src.analyzer.prompts import BATCH_TEMPLATE, SYSTEM_PROMPT


# ---------- Fixtures ----------

TEST_MESSAGES: List[Dict[str, Any]] = [
    {"index": 0, "text": "Bom dia a todos!", "group": "Consultores Lisboa"},
    {
        "index": 1,
        "text": "T2 em Sacavém, 85m2, remodelado, 3º andar com elevador. Preço: 195.000€. Contactar João 912345678",
        "group": "Partilhas AML",
    },
    {
        "index": 2,
        "text": "URGENTE - Casal em processo de divórcio precisa vender T3 em Almada, Pragal. 110m2, vista rio. Querem despachar rápido. 180.000€ negociáveis. Não está nos portais.",
        "group": "Off Market Sul",
    },
    {
        "index": 3,
        "text": "Alguém conhece bom canalizador na zona de Sintra?",
        "group": "Consultores Lisboa",
    },
    {
        "index": 4,
        "text": "Prédio inteiro em Mouraria, Lisboa. 4 frações, 2 devolutas. Proprietário idoso quer vender tudo junto. 650.000€. Potencial de reabilitação enorme. DM para mais info.",
        "group": "Investidores PT",
    },
    {
        "index": 5,
        "text": "Oferta de crédito habitação — taxas desde 2.1%. Simulação gratuita. Contacte-nos!",
        "group": "Partilhas AML",
    },
    {
        "index": 6,
        "text": "Off-market: Moradia T4 em Cascais, São Domingos de Rana. 200m2 + jardim 500m2. Herança, família quer resolver rápido. 420.000€. Exclusivo, não partilhar.",
        "group": "Off Market Cascais",
    },
    {
        "index": 7,
        "text": "Terreno rústico 5000m2 em Mafra com viabilidade para 3 moradias conforme PU. 150.000€. Alvará em fase de aprovação.",
        "group": "Investidores PT",
    },
]


def _build_mock_response() -> List[Dict[str, Any]]:
    """Constrói a resposta simulada da IA para as mensagens de teste."""
    return [
        {
            "message_index": 0,
            "is_opportunity": False,
            "confidence": 0.05,
            "opportunity_type": None,
            "property_type": None,
            "location": None,
            "parish": None,
            "municipality": None,
            "district": None,
            "price": None,
            "area_m2": None,
            "bedrooms": None,
            "reasoning": "Cumprimento genérico, sem dados imobiliários.",
        },
        {
            "message_index": 1,
            "is_opportunity": True,
            "confidence": 0.7,
            "opportunity_type": "abaixo_mercado",
            "property_type": "apartamento",
            "location": "Sacavém",
            "parish": "Sacavém",
            "municipality": "Loures",
            "district": "Lisboa",
            "price": 195000,
            "area_m2": 85,
            "bedrooms": 2,
            "reasoning": "T2 remodelado com preço possivelmente abaixo do mercado para a zona.",
        },
        {
            "message_index": 2,
            "is_opportunity": True,
            "confidence": 0.92,
            "opportunity_type": "venda_urgente",
            "property_type": "apartamento",
            "location": "Pragal, Almada",
            "parish": "Pragal",
            "municipality": "Almada",
            "district": "Setúbal",
            "price": 180000,
            "area_m2": 110,
            "bedrooms": 3,
            "reasoning": "Venda urgente por divórcio, off-market, preço negociável. Forte indicador de oportunidade.",
        },
        {
            "message_index": 3,
            "is_opportunity": False,
            "confidence": 0.02,
            "opportunity_type": None,
            "property_type": None,
            "location": None,
            "parish": None,
            "municipality": None,
            "district": None,
            "price": None,
            "area_m2": None,
            "bedrooms": None,
            "reasoning": "Pedido de recomendação de canalizador, não é imobiliário.",
        },
        {
            "message_index": 4,
            "is_opportunity": True,
            "confidence": 0.88,
            "opportunity_type": "predio_inteiro",
            "property_type": "prédio",
            "location": "Mouraria, Lisboa",
            "parish": "Santa Maria Maior",
            "municipality": "Lisboa",
            "district": "Lisboa",
            "price": 650000,
            "area_m2": None,
            "bedrooms": None,
            "reasoning": "Prédio inteiro com frações devolutas para reabilitação. Potencial elevado.",
        },
        {
            "message_index": 5,
            "is_opportunity": False,
            "confidence": 0.03,
            "opportunity_type": None,
            "property_type": None,
            "location": None,
            "parish": None,
            "municipality": None,
            "district": None,
            "price": None,
            "area_m2": None,
            "bedrooms": None,
            "reasoning": "Publicidade de crédito habitação, não é uma oportunidade imobiliária.",
        },
        {
            "message_index": 6,
            "is_opportunity": True,
            "confidence": 0.95,
            "opportunity_type": "off_market",
            "property_type": "moradia",
            "location": "São Domingos de Rana, Cascais",
            "parish": "São Domingos de Rana",
            "municipality": "Cascais",
            "district": "Lisboa",
            "price": 420000,
            "area_m2": 200,
            "bedrooms": 4,
            "reasoning": "Off-market, herança, venda urgente. Dados completos e preço potencialmente abaixo do mercado.",
        },
        {
            "message_index": 7,
            "is_opportunity": True,
            "confidence": 0.82,
            "opportunity_type": "terreno_viabilidade",
            "property_type": "terreno",
            "location": "Mafra",
            "parish": None,
            "municipality": "Mafra",
            "district": "Lisboa",
            "price": 150000,
            "area_m2": 5000,
            "bedrooms": None,
            "reasoning": "Terreno com viabilidade construtiva aprovada para 3 moradias.",
        },
    ]


@pytest.fixture
def mock_anthropic_client():
    """Cria um mock do cliente Anthropic."""
    client = MagicMock()
    response = MagicMock()
    content_block = MagicMock()
    content_block.text = json.dumps(_build_mock_response(), ensure_ascii=False)
    response.content = [content_block]
    client.messages.create.return_value = response
    return client


@pytest.fixture
def classifier(mock_anthropic_client):
    """Cria um classificador com cliente Anthropic mockado."""
    with patch("src.analyzer.classifier.get_settings") as mock_settings:
        settings = MagicMock()
        settings.anthropic_api_key = "test-key"
        settings.ai_model = "claude-haiku-4-5-20251001"
        settings.ai_max_tokens = 4096
        settings.ai_temperature = 0.1
        mock_settings.return_value = settings
        return OpportunityClassifier(client=mock_anthropic_client)


# ---------- Testes ----------


class TestClassifyBatch:
    """Testes para o método classify_batch."""

    def test_returns_empty_for_empty_input(self, classifier):
        """Retorna lista vazia quando não há mensagens."""
        results = classifier.classify_batch([])
        assert results == []

    def test_classifies_all_messages(self, classifier):
        """Classifica todas as mensagens do batch."""
        results = classifier.classify_batch(TEST_MESSAGES)
        assert len(results) == len(TEST_MESSAGES)

    def test_non_opportunities_detected(self, classifier):
        """Mensagens 0, 3, 5 não são oportunidades."""
        results = classifier.classify_batch(TEST_MESSAGES)
        results_by_index = {r.message_index: r for r in results}

        for idx in [0, 3, 5]:
            assert not results_by_index[idx].is_opportunity, (
                f"Mensagem {idx} deveria NÃO ser oportunidade"
            )

    def test_opportunities_detected(self, classifier):
        """Mensagens 1, 2, 4, 6, 7 são oportunidades."""
        results = classifier.classify_batch(TEST_MESSAGES)
        results_by_index = {r.message_index: r for r in results}

        for idx in [1, 2, 4, 6, 7]:
            assert results_by_index[idx].is_opportunity, (
                f"Mensagem {idx} deveria ser oportunidade"
            )

    def test_urgent_offmarket_high_confidence(self, classifier):
        """Mensagens 2 e 6 têm confiança mais alta (urgentes + off-market)."""
        results = classifier.classify_batch(TEST_MESSAGES)
        results_by_index = {r.message_index: r for r in results}

        assert results_by_index[2].confidence >= 0.85
        assert results_by_index[6].confidence >= 0.85

    def test_building_high_confidence(self, classifier):
        """Mensagem 4 tem confiança alta (prédio inteiro, reabilitação)."""
        results = classifier.classify_batch(TEST_MESSAGES)
        results_by_index = {r.message_index: r for r in results}

        assert results_by_index[4].confidence >= 0.8

    def test_result_dataclass_fields(self, classifier):
        """Verifica que os resultados têm todos os campos esperados."""
        results = classifier.classify_batch(TEST_MESSAGES)

        for result in results:
            assert isinstance(result, OpportunityResult)
            assert isinstance(result.message_index, int)
            assert isinstance(result.is_opportunity, bool)
            assert isinstance(result.confidence, float)
            assert isinstance(result.reasoning, str)
            assert 0.0 <= result.confidence <= 1.0

    def test_opportunity_extracts_location(self, classifier):
        """Oportunidades têm localização extraída."""
        results = classifier.classify_batch(TEST_MESSAGES)
        results_by_index = {r.message_index: r for r in results}

        # Mensagem 2: Almada, Pragal
        assert results_by_index[2].municipality == "Almada"
        assert results_by_index[2].parish == "Pragal"

        # Mensagem 6: Cascais
        assert results_by_index[6].municipality == "Cascais"

    def test_opportunity_extracts_price(self, classifier):
        """Oportunidades têm preço extraído."""
        results = classifier.classify_batch(TEST_MESSAGES)
        results_by_index = {r.message_index: r for r in results}

        assert results_by_index[1].price == 195000
        assert results_by_index[2].price == 180000
        assert results_by_index[4].price == 650000

    def test_api_called_with_correct_params(self, classifier, mock_anthropic_client):
        """Verifica que a API é chamada com os parâmetros corretos."""
        classifier.classify_batch(TEST_MESSAGES)

        mock_anthropic_client.messages.create.assert_called_once()
        call_kwargs = mock_anthropic_client.messages.create.call_args[1]

        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["max_tokens"] == 4096
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["system"] == SYSTEM_PROMPT


class TestBatching:
    """Testes para o batching de mensagens."""

    def test_splits_large_batch(self, mock_anthropic_client):
        """Divide mensagens em chunks quando excedem BATCH_SIZE."""
        with patch("src.analyzer.classifier.get_settings") as mock_settings:
            settings = MagicMock()
            settings.anthropic_api_key = "test-key"
            settings.ai_model = "claude-haiku-4-5-20251001"
            settings.ai_max_tokens = 4096
            settings.ai_temperature = 0.1
            mock_settings.return_value = settings

            classifier = OpportunityClassifier(client=mock_anthropic_client)
            classifier.BATCH_SIZE = 3

            # Preparar respostas para cada chunk
            def create_response(chunk_indices):
                items = [
                    {
                        "message_index": i,
                        "is_opportunity": False,
                        "confidence": 0.1,
                        "opportunity_type": None,
                        "property_type": None,
                        "location": None,
                        "parish": None,
                        "municipality": None,
                        "district": None,
                        "price": None,
                        "area_m2": None,
                        "bedrooms": None,
                        "reasoning": "Teste",
                    }
                    for i in chunk_indices
                ]
                response = MagicMock()
                content_block = MagicMock()
                content_block.text = json.dumps(items)
                response.content = [content_block]
                return response

            # 8 mensagens / batch_size 3 = 3 chamadas
            mock_anthropic_client.messages.create.side_effect = [
                create_response([0, 1, 2]),
                create_response([3, 4, 5]),
                create_response([6, 7]),
            ]

            results = classifier.classify_batch(TEST_MESSAGES)

            assert mock_anthropic_client.messages.create.call_count == 3
            assert len(results) == 8


class TestParseResponse:
    """Testes para o parse de respostas JSON."""

    def test_parse_valid_json(self, classifier):
        """Faz parse de JSON válido."""
        json_str = json.dumps([{"message_index": 0, "is_opportunity": False}])
        result = classifier._parse_response(json_str)
        assert len(result) == 1

    def test_parse_json_with_markdown_blocks(self, classifier):
        """Faz parse de JSON envolvido em code blocks markdown."""
        json_str = '```json\n[{"message_index": 0, "is_opportunity": false}]\n```'
        result = classifier._parse_response(json_str)
        assert len(result) == 1

    def test_parse_json_with_surrounding_text(self, classifier):
        """Extrai JSON de texto com conteúdo extra."""
        text = 'Aqui está o resultado: [{"message_index": 0, "is_opportunity": false}] Fim.'
        result = classifier._parse_response(text)
        assert len(result) == 1

    def test_parse_invalid_json_returns_empty(self, classifier):
        """Retorna lista vazia para JSON inválido."""
        result = classifier._parse_response("isto não é JSON")
        assert result == []


class TestFallback:
    """Testes para o comportamento de fallback."""

    def test_api_error_returns_fallback(self, mock_anthropic_client):
        """Em caso de erro da API, retorna resultados fallback."""
        with patch("src.analyzer.classifier.get_settings") as mock_settings:
            settings = MagicMock()
            settings.anthropic_api_key = "test-key"
            settings.ai_model = "claude-haiku-4-5-20251001"
            settings.ai_max_tokens = 4096
            settings.ai_temperature = 0.1
            mock_settings.return_value = settings

            mock_anthropic_client.messages.create.side_effect = Exception("API error")

            classifier = OpportunityClassifier(client=mock_anthropic_client)
            messages = [{"index": 0, "text": "teste", "group": "Grupo"}]
            results = classifier.classify_batch(messages)

            assert len(results) == 1
            assert not results[0].is_opportunity
            assert results[0].confidence == 0.0


class TestPrompts:
    """Testes para os prompts."""

    def test_system_prompt_not_empty(self):
        """System prompt não está vazio."""
        assert len(SYSTEM_PROMPT) > 100

    def test_batch_template_has_placeholders(self):
        """Batch template tem os placeholders necessários."""
        assert "{n}" in BATCH_TEMPLATE
        assert "{messages_json}" in BATCH_TEMPLATE

    def test_batch_template_formats_correctly(self):
        """Batch template formata corretamente."""
        result = BATCH_TEMPLATE.format(n=5, messages_json="[]")
        assert "5" in result
        assert "[]" in result
