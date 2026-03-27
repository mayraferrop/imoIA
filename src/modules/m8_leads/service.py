"""Servico M8 — CRM de Leads.

Logica de negocio para gestao de leads: CRUD, scoring, matching,
nurturing automatico, integracao Habta, e analytics.

Persistencia via Supabase REST (sem SQLAlchemy).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger

from src.database import supabase_rest as db

_DEFAULT_TENANT_SLUG = "default"

# Transicoes de estagio validas
STAGE_TRANSITIONS: Dict[str, List[str]] = {
    "new": ["contacted", "lost"],
    "contacted": ["qualified", "lost"],
    "qualified": ["visiting", "lost"],
    "visiting": ["proposal", "qualified", "lost"],
    "proposal": ["negotiation", "visiting", "lost"],
    "negotiation": ["won", "proposal", "lost"],
    "won": [],
    "lost": ["new"],
}

ALL_STAGES = list(STAGE_TRANSITIONS.keys())

# Definicao dos passos de nurturing standard
NURTURE_STEPS = [
    {"step": 0, "action": "welcome_email", "delay_hours": 0, "label": "Email de boas-vindas"},
    {"step": 1, "action": "send_matches", "delay_hours": 24, "label": "Enviar listings compativeis"},
    {"step": 2, "action": "follow_up_call", "delay_hours": 72, "label": "Chamada de follow-up"},
    {"step": 3, "action": "market_update", "delay_hours": 168, "label": "Actualizacao de mercado"},
    {"step": 4, "action": "exclusive_offer", "delay_hours": 336, "label": "Oferta exclusiva"},
]


def _lead_to_dict(lead: Dict[str, Any], interactions_count: int = 0) -> Dict[str, Any]:
    """Converte dict de Lead para formato de resposta."""
    return {
        "id": lead.get("id"),
        "name": lead.get("name"),
        "email": lead.get("email"),
        "phone": lead.get("phone"),
        "budget_min": lead.get("budget_min"),
        "budget_max": lead.get("budget_max"),
        "preferred_typology": lead.get("preferred_typology"),
        "preferred_locations": lead.get("preferred_locations") or [],
        "preferred_features": lead.get("preferred_features") or [],
        "timeline": lead.get("timeline"),
        "financing": lead.get("financing"),
        "buyer_type": lead.get("buyer_type"),
        "stage": lead.get("stage"),
        "stage_changed_at": lead.get("stage_changed_at"),
        "score": lead.get("score"),
        "score_breakdown": lead.get("score_breakdown") or {},
        "grade": lead.get("grade"),
        "source": lead.get("source"),
        "source_listing_id": lead.get("source_listing_id"),
        "source_campaign": lead.get("source_campaign"),
        "utm_source": lead.get("utm_source"),
        "utm_medium": lead.get("utm_medium"),
        "utm_campaign": lead.get("utm_campaign"),
        "habta_contact_id": lead.get("habta_contact_id"),
        "deal_id": lead.get("deal_id"),
        "assigned_to": lead.get("assigned_to"),
        "notes": lead.get("notes"),
        "tags": lead.get("tags") or [],
        "interactions_count": interactions_count,
        "created_at": lead.get("created_at"),
        "updated_at": lead.get("updated_at"),
    }


def _interaction_to_dict(interaction: Dict[str, Any]) -> Dict[str, Any]:
    """Converte dict de LeadInteraction para formato de resposta."""
    return {
        "id": interaction.get("id"),
        "lead_id": interaction.get("lead_id"),
        "type": interaction.get("type"),
        "channel": interaction.get("channel"),
        "direction": interaction.get("direction"),
        "subject": interaction.get("subject"),
        "content": interaction.get("content"),
        "listing_id": interaction.get("listing_id"),
        "metadata": interaction.get("metadata_") or interaction.get("metadata") or {},
        "performed_by": interaction.get("performed_by"),
        "created_at": interaction.get("created_at"),
    }


def _match_to_dict(match: Dict[str, Any], listing_info: Optional[Dict] = None) -> Dict[str, Any]:
    """Converte dict de LeadListingMatch para formato de resposta."""
    return {
        "id": match.get("id"),
        "lead_id": match.get("lead_id"),
        "listing_id": match.get("listing_id"),
        "match_score": match.get("match_score"),
        "match_reasons": match.get("match_reasons") or [],
        "status": match.get("status"),
        "sent_at": match.get("sent_at"),
        "response_at": match.get("response_at"),
        "listing_info": listing_info,
        "created_at": match.get("created_at"),
    }


def _nurture_to_dict(ns: Dict[str, Any]) -> Dict[str, Any]:
    """Converte dict de NurtureSequence para formato de resposta."""
    return {
        "id": ns.get("id"),
        "lead_id": ns.get("lead_id"),
        "listing_id": ns.get("listing_id"),
        "sequence_type": ns.get("sequence_type"),
        "current_step": ns.get("current_step"),
        "status": ns.get("status"),
        "next_action_at": ns.get("next_action_at"),
        "steps_executed": ns.get("steps_executed") or [],
        "created_at": ns.get("created_at"),
    }


def _calculate_grade(score: int) -> str:
    """Calcula grade a partir do score."""
    if score >= 70:
        return "A"
    elif score >= 50:
        return "B"
    elif score >= 30:
        return "C"
    return "D"


class LeadService:
    """Servico de gestao de leads (M8)."""

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_lead(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo lead."""
        tenant_id = db.ensure_tenant()
        now = datetime.utcnow().isoformat()
        lead_id = db.new_id()

        lead = db.insert("leads", {
            "id": lead_id,
            "tenant_id": tenant_id,
            "name": data["name"],
            "email": data.get("email"),
            "phone": data.get("phone"),
            "budget_min": data.get("budget_min"),
            "budget_max": data.get("budget_max"),
            "preferred_typology": data.get("preferred_typology"),
            "preferred_locations": data.get("preferred_locations", []),
            "preferred_features": data.get("preferred_features", []),
            "timeline": data.get("timeline"),
            "financing": data.get("financing"),
            "buyer_type": data.get("buyer_type"),
            "stage": "new",
            "stage_changed_at": now,
            "score": 0,
            "score_breakdown": {},
            "grade": "D",
            "source": data.get("source"),
            "source_listing_id": data.get("source_listing_id"),
            "source_campaign": data.get("source_campaign"),
            "utm_source": data.get("utm_source"),
            "utm_medium": data.get("utm_medium"),
            "utm_campaign": data.get("utm_campaign"),
            "habta_contact_id": data.get("habta_contact_id"),
            "deal_id": data.get("deal_id"),
            "assigned_to": data.get("assigned_to"),
            "notes": data.get("notes"),
            "tags": data.get("tags", []),
        })
        logger.info(f"Lead criado: {lead_id} ({data['name']})")

        # Calcular score automaticamente
        result = self._do_recalculate_score(lead)
        return result

    def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Obtem um lead por ID."""
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            return None
        count = db._count("lead_interactions", f"lead_id=eq.{lead_id}")
        return _lead_to_dict(lead, count)

    def update_lead(self, lead_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Actualiza um lead."""
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            return None

        updatable = (
            "name", "email", "phone", "budget_min", "budget_max",
            "preferred_typology", "preferred_locations", "preferred_features",
            "timeline", "financing", "buyer_type", "source",
            "source_listing_id", "source_campaign",
            "utm_source", "utm_medium", "utm_campaign",
            "deal_id", "assigned_to", "notes", "tags",
        )
        update_data = {}
        for field in updatable:
            if field in data and data[field] is not None:
                update_data[field] = data[field]

        if update_data:
            lead = db.update("leads", lead_id, update_data)

        result = self._do_recalculate_score(lead)
        logger.info(f"Lead actualizado: {lead_id}")
        return result

    def delete_lead(self, lead_id: str) -> bool:
        """Remove um lead."""
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            return False

        # Remover nurture sequences
        db.delete_by_filter("nurture_sequences", f"lead_id=eq.{lead_id}")
        # Remover matches
        db.delete_by_filter("lead_listing_matches", f"lead_id=eq.{lead_id}")
        # Remover lead
        db.delete_by_id("leads", lead_id)
        logger.info(f"Lead removido: {lead_id}")
        return True

    def list_leads(
        self,
        stage: Optional[str] = None,
        grade: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Lista leads com filtros e paginacao."""
        db.ensure_tenant()
        filter_parts = []

        if stage:
            filter_parts.append(f"stage=eq.{stage}")
        if grade:
            filter_parts.append(f"grade=eq.{grade}")
        if source:
            filter_parts.append(f"source=eq.{source}")
        if search:
            # ilike para busca parcial em nome, email, telefone
            filter_parts.append(
                f"or=(name.ilike.*{search}*,email.ilike.*{search}*,phone.ilike.*{search}*)"
            )

        filters = "&".join(filter_parts)

        # Mapa de ordenacao
        sort_map = {
            "created_at": "created_at.desc",
            "score": "score.desc",
            "name": "name.asc",
            "stage": "stage.asc",
            "updated_at": "updated_at.desc",
        }
        order = sort_map.get(sort_by, "created_at.desc")

        result = db.list_with_count(
            "leads",
            filters=filters,
            order=order,
            limit=limit,
            offset=offset,
        )

        items = []
        for lead in result["items"]:
            count = db._count("lead_interactions", f"lead_id=eq.{lead['id']}")
            items.append(_lead_to_dict(lead, count))

        return {"items": items, "total": result["total"], "limit": limit, "offset": offset}

    # ------------------------------------------------------------------
    # Stage Management
    # ------------------------------------------------------------------

    def advance_stage(self, lead_id: str, new_stage: str) -> Dict[str, Any]:
        """Avanca o estagio do lead com validacao de transicao."""
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} nao encontrado")

        current = lead.get("stage")
        allowed = STAGE_TRANSITIONS.get(current, [])
        if new_stage not in allowed:
            raise ValueError(
                f"Transicao invalida: {current} -> {new_stage}. "
                f"Permitidas: {allowed}"
            )

        now = datetime.utcnow().isoformat()
        lead = db.update("leads", lead_id, {
            "stage": new_stage,
            "stage_changed_at": now,
        })

        # Registar interaccao automatica
        db.insert("lead_interactions", {
            "id": db.new_id(),
            "tenant_id": lead.get("tenant_id"),
            "lead_id": lead_id,
            "type": "stage_change",
            "channel": "system",
            "direction": "internal",
            "subject": f"Estagio alterado: {current} -> {new_stage}",
            "content": f"Lead movido de '{current}' para '{new_stage}'",
            "performed_by": "system",
        })

        # Hook M4: ao chegar a 'proposal', pode criar proposta no deal
        if new_stage == "proposal" and lead.get("deal_id"):
            logger.info(
                f"Lead {lead_id} chegou a 'proposal' — "
                f"hook M4 para deal {lead.get('deal_id')}"
            )

        count = db._count("lead_interactions", f"lead_id=eq.{lead_id}")
        logger.info(f"Lead {lead_id}: {current} -> {new_stage}")
        return _lead_to_dict(lead, count)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def recalculate_score(self, lead_id: str) -> Dict[str, Any]:
        """Recalcula o score de um lead."""
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} nao encontrado")
        return self._do_recalculate_score(lead)

    def _do_recalculate_score(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula e persiste o score do lead (4 componentes)."""
        lead_id = lead["id"]

        # 1. Demografico (0-30): budget, email, telefone, tipologia
        demographic = 0
        if lead.get("budget_min") is not None or lead.get("budget_max") is not None:
            demographic += 10
        if lead.get("email"):
            demographic += 5
        if lead.get("phone"):
            demographic += 5
        if lead.get("preferred_typology"):
            demographic += 5
        pref_locs = lead.get("preferred_locations") or []
        if pref_locs and len(pref_locs) > 0:
            demographic += 5
        demographic = min(demographic, 30)

        # 2. Comportamental (0-40): interaccoes, visitas, propostas
        interactions_count = db._count(
            "lead_interactions", f"lead_id=eq.{lead_id}"
        )

        behavioral = 0
        if interactions_count >= 1:
            behavioral += 10
        if interactions_count >= 3:
            behavioral += 10
        if interactions_count >= 5:
            behavioral += 10

        # Bonus por tipos especificos (visitas)
        visit_count = db._count(
            "lead_interactions",
            f"lead_id=eq.{lead_id}&type=eq.visit",
        )
        if visit_count >= 1:
            behavioral += 10
        behavioral = min(behavioral, 40)

        # 3. Comunicacao (0-20): ultimo contacto recente, respostas
        communication = 0
        last_interactions = db.list_rows(
            "lead_interactions",
            filters=f"lead_id=eq.{lead_id}",
            order="created_at.desc",
            limit=1,
        )

        if last_interactions:
            last_interaction = last_interactions[0]
            created_str = last_interaction.get("created_at")
            if created_str:
                try:
                    created_dt = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    days_since = (datetime.utcnow() - created_dt).days
                    if days_since <= 3:
                        communication += 15
                    elif days_since <= 7:
                        communication += 10
                    elif days_since <= 14:
                        communication += 5
                except (ValueError, TypeError):
                    pass

        # Bonus por interaccoes recebidas (inbound)
        inbound_count = db._count(
            "lead_interactions",
            f"lead_id=eq.{lead_id}&direction=eq.inbound",
        )
        if inbound_count >= 1:
            communication += 5
        communication = min(communication, 20)

        # 4. Urgencia (0-10): timeline, financing, estagio avancado
        urgency = 0
        if lead.get("timeline") in ("imediato", "immediate", "1_month"):
            urgency += 5
        elif lead.get("timeline") in ("3_months", "3_meses"):
            urgency += 3
        if lead.get("financing") in ("pre_approved", "pre_aprovado", "cash"):
            urgency += 3
        if lead.get("stage") in ("visiting", "proposal", "negotiation"):
            urgency += 2
        urgency = min(urgency, 10)

        total = demographic + behavioral + communication + urgency
        grade = _calculate_grade(total)

        breakdown = {
            "demographic": demographic,
            "behavioral": behavioral,
            "communication": communication,
            "urgency": urgency,
            "total": total,
        }

        lead = db.update("leads", lead_id, {
            "score": total,
            "score_breakdown": breakdown,
            "grade": grade,
        })

        count = db._count("lead_interactions", f"lead_id=eq.{lead_id}")

        logger.debug(
            f"Score recalculado para lead {lead_id}: "
            f"{total} (grade={grade})"
        )
        return _lead_to_dict(lead, count)

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def add_interaction(
        self, lead_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Regista uma interaccao com o lead."""
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} nao encontrado")

        interaction = db.insert("lead_interactions", {
            "id": db.new_id(),
            "tenant_id": lead.get("tenant_id"),
            "lead_id": lead_id,
            "type": data["type"],
            "channel": data.get("channel"),
            "direction": data.get("direction"),
            "subject": data.get("subject"),
            "content": data.get("content"),
            "listing_id": data.get("listing_id"),
            "metadata_": data.get("metadata_") or data.get("metadata", {}),
            "performed_by": data.get("performed_by"),
        })

        # Recalcular score apos nova interaccao
        self._do_recalculate_score(lead)

        logger.info(
            f"Interaccao registada: {data['type']} "
            f"para lead {lead_id}"
        )
        return _interaction_to_dict(interaction)

    def list_interactions(
        self, lead_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """Lista interaccoes de um lead."""
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} nao encontrado")

        total = db._count("lead_interactions", f"lead_id=eq.{lead_id}")

        interactions = db.list_rows(
            "lead_interactions",
            filters=f"lead_id=eq.{lead_id}",
            order="created_at.desc",
            limit=limit,
            offset=offset,
        )

        return {
            "items": [_interaction_to_dict(i) for i in interactions],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_timeline(self, lead_id: str) -> List[Dict[str, Any]]:
        """Retorna timeline cronologica do lead (interaccoes + mudancas de estagio)."""
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} nao encontrado")

        interactions = db.list_rows(
            "lead_interactions",
            filters=f"lead_id=eq.{lead_id}",
            order="created_at.asc",
            limit=1000,
        )

        timeline = []
        for i in interactions:
            timeline.append({
                "timestamp": i.get("created_at"),
                "type": i.get("type"),
                "channel": i.get("channel"),
                "direction": i.get("direction"),
                "subject": i.get("subject"),
                "content": i.get("content"),
                "performed_by": i.get("performed_by"),
            })

        return timeline

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def find_matches(self, lead_id: str) -> List[Dict[str, Any]]:
        """Encontra listings compativeis com as preferencias do lead.

        Faz join Listing -> Deal -> Property para obter localizacao/tipologia.
        Score baseado em: budget (40%), localizacao (35%), tipologia (25%).
        """
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} nao encontrado")

        # Buscar listings activas
        active_listings = db.list_rows(
            "listings",
            filters="status=in.(active,published,draft)",
            limit=500,
        )

        matches = []
        for listing in active_listings:
            deal_id = listing.get("deal_id")
            if not deal_id:
                continue

            deal = db.get_by_id("deals", deal_id)
            if not deal:
                continue

            prop_id = deal.get("property_id")
            prop = db.get_by_id("properties", prop_id) if prop_id else None
            if not prop:
                continue

            score = 0.0
            reasons = []

            # Budget match (40%)
            if lead.get("budget_min") is not None or lead.get("budget_max") is not None:
                price = listing.get("listing_price", 0)
                budget_ok = True
                if lead.get("budget_min") is not None and price < lead["budget_min"]:
                    budget_ok = False
                if lead.get("budget_max") is not None and price > lead["budget_max"]:
                    budget_ok = False
                if budget_ok:
                    score += 40
                    reasons.append(
                        f"Preco {price:.0f}EUR dentro do orcamento"
                    )
                else:
                    # Partial score if close
                    if lead.get("budget_max") and price <= lead["budget_max"] * 1.1:
                        score += 15
                        reasons.append(
                            f"Preco {price:.0f}EUR proximo do orcamento"
                        )

            # Location match (35%)
            pref_locations = lead.get("preferred_locations") or []
            if pref_locations:
                locations_lower = [loc.lower() for loc in pref_locations]
                prop_locations = [
                    (prop.get("municipality") or "").lower(),
                    (prop.get("district") or "").lower(),
                    (prop.get("parish") or "").lower(),
                ]
                for loc in locations_lower:
                    if loc and any(loc in pl for pl in prop_locations if pl):
                        score += 35
                        reasons.append(
                            f"Localizacao compativel: {prop.get('municipality')}"
                        )
                        break

            # Typology match (25%)
            if lead.get("preferred_typology"):
                lead_typo = lead["preferred_typology"].upper()
                prop_typo = (prop.get("typology") or "").upper()
                if lead_typo == prop_typo:
                    score += 25
                    reasons.append(f"Tipologia compativel: {prop.get('typology')}")
                elif lead_typo and prop_typo:
                    # Partial: T2 lead might accept T3
                    try:
                        lead_rooms = int(lead_typo.replace("T", ""))
                        prop_rooms = int(prop_typo.replace("T", ""))
                        if abs(lead_rooms - prop_rooms) == 1:
                            score += 10
                            reasons.append(
                                f"Tipologia proxima: {prop.get('typology')}"
                            )
                    except (ValueError, AttributeError):
                        pass

            if score > 0:
                # Verificar se ja existe match
                existing_matches = db.list_rows(
                    "lead_listing_matches",
                    filters=f"lead_id=eq.{lead_id}&listing_id=eq.{listing['id']}",
                    limit=1,
                )

                if existing_matches:
                    match_obj = db.update(
                        "lead_listing_matches",
                        existing_matches[0]["id"],
                        {"match_score": score, "match_reasons": reasons},
                    )
                else:
                    match_obj = db.insert("lead_listing_matches", {
                        "id": db.new_id(),
                        "tenant_id": lead.get("tenant_id"),
                        "lead_id": lead_id,
                        "listing_id": listing["id"],
                        "match_score": score,
                        "match_reasons": reasons,
                        "status": "suggested",
                    })

                listing_info = {
                    "listing_price": listing.get("listing_price"),
                    "listing_type": listing.get("listing_type"),
                    "municipality": prop.get("municipality"),
                    "district": prop.get("district"),
                    "typology": prop.get("typology"),
                    "bedrooms": prop.get("bedrooms"),
                    "gross_area_m2": prop.get("gross_area_m2"),
                }
                matches.append(_match_to_dict(match_obj, listing_info))

        # Ordenar por score desc
        matches.sort(key=lambda x: x["match_score"] or 0, reverse=True)
        logger.info(f"Encontrados {len(matches)} matches para lead {lead_id}")
        return matches

    def send_listing_to_lead(
        self, lead_id: str, listing_id: str
    ) -> Dict[str, Any]:
        """Marca um match como enviado ao lead."""
        existing_matches = db.list_rows(
            "lead_listing_matches",
            filters=f"lead_id=eq.{lead_id}&listing_id=eq.{listing_id}",
            limit=1,
        )

        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} nao encontrado")

        now = datetime.utcnow().isoformat()

        if not existing_matches:
            # Criar match se nao existe
            match_obj = db.insert("lead_listing_matches", {
                "id": db.new_id(),
                "tenant_id": lead.get("tenant_id"),
                "lead_id": lead_id,
                "listing_id": listing_id,
                "match_score": 0,
                "match_reasons": ["Envio manual"],
                "status": "sent",
                "sent_at": now,
            })
        else:
            match_obj = db.update(
                "lead_listing_matches",
                existing_matches[0]["id"],
                {"status": "sent", "sent_at": now},
            )

        # Registar interaccao
        db.insert("lead_interactions", {
            "id": db.new_id(),
            "tenant_id": lead.get("tenant_id"),
            "lead_id": lead_id,
            "type": "listing_sent",
            "channel": "email",
            "direction": "outbound",
            "subject": f"Listing {listing_id} enviada",
            "listing_id": listing_id,
            "performed_by": "system",
        })

        logger.info(f"Listing {listing_id} enviada para lead {lead_id}")
        return _match_to_dict(match_obj)

    # ------------------------------------------------------------------
    # Habta Sync
    # ------------------------------------------------------------------

    def sync_from_habta(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Importa/actualiza leads a partir de contactos Habta (Supabase).

        Formato esperado de cada contacto:
        {
            "id": "habta-uuid",
            "name": "Nome",
            "email": "email@...",
            "phone": "+351...",
            "budget": "400000-500000",  (ou "300000" ou None)
            "preferences": {"typology": "T2", "locations": ["Lisboa"]},
            "source": "habta_website",
        }
        """
        created = 0
        updated = 0
        errors = 0

        tenant_id = db.ensure_tenant()

        for contact in contacts:
            try:
                habta_id = contact.get("id")
                if not habta_id:
                    errors += 1
                    continue

                # Parse budget
                budget_min = None
                budget_max = None
                budget_str = contact.get("budget")
                if budget_str:
                    if isinstance(budget_str, str) and "-" in budget_str:
                        parts = budget_str.split("-")
                        budget_min = float(parts[0].strip())
                        budget_max = float(parts[1].strip())
                    elif budget_str:
                        try:
                            val = float(budget_str)
                            budget_max = val
                        except (ValueError, TypeError):
                            pass

                prefs = contact.get("preferences", {}) or {}

                existing = db.list_rows(
                    "leads",
                    filters=f"habta_contact_id=eq.{habta_id}",
                    limit=1,
                )

                if existing:
                    update_data: Dict[str, Any] = {}
                    if contact.get("name"):
                        update_data["name"] = contact["name"]
                    if contact.get("email"):
                        update_data["email"] = contact["email"]
                    if contact.get("phone"):
                        update_data["phone"] = contact["phone"]
                    if budget_min is not None:
                        update_data["budget_min"] = budget_min
                    if budget_max is not None:
                        update_data["budget_max"] = budget_max
                    if prefs.get("typology"):
                        update_data["preferred_typology"] = prefs["typology"]
                    if prefs.get("locations"):
                        update_data["preferred_locations"] = prefs["locations"]
                    if update_data:
                        db.update("leads", existing[0]["id"], update_data)
                    updated += 1
                else:
                    db.insert("leads", {
                        "id": db.new_id(),
                        "tenant_id": tenant_id,
                        "name": contact.get("name", "Sem nome"),
                        "email": contact.get("email"),
                        "phone": contact.get("phone"),
                        "budget_min": budget_min,
                        "budget_max": budget_max,
                        "preferred_typology": prefs.get("typology"),
                        "preferred_locations": prefs.get("locations", []),
                        "preferred_features": prefs.get("features", []),
                        "source": contact.get("source", "habta"),
                        "habta_contact_id": habta_id,
                        "stage": "new",
                        "stage_changed_at": datetime.utcnow().isoformat(),
                        "score": 0,
                        "grade": "D",
                    })
                    created += 1

            except Exception as e:
                logger.error(f"Erro ao importar contacto Habta: {e}")
                errors += 1

        logger.info(
            f"Sync Habta concluido: {created} criados, "
            f"{updated} actualizados, {errors} erros"
        )
        return {"created": created, "updated": updated, "errors": errors}

    # ------------------------------------------------------------------
    # Nurturing
    # ------------------------------------------------------------------

    def start_nurture(
        self,
        lead_id: str,
        sequence_type: str = "standard",
        listing_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Inicia uma sequencia de nurturing para um lead."""
        lead = db.get_by_id("leads", lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} nao encontrado")

        # Verificar se ja tem nurture activo
        existing = db.list_rows(
            "nurture_sequences",
            filters=f"lead_id=eq.{lead_id}&status=eq.active",
            limit=1,
        )
        if existing:
            raise ValueError(
                f"Lead {lead_id} ja tem nurture activo: {existing[0]['id']}"
            )

        now = datetime.utcnow().isoformat()
        ns = db.insert("nurture_sequences", {
            "id": db.new_id(),
            "tenant_id": lead.get("tenant_id"),
            "lead_id": lead_id,
            "listing_id": listing_id,
            "sequence_type": sequence_type,
            "current_step": 0,
            "status": "active",
            "next_action_at": now,
            "steps_executed": [],
        })

        logger.info(
            f"Nurture iniciado para lead {lead_id}: "
            f"tipo={sequence_type}"
        )
        return _nurture_to_dict(ns)

    def execute_pending_nurtures(self) -> Dict[str, Any]:
        """Executa todos os passos de nurturing pendentes."""
        executed = 0
        completed = 0
        errors = 0

        now = datetime.utcnow()
        now_iso = now.isoformat()

        # Buscar nurtures activos com next_action_at <= agora
        pending = db.list_rows(
            "nurture_sequences",
            filters=f"status=eq.active&next_action_at=lte.{now_iso}",
            limit=500,
        )

        for ns in pending:
            try:
                step_idx = ns.get("current_step", 0)
                if step_idx >= len(NURTURE_STEPS):
                    db.update("nurture_sequences", ns["id"], {"status": "completed"})
                    completed += 1
                    continue

                step = NURTURE_STEPS[step_idx]
                # Registar interaccao
                db.insert("lead_interactions", {
                    "id": db.new_id(),
                    "tenant_id": ns.get("tenant_id"),
                    "lead_id": ns.get("lead_id"),
                    "type": f"nurture_{step['action']}",
                    "channel": "system",
                    "direction": "outbound",
                    "subject": step["label"],
                    "content": f"Passo {step_idx} da sequencia de nurturing: {step['label']}",
                    "listing_id": ns.get("listing_id"),
                    "performed_by": "nurture_system",
                })

                # Actualizar sequencia
                steps_exec = list(ns.get("steps_executed") or [])
                steps_exec.append({
                    "step": step_idx,
                    "action": step["action"],
                    "executed_at": now_iso,
                })

                new_step = step_idx + 1
                update_data: Dict[str, Any] = {
                    "steps_executed": steps_exec,
                    "current_step": new_step,
                }

                # Proximo passo
                if new_step >= len(NURTURE_STEPS):
                    update_data["status"] = "completed"
                    update_data["next_action_at"] = None
                    completed += 1
                else:
                    next_step = NURTURE_STEPS[new_step]
                    next_at = now + timedelta(hours=next_step["delay_hours"])
                    update_data["next_action_at"] = next_at.isoformat()

                db.update("nurture_sequences", ns["id"], update_data)
                executed += 1

            except Exception as e:
                logger.error(f"Erro ao executar nurture {ns.get('id')}: {e}")
                errors += 1

        logger.info(
            f"Nurtures executados: {executed}, "
            f"completados: {completed}, erros: {errors}"
        )
        return {
            "executed": executed,
            "completed": completed,
            "errors": errors,
        }

    def get_nurture_status(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Retorna estado da sequencia de nurturing activa do lead."""
        rows = db.list_rows(
            "nurture_sequences",
            filters=f"lead_id=eq.{lead_id}",
            order="created_at.desc",
            limit=1,
        )
        if not rows:
            return None
        return _nurture_to_dict(rows[0])

    def pause_nurture(self, lead_id: str) -> Dict[str, Any]:
        """Pausa a sequencia de nurturing activa do lead."""
        rows = db.list_rows(
            "nurture_sequences",
            filters=f"lead_id=eq.{lead_id}&status=eq.active",
            limit=1,
        )
        if not rows:
            raise ValueError(
                f"Nenhum nurture activo para lead {lead_id}"
            )
        ns = db.update("nurture_sequences", rows[0]["id"], {"status": "paused"})
        logger.info(f"Nurture pausado para lead {lead_id}")
        return _nurture_to_dict(ns)

    def resume_nurture(self, lead_id: str) -> Dict[str, Any]:
        """Retoma a sequencia de nurturing pausada do lead."""
        rows = db.list_rows(
            "nurture_sequences",
            filters=f"lead_id=eq.{lead_id}&status=eq.paused",
            limit=1,
        )
        if not rows:
            raise ValueError(
                f"Nenhum nurture pausado para lead {lead_id}"
            )

        ns = rows[0]
        update_data: Dict[str, Any] = {"status": "active"}

        # Recalcular next_action_at
        current_step = ns.get("current_step", 0)
        if current_step < len(NURTURE_STEPS):
            step = NURTURE_STEPS[current_step]
            next_at = datetime.utcnow() + timedelta(hours=step["delay_hours"])
            update_data["next_action_at"] = next_at.isoformat()

        ns = db.update("nurture_sequences", ns["id"], update_data)
        logger.info(f"Nurture retomado para lead {lead_id}")
        return _nurture_to_dict(ns)

    # ------------------------------------------------------------------
    # Analytics / Pipeline
    # ------------------------------------------------------------------

    def get_pipeline_summary(self) -> List[Dict[str, Any]]:
        """Retorna resumo do pipeline por estagio."""
        db.ensure_tenant()
        results = []
        for stage in ALL_STAGES:
            count = db._count("leads", f"stage=eq.{stage}")
            # Buscar leads do estagio para somar budget
            leads = db.list_rows(
                "leads",
                select="budget_max",
                filters=f"stage=eq.{stage}",
                limit=5000,
            )
            total_budget = sum(
                float(l.get("budget_max") or 0) for l in leads
            )
            results.append({
                "stage": stage,
                "count": count,
                "total_budget": total_budget,
            })
        return results

    def get_conversion_funnel(self) -> List[Dict[str, Any]]:
        """Retorna funil de conversao com contagens cumulativas."""
        db.ensure_tenant()
        funnel_stages = [
            "new", "contacted", "qualified", "visiting",
            "proposal", "negotiation", "won",
        ]
        # Total exclui lost
        total = db._count("leads", "stage=neq.lost")

        funnel = []
        for stage in funnel_stages:
            count = db._count("leads", f"stage=eq.{stage}")
            rate = (count / total * 100) if total > 0 else 0
            funnel.append({
                "stage": stage,
                "count": count,
                "percentage": round(rate, 1),
            })
        return funnel

    def get_source_breakdown(self) -> List[Dict[str, Any]]:
        """Retorna distribuicao de leads por fonte.

        Nota: como o PostgREST nao suporta GROUP BY directamente,
        fazemos a agregacao em Python.
        """
        db.ensure_tenant()
        leads = db.list_rows("leads", select="source", limit=5000)

        source_counts: Dict[str, int] = {}
        for lead in leads:
            src = lead.get("source") or "unknown"
            source_counts[src] = source_counts.get(src, 0) + 1

        # Ordenar por contagem desc
        sorted_sources = sorted(
            source_counts.items(), key=lambda x: x[1], reverse=True
        )
        return [{"source": s, "count": c} for s, c in sorted_sources]

    def get_grades_summary(self) -> Dict[str, int]:
        """Retorna contagem de leads por grade."""
        db.ensure_tenant()
        result = {}
        for grade in ("A", "B", "C", "D"):
            result[grade] = db._count("leads", f"grade=eq.{grade}")
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas globais de leads."""
        db.ensure_tenant()
        total = db._count("leads")

        # Por estagio
        by_stage = {}
        for stage in ALL_STAGES:
            by_stage[stage] = db._count("leads", f"stage=eq.{stage}")

        # Por grade
        by_grade = {}
        for grade in ("A", "B", "C", "D"):
            by_grade[grade] = db._count("leads", f"grade=eq.{grade}")

        # Por fonte (agregacao em Python)
        leads_source = db.list_rows("leads", select="source", limit=5000)
        by_source: Dict[str, int] = {}
        for lead in leads_source:
            src = lead.get("source") or "unknown"
            by_source[src] = by_source.get(src, 0) + 1

        # Score medio (agregar em Python)
        all_scores = db.list_rows("leads", select="score", limit=5000)
        scores = [l.get("score", 0) or 0 for l in all_scores]
        avg_score = sum(scores) / len(scores) if scores else 0

        # Conversao
        won = by_stage.get("won", 0)
        conversion_rate = (won / total * 100) if total > 0 else 0

        # Este mes vs mes passado
        now = datetime.utcnow()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 1:
            first_of_last_month = first_of_month.replace(
                year=now.year - 1, month=12
            )
        else:
            first_of_last_month = first_of_month.replace(
                month=now.month - 1
            )

        this_month = db._count(
            "leads",
            f"created_at=gte.{first_of_month.isoformat()}",
        )
        last_month = db._count(
            "leads",
            f"created_at=gte.{first_of_last_month.isoformat()}"
            f"&created_at=lt.{first_of_month.isoformat()}",
        )

        growth_rate = 0.0
        if last_month > 0:
            growth_rate = ((this_month - last_month) / last_month) * 100

        return {
            "total_leads": total,
            "by_stage": by_stage,
            "by_grade": by_grade,
            "by_source": by_source,
            "avg_score": round(float(avg_score), 1),
            "conversion_rate": round(conversion_rate, 1),
            "leads_this_month": this_month,
            "leads_last_month": last_month,
            "growth_rate": round(growth_rate, 1),
        }
