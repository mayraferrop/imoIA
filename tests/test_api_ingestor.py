"""Testes para o router API do Ingestor (M1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_check() -> None:
    """GET /health retorna status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_pipeline_status() -> None:
    """GET /api/v1/ingest/status retorna estado do pipeline."""
    response = client.get("/api/v1/ingest/status")
    assert response.status_code == 200
    data = response.json()
    assert "state" in data


def test_list_groups() -> None:
    """GET /api/v1/ingest/groups retorna lista de grupos."""
    response = client.get("/api/v1/ingest/groups")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_opportunities() -> None:
    """GET /api/v1/ingest/opportunities retorna oportunidades."""
    response = client.get("/api/v1/ingest/opportunities")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_list_opportunities_with_filters() -> None:
    """GET /api/v1/ingest/opportunities com filtros funciona."""
    response = client.get(
        "/api/v1/ingest/opportunities",
        params={"min_confidence": 0.8, "limit": 10, "offset": 0},
    )
    assert response.status_code == 200


def test_get_opportunity_not_found() -> None:
    """GET /api/v1/ingest/opportunities/999999 retorna 404."""
    response = client.get("/api/v1/ingest/opportunities/999999")
    assert response.status_code == 404


def test_get_stats() -> None:
    """GET /api/v1/ingest/stats retorna estatisticas."""
    response = client.get("/api/v1/ingest/stats")
    assert response.status_code == 200
    data = response.json()
    assert "groups" in data
    assert "opportunities" in data


def test_trigger_pipeline() -> None:
    """POST /api/v1/ingest/trigger dispara pipeline em background."""
    response = client.post("/api/v1/ingest/trigger")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pipeline_iniciado"
