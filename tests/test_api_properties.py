"""Testes para o router API de Properties."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_list_properties_empty() -> None:
    """GET /api/v1/properties/ retorna lista (possivelmente vazia)."""
    response = client.get("/api/v1/properties/")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data


def test_create_property_manual() -> None:
    """POST /api/v1/properties/ cria propriedade manualmente."""
    payload = {
        "district": "Lisboa",
        "municipality": "Lisboa",
        "parish": "Arroios",
        "property_type": "apartamento",
        "asking_price": 150000,
        "gross_area_m2": 65,
        "bedrooms": 2,
        "condition": "para_renovar",
        "notes": "Teste automatico",
    }
    response = client.post("/api/v1/properties/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["municipality"] == "Lisboa"
    assert data["asking_price"] == 150000
    assert data["source"] == "manual"
    assert data["status"] == "lead"
    return data["id"]


def test_get_property() -> None:
    """GET /api/v1/properties/{id} retorna detalhe."""
    # Criar primeiro
    payload = {"municipality": "Porto", "asking_price": 200000}
    create_resp = client.post("/api/v1/properties/", json=payload)
    prop_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/properties/{prop_id}")
    assert response.status_code == 200
    assert response.json()["municipality"] == "Porto"


def test_update_property() -> None:
    """PATCH /api/v1/properties/{id} actualiza campos."""
    # Criar primeiro
    payload = {"municipality": "Sintra", "asking_price": 100000}
    create_resp = client.post("/api/v1/properties/", json=payload)
    prop_id = create_resp.json()["id"]

    # Actualizar
    update_resp = client.patch(
        f"/api/v1/properties/{prop_id}",
        json={"asking_price": 95000, "status": "analise"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["asking_price"] == 95000
    assert update_resp.json()["status"] == "analise"


def test_get_property_not_found() -> None:
    """GET /api/v1/properties/inexistente retorna 404."""
    response = client.get("/api/v1/properties/nao-existe-este-id")
    assert response.status_code == 404


def test_create_from_opportunity_not_found() -> None:
    """POST /api/v1/properties/from-opportunity/999999 retorna 404."""
    response = client.post("/api/v1/properties/from-opportunity/999999")
    assert response.status_code == 404
