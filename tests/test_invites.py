"""Testes para o sistema de convites — Fase 2B Dia 2.

Testa service layer com mocks de httpx (sem pytest-asyncio — usa asyncio.run).
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.invites import (
    _invite_status,
    accept_invite,
    create_invite,
    get_invite_by_token,
    list_invites,
    revoke_invite,
    send_invite_email,
)

ORG_ID = "11111111-2222-3333-4444-555555555555"
USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TOKEN = "test-token-abc123"


# ---------------------------------------------------------------------------
# Fixtures e helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("FRONTEND_URL", "https://imoia.vercel.app")


def _run(coro):
    return asyncio.run(coro)


def _mock_resp(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = ""
    return resp


@contextmanager
def _mock_httpx(responses):
    """Mock httpx.AsyncClient com lista de respostas sequenciais.

    Cada chamada a client.get/post/patch consome a proxima resposta da lista.
    """
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    call_idx = {"i": 0}
    all_responses = list(responses)

    async def _next_response(*args, **kwargs):
        idx = call_idx["i"]
        call_idx["i"] += 1
        if idx < len(all_responses):
            return all_responses[idx]
        return _mock_resp([], 500)

    mock_client.get = AsyncMock(side_effect=_next_response)
    mock_client.post = AsyncMock(side_effect=_next_response)
    mock_client.patch = AsyncMock(side_effect=_next_response)

    with patch(
        "src.api.services.invites.httpx.AsyncClient",
        return_value=mock_client,
    ):
        yield mock_client


# ---------------------------------------------------------------------------
# _invite_status
# ---------------------------------------------------------------------------


class TestInviteStatus:

    def test_pending(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(days=5)).isoformat()
        assert _invite_status({"expires_at": future}) == "pending"

    def test_expired(self):
        past = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()
        assert _invite_status({"expires_at": past}) == "expired"

    def test_accepted(self):
        assert _invite_status({"accepted_at": "2026-01-01T00:00:00Z"}) == "accepted"

    def test_revoked(self):
        assert _invite_status({"revoked_at": "2026-01-01T00:00:00Z"}) == "revoked"

    def test_revoked_takes_precedence(self):
        assert _invite_status({
            "revoked_at": "2026-01-01T00:00:00Z",
            "accepted_at": "2026-01-01T00:00:00Z",
        }) == "revoked"


# ---------------------------------------------------------------------------
# create_invite
# ---------------------------------------------------------------------------


class TestCreateInvite:

    def test_success(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(days=7)).isoformat()
        invite_row = {
            "id": "inv-1",
            "email": "new@test.com",
            "role": "member",
            "token": TOKEN,
            "organization_id": ORG_ID,
            "invited_by": USER_ID,
            "created_at": "2026-04-10T00:00:00Z",
            "expires_at": future,
            "accepted_at": None,
            "revoked_at": None,
        }
        with _mock_httpx([
            _mock_resp([]),                          # check existing: nenhum
            _mock_resp([{"name": "HABTA"}]),          # get org name
            _mock_resp([invite_row], 201),             # insert invite
        ]):
            with patch("src.api.services.invites.send_invite_email", new_callable=AsyncMock, return_value=True):
                result = _run(create_invite(ORG_ID, "new@test.com", "member", USER_ID))

        assert result["email"] == "new@test.com"
        assert result["status"] == "pending"

    def test_duplicate_email_raises(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(days=5)).isoformat()
        with _mock_httpx([
            _mock_resp([{"id": "inv-existing", "expires_at": future}]),  # existing pending
        ]):
            with pytest.raises(ValueError, match="Ja existe"):
                _run(create_invite(ORG_ID, "existing@test.com", "member", USER_ID))


# ---------------------------------------------------------------------------
# get_invite_by_token
# ---------------------------------------------------------------------------


class TestGetInviteByToken:

    def test_valid_token(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(days=5)).isoformat()
        with _mock_httpx([
            _mock_resp([{
                "id": "inv-1", "token": TOKEN, "email": "a@b.com",
                "role": "member", "organization_id": ORG_ID,
                "expires_at": future,
                "accepted_at": None, "revoked_at": None,
                "organizations": {"name": "HABTA"},
            }]),
        ]):
            result = _run(get_invite_by_token(TOKEN))
        assert result is not None
        assert result["token"] == TOKEN

    def test_expired_token(self):
        past = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()
        with _mock_httpx([
            _mock_resp([{
                "id": "inv-1", "token": TOKEN, "email": "a@b.com",
                "role": "member", "organization_id": ORG_ID,
                "expires_at": past,
                "accepted_at": None, "revoked_at": None,
            }]),
        ]):
            result = _run(get_invite_by_token(TOKEN))
        assert result is None

    def test_revoked_token(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(days=5)).isoformat()
        with _mock_httpx([
            _mock_resp([{
                "id": "inv-1", "token": TOKEN, "email": "a@b.com",
                "role": "member", "organization_id": ORG_ID,
                "expires_at": future,
                "accepted_at": None,
                "revoked_at": "2026-01-01T00:00:00Z",
            }]),
        ]):
            result = _run(get_invite_by_token(TOKEN))
        assert result is None

    def test_not_found(self):
        with _mock_httpx([_mock_resp([])]):
            result = _run(get_invite_by_token("bad-token"))
        assert result is None


# ---------------------------------------------------------------------------
# accept_invite
# ---------------------------------------------------------------------------


class TestAcceptInvite:

    def test_success(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(days=5)).isoformat()
        invite = {
            "id": "inv-1", "token": TOKEN, "email": "user@test.com",
            "role": "member", "organization_id": ORG_ID,
            "expires_at": future,
            "accepted_at": None, "revoked_at": None,
            "organizations": {"name": "HABTA"},
        }
        with _mock_httpx([
            _mock_resp([invite]),                     # get_invite_by_token
            _mock_resp([]),                           # check existing member
            _mock_resp([{"id": "mem-1"}], 201),       # insert membership
            _mock_resp([{"id": "inv-1"}]),             # mark accepted
        ]):
            result = _run(accept_invite(TOKEN, USER_ID, "user@test.com"))
        assert result["success"] is True
        assert result["role"] == "member"

    def test_email_mismatch(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(days=5)).isoformat()
        invite = {
            "id": "inv-1", "token": TOKEN, "email": "other@test.com",
            "role": "member", "organization_id": ORG_ID,
            "expires_at": future,
            "accepted_at": None, "revoked_at": None,
        }
        with _mock_httpx([_mock_resp([invite])]):
            with pytest.raises(ValueError, match="email"):
                _run(accept_invite(TOKEN, USER_ID, "wrong@test.com"))

    def test_already_member(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(days=5)).isoformat()
        invite = {
            "id": "inv-1", "token": TOKEN, "email": "user@test.com",
            "role": "member", "organization_id": ORG_ID,
            "expires_at": future,
            "accepted_at": None, "revoked_at": None,
        }
        with _mock_httpx([
            _mock_resp([invite]),                    # get_invite_by_token
            _mock_resp([{"id": "existing-member"}]),  # already member
        ]):
            with pytest.raises(ValueError, match="Ja e membro"):
                _run(accept_invite(TOKEN, USER_ID, "user@test.com"))


# ---------------------------------------------------------------------------
# revoke_invite
# ---------------------------------------------------------------------------


class TestRevokeInvite:

    def test_success(self):
        with _mock_httpx([_mock_resp([{"id": "inv-1"}])]):
            result = _run(revoke_invite("inv-1", ORG_ID))
        assert result is True

    def test_not_found(self):
        with _mock_httpx([_mock_resp([])]):
            result = _run(revoke_invite("inv-missing", ORG_ID))
        assert result is False


# ---------------------------------------------------------------------------
# send_invite_email
# ---------------------------------------------------------------------------


class TestSendInviteEmail:

    def test_skips_without_api_key(self, monkeypatch):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        with _mock_httpx([]):
            result = _run(send_invite_email("a@b.com", TOKEN, "HABTA"))
        assert result is False

    def test_sends_with_api_key(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test123")
        with _mock_httpx([_mock_resp({"id": "email-1"}, 200)]):
            result = _run(send_invite_email("a@b.com", TOKEN, "HABTA"))
        assert result is True

    def test_handles_resend_error(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test123")
        with _mock_httpx([_mock_resp({"error": "bad"}, 422)]):
            result = _run(send_invite_email("a@b.com", TOKEN, "HABTA"))
        assert result is False
