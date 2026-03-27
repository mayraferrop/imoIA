"""Router para gestao de estrategias de investimento e sinais de classificacao.

Permite ao utilizador:
- Descrever a estrategia em linguagem natural -> IA sugere sinais
- CRUD de estrategias e sinais individuais
- Ativar/desativar estrategias

Migrado para Supabase REST (sem SQLAlchemy).
"""

from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

import anthropic
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src.config import get_settings
from src.database import supabase_rest as db

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
    """Retorna o tenant_id ativo. Cria um default se nao existir."""
    return db.ensure_tenant()


def _strategy_with_signals(row: dict) -> dict:
    """Monta StrategyOut a partir de uma row + sinais do Supabase."""
    signals = db.list_rows(
        "classification_signals",
        filters=f"strategy_id=eq.{row['id']}",
        order="priority.asc",
        limit=200,
    )
    return StrategyOut(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        is_active=row.get("is_active", False),
        signals=[
            SignalOut(
                id=s["id"],
                signal_text=s["signal_text"],
                signal_category=s.get("signal_category", "outro"),
                is_positive=s.get("is_positive", True),
                priority=s.get("priority", 1),
                is_ai_suggested=s.get("is_ai_suggested", False),
            )
            for s in signals
        ],
    ).model_dump()


# ---------------------------------------------------------------------------
# POST /suggest-signals — IA sugere sinais a partir da descricao
# ---------------------------------------------------------------------------

_SUGGEST_PROMPT = """Es um consultor de investimento imobiliario em Portugal.

O utilizador vai descrever a sua estrategia de investimento em linguagem natural.
Com base nisso, sugere 8 a 12 sinais de classificacao que devem ser usados para
identificar oportunidades relevantes em mensagens de grupos de WhatsApp.

Responde APENAS com um array JSON. Cada elemento:
{
  "signal_text": "<descricao do sinal em portugues de Portugal>",
  "signal_category": "<uma de: preco, urgencia, condicao, mercado, yield, legal, outro>",
  "is_positive": <true se e algo a PROCURAR, false se e algo a IGNORAR>,
  "priority": <int 1-12, 1 = mais importante>
}

Exemplos de sinais positivos (is_positive=true):
- "Preco abaixo do mercado (comparado com a zona) ou mencao a baixa de preco"
- "Venda urgente (divorcio, heranca, dacao em pagamento, penhora)"
- "Imovel para reabilitacao — que precise de obras, em mau estado, devoluto"
- "Imovel off-market (nao publicado em portais, exclusivo)"
- "Leilao ou venda judicial"

Exemplos de sinais negativos (is_positive=false):
- "Construcao nova, empreendimentos de promotores, imoveis em fase de obra"
- "Imoveis ja renovados vendidos a preco de mercado"
- "Ofertas de credito, seguros, ou servicos financeiros"
- "Arrendamentos puros sem dados de yield"

Adapta os sinais a estrategia descrita. Se o utilizador diz "fix and flip",
foca em sinais de imoveis com desconto e que precisem de obras.
Se diz "arrendamento", foca em yield e rentabilidade.

Inclui SEMPRE pelo menos 2-3 sinais negativos (coisas a ignorar).
Responde APENAS com o array JSON, sem texto adicional."""


@router.post("/suggest-signals")
async def suggest_signals(req: SuggestSignalsRequest) -> dict:
    """Usa IA para sugerir sinais de classificacao com base na estrategia descrita."""
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
        raise HTTPException(status_code=500, detail="Erro ao processar sugestoes da IA")
    except Exception as e:
        logger.error(f"Erro ao gerar sugestoes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# CRUD Estrategias
# ---------------------------------------------------------------------------


@router.get("")
async def list_strategies() -> list[dict]:
    """Lista todas as estrategias do tenant."""
    tenant_id = _get_tenant_id()
    rows = db.list_rows(
        "investment_strategies",
        filters=f"tenant_id=eq.{tenant_id}",
        order="created_at.desc",
        limit=100,
    )
    return [_strategy_with_signals(r) for r in rows]


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str) -> dict:
    """Obtem uma estrategia com os seus sinais."""
    row = db.get_by_id("investment_strategies", strategy_id)
    if not row:
        raise HTTPException(status_code=404, detail="Estrategia nao encontrada")
    return _strategy_with_signals(row)


@router.post("")
async def create_strategy(req: CreateStrategyRequest) -> dict:
    """Cria uma nova estrategia com sinais."""
    tenant_id = _get_tenant_id()

    # Se is_active, desativar as outras
    if req.is_active:
        db._patch(
            "investment_strategies",
            f"tenant_id=eq.{tenant_id}",
            {"is_active": False},
        )

    strategy_id = db.new_id()
    db.insert("investment_strategies", {
        "id": strategy_id,
        "tenant_id": tenant_id,
        "name": req.name,
        "description": req.description,
        "is_active": req.is_active,
    })

    # Adicionar sinais
    for s in req.signals:
        db.insert("classification_signals", {
            "id": s.get("id", db.new_id()),
            "strategy_id": strategy_id,
            "signal_text": s["signal_text"],
            "signal_category": s.get("signal_category", "outro"),
            "is_positive": s.get("is_positive", True),
            "priority": s.get("priority", 1),
            "is_ai_suggested": s.get("is_ai_suggested", False),
        })

    return {"id": strategy_id, "message": "Estrategia criada com sucesso"}


@router.put("/{strategy_id}")
async def update_strategy(strategy_id: str, req: UpdateStrategyRequest) -> dict:
    """Atualiza uma estrategia."""
    row = db.get_by_id("investment_strategies", strategy_id)
    if not row:
        raise HTTPException(status_code=404, detail="Estrategia nao encontrada")

    patch = {}
    if req.name is not None:
        patch["name"] = req.name
    if req.description is not None:
        patch["description"] = req.description
    if req.is_active is not None:
        if req.is_active:
            # Desativar outras do mesmo tenant
            db._patch(
                "investment_strategies",
                f"tenant_id=eq.{row['tenant_id']}&id=neq.{strategy_id}",
                {"is_active": False},
            )
        patch["is_active"] = req.is_active

    if patch:
        db.update("investment_strategies", strategy_id, patch)

    return {"message": "Estrategia atualizada"}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str) -> dict:
    """Remove uma estrategia e todos os seus sinais."""
    row = db.get_by_id("investment_strategies", strategy_id)
    if not row:
        raise HTTPException(status_code=404, detail="Estrategia nao encontrada")

    # Remover sinais primeiro (cascade manual)
    db.delete_by_filter("classification_signals", f"strategy_id=eq.{strategy_id}")
    db.delete_by_id("investment_strategies", strategy_id)
    return {"message": "Estrategia removida"}


@router.post("/{strategy_id}/activate")
async def activate_strategy(strategy_id: str) -> dict:
    """Ativa uma estrategia (desativa as outras do mesmo tenant)."""
    row = db.get_by_id("investment_strategies", strategy_id)
    if not row:
        raise HTTPException(status_code=404, detail="Estrategia nao encontrada")

    # Desativar todas do mesmo tenant
    db._patch(
        "investment_strategies",
        f"tenant_id=eq.{row['tenant_id']}",
        {"is_active": False},
    )
    # Ativar esta
    db.update("investment_strategies", strategy_id, {"is_active": True})
    return {"message": f"Estrategia '{row['name']}' ativada"}


# ---------------------------------------------------------------------------
# CRUD Sinais individuais
# ---------------------------------------------------------------------------


@router.post("/{strategy_id}/signals")
async def add_signal(strategy_id: str, req: AddSignalRequest) -> dict:
    """Adiciona um sinal a uma estrategia."""
    row = db.get_by_id("investment_strategies", strategy_id)
    if not row:
        raise HTTPException(status_code=404, detail="Estrategia nao encontrada")

    signal_id = db.new_id()
    db.insert("classification_signals", {
        "id": signal_id,
        "strategy_id": strategy_id,
        "signal_text": req.signal_text,
        "signal_category": req.signal_category,
        "is_positive": req.is_positive,
        "priority": req.priority,
        "is_ai_suggested": False,
    })
    return {"id": signal_id, "message": "Sinal adicionado"}


@router.put("/{strategy_id}/signals/{signal_id}")
async def update_signal(
    strategy_id: str, signal_id: str, req: UpdateSignalRequest
) -> dict:
    """Edita um sinal de uma estrategia."""
    signal = db.get_by_id("classification_signals", signal_id)
    if not signal or signal.get("strategy_id") != strategy_id:
        raise HTTPException(status_code=404, detail="Sinal nao encontrado")

    patch = {}
    if req.signal_text is not None:
        patch["signal_text"] = req.signal_text
    if req.signal_category is not None:
        patch["signal_category"] = req.signal_category
    if req.is_positive is not None:
        patch["is_positive"] = req.is_positive
    if req.priority is not None:
        patch["priority"] = req.priority

    if patch:
        db.update("classification_signals", signal_id, patch)

    return {"message": "Sinal atualizado"}


@router.delete("/{strategy_id}/signals/{signal_id}")
async def delete_signal(strategy_id: str, signal_id: str) -> dict:
    """Remove um sinal de uma estrategia."""
    signal = db.get_by_id("classification_signals", signal_id)
    if not signal or signal.get("strategy_id") != strategy_id:
        raise HTTPException(status_code=404, detail="Sinal nao encontrado")

    db.delete_by_id("classification_signals", signal_id)
    return {"message": "Sinal removido"}
