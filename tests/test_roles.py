"""Testes para helpers de role (Fase 2B Dia 1).

Testa get_user_role_in_org, is_user_admin_or_owner e is_user_owner
com mocks de httpx (sem pytest-asyncio — usa asyncio.run).
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.dependencies.roles import (
    get_user_role_in_org,
    is_user_admin_or_owner,
    is_user_owner,
)

USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ORG_ID = "11111111-2222-3333-4444-555555555555"


# ---------------------------------------------------------------------------
# Fixtures e helpers de teste
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    """Configurar vars de ambiente para todos os testes."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")


def _run(coro):
    """Executa coroutine em test sincrono (sem pytest-asyncio)."""
    return asyncio.run(coro)


@contextmanager
def _mock_postgrest(json_data, status_code=200):
    """Mock do httpx.AsyncClient para retornar resposta PostgREST."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=resp)

    with patch(
        "src.api.dependencies.roles.httpx.AsyncClient",
        return_value=mock_client,
    ):
        yield mock_client


# ---------------------------------------------------------------------------
# get_user_role_in_org
# ---------------------------------------------------------------------------


class TestGetUserRoleInOrg:

    def test_returns_owner(self):
        with _mock_postgrest([{"role": "owner"}]):
            assert _run(get_user_role_in_org(USER_ID, ORG_ID)) == "owner"

    def test_returns_admin(self):
        with _mock_postgrest([{"role": "admin"}]):
            assert _run(get_user_role_in_org(USER_ID, ORG_ID)) == "admin"

    def test_returns_member(self):
        with _mock_postgrest([{"role": "member"}]):
            assert _run(get_user_role_in_org(USER_ID, ORG_ID)) == "member"

    def test_returns_none_for_non_member(self):
        with _mock_postgrest([]):
            assert _run(get_user_role_in_org(USER_ID, ORG_ID)) is None

    def test_returns_none_on_http_error(self):
        with _mock_postgrest([], status_code=500):
            assert _run(get_user_role_in_org(USER_ID, ORG_ID)) is None

    def test_queries_correct_url(self):
        with _mock_postgrest([{"role": "member"}]) as mock_client:
            _run(get_user_role_in_org(USER_ID, ORG_ID))
            call_args = mock_client.get.call_args
            url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
            assert f"user_id=eq.{USER_ID}" in url
            assert f"organization_id=eq.{ORG_ID}" in url
            assert "select=role" in url


# ---------------------------------------------------------------------------
# is_user_admin_or_owner
# ---------------------------------------------------------------------------


class TestIsUserAdminOrOwner:

    def test_true_for_owner(self):
        with _mock_postgrest([{"role": "owner"}]):
            assert _run(is_user_admin_or_owner(USER_ID, ORG_ID)) is True

    def test_true_for_admin(self):
        with _mock_postgrest([{"role": "admin"}]):
            assert _run(is_user_admin_or_owner(USER_ID, ORG_ID)) is True

    def test_false_for_member(self):
        with _mock_postgrest([{"role": "member"}]):
            assert _run(is_user_admin_or_owner(USER_ID, ORG_ID)) is False

    def test_false_for_non_member(self):
        with _mock_postgrest([]):
            assert _run(is_user_admin_or_owner(USER_ID, ORG_ID)) is False


# ---------------------------------------------------------------------------
# is_user_owner
# ---------------------------------------------------------------------------


class TestIsUserOwner:

    def test_true_for_owner(self):
        with _mock_postgrest([{"role": "owner"}]):
            assert _run(is_user_owner(USER_ID, ORG_ID)) is True

    def test_false_for_admin(self):
        with _mock_postgrest([{"role": "admin"}]):
            assert _run(is_user_owner(USER_ID, ORG_ID)) is False

    def test_false_for_member(self):
        with _mock_postgrest([{"role": "member"}]):
            assert _run(is_user_owner(USER_ID, ORG_ID)) is False

    def test_false_for_non_member(self):
        with _mock_postgrest([]):
            assert _run(is_user_owner(USER_ID, ORG_ID)) is False
