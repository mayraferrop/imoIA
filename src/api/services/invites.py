"""Service de convites de organizacao — Fase 2B Dia 2.

CRUD de invites via PostgREST (Supabase) + envio de email via Resend.
Se RESEND_API_KEY nao estiver configurada, os convites sao criados
mas o email nao e enviado (graceful degradation).

# FIXME(jwt-refactor): migrar _supa_headers() para usar JWT do utilizador
# quando a tabela organization_invites tiver policies para 'authenticated'.
# Hoje usa SERVICE_ROLE_KEY que bypassa RLS.
# Depende de: Sub-tarefa 2 (aplicar policy invites_select_own_org).
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


# ---------------------------------------------------------------------------
# Config Supabase
# ---------------------------------------------------------------------------

def _supa_headers() -> Dict[str, str]:
    supa_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    return {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _supa_url() -> str:
    return os.getenv("SUPABASE_URL", "")


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _invite_status(invite: Dict[str, Any]) -> str:
    """Calcula o status legivel de um invite a partir dos timestamps."""
    if invite.get("revoked_at"):
        return "revoked"
    if invite.get("accepted_at"):
        return "accepted"
    expires = invite.get("expires_at", "")
    if expires:
        try:
            exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if exp_dt < datetime.now(tz=timezone.utc):
                return "expired"
        except (ValueError, TypeError):
            pass
    return "pending"


def _format_invite(invite: Dict[str, Any], org_name: Optional[str] = None) -> Dict[str, Any]:
    """Formata um invite para a resposta da API."""
    return {
        "id": invite["id"],
        "email": invite["email"],
        "role": invite["role"],
        "status": _invite_status(invite),
        "expires_at": invite.get("expires_at", ""),
        "created_at": invite.get("created_at", ""),
        "organization_name": org_name,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_invite(
    organization_id: str,
    email: str,
    role: str,
    invited_by: str,
) -> Dict[str, Any]:
    """Cria um convite e envia email (se Resend configurado).

    Raises HTTPException-ready dict se houver duplicado.
    """
    token = secrets.token_urlsafe(32)
    email_lower = email.strip().lower()

    # Verificar se ja existe invite pendente para este email+org
    async with httpx.AsyncClient() as client:
        existing = await client.get(
            f"{_supa_url()}/rest/v1/organization_invites"
            f"?organization_id=eq.{organization_id}&email=eq.{email_lower}"
            f"&revoked_at=is.null&accepted_at=is.null&select=id,expires_at",
            headers=_supa_headers(),
            timeout=10,
        )

    if existing.status_code == 200 and existing.json():
        pending = existing.json()[0]
        status = _invite_status(pending)
        if status == "pending":
            raise ValueError(f"Ja existe um convite pendente para {email_lower} nesta organizacao.")

    # Buscar nome da org para o email
    org_name = await _get_org_name(organization_id)

    # Inserir invite
    body = {
        "organization_id": organization_id,
        "email": email_lower,
        "role": role,
        "token": token,
        "invited_by": invited_by,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_supa_url()}/rest/v1/organization_invites",
            headers=_supa_headers(),
            json=body,
            timeout=10,
        )

    if resp.status_code not in (200, 201):
        logger.error(f"Erro ao criar invite: {resp.status_code} {resp.text}")
        raise RuntimeError(f"Erro ao criar invite: {resp.status_code}")

    invite = resp.json()[0] if resp.json() else body

    # Enviar email (graceful degradation)
    await send_invite_email(
        email=email_lower,
        token=token,
        organization_name=org_name or "imoIA",
    )

    return _format_invite(invite, org_name=org_name)


async def get_invite_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Procura invite por token. Retorna None se nao encontrado, expirado ou revogado."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_supa_url()}/rest/v1/organization_invites"
            f"?token=eq.{token}&select=*,organizations(name,slug)"
            f"&limit=1",
            headers=_supa_headers(),
            timeout=10,
        )

    if resp.status_code != 200 or not resp.json():
        return None

    invite = resp.json()[0]
    status = _invite_status(invite)

    if status != "pending":
        return None

    return invite


async def accept_invite(
    token: str,
    user_id: str,
    user_email: str,
) -> Dict[str, Any]:
    """Aceita um convite: valida token, verifica email, cria membership.

    Raises ValueError se o token for invalido ou o email nao bater.
    """
    invite = await get_invite_by_token(token)
    if not invite:
        raise ValueError("Convite invalido, expirado ou ja utilizado.")

    if invite["email"].lower() != user_email.strip().lower():
        raise ValueError("O email da conta nao corresponde ao email do convite.")

    org_id = invite["organization_id"]
    role = invite["role"]

    # Verificar se user ja e membro da org
    async with httpx.AsyncClient() as client:
        existing_member = await client.get(
            f"{_supa_url()}/rest/v1/organization_members"
            f"?user_id=eq.{user_id}&organization_id=eq.{org_id}&select=id&limit=1",
            headers=_supa_headers(),
            timeout=10,
        )

    if existing_member.status_code == 200 and existing_member.json():
        raise ValueError("Ja e membro desta organizacao.")

    # Inserir membership
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_supa_url()}/rest/v1/organization_members",
            headers=_supa_headers(),
            json={
                "organization_id": org_id,
                "user_id": user_id,
                "role": role,
            },
            timeout=10,
        )

    if resp.status_code not in (200, 201):
        logger.error(f"Erro ao criar membership: {resp.status_code} {resp.text}")
        raise RuntimeError("Erro ao adicionar utilizador a organizacao.")

    # Marcar invite como aceito
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{_supa_url()}/rest/v1/organization_invites"
            f"?id=eq.{invite['id']}",
            headers=_supa_headers(),
            json={"accepted_at": datetime.now(tz=timezone.utc).isoformat()},
            timeout=10,
        )

    return {
        "success": True,
        "organization_id": org_id,
        "role": role,
    }


async def list_invites(organization_id: str) -> List[Dict[str, Any]]:
    """Lista todos os invites de uma organizacao (pendentes primeiro)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_supa_url()}/rest/v1/organization_invites"
            f"?organization_id=eq.{organization_id}"
            f"&select=*&order=created_at.desc",
            headers=_supa_headers(),
            timeout=10,
        )

    if resp.status_code != 200:
        return []

    org_name = await _get_org_name(organization_id)
    return [_format_invite(inv, org_name=org_name) for inv in resp.json()]


async def revoke_invite(invite_id: str, organization_id: str) -> bool:
    """Revoga um invite (marca revoked_at). Retorna False se nao encontrado."""
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{_supa_url()}/rest/v1/organization_invites"
            f"?id=eq.{invite_id}&organization_id=eq.{organization_id}"
            f"&revoked_at=is.null&accepted_at=is.null",
            headers={**_supa_headers(), "Prefer": "return=representation"},
            json={"revoked_at": datetime.now(tz=timezone.utc).isoformat()},
            timeout=10,
        )

    if resp.status_code == 200 and resp.json():
        return True

    return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_org_name(organization_id: str) -> Optional[str]:
    """Busca o nome da organizacao."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_supa_url()}/rest/v1/organizations"
            f"?id=eq.{organization_id}&select=name&limit=1",
            headers=_supa_headers(),
            timeout=10,
        )

    if resp.status_code == 200 and resp.json():
        return resp.json()[0].get("name")
    return None


# ---------------------------------------------------------------------------
# Email via Resend (graceful degradation)
# ---------------------------------------------------------------------------

_INVITE_EMAIL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Convite imoIA</title>
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Roboto,Arial,sans-serif;background:#f4f5f7;">
  <div style="max-width:560px;margin:40px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div style="background:#1E3A5F;padding:32px 24px;text-align:center;">
      <span style="font-size:28px;font-weight:700;color:#ffffff;letter-spacing:1px;">imo<span style="color:#F4A261;">IA</span></span>
    </div>
    <div style="padding:32px 28px;color:#333333;line-height:1.7;">
      <h2 style="margin:0 0 16px;color:#1E3A5F;font-size:20px;">
        Convite para {organization_name}
      </h2>
      <p style="margin:0 0 24px;font-size:15px;">
        Voce foi convidado(a) para fazer parte da organizacao
        <strong>{organization_name}</strong> na plataforma imoIA.
      </p>
      <div style="text-align:center;margin:32px 0;">
        <a href="{invite_url}"
           style="display:inline-block;background:#F4A261;color:#ffffff;text-decoration:none;
                  padding:14px 36px;border-radius:8px;font-size:16px;font-weight:600;
                  letter-spacing:0.5px;">
          Aceitar convite
        </a>
      </div>
      <p style="margin:0 0 8px;font-size:13px;color:#888888;text-align:center;">
        Este convite expira em 7 dias.
      </p>
    </div>
    <div style="background:#f9fafb;padding:20px 28px;border-top:1px solid #e8e8e8;
                text-align:center;font-size:12px;color:#999999;">
      Se nao esperava este convite, ignore este email.
    </div>
  </div>
</body>
</html>
"""


async def send_invite_email(
    email: str,
    token: str,
    organization_name: str,
) -> bool:
    """Envia email de convite via Resend (shared provider).

    Retorna True se enviado, False se RESEND_API_KEY nao configurada
    ou se houve erro no envio (nao bloqueia criacao do invite).
    """
    from src.shared.email_provider import send_email

    frontend_url = os.getenv("FRONTEND_URL", "https://imoia.vercel.app")
    invite_url = f"{frontend_url}/invite/{token}"

    html_body = _INVITE_EMAIL_TEMPLATE.format(
        organization_name=organization_name,
        invite_url=invite_url,
    )

    result = await send_email(
        to=email,
        subject=f"Convite para {organization_name} — imoIA",
        html_body=html_body,
    )
    return result.get("sent", False)
