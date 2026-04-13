"""Testes para src/shared/email_provider.py — envio de email via Resend."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.email_provider import send_email, validate_email


# ---------------------------------------------------------------------------
# validate_email
# ---------------------------------------------------------------------------


class TestValidateEmail:
    def test_valid_emails(self):
        assert validate_email("user@example.com")
        assert validate_email("a@b.co")
        assert validate_email("name+tag@domain.org")

    def test_invalid_emails(self):
        assert not validate_email("")
        assert not validate_email("noat")
        assert not validate_email("@no-local.com")
        assert not validate_email("spaces in@email.com")
        assert not validate_email("no@dots")


# ---------------------------------------------------------------------------
# send_email
# ---------------------------------------------------------------------------


def _run(coro):
    """Helper para correr coroutines em testes sync."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestSendEmailSuccess:
    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    @patch("src.shared.email_provider.httpx.AsyncClient")
    def test_sends_and_returns_id(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "email-123"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = _run(send_email(
            to="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
        ))

        assert result["sent"] is True
        assert result["id"] == "email-123"
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["to"] == ["user@example.com"]


class TestSendEmailNoApiKey:
    @patch.dict("os.environ", {"RESEND_API_KEY": ""})
    def test_graceful_degradation(self):
        result = _run(send_email(
            to="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
        ))

        assert result["sent"] is False
        assert "not configured" in result["reason"]


class TestSendEmailResendError:
    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    @patch("src.shared.email_provider.httpx.AsyncClient")
    def test_handles_4xx_error(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.text = '{"message": "Invalid email"}'

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = _run(send_email(
            to="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
        ))

        assert result["sent"] is False
        assert "422" in result["reason"]


class TestSendEmailInvalidFormat:
    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    def test_rejects_invalid_email(self):
        result = _run(send_email(
            to="not-an-email",
            subject="Test",
            html_body="<p>Hello</p>",
        ))

        assert result["sent"] is False
        assert "invalido" in result["reason"]


class TestSendCampaignIntegration:
    """Testes de integracao minima para EmailService.send_campaign."""

    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    @patch("src.shared.email_provider.httpx.AsyncClient")
    @patch("src.modules.m7_marketing.email_service.get_session")
    def test_send_campaign_success(self, mock_session_ctx, mock_client_cls):
        # Mock da campanha no BD
        mock_campaign = MagicMock()
        mock_campaign.id = "camp-1"
        mock_campaign.subject = "Nova oportunidade"
        mock_campaign.body_html = "<p>Test</p>"
        mock_campaign.status = "draft"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_campaign
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session_ctx.return_value = mock_session

        # Mock do Resend
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "resend-abc"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from src.modules.m7_marketing.email_service import EmailService
        es = EmailService()
        result = _run(es.send_campaign("camp-1", ["a@b.com", "c@d.com"]))

        assert result["sent_count"] == 2
        assert result["failed_count"] == 0

    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"})
    @patch("src.shared.email_provider.httpx.AsyncClient")
    @patch("src.modules.m7_marketing.email_service.get_session")
    def test_send_campaign_partial_failure(self, mock_session_ctx, mock_client_cls):
        mock_campaign = MagicMock()
        mock_campaign.id = "camp-2"
        mock_campaign.subject = "Test"
        mock_campaign.body_html = "<p>Test</p>"
        mock_campaign.status = "draft"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_campaign
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session_ctx.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "resend-xyz"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from src.modules.m7_marketing.email_service import EmailService
        es = EmailService()
        result = _run(es.send_campaign("camp-2", ["valid@test.com", "invalid-email"]))

        assert result["sent_count"] == 1
        assert result["failed_count"] == 1

    @patch.dict("os.environ", {"RESEND_API_KEY": ""})
    @patch("src.modules.m7_marketing.email_service.get_session")
    def test_send_campaign_no_resend_key(self, mock_session_ctx):
        mock_campaign = MagicMock()
        mock_campaign.id = "camp-3"
        mock_campaign.subject = "Test"
        mock_campaign.body_html = "<p>Test</p>"
        mock_campaign.status = "draft"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_campaign
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session_ctx.return_value = mock_session

        from src.modules.m7_marketing.email_service import EmailService
        es = EmailService()
        result = _run(es.send_campaign("camp-3", ["a@b.com"]))

        assert result["sent_count"] == 0
        assert result["failed_count"] == 1
