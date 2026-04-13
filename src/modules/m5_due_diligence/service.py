"""Servico M5 — Due Diligence.

Logica de negocio para gestao de checklists de due diligence,
red flags e documentos associados a deals imobiliarios.

Persistencia via Supabase REST (sem SQLAlchemy).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

# FIXME(jwt-refactor): migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'
from src.database import supabase_rest as db
from src.modules.m5_due_diligence.templates import get_checklist_template

# Estados considerados concluidos (obtido ou nao aplicavel)
_DONE_STATUSES = ("obtido", "na")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um registo de due_diligence_items para o formato da API."""
    return {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "deal_id": row.get("deal_id"),
        "category": row.get("category"),
        "item_key": row.get("item_key"),
        "item_name": row.get("item_name"),
        "description": row.get("description"),
        "is_required": row.get("is_required"),
        "status": row.get("status"),
        "document_url": row.get("document_url"),
        "document_date": row.get("document_date"),
        "expiry_date": row.get("expiry_date"),
        "verified_by": row.get("verified_by"),
        "verified_at": row.get("verified_at"),
        "verification_notes": row.get("verification_notes"),
        "red_flag": row.get("red_flag"),
        "red_flag_severity": row.get("red_flag_severity"),
        "red_flag_description": row.get("red_flag_description"),
        "cost": row.get("cost"),
        "cost_paid": row.get("cost_paid"),
        "sort_order": row.get("sort_order"),
        "country": row.get("country"),
        "property_type": row.get("property_type"),
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
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
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        tenant_id = deal["tenant_id"]

        prop = db.get_by_id("properties", deal["property_id"]) if deal.get("property_id") else None
        country = (prop.get("country") if prop else None) or "PT"
        property_type = (prop.get("property_type") if prop else None) or "apartamento"
        strategy = deal.get("investment_strategy")

        template_items = get_checklist_template(country, property_type, strategy)

        items_created: List[Dict[str, Any]] = []
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

            row = {
                "id": db.new_id(),
                "tenant_id": tenant_id,
                "deal_id": deal_id,
                "category": tmpl.get("category", "geral"),
                "item_key": tmpl.get("item_key", f"item_{idx}"),
                "item_name": tmpl.get("item_name", ""),
                "description": tmpl.get("description"),
                "is_required": is_required,
                "status": "pendente",
                "cost": tmpl.get("cost"),
                "sort_order": tmpl.get("sort_order", idx),
                "country": country,
                "property_type": property_type,
            }
            inserted = db.insert("due_diligence_items", row)
            items_created.append(inserted)

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
        self, deal_id: str, deal_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Gera checklist para um deal (chamado pelo M4 advance_deal).

        Aceita deal_data como dict em vez de objecto ORM.
        Se deal_data nao for fornecido, busca o deal pelo id.
        """
        if not deal_data:
            deal_data = db.get_by_id("deals", deal_id)
            if not deal_data:
                raise ValueError(f"Deal nao encontrado: {deal_id}")

        prop = (
            db.get_by_id("properties", deal_data["property_id"])
            if deal_data.get("property_id")
            else None
        )
        country = (prop.get("country") if prop else None) or "PT"
        property_type = (prop.get("property_type") if prop else None) or "apartamento"
        strategy = deal_data.get("investment_strategy")

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

            row = {
                "id": db.new_id(),
                "tenant_id": deal_data.get("tenant_id"),
                "deal_id": deal_id,
                "category": tmpl.get("category", "geral"),
                "item_key": tmpl.get("item_key", f"item_{idx}"),
                "item_name": tmpl.get("item_name", ""),
                "description": tmpl.get("description"),
                "is_required": is_required,
                "status": "pendente",
                "cost": tmpl.get("cost"),
                "sort_order": tmpl.get("sort_order", idx),
                "country": country,
                "property_type": property_type,
            }
            db.insert("due_diligence_items", row)
            count += 1

        return {"deal_id": deal_id, "total_items": count, "country": country}

    def get_checklist(self, deal_id: str) -> Dict[str, Any]:
        """Retorna checklist completo de um deal com estatísticas e agrupamento por categoria."""
        items = db.list_rows(
            "due_diligence_items",
            filters=f"deal_id=eq.{deal_id}",
            order="sort_order.asc",
        )

        total_items = len(items)
        completed = sum(1 for i in items if i.get("status") in _DONE_STATUSES)
        pending = sum(1 for i in items if i.get("status") == "pendente")
        problems = sum(1 for i in items if i.get("status") == "problema")
        na_count = sum(1 for i in items if i.get("status") == "na")
        red_flags = sum(1 for i in items if i.get("red_flag"))
        estimated_cost = sum(
            i.get("cost", 0) or 0 for i in items
        )
        cost_paid = sum(
            (i.get("cost", 0) or 0) for i in items if i.get("cost_paid")
        )
        progress_pct = (
            round(completed / total_items * 100, 1) if total_items else 0.0
        )

        # Agrupar por categoria
        items_by_category: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            cat = item.get("category", "geral")
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
        item = db.get_by_id("due_diligence_items", item_id)
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

        old_status = item.get("status")
        update_data: Dict[str, Any] = {}
        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field]

        # Auto-set verified_at quando estado muda para obtido
        new_status = data.get("status")
        if new_status == "obtido" and old_status != "obtido":
            if not data.get("verified_at"):
                update_data["verified_at"] = datetime.now(timezone.utc).isoformat()

        updated = db.update("due_diligence_items", item_id, update_data)
        logger.info(f"Item DD {item_id} actualizado: {list(data.keys())}")
        return _item_to_dict(updated)

    def add_red_flag(
        self, item_id: str, severity: str, description: str
    ) -> Dict[str, Any]:
        """Assinala um red flag num item de due diligence.

        Se o item estava como 'obtido', retrocede para 'problema'.
        """
        item = db.get_by_id("due_diligence_items", item_id)
        if not item:
            raise ValueError(f"Item nao encontrado: {item_id}")

        update_data: Dict[str, Any] = {
            "red_flag": True,
            "red_flag_severity": severity,
            "red_flag_description": description,
        }

        # Apenas high/critical mudam status para problema
        if item.get("status") == "obtido" and severity in ("high", "critical"):
            update_data["status"] = "problema"

        updated = db.update("due_diligence_items", item_id, update_data)
        logger.warning(
            f"Red flag ({severity}) adicionado ao item DD {item_id}: {description}"
        )
        return _item_to_dict(updated)

    def resolve_red_flag(self, item_id: str, resolution: str) -> Dict[str, Any]:
        """Resolve um red flag num item de due diligence.

        Se o item estava como 'problema', avança para 'obtido'.
        Acrescenta a resolução às notas de verificação.
        """
        item = db.get_by_id("due_diligence_items", item_id)
        if not item:
            raise ValueError(f"Item nao encontrado: {item_id}")

        existing_notes = item.get("verification_notes") or ""
        separator = "\n" if existing_notes else ""
        new_notes = f"{existing_notes}{separator}Resolucao: {resolution}"

        update_data: Dict[str, Any] = {
            "red_flag": False,
            "verification_notes": new_notes,
        }

        if item.get("status") == "problema":
            update_data["status"] = "obtido"
            if not item.get("verified_at"):
                update_data["verified_at"] = datetime.now(timezone.utc).isoformat()

        updated = db.update("due_diligence_items", item_id, update_data)
        logger.info(f"Red flag resolvido no item DD {item_id}: {resolution}")
        return _item_to_dict(updated)

    def add_custom_item(self, deal_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Adiciona um item personalizado ao checklist de um deal."""
        deal = db.get_by_id("deals", deal_id)
        if not deal:
            raise ValueError(f"Deal nao encontrado: {deal_id}")

        custom_suffix = db.new_id()[:8]
        item_key = f"custom_{custom_suffix}"

        row = {
            "id": db.new_id(),
            "tenant_id": deal["tenant_id"],
            "deal_id": deal_id,
            "category": data.get("category", "custom"),
            "item_key": item_key,
            "item_name": data.get("item_name", "Item personalizado"),
            "description": data.get("description"),
            "is_required": data.get("is_required", True),
            "status": data.get("status", "pendente"),
            "cost": data.get("cost"),
            "sort_order": data.get("sort_order", 999),
            "country": data.get("country", "PT"),
            "property_type": data.get("property_type"),
            "notes": data.get("notes"),
        }
        inserted = db.insert("due_diligence_items", row)
        logger.info(
            f"Item personalizado adicionado ao deal {deal_id}: {row['item_name']}"
        )
        return _item_to_dict(inserted)

    # --- Red flags ---

    def get_red_flags(
        self, deal_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retorna todos os red flags activos, opcionalmente filtrados por deal."""
        filters = "red_flag=eq.true"
        if deal_id:
            filters += f"&deal_id=eq.{deal_id}"

        items = db.list_rows(
            "due_diligence_items",
            filters=filters,
            order="red_flag_severity.desc,created_at.desc",
        )
        return [_item_to_dict(i) for i in items]

    # --- Proceed assessment ---

    def can_proceed(self, deal_id: str) -> Dict[str, Any]:
        """Avalia se o deal pode avançar com base nos itens de due diligence.

        Verifica itens obrigatórios pendentes e red flags críticos.
        """
        items = db.list_rows(
            "due_diligence_items",
            filters=f"deal_id=eq.{deal_id}",
        )

        required_items = [i for i in items if i.get("is_required")]
        blocking_items = [
            i for i in required_items if i.get("status") not in _DONE_STATUSES
        ]
        critical_flags = [
            i
            for i in items
            if i.get("red_flag") and i.get("red_flag_severity") == "critical"
        ]
        warnings = [
            i
            for i in items
            if i.get("red_flag") and i.get("red_flag_severity") in ("medium", "high")
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
        all_items = db.list_rows("due_diligence_items")

        total_items = len(all_items)

        # Total de checklists (deal_ids distintos)
        deal_ids = set(i.get("deal_id") for i in all_items if i.get("deal_id"))
        total_checklists = len(deal_ids)

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
            did = item.get("deal_id")
            if did not in deal_progress:
                deal_progress[did] = {"total": 0, "completed": 0}
            deal_progress[did]["total"] += 1
            if item.get("status") in _DONE_STATUSES:
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
        red_flag_items = [i for i in all_items if i.get("red_flag")]
        red_flags_by_severity: Dict[str, int] = {}
        for item in red_flag_items:
            sev = item.get("red_flag_severity") or "unknown"
            red_flags_by_severity[sev] = red_flags_by_severity.get(sev, 0) + 1

        # Custo total estimado
        estimated_total_cost = sum(
            (i.get("cost", 0) or 0) for i in all_items
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
        """Faz upload de um documento e associa-o a um item de due diligence.

        Nota: DocumentStorageService ainda usa sessao SQLAlchemy internamente.
        Quando for migrado, este metodo sera simplificado.
        """
        from src.database.db import get_session
        from src.shared.document_storage import DocumentStorageService

        item = db.get_by_id("due_diligence_items", item_id)
        if not item:
            raise ValueError(f"Item nao encontrado: {item_id}")

        deal_id = item["deal_id"]
        tenant_id = item["tenant_id"]

        with get_session() as session:
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
        from src.database.db import get_session
        from src.shared.document_storage import DocumentStorageService

        item = db.get_by_id("due_diligence_items", item_id)
        if not item:
            raise ValueError(f"Item nao encontrado: {item_id}")

        with get_session() as session:
            storage = DocumentStorageService(session, base_path=storage_base)
            docs = storage.list_documents(dd_item_id=item_id)
            for doc in docs:
                storage.delete_document(doc["id"], hard_delete=True)

        # Repor estado do item via REST
        db.update("due_diligence_items", item_id, {
            "status": "pendente",
            "document_url": None,
            "document_date": None,
        })

        logger.info(
            f"{len(docs)} documento(s) removido(s) do item DD {item_id}"
        )
        return True

    def get_item_documents(self, item_id: str) -> List[Dict[str, Any]]:
        """Lista todos os documentos associados a um item de due diligence."""
        from src.database.db import get_session
        from src.shared.document_storage import DocumentStorageService

        with get_session() as session:
            storage = DocumentStorageService(session)
            return storage.list_documents(dd_item_id=item_id)
