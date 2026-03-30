"""Pipeline orquestrador do ImoIA.

Executa as 5 etapas de processamento:
1. Buscar mensagens não lidas de todos os grupos ativos
2. Filtrar ruído (stickers, bom dia, mídia sem texto, mensagens curtas)
3. Classificar com IA (batches de 15-20)
4. Enriquecer com dados de mercado para confidence >= 0.6
5. Finalizar (arquivar grupos, atualizar last_processed_at, logar resumo)
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select

from src.config import get_settings
from src.database.db import get_session, init_db
from src.database.models import Group, MarketData, Message, Opportunity
from src.modules.m1_ingestor.whatsapp_client import WhatsAppClient


@dataclass
class PipelineResult:
    """Resultado da execução do pipeline.

    Attributes:
        messages_fetched: Total de mensagens buscadas.
        opportunities_found: Total de oportunidades detetadas.
        groups_processed: Total de grupos processados.
        errors: Lista de erros ocorridos.
    """

    messages_fetched: int
    opportunities_found: int
    groups_processed: int
    errors: List[str]


def _get_whatsapp_client() -> WhatsAppClient:
    """Cria e retorna o cliente WhatsApp."""
    return WhatsAppClient()


def _get_classifier(tenant_id: str | None = None) -> Any:
    """Retorna o classificador de oportunidades.

    Args:
        tenant_id: ID do tenant para carregar estratégia personalizada.
    """
    try:
        from src.modules.m1_ingestor.classifier import OpportunityClassifier
        return OpportunityClassifier(tenant_id=tenant_id)
    except (ImportError, AttributeError):
        logger.warning("OpportunityClassifier não disponível — a usar mock")
        return _MockClassifier()


def _get_market_services() -> Dict[str, Any]:
    """Retorna os servicos de mercado disponiveis.

    Returns:
        Dict com clientes: ine, casafari, infocasa, sir, idealista, yield_calculator.
    """
    services: Dict[str, Any] = {}

    # INE (sempre disponivel — API publica)
    try:
        from src.modules.m2_market.ine_client import INEClient
        services["ine"] = INEClient()
    except (ImportError, AttributeError):
        services["ine"] = _MockINE()

    # Casafari
    try:
        from src.modules.m1_ingestor.casafari_compat import CasafariClient
        client = CasafariClient()
        services["casafari"] = client if client.is_configured else None
    except (ImportError, AttributeError):
        services["casafari"] = None

    # Infocasa — desativado (nao tem API publica)
    services["infocasa"] = None

    # SIR / Confidencial Imobiliario
    try:
        from src.modules.m1_ingestor.sir_client import SIRClient
        client = SIRClient()
        services["sir"] = client if client.is_configured else None
    except (ImportError, AttributeError):
        services["sir"] = None

    # Idealista (opcional)
    try:
        from src.modules.m1_ingestor.idealista_client import IdealistaClient
        services["idealista"] = IdealistaClient()
    except (ImportError, AttributeError):
        services["idealista"] = _MockIdealista()

    # Yield calculator
    try:
        from src.modules.m1_ingestor.yield_calculator import YieldCalculator
        services["yield_calculator"] = YieldCalculator()
    except (ImportError, AttributeError):
        services["yield_calculator"] = _MockYieldCalculator()

    configured = [k for k, v in services.items() if v is not None]
    logger.info(f"Servicos de mercado disponiveis: {', '.join(configured)}")

    return services


# --- Mocks inline (fallback quando módulos não estão disponíveis) ---


class _MockOpportunityResult:
    """Mock de OpportunityResult para quando o classificador não está disponível."""

    def __init__(self, index: int) -> None:
        self.message_index = index
        self.is_opportunity = False
        self.confidence = 0.0
        self.opportunity_type = None
        self.property_type = None
        self.location = None
        self.parish = None
        self.municipality = None
        self.district = None
        self.price = None
        self.area_m2 = None
        self.bedrooms = None
        self.reasoning = "Classificador não disponível"


class _MockClassifier:
    """Mock do OpportunityClassifier."""

    def classify_batch(self, messages: List[Dict[str, Any]]) -> List[_MockOpportunityResult]:
        """Retorna todos como não-oportunidade."""
        return [_MockOpportunityResult(i) for i in range(len(messages))]


class _MockINE:
    """Mock do INEClient."""

    def get_median_price(self, municipality: str) -> Optional[Dict[str, Any]]:
        """Retorna None (sem dados)."""
        return None


class _MockIdealista:
    """Mock do IdealistaClient."""

    def search_comparables(
        self, location: str, property_type: str, area_m2: float
    ) -> Optional[Dict[str, Any]]:
        """Retorna None (sem dados)."""
        return None


class _MockYieldCalculator:
    """Mock do YieldCalculator."""

    def calculate(
        self, purchase_price: float, monthly_rent: float, municipality: str
    ) -> None:
        """Retorna None (sem dados)."""
        return None


# --- Etapas do pipeline ---


def _filter_noise(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtra mensagens de ruído.

    Remove:
    - Mensagens não-texto (stickers, media, etc.)
    - Mensagens com menos de 15 caracteres
    - Mensagens com padrões de ruído (bom dia, parabéns, etc.)

    Args:
        messages: Lista de mensagens a filtrar.

    Returns:
        Lista de mensagens filtradas.
    """
    settings = get_settings()
    filtered: List[Dict[str, Any]] = []

    for msg in messages:
        # Remover mensagens não-texto
        if msg.get("message_type") != "text":
            continue

        content = msg.get("content", "")

        # Remover mensagens curtas
        if len(content) < settings.min_message_length:
            continue

        # Remover padrões de ruído — só descarta mensagens curtas (< 80 chars)
        # que contenham padrões de ruído. Mensagens longas com saudações no
        # início são oportunidades legítimas e devem passar para a IA.
        content_lower = content.lower()
        if len(content) < 80:
            is_noise = any(
                pattern in content_lower for pattern in settings.noise_patterns
            )
            if is_noise:
                continue

        filtered.append(msg)

    removed = len(messages) - len(filtered)
    if removed > 0:
        logger.info(f"Filtro de ruído: {removed} mensagens removidas, {len(filtered)} mantidas")

    return filtered


def _prepare_for_classifier(
    messages: List[Dict[str, Any]],
    group_name: str,
) -> List[Dict[str, Any]]:
    """Transforma mensagens do pipeline para o formato do classificador.

    O OpportunityClassifier espera dicts com keys 'index', 'text', 'group'.

    Args:
        messages: Mensagens no formato do pipeline.
        group_name: Nome do grupo de WhatsApp.

    Returns:
        Mensagens no formato do classificador.
    """
    return [
        {
            "index": i,
            "text": msg.get("content", ""),
            "group": group_name,
        }
        for i, msg in enumerate(messages)
    ]


def _classify_messages(
    messages: List[Dict[str, Any]],
    classifier: Any,
    batch_size: int,
    group_name: str = "Desconhecido",
) -> List[Any]:
    """Classifica mensagens com IA em batches.

    Args:
        messages: Mensagens filtradas para classificar.
        classifier: Instância do OpportunityClassifier.
        batch_size: Tamanho de cada batch.
        group_name: Nome do grupo para contexto do classificador.

    Returns:
        Lista de OpportunityResult.
    """
    classifier_messages = _prepare_for_classifier(messages, group_name)
    all_results: List[Any] = []

    for i in range(0, len(classifier_messages), batch_size):
        batch = classifier_messages[i : i + batch_size]
        logger.info(f"A classificar batch {i // batch_size + 1} ({len(batch)} mensagens)")

        try:
            results = classifier.classify_batch(batch)
            all_results.extend(results)
        except Exception as e:
            logger.error(f"Erro ao classificar batch: {e}")
            for j in range(len(batch)):
                all_results.append(_MockOpportunityResult(i + j))

    return all_results


def _enrich_opportunity(
    opportunity_result: Any,
    services: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Enriquece uma oportunidade com dados de mercado.

    Workflow do utilizador:
    1. Casafari + Infocasa — buscar comparaveis por localizacao e caracteristicas
    2. INE — baseline de precos medianos nacionais
    3. SIR — validar com transacoes reais (dentro/acima/abaixo do mercado)
    4. Idealista — listings ativos (opcional)
    5. Yield — calcular rentabilidade estimada

    Apenas enriquece oportunidades com confidence >= 0.6.

    Args:
        opportunity_result: Resultado da classificacao IA.
        services: Dict com clientes de mercado.

    Returns:
        Dicionario com dados de mercado ou None se nao aplicavel.
    """
    settings = get_settings()

    if not opportunity_result.is_opportunity:
        return None
    if opportunity_result.confidence < settings.min_confidence:
        return None

    market_data: Dict[str, Any] = {}
    municipality = opportunity_result.municipality
    property_type = opportunity_result.property_type
    bedrooms = opportunity_result.bedrooms
    area_m2 = opportunity_result.area_m2
    price = opportunity_result.price

    # --- Etapa 1: Casafari (comparaveis) ---
    casafari = services.get("casafari")
    if casafari and municipality:
        try:
            comp = casafari.search_comparables(
                municipality=municipality,
                property_type=property_type,
                bedrooms=bedrooms,
                area_m2=area_m2,
            )
            if comp:
                market_data["casafari_avg_price_m2"] = comp.get("avg_price_m2")
                market_data["casafari_median_price_m2"] = comp.get("median_price_m2")
                market_data["casafari_comparables_count"] = comp.get("comparables_count")
                logger.debug(
                    f"Casafari: {comp.get('comparables_count')} comparaveis, "
                    f"mediana {comp.get('median_price_m2')} EUR/m2"
                )
        except Exception as e:
            logger.error(f"Erro Casafari: {e}")

    # --- Etapa 1b: Infocasa (comparaveis) ---
    infocasa = services.get("infocasa")
    if infocasa and municipality:
        try:
            comp = infocasa.search_comparables(
                municipality=municipality,
                property_type=property_type,
                bedrooms=bedrooms,
                area_m2=area_m2,
            )
            if comp:
                market_data["infocasa_avg_price_m2"] = comp.get("avg_price_m2")
                market_data["infocasa_median_price_m2"] = comp.get("median_price_m2")
                market_data["infocasa_comparables_count"] = comp.get("comparables_count")
                logger.debug(
                    f"Infocasa: {comp.get('comparables_count')} comparaveis, "
                    f"mediana {comp.get('median_price_m2')} EUR/m2"
                )
        except Exception as e:
            logger.error(f"Erro Infocasa: {e}")

    # --- Etapa 2: INE (baseline nacional) ---
    ine = services.get("ine")
    if ine and municipality:
        try:
            ine_data = ine.get_median_price(municipality)
            if ine_data:
                market_data["ine_median_price_m2"] = ine_data.get("price_m2")
                market_data["ine_quarter"] = ine_data.get("quarter")
        except Exception as e:
            logger.error(f"Erro INE: {e}")

    # --- Etapa 3: SIR (validacao com transacoes reais) ---
    sir = services.get("sir")
    if sir and municipality and price:
        try:
            evaluation = sir.evaluate_price(
                price=price,
                municipality=municipality,
                area_m2=area_m2,
                property_type=property_type,
                bedrooms=bedrooms,
            )
            if evaluation:
                market_data["sir_median_price_m2"] = evaluation.get("market_median_m2")
                market_data["sir_market_position"] = evaluation.get("position")
                market_data["sir_price_vs_market_pct"] = evaluation.get("price_vs_market_pct")
                logger.debug(
                    f"SIR: {evaluation.get('position_label')} "
                    f"({evaluation.get('price_vs_market_pct')}%)"
                )
            else:
                # Tentar apenas dados de transacao sem avaliacao
                tx_data = sir.get_transaction_prices(
                    municipality=municipality,
                    property_type=property_type,
                    bedrooms=bedrooms,
                )
                if tx_data:
                    market_data["sir_median_price_m2"] = tx_data.get("median_price_m2")
                    market_data["sir_transactions_count"] = tx_data.get("transactions_count")
        except Exception as e:
            logger.error(f"Erro SIR: {e}")

    # --- Etapa 4: Idealista (listings ativos, opcional) ---
    idealista = services.get("idealista")
    if idealista and opportunity_result.location and property_type:
        try:
            area = area_m2 or 80.0
            idealista_data = idealista.search_comparables(
                opportunity_result.location,
                property_type,
                area,
            )
            if idealista_data:
                market_data["idealista_avg_price_m2"] = idealista_data.get("avg_price_m2")
                market_data["idealista_listings_count"] = idealista_data.get("listings_count")
                market_data["idealista_comparable_urls"] = str(
                    idealista_data.get("comparable_urls", [])
                )
        except Exception as e:
            logger.error(f"Erro Idealista: {e}")

    # --- Etapa 5: Valor estimado de mercado ---
    # Prioridade: SIR (transacoes reais) > Casafari > Infocasa > INE
    try:
        area = area_m2 or 80.0
        best_price_m2 = (
            market_data.get("sir_median_price_m2")
            or market_data.get("casafari_median_price_m2")
            or market_data.get("infocasa_median_price_m2")
            or market_data.get("ine_median_price_m2")
        )

        if best_price_m2:
            market_data["estimated_market_value"] = round(best_price_m2 * area, 2)

        # price_vs_market_pct (usando o melhor dado disponivel)
        if market_data.get("estimated_market_value") and price:
            market_data["price_vs_market_pct"] = round(
                (price / market_data["estimated_market_value"]) * 100, 1
            )
    except Exception as e:
        logger.error(f"Erro ao estimar valor de mercado: {e}")

    # --- Etapa 6: Yield estimado ---
    yield_calculator = services.get("yield_calculator")
    if yield_calculator and price and municipality:
        try:
            estimated_rent = _estimate_monthly_rent(
                price,
                market_data.get("ine_median_price_m2"),
                area_m2,
            )
            if estimated_rent:
                market_data["estimated_monthly_rent"] = estimated_rent
                yield_result = yield_calculator.calculate(
                    price,
                    estimated_rent,
                    municipality,
                )
                if yield_result:
                    market_data["gross_yield_pct"] = yield_result.gross_yield_pct
                    market_data["net_yield_pct"] = yield_result.net_yield_pct
                    market_data["imt_estimate"] = yield_result.imt
                    market_data["stamp_duty_estimate"] = yield_result.stamp_duty
                    market_data["total_acquisition_cost"] = yield_result.total_acquisition_cost
        except Exception as e:
            logger.error(f"Erro ao calcular yield: {e}")

    return market_data if market_data else None


def _estimate_monthly_rent(
    purchase_price: float,
    ine_price_m2: Optional[float],
    area_m2: Optional[float],
) -> Optional[float]:
    """Estima a renda mensal com base nos dados disponíveis.

    Usa uma heurística simples: yield bruta de 5% ao ano como estimativa
    quando não há dados de mercado para rendas.

    Args:
        purchase_price: Preço de compra do imóvel.
        ine_price_m2: Preço mediano por m2 do INE.
        area_m2: Área do imóvel em m2.

    Returns:
        Renda mensal estimada ou None.
    """
    # Heurística: 5% yield bruta anual como estimativa base
    return round(purchase_price * 0.05 / 12, 2)


def _save_results(
    session: Any,
    group_info: Dict[str, Any],
    messages: List[Dict[str, Any]],
    classifications: List[Any],
    market_enrichments: List[Optional[Dict[str, Any]]],
) -> int:
    """Persiste resultados na base de dados.

    Args:
        session: Sessão SQLAlchemy.
        group_info: Informação do grupo WhatsApp.
        messages: Mensagens processadas (já filtradas).
        classifications: Resultados da classificação IA.
        market_enrichments: Dados de mercado para cada classificação.

    Returns:
        Número de oportunidades guardadas.
    """
    opportunities_saved = 0
    group_wa_id = group_info["id"]
    group_name = group_info.get("name", "Desconhecido")

    # Buscar ou criar grupo na BD
    stmt = select(Group).where(Group.whatsapp_group_id == group_wa_id)
    db_group = session.execute(stmt).scalar_one_or_none()

    if db_group is None:
        db_group = Group(
            whatsapp_group_id=group_wa_id,
            name=group_name,
            is_active=True,
        )
        session.add(db_group)
        session.flush()

    for idx, classification in enumerate(classifications):
        if idx >= len(messages):
            break

        msg_data = messages[classification.message_index] if classification.message_index < len(messages) else None
        if msg_data is None:
            continue

        # Verificar se a mensagem já existe na BD
        wa_msg_id = msg_data.get("whatsapp_message_id", "")
        existing_msg = session.execute(
            select(Message).where(Message.whatsapp_message_id == wa_msg_id)
        ).scalar_one_or_none()

        if existing_msg is not None:
            continue

        # Guardar mensagem
        db_message = Message(
            whatsapp_message_id=wa_msg_id,
            group_id=db_group.id,
            group_name=group_name,
            sender_id=msg_data.get("sender_id"),
            sender_name=msg_data.get("sender_name"),
            content=msg_data.get("content", ""),
            message_type=msg_data.get("message_type", "text"),
            timestamp=msg_data.get("timestamp", datetime.now(tz=timezone.utc)),
            processed=True,
        )
        session.add(db_message)
        session.flush()

        # Guardar oportunidade
        db_opportunity = Opportunity(
            message_id=db_message.id,
            is_opportunity=classification.is_opportunity,
            confidence=classification.confidence,
            opportunity_type=classification.opportunity_type,
            property_type=classification.property_type,
            location_extracted=classification.location,
            parish=classification.parish,
            municipality=classification.municipality,
            district=classification.district,
            price_mentioned=classification.price,
            area_m2=classification.area_m2,
            bedrooms=classification.bedrooms,
            ai_reasoning=classification.reasoning,
            original_message=msg_data.get("content", ""),
            status="nova",
        )
        session.add(db_opportunity)
        session.flush()

        if classification.is_opportunity:
            opportunities_saved += 1

        # Guardar dados de mercado se disponíveis
        if idx < len(market_enrichments) and market_enrichments[idx] is not None:
            market = market_enrichments[idx]
            db_market = MarketData(
                opportunity_id=db_opportunity.id,
                # INE
                ine_median_price_m2=market.get("ine_median_price_m2"),
                ine_quarter=market.get("ine_quarter"),
                # Casafari
                casafari_avg_price_m2=market.get("casafari_avg_price_m2"),
                casafari_median_price_m2=market.get("casafari_median_price_m2"),
                casafari_comparables_count=market.get("casafari_comparables_count"),
                # Infocasa
                infocasa_avg_price_m2=market.get("infocasa_avg_price_m2"),
                infocasa_median_price_m2=market.get("infocasa_median_price_m2"),
                infocasa_comparables_count=market.get("infocasa_comparables_count"),
                # SIR
                sir_median_price_m2=market.get("sir_median_price_m2"),
                sir_market_position=market.get("sir_market_position"),
                sir_price_vs_market_pct=market.get("sir_price_vs_market_pct"),
                sir_transactions_count=market.get("sir_transactions_count"),
                # Idealista
                idealista_avg_price_m2=market.get("idealista_avg_price_m2"),
                idealista_listings_count=market.get("idealista_listings_count"),
                idealista_comparable_urls=market.get("idealista_comparable_urls"),
                # Estimativas
                estimated_market_value=market.get("estimated_market_value"),
                estimated_monthly_rent=market.get("estimated_monthly_rent"),
                gross_yield_pct=market.get("gross_yield_pct"),
                net_yield_pct=market.get("net_yield_pct"),
                price_vs_market_pct=market.get("price_vs_market_pct"),
                imt_estimate=market.get("imt_estimate"),
                stamp_duty_estimate=market.get("stamp_duty_estimate"),
                total_acquisition_cost=market.get("total_acquisition_cost"),
            )
            session.add(db_market)

    # Atualizar contadores do grupo
    db_group.message_count += len(messages)
    db_group.opportunity_count += opportunities_saved
    db_group.last_processed_at = datetime.now(tz=timezone.utc)

    return opportunities_saved


def _deduplicate_opportunities(
    session: Any,
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Remove mensagens cujo conteudo ja existe na BD (cross-grupo).

    Consultores frequentemente postam a mesma mensagem em varios grupos.
    Compara o conteudo normalizado (sem espacos extras) para detetar duplicados.

    Args:
        session: Sessao SQLAlchemy.
        messages: Mensagens a verificar.

    Returns:
        Mensagens sem duplicados.
    """
    if not messages:
        return messages

    # Buscar conteudos ja na BD
    existing = session.execute(select(Message.content)).scalars().all()
    existing_normalized = {c.strip().lower() for c in existing if c}

    unique: List[Dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content", "").strip().lower()
        if content and content not in existing_normalized:
            unique.append(msg)
            existing_normalized.add(content)

    removed = len(messages) - len(unique)
    if removed > 0:
        logger.info(f"Deduplicacao: {removed} mensagens duplicadas removidas, {len(unique)} unicas")

    return unique


def _score_group_opportunities(group_info: Dict[str, Any]) -> None:
    """Pontua oportunidades recém-guardadas de um grupo.

    Args:
        group_info: Informação do grupo WhatsApp.
    """
    from src.modules.m1_ingestor.deal_scorer import score_opportunity

    group_wa_id = group_info["id"]

    with get_session() as session:
        db_group = session.execute(
            select(Group).where(Group.whatsapp_group_id == group_wa_id)
        ).scalar_one_or_none()

        if not db_group:
            return

        # Buscar oportunidades sem score deste grupo
        stmt = (
            select(Opportunity)
            .join(Message, Opportunity.message_id == Message.id)
            .where(
                Message.group_id == db_group.id,
                Opportunity.is_opportunity.is_(True),
                Opportunity.deal_score.is_(None),
            )
        )
        opps = session.execute(stmt).scalars().all()

        for opp in opps:
            market = session.execute(
                select(MarketData).where(MarketData.opportunity_id == opp.id)
            ).scalar_one_or_none()

            result = score_opportunity(opp, market)
            opp.deal_score = result.score
            opp.deal_grade = result.grade

            logger.info(
                f"  Deal Score: {result.score} ({result.grade}) — "
                f"{opp.municipality or '?'} | {opp.opportunity_type} | "
                f"{opp.price_mentioned or '?'}€"
            )


def run_pipeline() -> PipelineResult:
    """Executa o pipeline completo de processamento.

    Etapas:
    1. Buscar mensagens não lidas de todos os grupos ativos
    2. Filtrar ruído
    2b. Deduplicar (remover mensagens identicas ja processadas)
    3. Classificar com IA
    4. Enriquecer com dados de mercado
    5. Finalizar (persistir, atualizar, logar)

    Returns:
        PipelineResult com métricas de execução.
    """
    logger.info("=== Pipeline ImoIA iniciado ===")
    pipeline_start = time.monotonic()

    settings = get_settings()
    errors: List[str] = []
    total_messages = 0
    total_opportunities = 0
    groups_processed = 0
    group_logs: List[Dict[str, Any]] = []

    # Inicializar BD
    init_db()

    # Etapa 1: Buscar grupos ativos
    wa_client = _get_whatsapp_client()

    try:
        active_groups = wa_client.list_active_groups()
    except Exception as e:
        error_msg = f"Erro ao listar grupos ativos: {e}"
        logger.error(error_msg)
        return PipelineResult(
            messages_fetched=0,
            opportunities_found=0,
            groups_processed=0,
            errors=[error_msg],
        )

    if not active_groups:
        logger.info("Nenhum grupo ativo encontrado")
        return PipelineResult(
            messages_fetched=0,
            opportunities_found=0,
            groups_processed=0,
            errors=[],
        )

    logger.info(f"Encontrados {len(active_groups)} grupos no WhatsApp (nao arquivados)")

    # Carregar TODOS os IDs inativos da BD de uma vez (evita problemas de cache)
    with get_session() as session:
        all_inactive = session.execute(
            select(Group.whatsapp_group_id).where(Group.is_active == False)  # noqa: E712
        ).scalars().all()
        disabled_ids = set(all_inactive)
        logger.info(f"{len(disabled_ids)} grupos desativados na BD")

    # Registar novos grupos na BD
    with get_session() as session:
        new_count = 0
        for group in active_groups:
            gid = group.get("id", "")
            gname = group.get("name", "Desconhecido")
            if gid in disabled_ids:
                continue
            db_group = session.execute(
                select(Group).where(Group.whatsapp_group_id == gid)
            ).scalar_one_or_none()

            if db_group is None:
                db_group = Group(
                    whatsapp_group_id=gid,
                    name=gname,
                    is_active=True,
                )
                session.add(db_group)
                new_count += 1

        session.commit()

        if new_count:
            logger.info(f"{new_count} novos grupos detetados e registados na BD")

    # Guardar lista completa antes de filtrar (para marcar inactivos como lidos)
    all_whatsapp_groups = list(active_groups)

    # Filtrar grupos desativados
    before_filter = len(active_groups)
    active_groups = [g for g in active_groups if g.get("id") not in disabled_ids]
    filtered_count = before_filter - len(active_groups)
    if filtered_count:
        logger.info(f"{filtered_count} grupos desativados removidos da lista")

    # Deduplicar grupos por ID (seguranca extra)
    seen_group_ids: set = set()
    unique_groups: List[Dict[str, Any]] = []
    for g in active_groups:
        gid = g.get("id", "")
        if gid and gid not in seen_group_ids:
            seen_group_ids.add(gid)
            unique_groups.append(g)
    if len(unique_groups) < len(active_groups):
        logger.warning(f"{len(active_groups) - len(unique_groups)} grupos duplicados removidos")
    active_groups = unique_groups

    logger.info(f"{len(active_groups)} grupos ativos para processar")

    # --- OPT 1: Separar grupos com unread > 0 dos ja lidos ---
    active_with_unread = [g for g in active_groups if g.get("unread", 0) and g["unread"] > 0]
    active_already_read = [g for g in active_groups if not g.get("unread", 0) or g["unread"] == 0]
    inactive_in_api = [g for g in all_whatsapp_groups if g.get("id") in disabled_ids]
    inactive_with_unread = [g for g in inactive_in_api if g.get("unread", 0) and g["unread"] > 0]

    logger.info(
        f"OPT: {len(active_with_unread)} activos com unread, "
        f"{len(active_already_read)} activos ja lidos (skip), "
        f"{len(inactive_with_unread)} inativos com unread"
    )

    # Obter tenant_id para estratégia personalizada
    _tenant_id = None
    try:
        from sqlalchemy import select as sa_select
        from src.database.models_v2 import Tenant
        with get_session() as _s:
            _t = _s.execute(sa_select(Tenant).limit(1)).scalar_one_or_none()
            if _t:
                _tenant_id = _t.id
    except Exception:
        pass

    # Obter servicos
    classifier = _get_classifier(tenant_id=_tenant_id)
    market_services = _get_market_services()

    # Carregar last_processed_at de todos os grupos de uma vez
    db_groups_map: Dict[str, Any] = {}
    with get_session() as session:
        all_db_groups = session.execute(select(Group)).scalars().all()
        for dbg in all_db_groups:
            if dbg.whatsapp_group_id:
                db_groups_map[dbg.whatsapp_group_id] = {
                    "last_processed_at": dbg.last_processed_at,
                }

    # --- FASE 1: Fetch + filter + mark_as_read em paralelo ---
    phase1_start = time.monotonic()

    def _fetch_group(group: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch mensagens de um grupo e filtrar ruido (sem mark_as_read)."""
        gid = group.get("id", "unknown")
        gname = group.get("name", "Desconhecido")
        entry: Dict[str, Any] = {
            "group": group, "messages": [], "filtered": [],
            "estado": "ok", "erro": None,
        }
        try:
            db_info = db_groups_map.get(gid)
            if db_info and db_info["last_processed_at"]:
                since = db_info["last_processed_at"]
                if since.tzinfo is None:
                    since = since.replace(tzinfo=timezone.utc)
            else:
                since = datetime.now(tz=timezone.utc) - timedelta(days=10)

            thread_client = WhatsAppClient()
            messages = thread_client.fetch_unread_messages(gid, since)
            entry["messages"] = messages

            if not messages:
                entry["estado"] = "sem_mensagens"
                return entry

            filtered = _filter_noise(messages)
            if not filtered:
                entry["estado"] = "so_ruido"
                return entry
            entry["filtered"] = filtered
        except Exception as e:
            entry["estado"] = "erro"
            entry["erro"] = str(e)
            logger.error(f"Erro fetch {gname}: {e}")
        return entry

    fetch_results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_group, g): g for g in active_with_unread}
        for future in as_completed(futures):
            fetch_results.append(future.result())

    phase1_elapsed = time.monotonic() - phase1_start
    logger.info(f"FASE 1 (fetch paralelo): {len(fetch_results)} grupos em {phase1_elapsed:.1f}s")

    # --- FASE 1a: Marcar TODOS os grupos com unread como lidos (sequencial) ---
    # Sequencial porque a Whapi nao sincroniza com o dispositivo em paralelo
    phase1a_start = time.monotonic()
    read_client = WhatsAppClient()
    active_read = 0
    for group in active_with_unread:
        gid = group.get("id", "")
        if gid:
            try:
                read_client.mark_group_as_read(gid)
                active_read += 1
            except Exception as e:
                logger.warning(f"Falha mark_as_read {group.get('name', '?')}: {e}")
    phase1a_elapsed = time.monotonic() - phase1a_start
    logger.info(f"FASE 1a (mark_as_read sequencial): {active_read}/{len(active_with_unread)} em {phase1a_elapsed:.1f}s")

    # --- FASE 1b: Marcar inativos com unread como lidos (paralelo) ---
    phase1b_start = time.monotonic()
    inactive_read = 0

    def _mark_inactive_read(group: Dict[str, Any]) -> bool:
        try:
            tc = WhatsAppClient()
            return tc.mark_group_as_read(group["id"])
        except Exception:
            return False

    if inactive_with_unread:
        with ThreadPoolExecutor(max_workers=10) as executor:
            inactive_futures = [executor.submit(_mark_inactive_read, g) for g in inactive_with_unread]
            inactive_results = [f.result() for f in inactive_futures]
            inactive_read = sum(1 for r in inactive_results if r)

    phase1b_elapsed = time.monotonic() - phase1b_start
    if inactive_with_unread:
        logger.info(f"FASE 1b (inativos paralelo): {inactive_read}/{len(inactive_with_unread)} em {phase1b_elapsed:.1f}s")

    # --- FASE 2: Deduplicar + preparar classificacao ---
    phase2_start = time.monotonic()
    total_filtered = 0
    all_filtered: List[Dict[str, Any]] = []
    group_filtered_map: Dict[str, List[Dict[str, Any]]] = {}

    for fr in fetch_results:
        group = fr["group"]
        gid = group.get("id", "unknown")
        gname = group.get("name", "Desconhecido")
        messages = fr.get("messages", [])
        filtered = fr.get("filtered", [])

        groups_processed += 1
        total_messages += len(messages)

        group_log: Dict[str, Any] = {
            "grupo": gname, "grupo_id": gid,
            "processado_em": datetime.now(tz=timezone.utc).isoformat(),
            "mensagens_buscadas": len(messages),
            "mensagens_filtradas": 0, "oportunidades": 0,
            "estado": fr.get("estado", "ok"), "erro": fr.get("erro"),
        }

        if fr.get("erro"):
            errors.append(f"Erro {gname}: {fr['erro']}")

        if not filtered:
            group_logs.append(group_log)
            continue

        with get_session() as session:
            filtered = _deduplicate_opportunities(session, filtered)
        if not filtered:
            group_log["estado"] = "duplicadas"
            group_logs.append(group_log)
            continue

        group_log["mensagens_filtradas"] = len(filtered)
        total_filtered += len(filtered)
        group_filtered_map[gid] = filtered
        group_logs.append(group_log)

        for msg in filtered:
            all_filtered.append({
                **msg, "_group_id": gid, "_group_name": gname, "_group_info": group,
            })

    phase2_elapsed = time.monotonic() - phase2_start
    logger.info(f"FASE 2 (dedup): {total_filtered} unicas de {total_messages} buscadas em {phase2_elapsed:.1f}s")

    # --- FASE 3: Classificar num batch unico ---
    phase3_start = time.monotonic()

    if all_filtered:
        classifier_messages = [
            {"index": i, "text": msg.get("content", ""), "group": msg.get("_group_name", "?")}
            for i, msg in enumerate(all_filtered)
        ]

        logger.info(f"A classificar {len(classifier_messages)} mensagens de {len(group_filtered_map)} grupos")
        all_classifications = classifier.classify_batch(classifier_messages)

        for i, classification in enumerate(all_classifications):
            if i >= len(all_filtered):
                break
            msg = all_filtered[i]
            gid = msg["_group_id"]
            group_info = msg["_group_info"]

            enrichment = _enrich_opportunity(classification, market_services)
            clean_msg = {k: v for k, v in msg.items() if not k.startswith("_")}

            with get_session() as session:
                opps = _save_results(session, group_info, [clean_msg], [classification], [enrichment])
                if opps > 0:
                    total_opportunities += opps
                    for gl in group_logs:
                        if gl.get("grupo_id") == gid:
                            gl["oportunidades"] = gl.get("oportunidades", 0) + opps
                            break

        for gid in group_filtered_map:
            gi = next((g for g in active_with_unread if g.get("id") == gid), None)
            if gi and any(gl.get("grupo_id") == gid and gl.get("oportunidades", 0) > 0 for gl in group_logs):
                try:
                    _score_group_opportunities(gi)
                except Exception as e:
                    logger.error(f"Erro ao pontuar oportunidades de {gid}: {e}")

    phase3_elapsed = time.monotonic() - phase3_start
    logger.info(f"FASE 3 (classificacao): {total_filtered} msgs, {total_opportunities} opps em {phase3_elapsed:.1f}s")

    # --- FASE 4: Archive fire-and-forget (paralelo) ---
    phase4_start = time.monotonic()
    archive_count = 0

    def _archive_group_task(gid: str) -> bool:
        try:
            tc = WhatsAppClient()
            return tc.archive_group(gid)
        except Exception:
            return False

    groups_to_archive = [g.get("id") for g in active_with_unread if g.get("id")]
    if groups_to_archive:
        with ThreadPoolExecutor(max_workers=10) as executor:
            archive_futures = [executor.submit(_archive_group_task, gid) for gid in groups_to_archive]
            archive_results = [f.result() for f in archive_futures]
            archive_count = sum(1 for r in archive_results if r)

    phase4_elapsed = time.monotonic() - phase4_start
    logger.info(f"FASE 4 (archive paralelo): {archive_count}/{len(groups_to_archive)} em {phase4_elapsed:.1f}s")

    # Resumo final
    pipeline_elapsed = time.monotonic() - pipeline_start
    result = PipelineResult(
        messages_fetched=total_messages,
        opportunities_found=total_opportunities,
        groups_processed=groups_processed,
        errors=errors,
    )

    logger.info("=" * 60)
    logger.info("RESUMO DO PIPELINE")
    logger.info("=" * 60)
    logger.info(f"  Duracao total: {pipeline_elapsed:.1f}s ({pipeline_elapsed/60:.1f} min)")
    logger.info(f"  FASE 1 fetch paralelo: {phase1_elapsed:.1f}s")
    logger.info(f"  FASE 1b inativos: {phase1b_elapsed:.1f}s")
    logger.info(f"  FASE 2 dedup: {phase2_elapsed:.1f}s")
    logger.info(f"  FASE 3 classificacao: {phase3_elapsed:.1f}s")
    logger.info(f"  FASE 4 archive: {phase4_elapsed:.1f}s")
    logger.info(f"  Grupos com unread: {len(active_with_unread)} activos + {len(inactive_with_unread)} inativos")
    logger.info(f"  Grupos skip (ja lidos): {len(active_already_read)}")
    logger.info(f"  Mensagens buscadas: {total_messages}")
    logger.info(f"  Mensagens apos filtro: {total_filtered}")
    logger.info(f"  Oportunidades: {total_opportunities}")
    logger.info(f"  Inativos lidos: {inactive_read}")
    logger.info(f"  Archive: {archive_count}/{len(groups_to_archive)}")
    logger.info(f"  Erros: {len(errors)}")
    if total_filtered > 0 and total_opportunities == 0:
        logger.warning("ATENCAO: 0 oportunidades detetadas!")
    logger.info("=" * 60)

    # Guardar log
    log_data = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "resumo": {
            "mensagens": result.messages_fetched,
            "mensagens_filtradas": total_filtered,
            "oportunidades": result.opportunities_found,
            "grupos_com_unread": len(active_with_unread),
            "grupos_skip": len(active_already_read),
            "inativos_lidos": inactive_read,
            "archive": archive_count,
            "erros": len(result.errors),
            "duracao_seg": round(pipeline_elapsed, 1),
        },
        "grupos": group_logs,
    }
    log_path = Path("logs/pipeline_groups.json")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2, default=str))

    # Atualizar status
    status_path = Path("logs/pipeline_status.json")
    status_data = {
        "state": "concluido",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "mensagens": result.messages_fetched,
        "mensagens_filtradas": total_filtered,
        "oportunidades": result.opportunities_found,
        "grupos_com_unread": len(active_with_unread),
        "inativos_lidos": inactive_read,
        "erros": len(result.errors),
        "duracao_seg": round(pipeline_elapsed, 1),
    }
    status_path.write_text(json.dumps(status_data, ensure_ascii=False))

    return result


def reprocess_pipeline(
    days: int = 10,
    progress_callback: Any = None,
) -> PipelineResult:
    """Reprocessa mensagens dos últimos N dias com a estratégia activa.

    Processa grupo a grupo sequencialmente. Só processa grupos com
    actividade recente para não desperdiçar tempo em grupos parados.
    Reporta progresso via callback para o frontend não dar timeout.

    Args:
        days: Número de dias para trás a reprocessar (default 10).
        progress_callback: Função(groups_done, total_msgs, total_opps) chamada após cada grupo.

    Returns:
        PipelineResult com métricas de execução.
    """
    logger.info(f"=== REPROCESS Pipeline: últimos {days} dias ===")
    pipeline_start = time.monotonic()

    errors: List[str] = []
    total_messages = 0
    total_filtered = 0
    total_opportunities = 0
    groups_processed = 0

    init_db()

    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    since_ts = int(since.timestamp())

    # Buscar grupos activos e filtrar só os com actividade recente
    wa_client = _get_whatsapp_client()
    try:
        all_groups = wa_client.list_active_groups()
    except Exception as e:
        return PipelineResult(
            messages_fetched=0, opportunities_found=0,
            groups_processed=0, errors=[str(e)],
        )

    # Filtrar grupos desativados na BD
    with get_session() as session:
        all_inactive = session.execute(
            select(Group.whatsapp_group_id).where(Group.is_active == False)  # noqa: E712
        ).scalars().all()
        disabled_ids = set(all_inactive)

    # Só processar grupos com última mensagem nos últimos N dias
    active_groups = []
    for g in all_groups:
        if g.get("id") in disabled_ids:
            continue
        last_ts = g.get("last_message_ts", 0) or 0
        if last_ts >= since_ts:
            active_groups.append(g)

    logger.info(f"Reprocessar {len(active_groups)} grupos com actividade (de {len(all_groups)} total)")

    classifier = _get_classifier()
    market_services = _get_market_services()

    # Processar grupo a grupo
    for group in active_groups:
        gid = group.get("id", "unknown")
        gname = group.get("name", "Desconhecido")
        groups_processed += 1

        try:
            messages = wa_client.fetch_unread_messages(gid, since)
            total_messages += len(messages)

            if not messages:
                if progress_callback:
                    progress_callback(groups_processed, total_messages, total_opportunities)
                continue

            filtered = _filter_noise(messages)
            if not filtered:
                if progress_callback:
                    progress_callback(groups_processed, total_messages, total_opportunities)
                continue

            total_filtered += len(filtered)

            # Classificar este grupo
            classifier_messages = [
                {"index": i, "text": msg.get("content", ""), "group": gname}
                for i, msg in enumerate(filtered)
            ]

            classifications = classifier.classify_batch(classifier_messages)

            # Persistir oportunidades encontradas
            for i, classification in enumerate(classifications):
                if i >= len(filtered):
                    break
                if not classification.is_opportunity or classification.confidence < 0.5:
                    continue

                enrichment = _enrich_opportunity(classification, market_services)
                with get_session() as session:
                    opps = _save_results(session, group, [filtered[i]], [classification], [enrichment])
                    total_opportunities += opps

            logger.info(
                f"Reprocess [{groups_processed}/{len(active_groups)}] {gname}: "
                f"{len(messages)} msgs, {len(filtered)} filtradas"
            )

        except Exception as e:
            errors.append(f"Erro {gname}: {str(e)[:100]}")
            logger.error(f"Reprocess erro {gname}: {e}")

        # Reportar progresso ao frontend
        if progress_callback:
            progress_callback(groups_processed, total_messages, total_opportunities)

    pipeline_elapsed = time.monotonic() - pipeline_start

    result = PipelineResult(
        messages_fetched=total_messages,
        opportunities_found=total_opportunities,
        groups_processed=groups_processed,
        errors=errors,
    )

    logger.info(
        f"REPROCESS concluído: {groups_processed} grupos, {total_messages} msgs, "
        f"{total_filtered} filtradas, {total_opportunities} oportunidades em {pipeline_elapsed:.1f}s"
    )

    return result


if __name__ == "__main__":
    result = run_pipeline()
    logger.info(f"Resultado final: {result}")
