"""Dead-letter queue para mensagens descartadas do pipeline M1 (Fase 5).

Captura mensagens que excederam o MAX_CLASSIFY numa corrida (ou falharam
a classificar/persistir) para serem re-tentadas em runs futuras, com
backoff exponencial. Evita perda silenciosa de leads em grupos muito
activos.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import text

from src.database.db import get_session, get_default_organization_id


MAX_RETRIES = 5
BACKOFF_BASE_MIN = 15  # 15, 30, 60, 120, 240 min


def _next_retry_at(retry_count: int) -> datetime:
    """Backoff exponencial: 15m * 2^retry_count."""
    mins = BACKOFF_BASE_MIN * (2 ** min(retry_count, 4))
    return datetime.now(tz=timezone.utc) + timedelta(minutes=mins)


def enqueue_failed(
    messages: List[Dict[str, Any]],
    reason: str,
    organization_id: Optional[str] = None,
) -> int:
    """Insere mensagens na fila de retry.

    Usa UPSERT (ON CONFLICT DO NOTHING) por (organization_id, whatsapp_message_id)
    para que re-execuções do pipeline não dupliquem linhas.

    Args:
        messages: dicts com keys compatíveis com o pipeline
            (whatsapp_message_id, content, _group_id, _group_name,
             sender_id, sender_name, timestamp).
        reason: motivo do enfileiramento (ex. "over_classify_limit").
        organization_id: default = org actual do contexto.

    Returns:
        Número de linhas efectivamente inseridas.
    """
    if not messages:
        return 0
    org_id = organization_id or get_default_organization_id()

    rows = []
    for m in messages:
        wid = m.get("whatsapp_message_id") or m.get("id")
        if not wid:
            continue
        ts = m.get("timestamp")
        if isinstance(ts, datetime) and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        rows.append({
            "org": org_id,
            "gid": m.get("_group_id") or m.get("group_id") or "",
            "gname": m.get("_group_name") or m.get("group_name"),
            "wid": wid,
            "content": m.get("content", ""),
            "sid": m.get("sender_id"),
            "sname": m.get("sender_name"),
            "ts": ts,
            "reason": reason,
        })

    if not rows:
        return 0

    inserted = 0
    with get_session() as session:
        for r in rows:
            res = session.execute(text("""
                INSERT INTO m1_failed_messages
                  (organization_id, group_id, group_name, whatsapp_message_id,
                   content, sender_id, sender_name, message_timestamp, reason)
                VALUES (:org, :gid, :gname, :wid, :content, :sid, :sname, :ts, :reason)
                ON CONFLICT (organization_id, whatsapp_message_id) DO NOTHING
            """), r)
            inserted += res.rowcount or 0
        session.commit()
    if inserted:
        logger.info(f"[dlq] enfileiradas {inserted} msgs (reason={reason})")
    return inserted


def pop_retries(limit: int = 500, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Devolve mensagens prontas para retry (retry_count<MAX, next_retry_at<=now).

    NÃO apaga — `mark_retried` é chamado após a tentativa para actualizar
    retry_count e next_retry_at, ou apagar se ficou processada.
    """
    org_id = organization_id or get_default_organization_id()
    now = datetime.now(tz=timezone.utc)
    with get_session() as session:
        rows = session.execute(text("""
            SELECT id, group_id, group_name, whatsapp_message_id, content,
                   sender_id, sender_name, message_timestamp, retry_count
            FROM m1_failed_messages
            WHERE organization_id = :org
              AND retry_count < :maxr
              AND next_retry_at <= :now
            ORDER BY created_at ASC
            LIMIT :lim
        """), {"org": org_id, "maxr": MAX_RETRIES, "now": now, "lim": limit}).mappings().all()
    out = []
    for r in rows:
        out.append({
            "_dlq_id": r["id"],
            "_dlq_retry_count": r["retry_count"],
            "whatsapp_message_id": r["whatsapp_message_id"],
            "_group_id": r["group_id"],
            "_group_name": r["group_name"],
            "content": r["content"],
            "sender_id": r["sender_id"],
            "sender_name": r["sender_name"],
            "timestamp": r["message_timestamp"] or now,
        })
    if out:
        logger.info(f"[dlq] {len(out)} msgs recuperadas para retry")
    return out


def mark_retried(dlq_id: int, success: bool, error: Optional[str] = None) -> None:
    """Actualiza ou apaga uma linha da queue após tentativa de retry."""
    with get_session() as session:
        if success:
            session.execute(text(
                "DELETE FROM m1_failed_messages WHERE id = :id"
            ), {"id": dlq_id})
        else:
            session.execute(text("""
                UPDATE m1_failed_messages
                SET retry_count = retry_count + 1,
                    next_retry_at = :nxt,
                    last_error = :err,
                    updated_at = now()
                WHERE id = :id
            """), {
                "id": dlq_id,
                "nxt": _next_retry_at(0),  # recomputado a partir do novo retry_count
                "err": (error or "")[:500],
            })
            session.execute(text("""
                UPDATE m1_failed_messages
                SET next_retry_at = :nxt
                WHERE id = :id
            """), {
                "id": dlq_id,
                "nxt": _next_retry_at(
                    session.execute(text(
                        "SELECT retry_count FROM m1_failed_messages WHERE id = :id"
                    ), {"id": dlq_id}).scalar() or 0
                ),
            })
        session.commit()


def count_pending(organization_id: Optional[str] = None) -> int:
    """Total de mensagens pendentes na queue (retry_count < MAX)."""
    org_id = organization_id or get_default_organization_id()
    with get_session() as session:
        n = session.execute(text("""
            SELECT COUNT(*) FROM m1_failed_messages
            WHERE organization_id = :org AND retry_count < :maxr
        """), {"org": org_id, "maxr": MAX_RETRIES}).scalar()
    return int(n or 0)
