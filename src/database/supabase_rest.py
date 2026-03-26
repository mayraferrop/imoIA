"""Cliente Supabase REST para persistencia de dados.

Substitui SQLAlchemy para escrita/leitura via REST API do Supabase,
igual ao CashFlow Pro. Sem conexao PostgreSQL directa.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from loguru import logger


def _url() -> str:
    return os.getenv("SUPABASE_URL", "")


def _key() -> str:
    return os.getenv("SUPABASE_ANON_KEY", "")


def _headers() -> Dict[str, str]:
    key = _key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _get(table: str, params: str = "", timeout: int = 10) -> List[Dict]:
    url = f"{_url()}/rest/v1/{table}?{params}"
    resp = httpx.get(url, headers=_headers(), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _post(table: str, data: Dict | List[Dict], timeout: int = 10) -> List[Dict]:
    url = f"{_url()}/rest/v1/{table}"
    resp = httpx.post(url, headers=_headers(), json=data, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _upsert(table: str, data: Dict | List[Dict], timeout: int = 10) -> List[Dict]:
    url = f"{_url()}/rest/v1/{table}"
    headers = _headers()
    headers["Prefer"] = "return=representation,resolution=merge-duplicates"
    resp = httpx.post(url, headers=headers, json=data, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# --- Tenant ---

def ensure_tenant() -> str:
    """Garante que o tenant default existe e retorna o id."""
    rows = _get("tenants", "slug=eq.default&limit=1")
    if rows:
        return rows[0]["id"]
    tid = str(uuid4())
    _post("tenants", {"id": tid, "name": "ImoIA", "slug": "default", "country": "PT"})
    return tid


# --- Properties ---

def list_properties(limit: int = 50, status_neq: str = "descartado") -> List[Dict]:
    params = f"select=id,municipality,parish,asking_price,property_type,status&status=neq.{status_neq}&order=created_at.desc&limit={limit}"
    return _get("properties", params)


def create_property(data: Dict) -> Dict:
    tenant_id = ensure_tenant()
    row = {
        "id": str(uuid4()),
        "tenant_id": tenant_id,
        "source": "manual",
        "country": "PT",
        "status": "lead",
        **{k: v for k, v in data.items() if v is not None},
    }
    result = _post("properties", row)
    return result[0] if result else row


# --- Financial Models (Scenarios) ---

def list_scenarios(limit: int = 20) -> List[Dict]:
    params = (
        "select=id,property_id,scenario_name,go_nogo,roi_pct,tir_anual_pct,"
        "net_profit,purchase_price,estimated_sale_price,total_investment,created_at,"
        "properties(municipality,parish,property_type)"
        f"&order=created_at.desc&limit={limit}"
    )
    return _get("financial_models", params)


def save_financial_model(model_data: Dict) -> Dict:
    result = _post("financial_models", model_data)
    return result[0] if result else model_data


def get_model(model_id: str) -> Optional[Dict]:
    rows = _get("financial_models", f"id=eq.{model_id}&limit=1")
    return rows[0] if rows else None


# --- Payment Conditions ---

def save_payment_condition(data: Dict) -> Dict:
    result = _post("payment_conditions", data)
    return result[0] if result else data


# --- Cashflow Projections ---

def save_projections(projections: List[Dict]) -> int:
    if not projections:
        return 0
    _post("cashflow_projections", projections)
    return len(projections)


def get_projections(model_id: str) -> Dict:
    projs = _get(
        "cashflow_projections",
        f"financial_model_id=eq.{model_id}&order=mes&select=mes,periodo_label,categoria,fluxo_projetado,acumulado_projetado,fluxo_real,acumulado_real"
    )
    conds = _get(
        "payment_conditions",
        f"financial_model_id=eq.{model_id}&limit=1&select=cpcv_date,escritura_date,tranches"
    )
    cond = conds[0] if conds else None
    return {
        "model_id": model_id,
        "payment_condition": cond,
        "projections": projs,
    }


def delete_model(model_id: str) -> bool:
    """Exclui modelo e dados associados."""
    base = _url()
    h = _headers()
    # Filhos primeiro
    httpx.delete(f"{base}/rest/v1/cashflow_projections?financial_model_id=eq.{model_id}", headers=h, timeout=10)
    httpx.delete(f"{base}/rest/v1/payment_conditions?financial_model_id=eq.{model_id}", headers=h, timeout=10)
    resp = httpx.delete(f"{base}/rest/v1/financial_models?id=eq.{model_id}", headers=h, timeout=10)
    return resp.status_code < 300
