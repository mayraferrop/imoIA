"""Cliente Supabase REST para persistencia de dados.

Toda leitura e escrita passa por aqui via REST API do Supabase,
igual ao CashFlow Pro. Sem conexao PostgreSQL directa.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from loguru import logger

# Cache do URL e key para evitar os.getenv em cada chamada
_SUPA_URL: str = ""
_SUPA_KEY: str = ""


def _ensure_config():
    """Carrega e valida config do Supabase (uma vez)."""
    global _SUPA_URL, _SUPA_KEY
    if not _SUPA_URL:
        _SUPA_URL = os.getenv("SUPABASE_URL", "")
        _SUPA_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    if not _SUPA_URL or not _SUPA_KEY:
        raise ValueError(
            "SUPABASE_URL e SUPABASE_ANON_KEY nao configurados. "
            f"URL={_SUPA_URL!r}, KEY_LEN={len(_SUPA_KEY)}"
        )


def _headers() -> Dict[str, str]:
    _ensure_config()
    return {
        "apikey": _SUPA_KEY,
        "Authorization": f"Bearer {_SUPA_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _get(table: str, params: str = "", timeout: int = 10) -> List[Dict]:
    _ensure_config()
    url = f"{_SUPA_URL}/rest/v1/{table}?{params}"
    try:
        resp = httpx.get(url, headers=_headers(), timeout=timeout)
        if resp.status_code >= 400:
            logger.error(f"Supabase GET {table} HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        return resp.json()
    except Exception as e:
        logger.error(f"Supabase GET {table} falhou: {e}")
        return []


def _post(table: str, data: Dict | List[Dict], timeout: int = 15) -> List[Dict]:
    _ensure_config()
    url = f"{_SUPA_URL}/rest/v1/{table}"
    try:
        resp = httpx.post(url, headers=_headers(), json=data, timeout=timeout)
        if resp.status_code >= 400:
            logger.error(f"Supabase POST {table} HTTP {resp.status_code}: {resp.text[:300]}")
            raise ValueError(f"Supabase POST {table} falhou: {resp.text[:200]}")
        result = resp.json()
        logger.info(f"Supabase POST {table}: {len(result) if isinstance(result, list) else 1} registos")
        return result
    except httpx.TimeoutException:
        logger.error(f"Supabase POST {table} timeout ({timeout}s)")
        raise ValueError(f"Supabase POST {table} timeout")
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Supabase POST {table} erro: {e}")
        raise ValueError(f"Supabase POST {table}: {e}")


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
    return _get(
        "properties",
        f"select=id,municipality,parish,asking_price,property_type,status"
        f"&status=neq.{status_neq}&order=created_at.desc&limit={limit}"
    )


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
    return _get(
        "financial_models",
        "select=id,property_id,scenario_name,go_nogo,roi_pct,tir_anual_pct,"
        "net_profit,purchase_price,estimated_sale_price,total_investment,created_at,"
        "properties(municipality,parish,property_type)"
        f"&order=created_at.desc&limit={limit}"
    )


def save_financial_model(model_data: Dict) -> Dict:
    result = _post("financial_models", model_data)
    return result[0] if result else model_data


def get_model(model_id: str) -> Optional[Dict]:
    rows = _get("financial_models", f"id=eq.{model_id}&select=*&limit=1")
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
        f"financial_model_id=eq.{model_id}&order=mes"
        f"&select=mes,periodo_label,categoria,fluxo_projetado,acumulado_projetado,fluxo_real,acumulado_real"
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
    _ensure_config()
    h = _headers()
    httpx.delete(f"{_SUPA_URL}/rest/v1/cashflow_projections?financial_model_id=eq.{model_id}", headers=h, timeout=10)
    httpx.delete(f"{_SUPA_URL}/rest/v1/payment_conditions?financial_model_id=eq.{model_id}", headers=h, timeout=10)
    resp = httpx.delete(f"{_SUPA_URL}/rest/v1/financial_models?id=eq.{model_id}", headers=h, timeout=10)
    return resp.status_code < 300
