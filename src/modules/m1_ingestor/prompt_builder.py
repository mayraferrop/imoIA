"""Construtor dinâmico de system prompt para classificação de oportunidades.

Monta o prompt a partir dos sinais configurados na estratégia ativa do
utilizador, permitindo critérios personalizados por tenant/utilizador.
Quando não existe estratégia ativa, usa o SYSTEM_PROMPT hardcoded (fallback).
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy import select

from src.database.db import get_session
from src.database.models_v2 import ClassificationSignal, InvestmentStrategy
from src.modules.m1_ingestor.prompts import SYSTEM_PROMPT

# Parte estrutural do prompt que NÃO muda — definição de papel, formato, extração
_PROMPT_PREAMBLE = """És um analista especializado em detetar oportunidades de investimento imobiliário em Portugal.

Recebes mensagens de grupos de WhatsApp de consultores, investidores e mediadores imobiliários. A tua tarefa é classificar cada mensagem como oportunidade ou não, e extrair dados relevantes.

## REGRA FUNDAMENTAL — Só imóveis À VENDA
APENAS classifica como oportunidade mensagens de alguém que ESTÁ A VENDER ou PARTILHAR um imóvel concreto. Ignora SEMPRE:
- Mensagens de quem PROCURA imóveis ("procuro", "procura-se", "estou à procura", "cliente procura", "procuramos")
- Pedidos genéricos ("alguém tem?", "alguém conhece?", "alguém com cliente para isto?")
Estas mensagens são PEDIDOS de compra, NÃO ofertas de venda — nunca são oportunidades.

## Modelo de Negócio do Utilizador
{business_model}"""

_PROMPT_SUFFIX = """
## Dados a Extrair
Para cada mensagem classificada como oportunidade, extrai:
- **location**: localização geral (texto livre)
- **parish**: freguesia (se mencionada)
- **municipality**: concelho
- **district**: distrito
- **price**: preço em euros (número)
- **property_type**: tipo de imóvel (apartamento, moradia, terreno, prédio, loja, escritório, armazém, quinta, outro)
- **typology**: tipologia (T0, T1, T2, T3, T4, T5+)
- **area_m2**: área em m2 (número)
- **bedrooms**: número de quartos (número inteiro)
- **opportunity_type**: tipo de oportunidade (abaixo_mercado, venda_urgente, off_market, reabilitacao, leilao, predio_inteiro, terreno_viabilidade, yield_alto, outro)

## Regras de Confiança
- **> 0.8**: Dados concretos completos (preço + localização + tipologia/área) + sinais CLAROS de oportunidade
- **0.6 - 0.8**: Imóvel interessante mas faltam alguns dados (sem preço, sem área, localização vaga) OU sinais moderados de oportunidade
- **< 0.6**: Faltam dados essenciais ou a mensagem é muito ambígua
- NUNCA dar confiança > 0.0 a mensagens de quem PROCURA imóveis

SÊ GENEROSO na classificação de imóveis que se encaixam nos critérios — é melhor incluir uma oportunidade duvidosa (0.6) do que perder uma boa.

## Formato de Resposta
Responde APENAS com um array JSON válido. Cada elemento deve ter esta estrutura:
```json
{
  "message_index": <int>,
  "is_opportunity": <bool>,
  "confidence": <float 0.0-1.0>,
  "opportunity_type": <string ou null>,
  "property_type": <string ou null>,
  "location": <string ou null>,
  "parish": <string ou null>,
  "municipality": <string ou null>,
  "district": <string ou null>,
  "price": <float ou null>,
  "area_m2": <float ou null>,
  "bedrooms": <int ou null>,
  "reasoning": <string com justificação curta em português>
}
```

NÃO incluas texto fora do JSON. NÃO uses markdown code blocks. Responde APENAS com o array JSON."""


def _build_criteria_section(positive_signals: list[ClassificationSignal]) -> str:
    """Constrói a secção de critérios a partir dos sinais positivos."""
    if not positive_signals:
        return ""

    lines = [
        "\n## Critérios de Oportunidade",
        "Considera como oportunidade mensagens que OFEREÇAM para venda um imóvel com pelo menos um destes sinais:",
    ]
    for s in positive_signals:
        lines.append(f"- {s.signal_text}")
    return "\n".join(lines)


def _build_ignore_section(negative_signals: list[ClassificationSignal]) -> str:
    """Constrói a secção de exclusão a partir dos sinais negativos."""
    if not negative_signals:
        return ""

    lines = [
        "\n## O Que Ignorar (NÃO é oportunidade)",
        "Estas mensagens NUNCA devem ser classificadas como oportunidade:",
    ]
    for s in negative_signals:
        lines.append(f"- {s.signal_text}")
    return "\n".join(lines)


def build_system_prompt(tenant_id: Optional[str] = None) -> str:
    """Constrói o system prompt dinâmico com base na estratégia ativa.

    Args:
        tenant_id: ID do tenant. Se None ou sem estratégia ativa, usa o prompt hardcoded.

    Returns:
        System prompt completo para o classificador.
    """
    if not tenant_id:
        return SYSTEM_PROMPT

    try:
        with get_session() as session:
            strategy = session.execute(
                select(InvestmentStrategy)
                .where(
                    InvestmentStrategy.tenant_id == tenant_id,
                    InvestmentStrategy.is_active.is_(True),
                )
                .limit(1)
            ).scalar_one_or_none()

            if not strategy:
                logger.debug(f"Sem estratégia ativa para tenant {tenant_id} — a usar prompt padrão")
                return SYSTEM_PROMPT

            # Separar sinais positivos e negativos
            positive = [s for s in strategy.signals if s.is_positive]
            negative = [s for s in strategy.signals if not s.is_positive]

            # Descrição do modelo de negócio do utilizador
            business_model = strategy.description or "Investimento imobiliário em Portugal."

            prompt = _PROMPT_PREAMBLE.format(business_model=business_model)
            prompt += _build_criteria_section(positive)
            prompt += _build_ignore_section(negative)
            prompt += _PROMPT_SUFFIX

            logger.info(
                f"Prompt dinâmico gerado para tenant {tenant_id}: "
                f"estratégia '{strategy.name}', {len(positive)} sinais positivos, {len(negative)} negativos"
            )
            return prompt

    except Exception as e:
        logger.error(f"Erro ao construir prompt dinâmico: {e} — a usar prompt padrão")
        return SYSTEM_PROMPT
