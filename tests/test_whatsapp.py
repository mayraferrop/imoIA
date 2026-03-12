"""Testes para o cliente WhatsApp (Baileys Bridge + Whapi.Cloud).

Testa WhatsAppClient com mocks de httpx — nunca chama a API real.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.whatsapp.client import WhatsAppClient


@pytest.fixture
def client() -> WhatsAppClient:
    """Cria um WhatsAppClient com token Whapi (backend pago)."""
    return WhatsAppClient(token="test-token-123", base_url="https://gate.whapi.cloud")


@pytest.fixture
def baileys_client() -> WhatsAppClient:
    """Cria um WhatsAppClient com backend Baileys (gratuito)."""
    return WhatsAppClient(token=None, base_url="http://localhost:3000")


class TestListActiveGroups:
    """Testes para list_active_groups."""

    def test_returns_active_groups(self, client: WhatsAppClient) -> None:
        """Retorna apenas grupos não arquivados."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "groups": [
                {"id": "g1", "name": "Investidores PT", "is_archived": False},
                {"id": "g2", "name": "Consultores Lisboa", "is_archived": False},
                {"id": "g3", "name": "Grupo Antigo", "is_archived": True},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_request", return_value=mock_response.json.return_value):
            groups = client.list_active_groups()

        assert len(groups) == 2
        assert groups[0]["id"] == "g1"
        assert groups[1]["id"] == "g2"

    def test_returns_empty_list_when_no_groups(self, client: WhatsAppClient) -> None:
        """Retorna lista vazia se não houver grupos."""
        with patch.object(client, "_request", return_value={"groups": []}):
            groups = client.list_active_groups()

        assert groups == []

    def test_handles_missing_groups_key(self, client: WhatsAppClient) -> None:
        """Retorna lista vazia se resposta não tiver chave 'groups'."""
        with patch.object(client, "_request", return_value={}):
            groups = client.list_active_groups()

        assert groups == []


class TestFetchUnreadMessages:
    """Testes para fetch_unread_messages."""

    def test_returns_text_messages_only(self, client: WhatsAppClient) -> None:
        """Filtra mensagens que não sejam de texto."""
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_data = {
            "messages": [
                {
                    "id": "m1",
                    "from": "351912345678",
                    "from_name": "João",
                    "type": "text",
                    "text": {"body": "T2 em Sacavém, 85m2, 195.000€"},
                    "timestamp": 1704110400,
                },
                {
                    "id": "m2",
                    "from": "351918765432",
                    "from_name": "Maria",
                    "type": "image",
                    "image": {"caption": "foto"},
                    "timestamp": 1704110500,
                },
                {
                    "id": "m3",
                    "from": "351911111111",
                    "from_name": "Pedro",
                    "type": "text",
                    "text": {"body": "Moradia T4 em Cascais, 420.000€"},
                    "timestamp": 1704110600,
                },
            ]
        }

        with patch.object(client, "_request", return_value=mock_data):
            messages = client.fetch_unread_messages("group-123", since)

        assert len(messages) == 2
        assert messages[0]["content"] == "T2 em Sacavém, 85m2, 195.000€"
        assert messages[1]["content"] == "Moradia T4 em Cascais, 420.000€"

    def test_filters_messages_before_since(self, client: WhatsAppClient) -> None:
        """Filtra mensagens anteriores ao timestamp 'since'."""
        since = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_data = {
            "messages": [
                {
                    "id": "m1",
                    "from": "351912345678",
                    "from_name": "João",
                    "type": "text",
                    "text": {"body": "Mensagem antiga"},
                    "timestamp": 1704067200,  # 2024-01-01 00:00 UTC
                },
                {
                    "id": "m2",
                    "from": "351918765432",
                    "from_name": "Maria",
                    "type": "text",
                    "text": {"body": "Mensagem nova"},
                    "timestamp": 1704114000,  # 2024-01-01 13:00 UTC
                },
            ]
        }

        with patch.object(client, "_request", return_value=mock_data):
            messages = client.fetch_unread_messages("group-123", since)

        assert len(messages) == 1
        assert messages[0]["content"] == "Mensagem nova"

    def test_returns_empty_when_no_messages(self, client: WhatsAppClient) -> None:
        """Retorna lista vazia quando não há mensagens."""
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)

        with patch.object(client, "_request", return_value={"messages": []}):
            messages = client.fetch_unread_messages("group-123", since)

        assert messages == []

    def test_pagination_multiple_pages(self, client: WhatsAppClient) -> None:
        """Busca múltiplas páginas quando há mais de 100 mensagens."""
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)

        page1_messages = [
            {
                "id": f"m{i}",
                "from": "351912345678",
                "from_name": "João",
                "type": "text",
                "text": {"body": f"Mensagem {i}"},
                "timestamp": 1704110400 + i,
            }
            for i in range(100)
        ]
        page2_messages = [
            {
                "id": "m100",
                "from": "351912345678",
                "from_name": "João",
                "type": "text",
                "text": {"body": "Mensagem 100"},
                "timestamp": 1704110500,
            }
        ]

        call_count = 0

        def mock_request(method: str, endpoint: str, **kwargs) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"messages": page1_messages}
            return {"messages": page2_messages}

        with patch.object(client, "_request", side_effect=mock_request):
            messages = client.fetch_unread_messages("group-123", since)

        assert len(messages) == 101
        assert call_count == 2

    def test_message_dict_structure(self, client: WhatsAppClient) -> None:
        """Verifica estrutura do dicionário de mensagem retornado."""
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_data = {
            "messages": [
                {
                    "id": "msg-abc-123",
                    "from": "351912345678",
                    "from_name": "João Silva",
                    "type": "text",
                    "text": {"body": "T2 em Sacavém"},
                    "timestamp": 1704110400,
                },
            ]
        }

        with patch.object(client, "_request", return_value=mock_data):
            messages = client.fetch_unread_messages("group-123", since)

        msg = messages[0]
        assert msg["whatsapp_message_id"] == "msg-abc-123"
        assert msg["sender_id"] == "351912345678"
        assert msg["sender_name"] == "João Silva"
        assert msg["content"] == "T2 em Sacavém"
        assert msg["message_type"] == "text"
        assert isinstance(msg["timestamp"], datetime)


class TestArchiveGroup:
    """Testes para archive_group."""

    def test_archive_returns_true_on_success(self, client: WhatsAppClient) -> None:
        """Retorna True quando o grupo é arquivado com sucesso."""
        with patch.object(client, "_do_request", return_value={"result": "success"}):
            result = client.archive_group("group-123")

        assert result is True

    def test_archive_returns_true_on_already_archived(self, client: WhatsAppClient) -> None:
        """Retorna True quando 500 (provavelmente ja arquivado)."""
        with patch.object(client, "_do_request", side_effect=httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock(status_code=500)
        )):
            result = client.archive_group("group-123")

        assert result is True

    def test_archive_returns_false_on_failure(self, client: WhatsAppClient) -> None:
        """Retorna False quando o arquivamento falha com erro real."""
        with patch.object(client, "_do_request", side_effect=httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock(status_code=403)
        )):
            result = client.archive_group("group-123")

        assert result is False


class TestRequestWithRetry:
    """Testes para mecanismo de retry."""

    def test_builds_correct_headers(self, client: WhatsAppClient) -> None:
        """Verifica que os headers incluem Authorization Bearer."""
        assert client._headers["Authorization"] == "Bearer test-token-123"

    def test_request_raises_on_persistent_failure(self, client: WhatsAppClient) -> None:
        """Levanta exceção após esgotar retries."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.Client.request", return_value=mock_response):
            with pytest.raises(Exception):
                client._request("GET", "/test")


class TestBackendDetection:
    """Testes para detecao automatica de backend."""

    def test_detects_whapi_with_token(self) -> None:
        """Usa Whapi quando token esta presente."""
        c = WhatsAppClient(token="tk-123", base_url="https://gate.whapi.cloud")
        assert c.backend == "whapi"
        assert "Bearer" in c._headers.get("Authorization", "")

    def test_detects_baileys_with_localhost(self) -> None:
        """Usa Baileys quando base_url e localhost."""
        c = WhatsAppClient(token=None, base_url="http://localhost:3000")
        assert c.backend == "baileys"
        assert "Authorization" not in c._headers

    def test_detects_baileys_with_127(self) -> None:
        """Usa Baileys quando base_url e 127.0.0.1."""
        c = WhatsAppClient(token=None, base_url="http://127.0.0.1:3000")
        assert c.backend == "baileys"


class TestBaileysBackend:
    """Testes para o backend Baileys Bridge."""

    def test_get_status_connected(self, baileys_client: WhatsAppClient) -> None:
        """Retorna estado da conexao do bridge."""
        mock_data = {"status": "connected", "connected": True, "qr": None}
        with patch.object(baileys_client, "_request", return_value=mock_data):
            status = baileys_client.get_status()
        assert status["connected"] is True

    def test_get_status_offline(self, baileys_client: WhatsAppClient) -> None:
        """Retorna offline quando bridge nao esta disponivel."""
        with patch.object(baileys_client, "_request", side_effect=httpx.ConnectError("refused")):
            status = baileys_client.get_status()
        assert status["connected"] is False
        assert status["status"] == "offline"

    def test_fetch_baileys_messages(self, baileys_client: WhatsAppClient) -> None:
        """Busca mensagens via Baileys Bridge."""
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_data = {
            "messages": [
                {
                    "id": "msg1",
                    "from": "351912345678",
                    "pushName": "Joao",
                    "type": "text",
                    "body": "T2 em Sacavem, 195.000EUR",
                    "timestamp": 1704110400,
                },
                {
                    "id": "msg2",
                    "from": "351911111111",
                    "pushName": "Maria",
                    "type": "image",
                    "body": "",
                    "timestamp": 1704110500,
                },
            ]
        }

        with patch.object(baileys_client, "_request", return_value=mock_data):
            messages = baileys_client.fetch_unread_messages("group-123", since)

        assert len(messages) == 1
        assert messages[0]["content"] == "T2 em Sacavem, 195.000EUR"
        assert messages[0]["sender_name"] == "Joao"

    def test_fetch_baileys_empty(self, baileys_client: WhatsAppClient) -> None:
        """Retorna lista vazia quando nao ha mensagens."""
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with patch.object(baileys_client, "_request", return_value={"messages": []}):
            messages = baileys_client.fetch_unread_messages("group-123", since)
        assert messages == []
