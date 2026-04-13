"""Provider de email partilhado — Resend HTTP API.

Modulo reutilizavel para enviar emails via Resend. Usado por:
  - invites.py (Fase 2B) — convites de organizacao
  - email_service.py (M7) — campanhas de marketing
  - m8_leads/service.py — nurture sequences

Graceful degradation: se RESEND_API_KEY nao configurada,
retorna sent=False sem levantar excepcao.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

import httpx
from loguru import logger

_RESEND_API_URL = "https://api.resend.com/emails"
_DEFAULT_FROM = "imoIA <noreply@mail.ironcapitals.com>"
_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> bool:
    """Validacao basica de formato de email."""
    return bool(_EMAIL_REGEX.match(email.strip()))


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Envia um email via Resend HTTP API.

    Parametros
    ----------
    to : str
        Email do destinatario.
    subject : str
        Assunto do email.
    html_body : str
        Corpo HTML do email.
    from_email : str, optional
        Remetente. Default: noreply@mail.ironcapitals.com
    reply_to : str, optional
        Email de reply-to.

    Retorna
    -------
    dict com:
        - sent (bool): se o email foi enviado com sucesso
        - id (str): ID do email no Resend (se enviado)
        - reason (str): motivo da falha (se nao enviado)
    """
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("RESEND_API_KEY not configured, skipping email send")
        return {"sent": False, "reason": "RESEND_API_KEY not configured"}

    if not validate_email(to):
        logger.warning(f"Email invalido, skipping: {to}")
        return {"sent": False, "reason": f"Email invalido: {to}"}

    payload: Dict[str, Any] = {
        "from": from_email or _DEFAULT_FROM,
        "to": [to.strip()],
        "subject": subject,
        "html": html_body,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )

        if resp.status_code in (200, 201):
            data = resp.json()
            email_id = data.get("id", "")
            logger.info(f"Email enviado para {to} (id={email_id})")
            return {"sent": True, "id": email_id}

        error_text = resp.text[:300]
        logger.warning(f"Resend retornou {resp.status_code} para {to}: {error_text}")
        return {
            "sent": False,
            "reason": f"Resend HTTP {resp.status_code}",
            "error": error_text,
        }

    except httpx.TimeoutException:
        logger.error(f"Timeout ao enviar email para {to}")
        return {"sent": False, "reason": "Timeout"}
    except Exception as exc:
        logger.error(f"Erro ao enviar email para {to}: {exc}")
        return {"sent": False, "reason": str(exc)}
