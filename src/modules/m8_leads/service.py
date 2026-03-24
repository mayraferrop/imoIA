"""Servico M8 — CRM de Leads.

Logica de negocio para gestao de leads: CRUD, scoring, matching,
nurturing automatico, integracao Habta, e analytics.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import func as sql_func, or_, select

from src.database.db import get_session
from src.database.models_v2 import (
    Deal,
    Lead,
    LeadInteraction,
    LeadListingMatch,
    Listing,
    NurtureSequence,
    Property,
    Tenant,
)

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


def _ensure_default_tenant(session: Any) -> str:
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
        logger.info("Tenant default criado (m8_leads)")

    return tenant.id


def _lead_to_dict(lead: Lead, interactions_count: int = 0) -> Dict[str, Any]:
    """Converte modelo Lead para dicionario."""
    return {
        "id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "budget_min": lead.budget_min,
        "budget_max": lead.budget_max,
        "preferred_typology": lead.preferred_typology,
        "preferred_locations": lead.preferred_locations or [],
        "preferred_features": lead.preferred_features or [],
        "timeline": lead.timeline,
        "financing": lead.financing,
        "buyer_type": lead.buyer_type,
        "stage": lead.stage,
        "stage_changed_at": lead.stage_changed_at.isoformat() if lead.stage_changed_at else None,
        "score": lead.score,
        "score_breakdown": lead.score_breakdown or {},
        "grade": lead.grade,
        "source": lead.source,
        "source_listing_id": lead.source_listing_id,
        "source_campaign": lead.source_campaign,
        "utm_source": lead.utm_source,
        "utm_medium": lead.utm_medium,
        "utm_campaign": lead.utm_campaign,
        "habta_contact_id": lead.habta_contact_id,
        "deal_id": lead.deal_id,
        "assigned_to": lead.assigned_to,
        "notes": lead.notes,
        "tags": lead.tags or [],
        "interactions_count": interactions_count,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


def _interaction_to_dict(interaction: LeadInteraction) -> Dict[str, Any]:
    """Converte modelo LeadInteraction para dicionario."""
    return {
        "id": interaction.id,
        "lead_id": interaction.lead_id,
        "type": interaction.type,
        "channel": interaction.channel,
        "direction": interaction.direction,
        "subject": interaction.subject,
        "content": interaction.content,
        "listing_id": interaction.listing_id,
        "metadata": interaction.metadata_ or {},
        "performed_by": interaction.performed_by,
        "created_at": interaction.created_at.isoformat() if interaction.created_at else None,
    }


def _match_to_dict(match: LeadListingMatch, listing_info: Optional[Dict] = None) -> Dict[str, Any]:
    """Converte modelo LeadListingMatch para dicionario."""
    return {
        "id": match.id,
        "lead_id": match.lead_id,
        "listing_id": match.listing_id,
        "match_score": match.match_score,
        "match_reasons": match.match_reasons or [],
        "status": match.status,
        "sent_at": match.sent_at.isoformat() if match.sent_at else None,
        "response_at": match.response_at.isoformat() if match.response_at else None,
        "listing_info": listing_info,
        "created_at": match.created_at.isoformat() if match.created_at else None,
    }


def _nurture_to_dict(ns: NurtureSequence) -> Dict[str, Any]:
    """Converte modelo NurtureSequence para dicionario."""
    return {
        "id": ns.id,
        "lead_id": ns.lead_id,
        "listing_id": ns.listing_id,
        "sequence_type": ns.sequence_type,
        "current_step": ns.current_step,
        "status": ns.status,
        "next_action_at": ns.next_action_at.isoformat() if ns.next_action_at else None,
        "steps_executed": ns.steps_executed or [],
        "created_at": ns.created_at.isoformat() if ns.created_at else None,
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
        with get_session() as session:
            tenant_id = _ensure_default_tenant(session)
            lead = Lead(
                id=str(uuid4()),
                tenant_id=tenant_id,
                name=data["name"],
                email=data.get("email"),
                phone=data.get("phone"),
                budget_min=data.get("budget_min"),
                budget_max=data.get("budget_max"),
                preferred_typology=data.get("preferred_typology"),
                preferred_locations=data.get("preferred_locations", []),
                preferred_features=data.get("preferred_features", []),
                timeline=data.get("timeline"),
                financing=data.get("financing"),
                buyer_type=data.get("buyer_type"),
                stage="new",
                stage_changed_at=datetime.utcnow(),
                score=0,
                score_breakdown={},
                grade="D",
                source=data.get("source"),
                source_listing_id=data.get("source_listing_id"),
                source_campaign=data.get("source_campaign"),
                utm_source=data.get("utm_source"),
                utm_medium=data.get("utm_medium"),
                utm_campaign=data.get("utm_campaign"),
                habta_contact_id=data.get("habta_contact_id"),
                deal_id=data.get("deal_id"),
                assigned_to=data.get("assigned_to"),
                notes=data.get("notes"),
                tags=data.get("tags", []),
            )
            session.add(lead)
            session.flush()
            logger.info(f"Lead criado: {lead.id} ({lead.name})")

            # Calcular score automaticamente
            result = self._do_recalculate_score(session, lead)
            return result

    def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Obtem um lead por ID."""
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            if lead is None:
                return None
            count = session.execute(
                select(sql_func.count(LeadInteraction.id)).where(
                    LeadInteraction.lead_id == lead_id
                )
            ).scalar() or 0
            return _lead_to_dict(lead, count)

    def update_lead(self, lead_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Actualiza um lead."""
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
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
            for field in updatable:
                if field in data and data[field] is not None:
                    setattr(lead, field, data[field])

            session.flush()
            result = self._do_recalculate_score(session, lead)
            logger.info(f"Lead actualizado: {lead_id}")
            return result

    def delete_lead(self, lead_id: str) -> bool:
        """Remove um lead."""
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            if lead is None:
                return False

            # Remover nurture sequences
            session.execute(
                select(NurtureSequence).where(NurtureSequence.lead_id == lead_id)
            )
            nurtures = session.execute(
                select(NurtureSequence).where(NurtureSequence.lead_id == lead_id)
            ).scalars().all()
            for ns in nurtures:
                session.delete(ns)

            # Remover matches
            matches = session.execute(
                select(LeadListingMatch).where(LeadListingMatch.lead_id == lead_id)
            ).scalars().all()
            for m in matches:
                session.delete(m)

            session.delete(lead)
            session.flush()
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
        with get_session() as session:
            _ensure_default_tenant(session)
            query = select(Lead)

            if stage:
                query = query.where(Lead.stage == stage)
            if grade:
                query = query.where(Lead.grade == grade)
            if source:
                query = query.where(Lead.source == source)
            if search:
                pattern = f"%{search}%"
                query = query.where(
                    or_(
                        Lead.name.ilike(pattern),
                        Lead.email.ilike(pattern),
                        Lead.phone.ilike(pattern),
                    )
                )

            # Count total
            count_query = select(sql_func.count()).select_from(query.subquery())
            total = session.execute(count_query).scalar() or 0

            # Sort
            sort_map = {
                "created_at": Lead.created_at.desc(),
                "score": Lead.score.desc(),
                "name": Lead.name.asc(),
                "stage": Lead.stage.asc(),
                "updated_at": Lead.updated_at.desc(),
            }
            order = sort_map.get(sort_by, Lead.created_at.desc())
            query = query.order_by(order).limit(limit).offset(offset)

            leads = session.execute(query).scalars().all()
            items = []
            for lead in leads:
                count = session.execute(
                    select(sql_func.count(LeadInteraction.id)).where(
                        LeadInteraction.lead_id == lead.id
                    )
                ).scalar() or 0
                items.append(_lead_to_dict(lead, count))

            return {"items": items, "total": total, "limit": limit, "offset": offset}

    # ------------------------------------------------------------------
    # Stage Management
    # ------------------------------------------------------------------

    def advance_stage(self, lead_id: str, new_stage: str) -> Dict[str, Any]:
        """Avanca o estagio do lead com validacao de transicao."""
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} nao encontrado")

            current = lead.stage
            allowed = STAGE_TRANSITIONS.get(current, [])
            if new_stage not in allowed:
                raise ValueError(
                    f"Transicao invalida: {current} -> {new_stage}. "
                    f"Permitidas: {allowed}"
                )

            lead.stage = new_stage
            lead.stage_changed_at = datetime.utcnow()
            session.flush()

            # Registar interaccao automatica
            interaction = LeadInteraction(
                id=str(uuid4()),
                tenant_id=lead.tenant_id,
                lead_id=lead.id,
                type="stage_change",
                channel="system",
                direction="internal",
                subject=f"Estagio alterado: {current} -> {new_stage}",
                content=f"Lead movido de '{current}' para '{new_stage}'",
                performed_by="system",
            )
            session.add(interaction)

            # Hook M4: ao chegar a 'proposal', pode criar proposta no deal
            if new_stage == "proposal" and lead.deal_id:
                logger.info(
                    f"Lead {lead_id} chegou a 'proposal' — "
                    f"hook M4 para deal {lead.deal_id}"
                )

            session.flush()
            count = session.execute(
                select(sql_func.count(LeadInteraction.id)).where(
                    LeadInteraction.lead_id == lead_id
                )
            ).scalar() or 0
            logger.info(f"Lead {lead_id}: {current} -> {new_stage}")
            return _lead_to_dict(lead, count)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def recalculate_score(self, lead_id: str) -> Dict[str, Any]:
        """Recalcula o score de um lead."""
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} nao encontrado")
            return self._do_recalculate_score(session, lead)

    def _do_recalculate_score(self, session: Any, lead: Lead) -> Dict[str, Any]:
        """Calcula e persiste o score do lead (4 componentes)."""
        # 1. Demografico (0-30): budget, email, telefone, tipologia
        demographic = 0
        if lead.budget_min is not None or lead.budget_max is not None:
            demographic += 10
        if lead.email:
            demographic += 5
        if lead.phone:
            demographic += 5
        if lead.preferred_typology:
            demographic += 5
        if lead.preferred_locations and len(lead.preferred_locations) > 0:
            demographic += 5
        demographic = min(demographic, 30)

        # 2. Comportamental (0-40): interaccoes, visitas, propostas
        interactions_count = session.execute(
            select(sql_func.count(LeadInteraction.id)).where(
                LeadInteraction.lead_id == lead.id
            )
        ).scalar() or 0

        behavioral = 0
        if interactions_count >= 1:
            behavioral += 10
        if interactions_count >= 3:
            behavioral += 10
        if interactions_count >= 5:
            behavioral += 10

        # Bonus por tipos especificos
        visit_count = session.execute(
            select(sql_func.count(LeadInteraction.id)).where(
                LeadInteraction.lead_id == lead.id,
                LeadInteraction.type == "visit",
            )
        ).scalar() or 0
        if visit_count >= 1:
            behavioral += 10
        behavioral = min(behavioral, 40)

        # 3. Comunicacao (0-20): ultimo contacto recente, respostas
        communication = 0
        last_interaction = session.execute(
            select(LeadInteraction)
            .where(LeadInteraction.lead_id == lead.id)
            .order_by(LeadInteraction.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if last_interaction and last_interaction.created_at:
            days_since = (datetime.utcnow() - last_interaction.created_at).days
            if days_since <= 3:
                communication += 15
            elif days_since <= 7:
                communication += 10
            elif days_since <= 14:
                communication += 5

        # Bonus por interaccoes recebidas (inbound)
        inbound_count = session.execute(
            select(sql_func.count(LeadInteraction.id)).where(
                LeadInteraction.lead_id == lead.id,
                LeadInteraction.direction == "inbound",
            )
        ).scalar() or 0
        if inbound_count >= 1:
            communication += 5
        communication = min(communication, 20)

        # 4. Urgencia (0-10): timeline, financing, estagio avancado
        urgency = 0
        if lead.timeline in ("imediato", "immediate", "1_month"):
            urgency += 5
        elif lead.timeline in ("3_months", "3_meses"):
            urgency += 3
        if lead.financing in ("pre_approved", "pre_aprovado", "cash"):
            urgency += 3
        if lead.stage in ("visiting", "proposal", "negotiation"):
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

        lead.score = total
        lead.score_breakdown = breakdown
        lead.grade = grade
        session.flush()

        count = session.execute(
            select(sql_func.count(LeadInteraction.id)).where(
                LeadInteraction.lead_id == lead.id
            )
        ).scalar() or 0

        logger.debug(
            f"Score recalculado para lead {lead.id}: "
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
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} nao encontrado")

            interaction = LeadInteraction(
                id=str(uuid4()),
                tenant_id=lead.tenant_id,
                lead_id=lead.id,
                type=data["type"],
                channel=data.get("channel"),
                direction=data.get("direction"),
                subject=data.get("subject"),
                content=data.get("content"),
                listing_id=data.get("listing_id"),
                metadata_=data.get("metadata_") or data.get("metadata", {}),
                performed_by=data.get("performed_by"),
            )
            session.add(interaction)
            session.flush()

            # Recalcular score apos nova interaccao
            self._do_recalculate_score(session, lead)

            logger.info(
                f"Interaccao registada: {interaction.type} "
                f"para lead {lead_id}"
            )
            return _interaction_to_dict(interaction)

    def list_interactions(
        self, lead_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """Lista interaccoes de um lead."""
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} nao encontrado")

            total = session.execute(
                select(sql_func.count(LeadInteraction.id)).where(
                    LeadInteraction.lead_id == lead_id
                )
            ).scalar() or 0

            interactions = session.execute(
                select(LeadInteraction)
                .where(LeadInteraction.lead_id == lead_id)
                .order_by(LeadInteraction.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).scalars().all()

            return {
                "items": [_interaction_to_dict(i) for i in interactions],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def get_timeline(self, lead_id: str) -> List[Dict[str, Any]]:
        """Retorna timeline cronologica do lead (interaccoes + mudancas de estagio)."""
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} nao encontrado")

            interactions = session.execute(
                select(LeadInteraction)
                .where(LeadInteraction.lead_id == lead_id)
                .order_by(LeadInteraction.created_at.asc())
            ).scalars().all()

            timeline = []
            for i in interactions:
                timeline.append({
                    "timestamp": i.created_at.isoformat() if i.created_at else None,
                    "type": i.type,
                    "channel": i.channel,
                    "direction": i.direction,
                    "subject": i.subject,
                    "content": i.content,
                    "performed_by": i.performed_by,
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
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} nao encontrado")

            # Buscar listings activas com deal e property
            listings_query = (
                select(Listing, Deal, Property)
                .join(Deal, Listing.deal_id == Deal.id)
                .join(Property, Deal.property_id == Property.id)
                .where(Listing.status.in_(["active", "published", "draft"]))
            )
            rows = session.execute(listings_query).all()

            matches = []
            for listing, deal, prop in rows:
                score = 0.0
                reasons = []

                # Budget match (40%)
                if lead.budget_min is not None or lead.budget_max is not None:
                    price = listing.listing_price
                    budget_ok = True
                    if lead.budget_min is not None and price < lead.budget_min:
                        budget_ok = False
                    if lead.budget_max is not None and price > lead.budget_max:
                        budget_ok = False
                    if budget_ok:
                        score += 40
                        reasons.append(
                            f"Preco {price:.0f}EUR dentro do orcamento"
                        )
                    else:
                        # Partial score if close
                        if lead.budget_max and price <= lead.budget_max * 1.1:
                            score += 15
                            reasons.append(
                                f"Preco {price:.0f}EUR proximo do orcamento"
                            )

                # Location match (35%)
                if lead.preferred_locations:
                    locations_lower = [
                        loc.lower() for loc in lead.preferred_locations
                    ]
                    prop_locations = [
                        (prop.municipality or "").lower(),
                        (prop.district or "").lower(),
                        (prop.parish or "").lower(),
                    ]
                    for loc in locations_lower:
                        if loc and any(loc in pl for pl in prop_locations if pl):
                            score += 35
                            reasons.append(
                                f"Localizacao compativel: {prop.municipality}"
                            )
                            break

                # Typology match (25%)
                if lead.preferred_typology:
                    lead_typo = lead.preferred_typology.upper()
                    prop_typo = (prop.typology or "").upper()
                    if lead_typo == prop_typo:
                        score += 25
                        reasons.append(f"Tipologia compativel: {prop.typology}")
                    elif lead_typo and prop_typo:
                        # Partial: T2 lead might accept T3
                        try:
                            lead_rooms = int(lead_typo.replace("T", ""))
                            prop_rooms = int(prop_typo.replace("T", ""))
                            if abs(lead_rooms - prop_rooms) == 1:
                                score += 10
                                reasons.append(
                                    f"Tipologia proxima: {prop.typology}"
                                )
                        except (ValueError, AttributeError):
                            pass

                if score > 0:
                    # Verificar se ja existe match
                    existing = session.execute(
                        select(LeadListingMatch).where(
                            LeadListingMatch.lead_id == lead_id,
                            LeadListingMatch.listing_id == listing.id,
                        )
                    ).scalar_one_or_none()

                    if existing:
                        existing.match_score = score
                        existing.match_reasons = reasons
                        match_obj = existing
                    else:
                        match_obj = LeadListingMatch(
                            id=str(uuid4()),
                            tenant_id=lead.tenant_id,
                            lead_id=lead.id,
                            listing_id=listing.id,
                            match_score=score,
                            match_reasons=reasons,
                            status="suggested",
                        )
                        session.add(match_obj)

                    session.flush()

                    listing_info = {
                        "listing_price": listing.listing_price,
                        "listing_type": listing.listing_type,
                        "municipality": prop.municipality,
                        "district": prop.district,
                        "typology": prop.typology,
                        "bedrooms": prop.bedrooms,
                        "gross_area_m2": prop.gross_area_m2,
                    }
                    matches.append(_match_to_dict(match_obj, listing_info))

            # Ordenar por score desc
            matches.sort(key=lambda x: x["match_score"], reverse=True)
            logger.info(f"Encontrados {len(matches)} matches para lead {lead_id}")
            return matches

    def send_listing_to_lead(
        self, lead_id: str, listing_id: str
    ) -> Dict[str, Any]:
        """Marca um match como enviado ao lead."""
        with get_session() as session:
            match = session.execute(
                select(LeadListingMatch).where(
                    LeadListingMatch.lead_id == lead_id,
                    LeadListingMatch.listing_id == listing_id,
                )
            ).scalar_one_or_none()

            if match is None:
                # Criar match se nao existe
                lead = session.execute(
                    select(Lead).where(Lead.id == lead_id)
                ).scalar_one_or_none()
                if lead is None:
                    raise ValueError(f"Lead {lead_id} nao encontrado")
                match = LeadListingMatch(
                    id=str(uuid4()),
                    tenant_id=lead.tenant_id,
                    lead_id=lead_id,
                    listing_id=listing_id,
                    match_score=0,
                    match_reasons=["Envio manual"],
                    status="sent",
                    sent_at=datetime.utcnow(),
                )
                session.add(match)
            else:
                match.status = "sent"
                match.sent_at = datetime.utcnow()

            # Registar interaccao
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            interaction = LeadInteraction(
                id=str(uuid4()),
                tenant_id=lead.tenant_id,
                lead_id=lead_id,
                type="listing_sent",
                channel="email",
                direction="outbound",
                subject=f"Listing {listing_id} enviada",
                listing_id=listing_id,
                performed_by="system",
            )
            session.add(interaction)
            session.flush()

            logger.info(f"Listing {listing_id} enviada para lead {lead_id}")
            return _match_to_dict(match)

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

        with get_session() as session:
            tenant_id = _ensure_default_tenant(session)

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

                    existing = session.execute(
                        select(Lead).where(
                            Lead.habta_contact_id == habta_id
                        )
                    ).scalar_one_or_none()

                    if existing:
                        existing.name = contact.get("name", existing.name)
                        existing.email = contact.get("email", existing.email)
                        existing.phone = contact.get("phone", existing.phone)
                        if budget_min is not None:
                            existing.budget_min = budget_min
                        if budget_max is not None:
                            existing.budget_max = budget_max
                        if prefs.get("typology"):
                            existing.preferred_typology = prefs["typology"]
                        if prefs.get("locations"):
                            existing.preferred_locations = prefs["locations"]
                        updated += 1
                    else:
                        lead = Lead(
                            id=str(uuid4()),
                            tenant_id=tenant_id,
                            name=contact.get("name", "Sem nome"),
                            email=contact.get("email"),
                            phone=contact.get("phone"),
                            budget_min=budget_min,
                            budget_max=budget_max,
                            preferred_typology=prefs.get("typology"),
                            preferred_locations=prefs.get("locations", []),
                            preferred_features=prefs.get("features", []),
                            source=contact.get("source", "habta"),
                            habta_contact_id=habta_id,
                            stage="new",
                            stage_changed_at=datetime.utcnow(),
                            score=0,
                            grade="D",
                        )
                        session.add(lead)
                        created += 1

                except Exception as e:
                    logger.error(f"Erro ao importar contacto Habta: {e}")
                    errors += 1

            session.flush()

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
        with get_session() as session:
            lead = session.execute(
                select(Lead).where(Lead.id == lead_id)
            ).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} nao encontrado")

            # Verificar se ja tem nurture activo
            existing = session.execute(
                select(NurtureSequence).where(
                    NurtureSequence.lead_id == lead_id,
                    NurtureSequence.status == "active",
                )
            ).scalar_one_or_none()
            if existing:
                raise ValueError(
                    f"Lead {lead_id} ja tem nurture activo: {existing.id}"
                )

            now = datetime.utcnow()
            ns = NurtureSequence(
                id=str(uuid4()),
                tenant_id=lead.tenant_id,
                lead_id=lead_id,
                listing_id=listing_id,
                sequence_type=sequence_type,
                current_step=0,
                status="active",
                next_action_at=now,
                steps_executed=[],
            )
            session.add(ns)
            session.flush()

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

        with get_session() as session:
            now = datetime.utcnow()
            pending = session.execute(
                select(NurtureSequence).where(
                    NurtureSequence.status == "active",
                    NurtureSequence.next_action_at <= now,
                )
            ).scalars().all()

            for ns in pending:
                try:
                    step_idx = ns.current_step
                    if step_idx >= len(NURTURE_STEPS):
                        ns.status = "completed"
                        completed += 1
                        continue

                    step = NURTURE_STEPS[step_idx]
                    # Registar interaccao
                    interaction = LeadInteraction(
                        id=str(uuid4()),
                        tenant_id=ns.tenant_id,
                        lead_id=ns.lead_id,
                        type=f"nurture_{step['action']}",
                        channel="system",
                        direction="outbound",
                        subject=step["label"],
                        content=f"Passo {step_idx} da sequencia de nurturing: {step['label']}",
                        listing_id=ns.listing_id,
                        performed_by="nurture_system",
                    )
                    session.add(interaction)

                    # Actualizar sequencia
                    steps_exec = list(ns.steps_executed or [])
                    steps_exec.append({
                        "step": step_idx,
                        "action": step["action"],
                        "executed_at": now.isoformat(),
                    })
                    ns.steps_executed = steps_exec
                    ns.current_step = step_idx + 1

                    # Proximo passo
                    if ns.current_step >= len(NURTURE_STEPS):
                        ns.status = "completed"
                        ns.next_action_at = None
                        completed += 1
                    else:
                        next_step = NURTURE_STEPS[ns.current_step]
                        ns.next_action_at = now + timedelta(
                            hours=next_step["delay_hours"]
                        )

                    executed += 1

                except Exception as e:
                    logger.error(f"Erro ao executar nurture {ns.id}: {e}")
                    errors += 1

            session.flush()

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
        with get_session() as session:
            ns = session.execute(
                select(NurtureSequence)
                .where(NurtureSequence.lead_id == lead_id)
                .order_by(NurtureSequence.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if ns is None:
                return None
            return _nurture_to_dict(ns)

    def pause_nurture(self, lead_id: str) -> Dict[str, Any]:
        """Pausa a sequencia de nurturing activa do lead."""
        with get_session() as session:
            ns = session.execute(
                select(NurtureSequence).where(
                    NurtureSequence.lead_id == lead_id,
                    NurtureSequence.status == "active",
                )
            ).scalar_one_or_none()
            if ns is None:
                raise ValueError(
                    f"Nenhum nurture activo para lead {lead_id}"
                )
            ns.status = "paused"
            session.flush()
            logger.info(f"Nurture pausado para lead {lead_id}")
            return _nurture_to_dict(ns)

    def resume_nurture(self, lead_id: str) -> Dict[str, Any]:
        """Retoma a sequencia de nurturing pausada do lead."""
        with get_session() as session:
            ns = session.execute(
                select(NurtureSequence).where(
                    NurtureSequence.lead_id == lead_id,
                    NurtureSequence.status == "paused",
                )
            ).scalar_one_or_none()
            if ns is None:
                raise ValueError(
                    f"Nenhum nurture pausado para lead {lead_id}"
                )
            ns.status = "active"
            # Recalcular next_action_at
            if ns.current_step < len(NURTURE_STEPS):
                step = NURTURE_STEPS[ns.current_step]
                ns.next_action_at = datetime.utcnow() + timedelta(
                    hours=step["delay_hours"]
                )
            session.flush()
            logger.info(f"Nurture retomado para lead {lead_id}")
            return _nurture_to_dict(ns)

    # ------------------------------------------------------------------
    # Analytics / Pipeline
    # ------------------------------------------------------------------

    def get_pipeline_summary(self) -> List[Dict[str, Any]]:
        """Retorna resumo do pipeline por estagio."""
        with get_session() as session:
            _ensure_default_tenant(session)
            results = []
            for stage in ALL_STAGES:
                count = session.execute(
                    select(sql_func.count(Lead.id)).where(Lead.stage == stage)
                ).scalar() or 0
                total_budget = session.execute(
                    select(sql_func.coalesce(sql_func.sum(Lead.budget_max), 0)).where(
                        Lead.stage == stage
                    )
                ).scalar() or 0
                results.append({
                    "stage": stage,
                    "count": count,
                    "total_budget": float(total_budget),
                })
            return results

    def get_conversion_funnel(self) -> List[Dict[str, Any]]:
        """Retorna funil de conversao com contagens cumulativas."""
        with get_session() as session:
            _ensure_default_tenant(session)
            funnel_stages = [
                "new", "contacted", "qualified", "visiting",
                "proposal", "negotiation", "won",
            ]
            funnel = []
            total = session.execute(
                select(sql_func.count(Lead.id)).where(
                    Lead.stage != "lost"
                )
            ).scalar() or 0

            for stage in funnel_stages:
                count = session.execute(
                    select(sql_func.count(Lead.id)).where(Lead.stage == stage)
                ).scalar() or 0
                rate = (count / total * 100) if total > 0 else 0
                funnel.append({
                    "stage": stage,
                    "count": count,
                    "percentage": round(rate, 1),
                })
            return funnel

    def get_source_breakdown(self) -> List[Dict[str, Any]]:
        """Retorna distribuicao de leads por fonte."""
        with get_session() as session:
            _ensure_default_tenant(session)
            rows = session.execute(
                select(
                    Lead.source,
                    sql_func.count(Lead.id).label("count"),
                )
                .group_by(Lead.source)
                .order_by(sql_func.count(Lead.id).desc())
            ).all()

            return [
                {"source": row[0] or "unknown", "count": row[1]}
                for row in rows
            ]

    def get_grades_summary(self) -> Dict[str, int]:
        """Retorna contagem de leads por grade."""
        with get_session() as session:
            _ensure_default_tenant(session)
            result = {}
            for grade in ("A", "B", "C", "D"):
                count = session.execute(
                    select(sql_func.count(Lead.id)).where(Lead.grade == grade)
                ).scalar() or 0
                result[grade] = count
            return result

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas globais de leads."""
        with get_session() as session:
            _ensure_default_tenant(session)
            total = session.execute(
                select(sql_func.count(Lead.id))
            ).scalar() or 0

            # Por estagio
            by_stage = {}
            for stage in ALL_STAGES:
                count = session.execute(
                    select(sql_func.count(Lead.id)).where(Lead.stage == stage)
                ).scalar() or 0
                by_stage[stage] = count

            # Por grade
            by_grade = {}
            for grade in ("A", "B", "C", "D"):
                count = session.execute(
                    select(sql_func.count(Lead.id)).where(Lead.grade == grade)
                ).scalar() or 0
                by_grade[grade] = count

            # Por fonte
            by_source = {}
            rows = session.execute(
                select(Lead.source, sql_func.count(Lead.id))
                .group_by(Lead.source)
            ).all()
            for row in rows:
                by_source[row[0] or "unknown"] = row[1]

            # Score medio
            avg_score = session.execute(
                select(sql_func.avg(Lead.score))
            ).scalar() or 0

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

            this_month = session.execute(
                select(sql_func.count(Lead.id)).where(
                    Lead.created_at >= first_of_month
                )
            ).scalar() or 0

            last_month = session.execute(
                select(sql_func.count(Lead.id)).where(
                    Lead.created_at >= first_of_last_month,
                    Lead.created_at < first_of_month,
                )
            ).scalar() or 0

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
