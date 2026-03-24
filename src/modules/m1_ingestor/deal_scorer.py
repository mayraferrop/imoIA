"""Deal Scorer — avaliação de qualidade de oportunidades imobiliárias.

Pontua cada oportunidade de 0 a 100 com base em:
1. Desconto vs mercado (0-30 pts)
2. Completude dos dados (0-20 pts)
3. Sinais de oportunidade (0-25 pts)
4. Viabilidade financeira (0-15 pts)
5. Red flags / penalizações (-10 a 0 pts)

Grade: A (80+), B (60-79), C (40-59), D (20-39), F (<20)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


# Tipos de propriedade onde INE price/m2 residencial NÃO é comparável
_NON_RESIDENTIAL_TYPES = {"terreno", "armazém", "loja", "quinta"}


@dataclass
class DealScoreResult:
    """Resultado do scoring de uma oportunidade."""

    score: int
    grade: str
    breakdown: Dict[str, Any]


def score_opportunity(
    opportunity: Any,
    market_data: Any | None,
) -> DealScoreResult:
    """Pontua uma oportunidade de 0-100.

    Args:
        opportunity: Objeto Opportunity (SQLAlchemy ou dict-like).
        market_data: Objeto MarketData associado (pode ser None).

    Returns:
        DealScoreResult com score, grade e breakdown detalhado.
    """
    breakdown: Dict[str, Any] = {}

    # --- 1. Desconto vs Mercado (0-30 pts) ---
    price_score, price_detail = _score_price_discount(opportunity, market_data)
    breakdown["price_discount"] = {"score": price_score, "max": 30, **price_detail}

    # --- 2. Completude dos Dados (0-20 pts) ---
    data_score, data_detail = _score_data_quality(opportunity, market_data)
    breakdown["data_quality"] = {"score": data_score, "max": 20, **data_detail}

    # --- 3. Sinais de Oportunidade (0-25 pts) ---
    signal_score, signal_detail = _score_opportunity_signals(opportunity)
    breakdown["signals"] = {"score": signal_score, "max": 25, **signal_detail}

    # --- 4. Viabilidade Financeira (0-15 pts) ---
    financial_score, financial_detail = _score_financials(opportunity, market_data)
    breakdown["financials"] = {"score": financial_score, "max": 15, **financial_detail}

    # --- 5. Red Flags (penalizações, -10 a 0 pts) ---
    penalty, penalty_detail = _score_red_flags(opportunity, market_data)
    breakdown["red_flags"] = {"penalty": penalty, **penalty_detail}

    # --- 6. Bonus Preferencias (0-10 pts) ---
    try:
        from src.modules.m1_ingestor.preferences import match_opportunity
        match_result = match_opportunity(opportunity, market_data)
        pref_match_pct = match_result.get("match_pct", 50)
        if match_result.get("total", 0) > 0:
            pref_score = round(pref_match_pct / 100 * 10)
        else:
            pref_score = 5  # neutral when no prefs defined
        breakdown["preferences"] = {
            "score": pref_score,
            "max": 10,
            "match_pct": pref_match_pct,
            "label": match_result.get("match_label", ""),
        }
    except Exception:
        pref_score = 5
        breakdown["preferences"] = {"score": 5, "max": 10, "note": "erro ao avaliar preferencias"}

    # --- Total ---
    total_score = price_score + data_score + signal_score + financial_score + penalty + pref_score
    score = max(0, min(100, total_score))
    grade = _score_to_grade(score)

    return DealScoreResult(score=score, grade=grade, breakdown=breakdown)


def _score_price_discount(
    opp: Any, market: Any | None
) -> tuple[int, Dict[str, Any]]:
    """Avalia desconto do preço face ao mercado (0-30 pts)."""
    detail: Dict[str, Any] = {}
    price = _get_attr(opp, "price_mentioned")
    prop_type = _get_attr(opp, "property_type")

    if not price or price <= 0:
        detail["reason"] = "sem_preco"
        return 0, detail

    if market is None:
        detail["reason"] = "sem_dados_mercado"
        return 0, detail

    # Verificar se temos price_vs_market_pct fiável
    pvm = _get_attr(market, "price_vs_market_pct")
    estimated_value = _get_attr(market, "estimated_market_value")

    # Desconfiar de price_vs_market quando só temos INE para tipos não-residenciais
    if prop_type and prop_type.lower() in _NON_RESIDENTIAL_TYPES:
        has_specific_data = any([
            _get_attr(market, "sir_median_price_m2"),
            _get_attr(market, "casafari_median_price_m2"),
            _get_attr(market, "infocasa_median_price_m2"),
        ])
        if not has_specific_data:
            detail["reason"] = "ine_nao_aplicavel_tipo_imovel"
            detail["property_type"] = prop_type
            return 0, detail

    if pvm is None or pvm <= 0:
        detail["reason"] = "sem_comparacao_mercado"
        return 0, detail

    detail["price_vs_market_pct"] = pvm
    detail["estimated_market_value"] = estimated_value

    # price_vs_market_pct = (preço pedido / valor mercado) * 100
    # <100% = abaixo do mercado (bom), >100% = acima (mau)
    if pvm < 50:
        score = 30
    elif pvm < 65:
        score = 25
    elif pvm < 75:
        score = 20
    elif pvm < 85:
        score = 15
    elif pvm < 95:
        score = 8
    elif pvm <= 105:
        score = 2
    else:
        score = 0
        detail["flag"] = "acima_do_mercado"

    return score, detail


def _score_data_quality(
    opp: Any, market: Any | None
) -> tuple[int, Dict[str, Any]]:
    """Avalia completude dos dados (0-20 pts)."""
    score = 0
    fields: Dict[str, bool] = {}

    # Preço (5 pts) — crítico para avaliar
    has_price = bool(_get_attr(opp, "price_mentioned"))
    fields["preco"] = has_price
    if has_price:
        score += 5

    # Área (4 pts) — essencial para price/m2
    has_area = bool(_get_attr(opp, "area_m2"))
    fields["area"] = has_area
    if has_area:
        score += 4

    # Município (4 pts) — necessário para comparação de mercado
    has_muni = bool(_get_attr(opp, "municipality"))
    fields["municipio"] = has_muni
    if has_muni:
        score += 4

    # Tipo de propriedade (3 pts)
    has_type = bool(_get_attr(opp, "property_type"))
    fields["tipo_imovel"] = has_type
    if has_type:
        score += 3

    # Dados de mercado de pelo menos 1 fonte fiável (4 pts)
    has_market = False
    if market:
        has_market = any([
            _get_attr(market, "sir_median_price_m2"),
            _get_attr(market, "casafari_median_price_m2"),
            _get_attr(market, "infocasa_median_price_m2"),
            _get_attr(market, "ine_median_price_m2"),
        ])
    fields["dados_mercado"] = has_market
    if has_market:
        score += 4

    return score, {"fields": fields}


def _score_opportunity_signals(opp: Any) -> tuple[int, Dict[str, Any]]:
    """Avalia sinais de oportunidade (0-25 pts)."""
    score = 0
    detail: Dict[str, Any] = {}

    # Tipo de oportunidade (0-12 pts)
    opp_type = _get_attr(opp, "opportunity_type") or ""
    type_scores = {
        "venda_urgente": 12,
        "off_market": 10,
        "abaixo_mercado": 9,
        "reabilitacao": 7,
        "predio_inteiro": 7,
        "leilao": 6,
        "yield_alto": 6,
        "terreno_viabilidade": 4,
        "outro": 1,
    }
    type_score = type_scores.get(opp_type.lower(), 1)
    score += type_score
    detail["opportunity_type"] = opp_type
    detail["type_score"] = type_score

    # Confiança da IA (0-8 pts)
    confidence = _get_attr(opp, "confidence") or 0.0
    if confidence >= 0.85:
        conf_score = 8
    elif confidence >= 0.75:
        conf_score = 5
    elif confidence >= 0.65:
        conf_score = 2
    else:
        conf_score = 0
    score += conf_score
    detail["confidence"] = confidence
    detail["confidence_score"] = conf_score

    # Sinais no texto da mensagem (0-5 pts)
    text = (_get_attr(opp, "original_message") or "").lower()
    text_signals = 0
    found_signals: List[str] = []

    urgency_words = ["urgente", "urgência", "despachar", "resolver rápido"]
    if any(w in text for w in urgency_words):
        text_signals += 2
        found_signals.append("urgencia")

    offmarket_words = ["off-market", "off market", "não está nos portais", "exclusivo", "não partilhar"]
    if any(w in text for w in offmarket_words):
        text_signals += 2
        found_signals.append("off_market")

    motivation_words = ["divórcio", "herança", "falecimento", "penhora", "insolvência", "dívida"]
    if any(w in text for w in motivation_words):
        text_signals += 2
        found_signals.append("motivacao_forte")

    negotiation_words = ["negociável", "negociaveis", "negociáveis", "aceita propostas", "valor mínimo"]
    if any(w in text for w in negotiation_words):
        text_signals += 1
        found_signals.append("negociavel")

    price_drop_words = ["baixa de preço", "baixa de valor", "novo preço", "novo valor", "preço reduzido", "redução"]
    if any(w in text for w in price_drop_words):
        text_signals += 1
        found_signals.append("baixa_preco")

    text_signals = min(text_signals, 5)  # cap a 5
    score += text_signals
    detail["text_signals"] = found_signals
    detail["text_score"] = text_signals

    return score, detail


def _score_financials(
    opp: Any, market: Any | None
) -> tuple[int, Dict[str, Any]]:
    """Avalia viabilidade financeira (0-15 pts)."""
    detail: Dict[str, Any] = {}
    price = _get_attr(opp, "price_mentioned")

    if not price or price <= 0:
        detail["reason"] = "sem_preco"
        return 0, detail

    score = 0

    # Faixa de preço acessível para investidor individual (0-5 pts)
    # Preços entre 50k-500k são mais acessíveis
    if 50_000 <= price <= 300_000:
        price_range_score = 5
        detail["faixa_preco"] = "acessivel"
    elif 300_000 < price <= 500_000:
        price_range_score = 3
        detail["faixa_preco"] = "media"
    elif price < 50_000:
        price_range_score = 2
        detail["faixa_preco"] = "muito_baixo"
    elif 500_000 < price <= 1_000_000:
        price_range_score = 1
        detail["faixa_preco"] = "alta"
    else:
        price_range_score = 0
        detail["faixa_preco"] = "institucional"
    score += price_range_score
    detail["price_range_score"] = price_range_score

    # Yield real (0-5 pts) — só se tiver dados de mercado reais para renda
    # O yield de 5% heurístico é circular, não conta
    if market:
        sir_pos = _get_attr(market, "sir_market_position")
        gross_yield = _get_attr(market, "gross_yield_pct")

        # Se temos posição SIR que confirma below-market, bonus
        if sir_pos in ("muito_abaixo", "abaixo"):
            score += 5
            detail["sir_bonus"] = True
            detail["sir_position"] = sir_pos

    # Preço por m2 razoável (0-5 pts)
    area = _get_attr(opp, "area_m2")
    if price and area and area > 0:
        price_m2 = price / area
        detail["price_m2"] = round(price_m2, 0)

        prop_type = (_get_attr(opp, "property_type") or "").lower()
        if prop_type in ("apartamento", "moradia"):
            # Residencial: preço/m2 < 2000€ é bom para Portugal
            if price_m2 < 1500:
                score += 5
            elif price_m2 < 2500:
                score += 3
            elif price_m2 < 3500:
                score += 1
        elif prop_type == "terreno":
            # Terreno: depende muito da zona, não penalizar
            if price_m2 < 50:
                score += 3
            elif price_m2 < 150:
                score += 1
        elif prop_type in ("armazém", "loja"):
            if price_m2 < 1000:
                score += 4
            elif price_m2 < 2000:
                score += 2

    return score, detail


def _score_red_flags(
    opp: Any, market: Any | None
) -> tuple[int, Dict[str, Any]]:
    """Deteta red flags e penaliza (-10 a 0 pts)."""
    penalty = 0
    flags: List[str] = []

    price = _get_attr(opp, "price_mentioned")
    area = _get_attr(opp, "area_m2")
    municipality = _get_attr(opp, "municipality")
    text = (_get_attr(opp, "original_message") or "").lower()

    # Sem preço E sem área = demasiado vago
    if not price and not area:
        penalty -= 3
        flags.append("sem_preco_nem_area")

    # Sem município = difícil comparar
    if not municipality:
        penalty -= 2
        flags.append("sem_municipio")

    # Preço muito acima do mercado (overpriced)
    if market:
        pvm = _get_attr(market, "price_vs_market_pct")
        if pvm and pvm > 150:
            prop_type = (_get_attr(opp, "property_type") or "").lower()
            # Só penalizar se temos dados fiáveis (não INE para terrenos)
            has_specific = any([
                _get_attr(market, "sir_median_price_m2"),
                _get_attr(market, "casafari_median_price_m2"),
                _get_attr(market, "infocasa_median_price_m2"),
            ])
            if has_specific or prop_type not in _NON_RESIDENTIAL_TYPES:
                penalty -= 3
                flags.append(f"acima_mercado_{pvm:.0f}pct")

    # Mensagem parece publicidade genérica (AMI + emojis abundantes + "partilha")
    ami_count = text.count("ami")
    emoji_heavy = sum(1 for c in text if ord(c) > 0x1F300) > 10
    if ami_count >= 1 and "partilha" in text and emoji_heavy:
        penalty -= 2
        flags.append("publicidade_generica")

    # Área irrealistamente grande para o preço (erro de parsing)
    if price and area and area > 10_000 and price < 1_000_000:
        price_m2 = price / area
        if price_m2 < 1:  # <1€/m2 = provavelmente erro
            penalty -= 3
            flags.append("area_irreal_para_preco")

    return penalty, {"flags": flags}


def _score_to_grade(score: int) -> str:
    """Converte score numérico em grade A-F."""
    if score >= 80:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 40:
        return "C"
    elif score >= 20:
        return "D"
    return "F"


def _get_attr(obj: Any, attr: str) -> Any:
    """Acede a atributo de objeto ou dict."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)


def rescore_all_opportunities() -> List[Dict[str, Any]]:
    """Re-pontua todas as oportunidades na BD.

    Returns:
        Lista de dicts com id, score, grade e breakdown.
    """
    from sqlalchemy import select, update

    from src.database.db import get_session
    from src.database.models import MarketData, Opportunity

    results: List[Dict[str, Any]] = []

    with get_session() as session:
        opps = session.execute(
            select(Opportunity).where(Opportunity.is_opportunity.is_(True))
        ).scalars().all()

        for opp in opps:
            market = session.execute(
                select(MarketData).where(MarketData.opportunity_id == opp.id)
            ).scalar_one_or_none()

            result = score_opportunity(opp, market)

            opp.deal_score = result.score
            opp.deal_grade = result.grade

            results.append({
                "id": opp.id,
                "score": result.score,
                "grade": result.grade,
                "municipality": opp.municipality,
                "price": opp.price_mentioned,
                "type": opp.opportunity_type,
                "breakdown": result.breakdown,
            })

        session.commit()

    results.sort(key=lambda r: r["score"], reverse=True)
    logger.info(
        f"Rescoring concluído: {len(results)} oportunidades. "
        f"A={sum(1 for r in results if r['grade'] == 'A')}, "
        f"B={sum(1 for r in results if r['grade'] == 'B')}, "
        f"C={sum(1 for r in results if r['grade'] == 'C')}, "
        f"D={sum(1 for r in results if r['grade'] == 'D')}, "
        f"F={sum(1 for r in results if r['grade'] == 'F')}"
    )
    return results
