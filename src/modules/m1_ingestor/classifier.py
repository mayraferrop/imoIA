"""Classificador de oportunidades imobiliárias com Claude Haiku.

Usa a API Anthropic para classificar mensagens de WhatsApp em batch,
detetando oportunidades de investimento imobiliário em Portugal.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import anthropic
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.modules.m1_ingestor.prompts import BATCH_TEMPLATE, SYSTEM_PROMPT
from src.modules.m1_ingestor.prompt_builder import build_system_prompt
from src.config import get_settings


@dataclass
class OpportunityResult:
    """Resultado da classificação de uma mensagem."""

    message_index: int
    is_opportunity: bool
    confidence: float
    opportunity_type: Optional[str]
    property_type: Optional[str]
    location: Optional[str]
    parish: Optional[str]
    municipality: Optional[str]
    district: Optional[str]
    price: Optional[float]
    area_m2: Optional[float]
    bedrooms: Optional[int]
    reasoning: str


class OpportunityClassifier:
    """Classificador de oportunidades usando Claude Haiku."""

    BATCH_SIZE = 20

    def __init__(
        self,
        client: Optional[anthropic.Anthropic] = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        """Inicializa o classificador.

        Args:
            client: Cliente Anthropic opcional (útil para testes).
            tenant_id: ID do tenant para carregar estratégia personalizada.
        """
        self._settings = get_settings()
        self._client = client or anthropic.Anthropic(
            api_key=self._settings.anthropic_api_key,
        )
        self._system_prompt = build_system_prompt(tenant_id)

    def classify_batch(self, messages: List[Dict[str, Any]]) -> List[OpportunityResult]:
        """Classifica um lote de mensagens.

        Args:
            messages: Lista de dicts com keys 'index', 'text', 'group'.

        Returns:
            Lista de OpportunityResult, um para cada mensagem.
        """
        if not messages:
            return []

        results: List[OpportunityResult] = []

        for i in range(0, len(messages), self.BATCH_SIZE):
            chunk = messages[i : i + self.BATCH_SIZE]
            chunk_results = self._classify_chunk(chunk)
            results.extend(chunk_results)

        return results

    @retry(
        retry=retry_if_exception_type(anthropic.RateLimitError),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(3),
        before_sleep=lambda retry_state: logger.warning(
            f"Rate limit atingido, a aguardar {retry_state.next_action.sleep}s (tentativa {retry_state.attempt_number})"
        ),
    )
    def _call_api(self, user_content: str) -> str:
        """Faz a chamada à API Anthropic com retry em rate limit.

        Args:
            user_content: Conteúdo da mensagem do utilizador.

        Returns:
            Texto da resposta do modelo.
        """
        response = self._client.messages.create(
            model=self._settings.ai_model,
            max_tokens=self._settings.ai_max_tokens,
            temperature=self._settings.ai_temperature,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text

    def _classify_chunk(self, chunk: List[Dict[str, Any]]) -> List[OpportunityResult]:
        """Classifica um chunk de mensagens (até BATCH_SIZE).

        Args:
            chunk: Lista de mensagens para classificar.

        Returns:
            Lista de OpportunityResult.
        """
        messages_for_prompt = [
            {"index": msg["index"], "text": msg["text"], "group": msg["group"]}
            for msg in chunk
        ]
        messages_json = json.dumps(messages_for_prompt, ensure_ascii=False, indent=2)
        user_content = BATCH_TEMPLATE.format(
            n=len(chunk), messages_json=messages_json
        )

        try:
            response_text = self._call_api(user_content)
            parsed = self._parse_response(response_text)
            return self._build_results(parsed, chunk)
        except Exception as e:
            logger.error(f"Erro ao classificar chunk: {e}")
            return self._build_fallback_results(chunk)

    def _parse_response(self, text: str) -> List[Dict[str, Any]]:
        """Faz parse da resposta JSON do modelo.

        Tenta parse direto e, se falhar, extrai JSON com regex.

        Args:
            text: Texto da resposta do modelo.

        Returns:
            Lista de dicionários com os resultados.
        """
        text = text.strip()

        # Remover markdown code blocks se presentes
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
            text = text.strip()

        # Tentar parse direto
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # Fallback: extrair array JSON com regex
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        logger.warning(f"Não foi possível fazer parse da resposta: {text[:200]}...")
        return []

    def _build_results(
        self, parsed: List[Dict[str, Any]], chunk: List[Dict[str, Any]]
    ) -> List[OpportunityResult]:
        """Constrói OpportunityResult a partir dos dados parseados.

        Args:
            parsed: Dados parseados da resposta da IA.
            chunk: Mensagens originais do chunk.

        Returns:
            Lista de OpportunityResult.
        """
        if not parsed:
            return self._build_fallback_results(chunk)

        results: List[OpportunityResult] = []
        parsed_by_index = {item.get("message_index", i): item for i, item in enumerate(parsed)}

        for msg in chunk:
            idx = msg["index"]
            item = parsed_by_index.get(idx)

            if item is None:
                results.append(self._fallback_result(idx))
                continue

            results.append(
                OpportunityResult(
                    message_index=idx,
                    is_opportunity=bool(item.get("is_opportunity", False)),
                    confidence=float(item.get("confidence", 0.0)),
                    opportunity_type=item.get("opportunity_type"),
                    property_type=item.get("property_type"),
                    location=item.get("location"),
                    parish=item.get("parish"),
                    municipality=item.get("municipality"),
                    district=item.get("district"),
                    price=_safe_float(item.get("price")),
                    area_m2=_safe_float(item.get("area_m2")),
                    bedrooms=_safe_int(item.get("bedrooms")),
                    reasoning=item.get("reasoning", "Sem justificação"),
                )
            )

        return results

    def _build_fallback_results(
        self, chunk: List[Dict[str, Any]]
    ) -> List[OpportunityResult]:
        """Cria resultados fallback quando o parse falha.

        Args:
            chunk: Mensagens originais.

        Returns:
            Lista de OpportunityResult com classificação neutra.
        """
        return [self._fallback_result(msg["index"]) for msg in chunk]

    @staticmethod
    def _fallback_result(index: int) -> OpportunityResult:
        """Cria um resultado fallback para uma mensagem.

        Args:
            index: Índice da mensagem.

        Returns:
            OpportunityResult com classificação neutra.
        """
        return OpportunityResult(
            message_index=index,
            is_opportunity=False,
            confidence=0.0,
            opportunity_type=None,
            property_type=None,
            location=None,
            parish=None,
            municipality=None,
            district=None,
            price=None,
            area_m2=None,
            bedrooms=None,
            reasoning="Erro no processamento — classificação indisponível",
        )


def _safe_float(value: Any) -> Optional[float]:
    """Converte um valor para float de forma segura."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """Converte um valor para int de forma segura."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
