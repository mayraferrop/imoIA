"""Router para gestão de estratégias de investimento e sinais de classificação.

Permite ao utilizador:
- Descrever a estratégia em linguagem natural → IA sugere sinais
- CRUD de estratégias e sinais individuais
- Ativar/desativar estratégias
"""

from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

import anthropic
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from src.config import get_settings
from src.database.db import get_session
from src.database.models_v2 import (
    ClassificationSignal,
    InvestmentStrategy,
    Tenant,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------


class SignalOut(BaseModel):
    id: str
    signal_text: str
    signal_category: str
    is_positive: bool
    priority: int
    is_ai_suggested: bool


class StrategyOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_active: bool
    signals: list[SignalOut] = []


class SuggestSignalsRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=2000)


class SuggestSignalsResponse(BaseModel):
    signals: list[SignalOut]


class CreateStrategyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: bool = True
    signals: list[dict] = []


class UpdateStrategyRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AddSignalRequest(BaseModel):
    signal_text: str = Field(..., min_length=3)
    signal_category: str = "outro"
    is_positive: bool = True
    priority: int = 1


class UpdateSignalRequest(BaseModel):
    signal_text: Optional[str] = None
    signal_category: Optional[str] = None
    is_positive: Optional[bool] = None
    priority: Optional[int] = None


# ---------------------------------------------------------------------------
# Helper: obter tenant_id (single-tenant por agora)
# ---------------------------------------------------------------------------

def _get_tenant_id() -> str:
    """Retorna o tenant_id ativo. Cria um default se não existir."""
    with get_session() as session:
        tenant = session.execute(select(Tenant).limit(1)).scalar_one_or_none()
        if tenant:
            return tenant.id
        # Criar tenant default
        tid = str(uuid4())
        session.add(Tenant(id=tid, name="ImoIA", slug="default", country="PT"))
        session.flush()
        return tid


# ---------------------------------------------------------------------------
# POST /suggest-signals — IA sugere sinais a partir da descrição
# ---------------------------------------------------------------------------

_SUGGEST_PROMPT = """És um consultor de investimento imobiliário em Portugal.

O utilizador vai descrever a sua estratégia de investimento em linguagem natural.
Com base nisso, sugere 8 a 12 sinais de classificação que devem ser usados para
identificar oportunidades relevantes em mensagens de grupos de WhatsApp.

Responde APENAS com um array JSON. Cada elemento:
{
  "signal_text": "<descrição do sinal em português de Portugal>",
  "signal_category": "<uma de: preco, urgencia, condicao, mercado, yield, legal, outro>",
  "is_positive": <true se é algo a PROCURAR, false se é algo a IGNORAR>,
  "priority": <int 1-12, 1 = mais importante>
}

Exemplos de sinais positivos (is_positive=true):
- "Preço abaixo do mercado (comparado com a zona) ou menção a baixa de preço"
- "Venda urgente (divórcio, herança, dação em pagamento, penhora)"
- "Imóvel para reabilitação — que precise de obras, em mau estado, devoluto"
- "Imóvel off-market (não publicado em portais, exclusivo)"
- "Leilão ou venda judicial"

Exemplos de sinais negativos (is_positive=false):
- "Construção nova, empreendimentos de promotores, imóveis em fase de obra"
- "Imóveis já renovados vendidos a preço de mercado"
- "Ofertas de crédito, seguros, ou serviços financeiros"
- "Arrendamentos puros sem dados de yield"

Adapta os sinais à estratégia descrita. Se o utilizador diz "fix and flip",
foca em sinais de imóveis com desconto e que precisem de obras.
Se diz "arrendamento", foca em yield e rentabilidade.

Inclui SEMPRE pelo menos 2-3 sinais negativos (coisas a ignorar).
Responde APENAS com o array JSON, sem texto adicional."""


@router.post("/suggest-signals")
async def suggest_signals(req: SuggestSignalsRequest) -> dict:
    """Usa IA para sugerir sinais de classificação com base na estratégia descrita."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model=settings.ai_model,
            max_tokens=2000,
            temperature=0.3,
            system=_SUGGEST_PROMPT,
            messages=[{"role": "user", "content": req.description}],
        )
        text = response.content[0].text.strip()

        # Limpar markdown se presente
        if text.startswith("```"):
            import re
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
            text = text.strip()

        signals_data = json.loads(text)

        signals = []
        for s in signals_data:
            signals.append(SignalOut(
                id=str(uuid4()),
                signal_text=s["signal_text"],
                signal_category=s.get("signal_category", "outro"),
                is_positive=s.get("is_positive", True),
                priority=s.get("priority", 1),
                is_ai_suggested=True,
            ))

        return {"signals": [s.model_dump() for s in signals]}

    except json.JSONDecodeError as e:
        logger.error(f"Erro ao fazer parse da resposta IA: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar sugestões da IA")
    except Exception as e:
        logger.error(f"Erro ao gerar sugestões: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# CRUD Estratégias
# ---------------------------------------------------------------------------


@router.get("")
async def list_strategies() -> list[dict]:
    """Lista todas as estratégias do tenant."""
    tenant_id = _get_tenant_id()
    with get_session() as session:
        strategies = session.execute(
            select(InvestmentStrategy)
            .where(InvestmentStrategy.tenant_id == tenant_id)
            .order_by(InvestmentStrategy.created_at.desc())
        ).scalars().all()

        return [
            StrategyOut(
                id=s.id,
                name=s.name,
                description=s.description,
                is_active=s.is_active,
                signals=[
                    SignalOut(
                        id=sig.id,
                        signal_text=sig.signal_text,
                        signal_category=sig.signal_category,
                        is_positive=sig.is_positive,
                        priority=sig.priority,
                        is_ai_suggested=sig.is_ai_suggested,
                    )
                    for sig in s.signals
                ],
            ).model_dump()
            for s in strategies
        ]


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str) -> dict:
    """Obtém uma estratégia com os seus sinais."""
    with get_session() as session:
        strategy = session.get(InvestmentStrategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Estratégia não encontrada")

        return StrategyOut(
            id=strategy.id,
            name=strategy.name,
            description=strategy.description,
            is_active=strategy.is_active,
            signals=[
                SignalOut(
                    id=sig.id,
                    signal_text=sig.signal_text,
                    signal_category=sig.signal_category,
                    is_positive=sig.is_positive,
                    priority=sig.priority,
                    is_ai_suggested=sig.is_ai_suggested,
                )
                for sig in strategy.signals
            ],
        ).model_dump()


@router.post("")
async def create_strategy(req: CreateStrategyRequest) -> dict:
    """Cria uma nova estratégia com sinais."""
    tenant_id = _get_tenant_id()

    with get_session() as session:
        # Se is_active, desativar as outras
        if req.is_active:
            session.execute(
                update(InvestmentStrategy)
                .where(InvestmentStrategy.tenant_id == tenant_id)
                .values(is_active=False)
            )

        strategy = InvestmentStrategy(
            id=str(uuid4()),
            tenant_id=tenant_id,
            name=req.name,
            description=req.description,
            is_active=req.is_active,
        )
        session.add(strategy)
        session.flush()

        # Adicionar sinais
        for s in req.signals:
            signal = ClassificationSignal(
                id=s.get("id", str(uuid4())),
                strategy_id=strategy.id,
                signal_text=s["signal_text"],
                signal_category=s.get("signal_category", "outro"),
                is_positive=s.get("is_positive", True),
                priority=s.get("priority", 1),
                is_ai_suggested=s.get("is_ai_suggested", False),
            )
            session.add(signal)

        session.flush()

        return {"id": strategy.id, "message": "Estratégia criada com sucesso"}


@router.put("/{strategy_id}")
async def update_strategy(strategy_id: str, req: UpdateStrategyRequest) -> dict:
    """Atualiza uma estratégia."""
    with get_session() as session:
        strategy = session.get(InvestmentStrategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Estratégia não encontrada")

        if req.name is not None:
            strategy.name = req.name
        if req.description is not None:
            strategy.description = req.description
        if req.is_active is not None:
            if req.is_active:
                # Desativar outras do mesmo tenant
                session.execute(
                    update(InvestmentStrategy)
                    .where(
                        InvestmentStrategy.tenant_id == strategy.tenant_id,
                        InvestmentStrategy.id != strategy_id,
                    )
                    .values(is_active=False)
                )
            strategy.is_active = req.is_active

        session.flush()
        return {"message": "Estratégia atualizada"}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str) -> dict:
    """Remove uma estratégia e todos os seus sinais."""
    with get_session() as session:
        strategy = session.get(InvestmentStrategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Estratégia não encontrada")

        session.delete(strategy)
        session.flush()
        return {"message": "Estratégia removida"}


@router.post("/{strategy_id}/activate")
async def activate_strategy(strategy_id: str) -> dict:
    """Ativa uma estratégia (desativa as outras do mesmo tenant)."""
    with get_session() as session:
        strategy = session.get(InvestmentStrategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Estratégia não encontrada")

        session.execute(
            update(InvestmentStrategy)
            .where(InvestmentStrategy.tenant_id == strategy.tenant_id)
            .values(is_active=False)
        )
        strategy.is_active = True
        session.flush()
        return {"message": f"Estratégia '{strategy.name}' ativada"}


# ---------------------------------------------------------------------------
# CRUD Sinais individuais
# ---------------------------------------------------------------------------


@router.post("/{strategy_id}/signals")
async def add_signal(strategy_id: str, req: AddSignalRequest) -> dict:
    """Adiciona um sinal a uma estratégia."""
    with get_session() as session:
        strategy = session.get(InvestmentStrategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Estratégia não encontrada")

        signal = ClassificationSignal(
            id=str(uuid4()),
            strategy_id=strategy_id,
            signal_text=req.signal_text,
            signal_category=req.signal_category,
            is_positive=req.is_positive,
            priority=req.priority,
            is_ai_suggested=False,
        )
        session.add(signal)
        session.flush()
        return {"id": signal.id, "message": "Sinal adicionado"}


@router.put("/{strategy_id}/signals/{signal_id}")
async def update_signal(
    strategy_id: str, signal_id: str, req: UpdateSignalRequest
) -> dict:
    """Edita um sinal de uma estratégia."""
    with get_session() as session:
        signal = session.get(ClassificationSignal, signal_id)
        if not signal or signal.strategy_id != strategy_id:
            raise HTTPException(status_code=404, detail="Sinal não encontrado")

        if req.signal_text is not None:
            signal.signal_text = req.signal_text
        if req.signal_category is not None:
            signal.signal_category = req.signal_category
        if req.is_positive is not None:
            signal.is_positive = req.is_positive
        if req.priority is not None:
            signal.priority = req.priority

        session.flush()
        return {"message": "Sinal atualizado"}


@router.delete("/{strategy_id}/signals/{signal_id}")
async def delete_signal(strategy_id: str, signal_id: str) -> dict:
    """Remove um sinal de uma estratégia."""
    with get_session() as session:
        signal = session.get(ClassificationSignal, signal_id)
        if not signal or signal.strategy_id != strategy_id:
            raise HTTPException(status_code=404, detail="Sinal não encontrado")

        session.delete(signal)
        session.flush()
        return {"message": "Sinal removido"}
