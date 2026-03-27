"""Cliente Supabase REST — unica fonte de dados persistentes.

Todas as operacoes CRUD passam por aqui via PostgREST API do Supabase.
Sem SQLAlchemy, sem SQLite, sem conexao PostgreSQL directa.
Arquitectura igual ao CashFlow Pro.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from loguru import logger

# Cache do URL e key
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


def _headers(prefer: str = "return=representation") -> Dict[str, str]:
    _ensure_config()
    return {
        "apikey": _SUPA_KEY,
        "Authorization": f"Bearer {_SUPA_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def new_id() -> str:
    """Gera um UUID para chave primaria."""
    return str(uuid4())


# =========================================================================
# Operacoes CRUD genericas
# =========================================================================


def _get(table: str, params: str = "", timeout: int = 10) -> List[Dict]:
    """SELECT — retorna lista de dicts. Retorna [] em caso de erro."""
    _ensure_config()
    url = f"{_SUPA_URL}/rest/v1/{table}?{params}"
    try:
        resp = httpx.get(url, headers=_headers(), timeout=timeout)
        if resp.status_code >= 400:
            logger.error(f"GET {table} HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        return resp.json()
    except Exception as e:
        logger.error(f"GET {table} falhou: {e}")
        return []


def _post(table: str, data: Dict | List[Dict], timeout: int = 15) -> List[Dict]:
    """INSERT — retorna lista de registos criados. Lanca ValueError em caso de erro."""
    _ensure_config()
    url = f"{_SUPA_URL}/rest/v1/{table}"
    try:
        resp = httpx.post(url, headers=_headers(), json=data, timeout=timeout)
        if resp.status_code >= 400:
            logger.error(f"POST {table} HTTP {resp.status_code}: {resp.text[:300]}")
            raise ValueError(f"POST {table} falhou: {resp.text[:200]}")
        return resp.json()
    except httpx.TimeoutException:
        logger.error(f"POST {table} timeout ({timeout}s)")
        raise ValueError(f"POST {table} timeout")
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"POST {table} erro: {e}")
        raise ValueError(f"POST {table}: {e}")


def _upsert(table: str, data: Dict | List[Dict], timeout: int = 15) -> List[Dict]:
    """INSERT ON CONFLICT UPDATE (upsert)."""
    _ensure_config()
    url = f"{_SUPA_URL}/rest/v1/{table}"
    headers = _headers("return=representation,resolution=merge-duplicates")
    try:
        resp = httpx.post(url, headers=headers, json=data, timeout=timeout)
        if resp.status_code >= 400:
            logger.error(f"UPSERT {table} HTTP {resp.status_code}: {resp.text[:300]}")
            raise ValueError(f"UPSERT {table} falhou: {resp.text[:200]}")
        return resp.json()
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"UPSERT {table} erro: {e}")
        raise ValueError(f"UPSERT {table}: {e}")


def _patch(table: str, filter_str: str, data: Dict, timeout: int = 10) -> List[Dict]:
    """UPDATE — actualiza registos que correspondem ao filtro. Retorna registos actualizados."""
    _ensure_config()
    url = f"{_SUPA_URL}/rest/v1/{table}?{filter_str}"
    try:
        resp = httpx.patch(url, headers=_headers(), json=data, timeout=timeout)
        if resp.status_code >= 400:
            logger.error(f"PATCH {table} HTTP {resp.status_code}: {resp.text[:200]}")
            raise ValueError(f"PATCH {table} falhou: {resp.text[:200]}")
        return resp.json()
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"PATCH {table} erro: {e}")
        raise ValueError(f"PATCH {table}: {e}")


def _delete(table: str, filter_str: str, timeout: int = 10) -> bool:
    """DELETE — exclui registos que correspondem ao filtro."""
    _ensure_config()
    url = f"{_SUPA_URL}/rest/v1/{table}?{filter_str}"
    try:
        resp = httpx.delete(url, headers=_headers(), timeout=timeout)
        if resp.status_code >= 400:
            logger.error(f"DELETE {table} HTTP {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        logger.error(f"DELETE {table} erro: {e}")
        return False


def _count(table: str, filter_str: str = "") -> int:
    """COUNT — retorna total de registos que correspondem ao filtro."""
    _ensure_config()
    params = "select=id" + (f"&{filter_str}" if filter_str else "")
    url = f"{_SUPA_URL}/rest/v1/{table}?{params}"
    try:
        resp = httpx.get(
            url,
            headers={**_headers("count=exact"), "Range": "0-0"},
            timeout=10,
        )
        cr = resp.headers.get("content-range", "")
        return int(cr.split("/")[1]) if "/" in cr else 0
    except Exception as e:
        logger.error(f"COUNT {table} erro: {e}")
        return 0


# =========================================================================
# Helpers de alto nivel
# =========================================================================


def get_by_id(table: str, row_id: str, select: str = "*") -> Optional[Dict]:
    """Busca um registo por ID."""
    rows = _get(table, f"id=eq.{row_id}&select={select}&limit=1")
    return rows[0] if rows else None


def insert(table: str, data: Dict) -> Dict:
    """Insere um registo. Gera UUID se nao tiver id."""
    if "id" not in data:
        data["id"] = new_id()
    result = _post(table, data)
    return result[0] if result else data


def update(table: str, row_id: str, data: Dict) -> Dict:
    """Actualiza um registo por ID."""
    result = _patch(table, f"id=eq.{row_id}", data)
    return result[0] if result else {}


def delete_by_id(table: str, row_id: str) -> bool:
    """Exclui um registo por ID."""
    return _delete(table, f"id=eq.{row_id}")


def delete_by_filter(table: str, filter_str: str) -> bool:
    """Exclui registos por filtro."""
    return _delete(table, filter_str)


def list_rows(
    table: str,
    select: str = "*",
    filters: str = "",
    order: str = "created_at.desc",
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """Lista registos com filtros, ordenacao e paginacao."""
    params = f"select={select}&order={order}&limit={limit}&offset={offset}"
    if filters:
        params += f"&{filters}"
    return _get(table, params)


def list_with_count(
    table: str,
    select: str = "*",
    filters: str = "",
    order: str = "created_at.desc",
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Lista registos com total count para paginacao."""
    items = list_rows(table, select, filters, order, limit, offset)
    total = _count(table, filters)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


# =========================================================================
# Helpers de dominio (mantidos para retrocompatibilidade)
# =========================================================================


def ensure_tenant() -> str:
    """Garante que o tenant default existe e retorna o id."""
    rows = _get("tenants", "slug=eq.default&limit=1")
    if rows:
        return rows[0]["id"]
    tid = new_id()
    _post("tenants", {"id": tid, "name": "ImoIA", "slug": "default", "country": "PT"})
    return tid


# --- Properties ---

def list_properties(limit: int = 50, status_neq: str = "descartado") -> List[Dict]:
    return list_rows("properties", "id,municipality,parish,asking_price,property_type,status",
                     f"status=neq.{status_neq}", "created_at.desc", limit)


def create_property(data: Dict) -> Dict:
    tenant_id = ensure_tenant()
    row = {
        "id": new_id(),
        "tenant_id": tenant_id,
        "source": "manual",
        "country": "PT",
        "status": "lead",
        **{k: v for k, v in data.items() if v is not None},
    }
    return insert("properties", row)


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
    return insert("financial_models", model_data)


def get_model(model_id: str) -> Optional[Dict]:
    return get_by_id("financial_models", model_id)


# --- Payment Conditions ---

def save_payment_condition(data: Dict) -> Dict:
    return insert("payment_conditions", data)


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
    return {
        "model_id": model_id,
        "payment_condition": conds[0] if conds else None,
        "projections": projs,
    }


def delete_model(model_id: str) -> bool:
    """Exclui modelo e dados associados (cascade manual)."""
    delete_by_filter("cashflow_projections", f"financial_model_id=eq.{model_id}")
    delete_by_filter("payment_conditions", f"financial_model_id=eq.{model_id}")
    return delete_by_id("financial_models", model_id)
