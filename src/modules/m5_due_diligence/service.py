"""Servico M5 — Due Diligence.

Logica de negocio para gestao de checklists de due diligence,
red flags e documentos associados a deals imobiliarios.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.db import get_session
from src.database.models_v2 import (
    Deal,
    Document,
    DueDiligenceItem,
    Property,
    Tenant,
)
from src.modules.m5_due_diligence.templates import get_checklist_template
from src.shared.document_storage import DocumentStorageService

_DEFAULT_TENANT_SLUG = "default"

# Estados considerados concluidos (obtido ou nao aplicavel)
_DONE_STATUSES = ("obtido", "na")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_default_tenant(session: Session) -> str:
    """Garante que o tenant default existe e retorna o id."""
    tenant = session.execute(
        select(Tenant).where(Tenant.slug == _DEFAULT_TENANT_SLUG)
    ).scalar_one_or_none()

    if tenant is None:
        tenant = Tenant(
            id=str(uuid4()),
            name="ImoIA",
            slug=_DEFAULT_TENANT_SLUG,
            country="PT",
        )
        session.add(tenant)
        session.flush()
        logger.info("Tenant default criado")

    return tenant.id


def _item_to_dict(item: DueDiligenceItem) -> Dict[str, Any]:
    """Serializa DueDiligenceItem para dict."""
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "deal_id": item.deal_id,
        "category": item.category,
        "item_key": item.item_key,
        "item_name": item.item_name,
        "description": item.description,
        "is_required": item.is_required,
        "status": item.status,
        "document_url": item.document_url,
        "document_date": (
            item.document_date.isoformat() if item.document_date else None
        ),
        "expiry_date": (
            item.expiry_date.isoformat() if item.expiry_date else None
        ),
        "verified_by": item.verified_by,
        "verified_at": (
            item.verified_at.isoformat() if item.verified_at else None
        ),
        "verification_notes": item.verification_notes,
        "red_flag": item.red_flag,
        "red_flag_severity": item.red_flag_severity,
        "red_flag_description": item.red_flag_description,
        "cost": item.cost,
        "cost_paid": item.cost_paid,
        "sort_order": item.sort_order,
        "country": item.country,
        "property_type": item.property_type,
        "notes": item.notes,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DueDiligenceService:
    """Logica de negocio do M5 — Due Diligence."""

    # --- Checklist ---

    def generate_checklist(self, deal_id: str) -> Dict[str, Any]:
        """Gera checklist de due diligence para um deal.

        Obtém o template adequado com base no país, tipo de imóvel e estratégia
        de investimento. Cria os DueDiligenceItem correspondentes na BD.
        """
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            tenant_id = deal.tenant_id

            prop = session.get(Property, deal.property_id)
            country = (prop.country if prop else None) or "PT"
            property_type = (prop.property_type if prop else None) or "apartamento"
            strategy = deal.investment_strategy

            template_items = get_checklist_template(country, property_type, strategy)

            items_created = []
            for idx, tmpl in enumerate(template_items):
                is_required = tmpl.get("is_required", True)

                # Ajuste: itens de condomínio não são obrigatórios para moradias
                if (
                    tmpl.get("category") == "condominio"
                    or "condominio" in tmpl.get("item_key", "").lower()
                ):
                    if property_type == "moradia":
                        is_required = False

                # Ajuste: PDM é obrigatório para terrenos ou estratégia de desenvolvimento
                if "pdm" in tmpl.get("item_key", "").lower():
                    if property_type in ("terreno",) or strategy == "desenvolvimento":
                        is_required = True

                item = DueDiligenceItem(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    deal_id=deal_id,
                    category=tmpl.get("category", "geral"),
                    item_key=tmpl.get("item_key", f"item_{idx}"),
                    item_name=tmpl.get("item_name", ""),
                    description=tmpl.get("description"),
                    is_required=is_required,
                    status="pendente",
                    cost=tmpl.get("cost"),
                    sort_order=tmpl.get("sort_order", idx),
                    country=country,
                    property_type=property_type,
                )
                session.add(item)
                items_created.append(item)

            session.flush()
            logger.info(
                f"Checklist gerado para deal {deal_id}: "
                f"{len(items_created)} itens ({country}, {property_type}, {strategy})"
            )

            return {
                "deal_id": deal_id,
                "total_items": len(items_created),
                "country": country,
                "property_type": property_type,
                "strategy": strategy,
                "items": [_item_to_dict(i) for i in items_created],
            }

    def generate_checklist_in_session(
        self, session: Any, deal: Any
    ) -> Dict[str, Any]:
        """Gera checklist usando sessao existente (chamado pelo M4 advance_deal)."""
        from src.database.models_v2 import Property as Prop

        prop = session.get(Prop, deal.property_id)
        country = (prop.country if prop else None) or "PT"
        property_type = (prop.property_type if prop else None) or "apartamento"
        strategy = deal.investment_strategy

        template_items = get_checklist_template(country, property_type, strategy)

        count = 0
        for idx, tmpl in enumerate(template_items):
            is_required = tmpl.get("is_required", True)
            if tmpl.get("category") == "condominio" and property_type == "moradia":
                is_required = False
            if "pdm" in tmpl.get("item_key", "") and (
                property_type == "terreno" or strategy == "desenvolvimento"
            ):
                is_required = True

            item = DueDiligenceItem(
                id=str(uuid4()),
                tenant_id=deal.tenant_id,
                deal_id=deal.id,
                category=tmpl.get("category", "geral"),
                item_key=tmpl.get("item_key", f"item_{idx}"),
                item_name=tmpl.get("item_name", ""),
                description=tmpl.get("description"),
                is_required=is_required,
                status="pendente",
                cost=tmpl.get("cost"),
                sort_order=tmpl.get("sort_order", idx),
                country=country,
                property_type=property_type,
            )
            session.add(item)
            count += 1

        return {"deal_id": deal.id, "total_items": count, "country": country}

    def get_checklist(self, deal_id: str) -> Dict[str, Any]:
        """Retorna checklist completo de um deal com estatísticas e agrupamento por categoria."""
        with get_session() as session:
            stmt = (
                select(DueDiligenceItem)
                .where(DueDiligenceItem.deal_id == deal_id)
                .order_by(DueDiligenceItem.sort_order)
            )
            items = session.execute(stmt).scalars().all()

            total_items = len(items)
            completed = sum(1 for i in items if i.status in _DONE_STATUSES)
            pending = sum(1 for i in items if i.status == "pendente")
            problems = sum(1 for i in items if i.status == "problema")
            na_count = sum(1 for i in items if i.status == "na")
            red_flags = sum(1 for i in items if i.red_flag)
            estimated_cost = sum(
                i.cost for i in items if i.cost is not None
            )
            cost_paid = sum(
                i.cost for i in items if i.cost is not None and i.cost_paid
            )
            progress_pct = (
                round(completed / total_items * 100, 1) if total_items else 0.0
            )

            # Agrupar por categoria
            items_by_category: Dict[str, List[Dict[str, Any]]] = {}
            for item in items:
                cat = item.category
                if cat not in items_by_category:
                    items_by_category[cat] = []
                items_by_category[cat].append(_item_to_dict(item))

            return {
                "deal_id": deal_id,
                "total_items": total_items,
                "completed": completed,
                "pending": pending,
                "problems": problems,
                "na_count": na_count,
                "progress_pct": progress_pct,
                "red_flags": red_flags,
                "estimated_cost": estimated_cost,
                "cost_paid": cost_paid,
                "items_by_category": items_by_category,
            }

    # --- Item operations ---

    def update_item(self, item_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza campos de um item de due diligence.

        Se o estado mudar para 'obtido', define verified_at automaticamente
        caso não tenha sido fornecido.
        """
        with get_session() as session:
            item = session.get(DueDiligenceItem, item_id)
            if not item:
                raise ValueError(f"Item nao encontrado: {item_id}")

            updatable_fields = (
                "status",
                "document_url",
                "document_date",
                "verification_notes",
                "verified_by",
                "verified_at",
                "red_flag",
                "red_flag_severity",
                "red_flag_description",
                "cost_paid",
                "notes",
            )

            old_status = item.status
            for field in updatable_fields:
                if field in data:
                    setattr(item, field, data[field])

            # Auto-set verified_at quando estado muda para obtido
            new_status = data.get("status")
            if new_status == "obtido" and old_status != "obtido":
                if not data.get("verified_at"):
                    item.verified_at = datetime.now(timezone.utc)

            session.flush()
            logger.info(f"Item DD {item_id} actualizado: {list(data.keys())}")
            return _item_to_dict(item)

    def add_red_flag(
        self, item_id: str, severity: str, description: str
    ) -> Dict[str, Any]:
        """Assinala um red flag num item de due diligence.

        Se o item estava como 'obtido', retrocede para 'problema'.
        """
        with get_session() as session:
            item = session.get(DueDiligenceItem, item_id)
            if not item:
                raise ValueError(f"Item nao encontrado: {item_id}")

            item.red_flag = True
            item.red_flag_severity = severity
            item.red_flag_description = description

            # Apenas high/critical mudam status para problema
            if item.status == "obtido" and severity in ("high", "critical"):
                item.status = "problema"

            session.flush()
            logger.warning(
                f"Red flag ({severity}) adicionado ao item DD {item_id}: {description}"
            )
            return _item_to_dict(item)

    def resolve_red_flag(self, item_id: str, resolution: str) -> Dict[str, Any]:
        """Resolve um red flag num item de due diligence.

        Se o item estava como 'problema', avança para 'obtido'.
        Acrescenta a resolução às notas de verificação.
        """
        with get_session() as session:
            item = session.get(DueDiligenceItem, item_id)
            if not item:
                raise ValueError(f"Item nao encontrado: {item_id}")

            item.red_flag = False

            existing_notes = item.verification_notes or ""
            separator = "\n" if existing_notes else ""
            item.verification_notes = (
                f"{existing_notes}{separator}Resolucao: {resolution}"
            )

            if item.status == "problema":
                item.status = "obtido"
                if not item.verified_at:
                    item.verified_at = datetime.now(timezone.utc)

            session.flush()
            logger.info(f"Red flag resolvido no item DD {item_id}: {resolution}")
            return _item_to_dict(item)

    def add_custom_item(self, deal_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Adiciona um item personalizado ao checklist de um deal."""
        with get_session() as session:
            deal = session.get(Deal, deal_id)
            if not deal:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

            custom_suffix = str(uuid4())[:8]
            item_key = f"custom_{custom_suffix}"

            item = DueDiligenceItem(
                id=str(uuid4()),
                tenant_id=deal.tenant_id,
                deal_id=deal_id,
                category=data.get("category", "custom"),
                item_key=item_key,
                item_name=data.get("item_name", "Item personalizado"),
                description=data.get("description"),
                is_required=data.get("is_required", True),
                status=data.get("status", "pendente"),
                cost=data.get("cost"),
                sort_order=data.get("sort_order", 999),
                country=data.get("country", "PT"),
                property_type=data.get("property_type"),
                notes=data.get("notes"),
            )
            session.add(item)
            session.flush()
            logger.info(
                f"Item personalizado adicionado ao deal {deal_id}: {item.item_name}"
            )
            return _item_to_dict(item)

    # --- Red flags ---

    def get_red_flags(
        self, deal_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retorna todos os red flags activos, opcionalmente filtrados por deal."""
        with get_session() as session:
            stmt = select(DueDiligenceItem).where(
                DueDiligenceItem.red_flag == True  # noqa: E712
            )
            if deal_id:
                stmt = stmt.where(DueDiligenceItem.deal_id == deal_id)

            stmt = stmt.order_by(
                DueDiligenceItem.red_flag_severity.desc(),
                DueDiligenceItem.created_at.desc(),
            )
            items = session.execute(stmt).scalars().all()
            return [_item_to_dict(i) for i in items]

    # --- Proceed assessment ---

    def can_proceed(self, deal_id: str) -> Dict[str, Any]:
        """Avalia se o deal pode avançar com base nos itens de due diligence.

        Verifica itens obrigatórios pendentes e red flags críticos.
        """
        with get_session() as session:
            stmt = select(DueDiligenceItem).where(
                DueDiligenceItem.deal_id == deal_id
            )
            items = session.execute(stmt).scalars().all()

            required_items = [i for i in items if i.is_required]
            blocking_items = [
                i for i in required_items if i.status not in _DONE_STATUSES
            ]
            critical_flags = [
                i
                for i in items
                if i.red_flag and i.red_flag_severity == "critical"
            ]
            warnings = [
                i
                for i in items
                if i.red_flag and i.red_flag_severity in ("medium", "high")
            ]

            proceed = len(blocking_items) == 0 and len(critical_flags) == 0

            return {
                "deal_id": deal_id,
                "can_proceed": proceed,
                "blocking_items": [_item_to_dict(i) for i in blocking_items],
                "critical_flags": [_item_to_dict(i) for i in critical_flags],
                "warnings": [_item_to_dict(i) for i in warnings],
                "blocking_count": len(blocking_items),
                "critical_count": len(critical_flags),
                "warning_count": len(warnings),
            }

    # --- Stats ---

    def get_dd_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas globais de due diligence."""
        with get_session() as session:
            # Total de checklists (deal_ids distintos)
            distinct_deals_stmt = select(
                func.count(func.distinct(DueDiligenceItem.deal_id))
            )
            total_checklists = (
                session.execute(distinct_deals_stmt).scalar() or 0
            )

            # Todos os itens para calcular métricas
            all_items = session.execute(select(DueDiligenceItem)).scalars().all()

            total_items = len(all_items)
            if total_items == 0:
                return {
                    "total_checklists": total_checklists,
                    "average_progress_pct": 0.0,
                    "red_flags_by_severity": {},
                    "estimated_total_cost": 0.0,
                }

            # Progresso médio por deal
            deal_progress: Dict[str, Dict[str, int]] = {}
            for item in all_items:
                did = item.deal_id
                if did not in deal_progress:
                    deal_progress[did] = {"total": 0, "completed": 0}
                deal_progress[did]["total"] += 1
                if item.status in _DONE_STATUSES:
                    deal_progress[did]["completed"] += 1

            avg_progress = 0.0
            if deal_progress:
                pcts = [
                    v["completed"] / v["total"] * 100
                    for v in deal_progress.values()
                    if v["total"] > 0
                ]
                avg_progress = round(sum(pcts) / len(pcts), 1) if pcts else 0.0

            # Red flags por severidade
            red_flag_items = [i for i in all_items if i.red_flag]
            red_flags_by_severity: Dict[str, int] = {}
            for item in red_flag_items:
                sev = item.red_flag_severity or "unknown"
                red_flags_by_severity[sev] = red_flags_by_severity.get(sev, 0) + 1

            # Custo total estimado
            estimated_total_cost = sum(
                i.cost for i in all_items if i.cost is not None
            )

            return {
                "total_checklists": total_checklists,
                "average_progress_pct": avg_progress,
                "red_flags_by_severity": red_flags_by_severity,
                "estimated_total_cost": estimated_total_cost,
            }

    # --- Document operations ---

    def upload_item_document(
        self,
        item_id: str,
        file_content: bytes,
        filename: str,
        uploaded_by: str = "system",
        storage_base: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Faz upload de um documento e associa-o a um item de due diligence."""
        with get_session() as session:
            item = session.get(DueDiligenceItem, item_id)
            if not item:
                raise ValueError(f"Item nao encontrado: {item_id}")

            deal_id = item.deal_id
            tenant_id = item.tenant_id

            storage = DocumentStorageService(session, base_path=storage_base)
            doc = storage.upload_document(
                file_content=file_content,
                filename=filename,
                tenant_id=tenant_id,
                deal_id=deal_id,
                dd_item_id=item_id,
                uploaded_by=uploaded_by,
            )

            logger.info(
                f"Documento '{filename}' associado ao item DD {item_id} "
                f"(deal {deal_id})"
            )
            return doc

    def remove_item_document(
        self, item_id: str, storage_base: Optional[str] = None
    ) -> bool:
        """Remove todos os documentos de um item e repoe o estado para pendente."""
        with get_session() as session:
            item = session.get(DueDiligenceItem, item_id)
            if not item:
                raise ValueError(f"Item nao encontrado: {item_id}")

            storage = DocumentStorageService(session, base_path=storage_base)
            docs = storage.list_documents(dd_item_id=item_id)

            for doc in docs:
                storage.delete_document(doc["id"], hard_delete=True)

            item.status = "pendente"
            item.document_url = None
            item.document_date = None

            session.flush()
            logger.info(
                f"{len(docs)} documento(s) removido(s) do item DD {item_id}"
            )
            return True

    def get_item_documents(self, item_id: str) -> List[Dict[str, Any]]:
        """Lista todos os documentos associados a um item de due diligence."""
        with get_session() as session:
            storage = DocumentStorageService(session)
            return storage.list_documents(dd_item_id=item_id)
