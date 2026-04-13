"""Construtor dinamico de system prompt para classificacao de oportunidades.

Monta o prompt a partir dos sinais configurados na estrategia ativa do
utilizador, permitindo criterios personalizados por tenant/utilizador.
Quando nao existe estrategia ativa, usa o SYSTEM_PROMPT hardcoded (fallback).

Migrado para Supabase REST (sem SQLAlchemy).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

# FIXME(jwt-refactor): migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'
from src.database import supabase_rest as db
from src.modules.m1_ingestor.prompts import SYSTEM_PROMPT

# Parte estrutural do prompt que NAO muda
_PROMPT_PREAMBLE = """Es um analista especializado em detetar oportunidades de investimento imobiliario em Portugal.

Recebes mensagens de grupos de WhatsApp de consultores, investidores e mediadores imobiliarios. A tua tarefa e classificar cada mensagem como oportunidade ou nao, e extrair dados relevantes.

## REGRA FUNDAMENTAL — So imoveis A VENDA
APENAS classifica como oportunidade mensagens de alguem que ESTA A VENDER ou PARTILHAR um imovel concreto. Ignora SEMPRE:
- Mensagens de quem PROCURA imoveis ("procuro", "procura-se", "estou a procura", "cliente procura", "procuramos")
- Pedidos genericos ("alguem tem?", "alguem conhece?", "alguem com cliente para isto?")
Estas mensagens sao PEDIDOS de compra, NAO ofertas de venda — nunca sao oportunidades.

## Modelo de Negocio do Utilizador
{business_model}"""

_PROMPT_SUFFIX = """
## Dados a Extrair
Para cada mensagem classificada como oportunidade, extrai:
- **location**: localizacao geral (texto livre)
- **parish**: freguesia (se mencionada)
- **municipality**: concelho
- **district**: distrito
- **price**: preco em euros (numero)
- **property_type**: tipo de imovel (apartamento, moradia, terreno, predio, loja, escritorio, armazem, quinta, outro)
- **typology**: tipologia (T0, T1, T2, T3, T4, T5+)
- **area_m2**: area em m2 (numero)
- **bedrooms**: numero de quartos (numero inteiro)
- **opportunity_type**: tipo de oportunidade (abaixo_mercado, venda_urgente, off_market, reabilitacao, leilao, predio_inteiro, terreno_viabilidade, yield_alto, outro)

## Regras de Confianca
- **> 0.8**: Dados concretos completos (preco + localizacao + tipologia/area) + sinais CLAROS de oportunidade
- **0.6 - 0.8**: Imovel interessante mas faltam alguns dados (sem preco, sem area, localizacao vaga) OU sinais moderados de oportunidade
- **< 0.6**: Faltam dados essenciais ou a mensagem e muito ambigua
- NUNCA dar confianca > 0.0 a mensagens de quem PROCURA imoveis

SE GENEROSO na classificacao de imoveis que se encaixam nos criterios — e melhor incluir uma oportunidade duvidosa (0.6) do que perder uma boa.

## Formato de Resposta
Responde APENAS com um array JSON valido. Cada elemento deve ter esta estrutura:
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
  "reasoning": <string com justificacao curta em portugues>
}
```

NAO incluas texto fora do JSON. NAO uses markdown code blocks. Responde APENAS com o array JSON."""


def _build_criteria_section(positive_signals: List[Dict[str, Any]]) -> str:
    """Constroi a seccao de criterios a partir dos sinais positivos."""
    if not positive_signals:
        return ""

    lines = [
        "\n## Criterios de Oportunidade",
        "Considera como oportunidade mensagens que OFERECAM para venda um imovel com pelo menos um destes sinais:",
    ]
    for s in positive_signals:
        lines.append(f"- {s['signal_text']}")
    return "\n".join(lines)


def _build_ignore_section(negative_signals: List[Dict[str, Any]]) -> str:
    """Constroi a seccao de exclusao a partir dos sinais negativos."""
    if not negative_signals:
        return ""

    lines = [
        "\n## O Que Ignorar (NAO e oportunidade)",
        "Estas mensagens NUNCA devem ser classificadas como oportunidade:",
    ]
    for s in negative_signals:
        lines.append(f"- {s['signal_text']}")
    return "\n".join(lines)


def build_system_prompt(tenant_id: Optional[str] = None) -> str:
    """Constroi o system prompt dinamico com base na estrategia ativa.

    Tenta Supabase REST primeiro. Se falhar, usa o prompt hardcoded.

    Args:
        tenant_id: ID do tenant. Se None ou sem estrategia ativa, usa fallback.

    Returns:
        System prompt completo para o classificador.
    """
    # Tentar buscar estrategia ativa via Supabase REST (funciona no Render)
    try:
        strategies = db.list_rows(
            "investment_strategies",
            filters="is_active=eq.true",
            order="created_at.desc",
            limit=1,
        )

        if not strategies:
            logger.debug("Sem estrategia ativa no Supabase — a usar prompt padrao")
            return SYSTEM_PROMPT

        strategy = strategies[0]

        # Buscar sinais desta estrategia
        signals = db.list_rows(
            "classification_signals",
            filters=f"strategy_id=eq.{strategy['id']}",
            order="priority.asc",
            limit=200,
        )

        positive = [s for s in signals if s.get("is_positive", True)]
        negative = [s for s in signals if not s.get("is_positive", True)]

        business_model = strategy.get("description") or "Investimento imobiliario em Portugal."

        prompt = _PROMPT_PREAMBLE.format(business_model=business_model)
        prompt += _build_criteria_section(positive)
        prompt += _build_ignore_section(negative)
        prompt += _PROMPT_SUFFIX

        logger.info(
            f"Prompt dinamico gerado: estrategia '{strategy['name']}', "
            f"{len(positive)} sinais positivos, {len(negative)} negativos"
        )
        return prompt

    except Exception as e:
        logger.warning(f"Supabase REST falhou para prompt builder: {e} — a usar prompt padrao")
        return SYSTEM_PROMPT
