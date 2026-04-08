#!/usr/bin/env python3
"""Associar Mayara como owner da organização HABTA.

Operações (idempotentes):
1. Encontra a organização HABTA (slug='habta')
2. Associa o user_id como owner da HABTA
3. Remove a organização "Personal" criada pelo trigger handle_new_user

Uso:
    python scripts/setup_owner.py <user_id>
    MAYARA_USER_ID=<uuid> python scripts/setup_owner.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(Path(_PROJECT_ROOT) / ".env")

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def _headers() -> dict[str, str]:
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _get(table: str, query: str) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    r = httpx.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def _post(table: str, body: dict) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = httpx.post(url, headers=_headers(), json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def _patch(table: str, query: str, body: dict) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    r = httpx.patch(url, headers=_headers(), json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def _delete(table: str, query: str) -> None:
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    h = _headers()
    h.pop("Prefer", None)
    r = httpx.delete(url, headers=h, timeout=15)
    r.raise_for_status()


def main() -> None:
    # --- Validar configuração ---
    if not SUPABASE_URL or not SERVICE_KEY:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar no .env")
        sys.exit(1)

    # --- Obter user_id ---
    user_id = ""
    if len(sys.argv) > 1:
        user_id = sys.argv[1].strip()
    if not user_id:
        user_id = os.environ.get("MAYARA_USER_ID", "").strip()
    if not user_id:
        print("ERRO: Passa o user_id como argumento ou define MAYARA_USER_ID")
        print("Uso: python scripts/setup_owner.py <user_id>")
        sys.exit(1)
    if not UUID_RE.match(user_id):
        print(f"ERRO: '{user_id}' não é um UUID válido")
        sys.exit(1)

    print(f"User ID: {user_id}")
    print(f"Supabase: {SUPABASE_URL}")
    print()

    # --- Passo 1: Encontrar organização HABTA ---
    print("1. A procurar organização HABTA...")
    orgs = _get("organizations", "slug=eq.habta&select=id,name,slug")
    if not orgs:
        print("ERRO: Organização com slug='habta' não encontrada!")
        print("Verifica se a migração 001_migrate_org_data.py foi executada.")
        sys.exit(1)
    habta_id = orgs[0]["id"]
    print(f"   Encontrada: {orgs[0]['name']} (id={habta_id})")

    # --- Passo 2: Associar user como owner da HABTA ---
    print("2. A associar user como owner da HABTA...")
    existing = _get(
        "organization_members",
        f"organization_id=eq.{habta_id}&user_id=eq.{user_id}&select=id,role",
    )
    if existing:
        current_role = existing[0]["role"]
        if current_role == "owner":
            print(f"   Já é owner da HABTA (idempotente). OK.")
        else:
            print(f"   Membro existente com role='{current_role}'. A actualizar para owner...")
            _patch(
                "organization_members",
                f"organization_id=eq.{habta_id}&user_id=eq.{user_id}",
                {"role": "owner"},
            )
            print("   Actualizado para owner.")
    else:
        _post(
            "organization_members",
            {"organization_id": habta_id, "user_id": user_id, "role": "owner"},
        )
        print("   Inserido como owner.")

    # --- Passo 3: Apagar organização Personal ---
    print("3. A procurar organização Personal para apagar...")
    personal_orgs = _get(
        "organizations",
        f"created_by=eq.{user_id}&name=eq.Personal&select=id,name,slug",
    )
    if not personal_orgs:
        print("   Nenhuma organização Personal encontrada. OK.")
    else:
        for porg in personal_orgs:
            pid = porg["id"]
            print(f"   A apagar '{porg['name']}' (slug={porg['slug']}, id={pid})...")
            _delete("organization_members", f"organization_id=eq.{pid}")
            print("   - Members apagados.")
            _delete("organizations", f"id=eq.{pid}")
            print("   - Organização apagada.")

    # --- Passo 4: Validação final ---
    print()
    print("4. Validação final...")
    memberships = _get(
        "organization_members",
        f"user_id=eq.{user_id}&role=eq.owner&select=role,organizations(name,slug)",
    )
    owner_count = len(memberships)
    if owner_count == 1:
        org = memberships[0].get("organizations", {})
        print(f"   Mayara é owner de: {org.get('name')} (slug={org.get('slug')})")
        print()
        print("SUCESSO: Mayara é agora owner da HABTA. Pode fazer login.")
    elif owner_count == 0:
        print("ERRO: Nenhuma membership owner encontrada!")
        sys.exit(1)
    else:
        print(f"AVISO: {owner_count} memberships owner encontradas:")
        for m in memberships:
            org = m.get("organizations", {})
            print(f"   - {org.get('name')} ({org.get('slug')})")
        print("Esperava-se apenas 1 (HABTA). Verifica manualmente.")
        sys.exit(1)


if __name__ == "__main__":
    main()
