"""Avaliador automatico de criativos M7 via Claude Vision.

Envia cada criativo PNG ao Claude Haiku 4.5 para avaliacao de design,
recebendo score 1-10 e feedback estruturado em PT-PT.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# ---------------------------------------------------------------------------
# Prompt de avaliacao
# ---------------------------------------------------------------------------

_EVALUATION_PROMPT = """Analisa este criativo imobiliario para publicacao em redes sociais.

Contexto:
- Tipo: {creative_type}
- Dimensoes: {width}x{height}
- Titulo: {title}
- Preco: {price}
- Localizacao: {location}
- Brand: HABTA (imobiliaria premium em Portugal)

Avalia cada criterio de 1-10 e da feedback concreto em portugues de Portugal.

Responde APENAS com JSON valido (sem markdown, sem ```):
{{
  "score_global": <1-10>,
  "criterios": {{
    "legibilidade": {{
      "score": <1-10>,
      "feedback": "<texto curto>"
    }},
    "hierarquia_visual": {{
      "score": <1-10>,
      "feedback": "<texto curto>"
    }},
    "brand_consistency": {{
      "score": <1-10>,
      "feedback": "<texto curto>"
    }},
    "qualidade_foto": {{
      "score": <1-10>,
      "feedback": "<texto curto>"
    }},
    "contraste_texto_fundo": {{
      "score": <1-10>,
      "feedback": "<texto curto>"
    }},
    "cta_visibilidade": {{
      "score": <1-10>,
      "feedback": "<texto curto>"
    }}
  }},
  "pontos_fortes": ["<ponto 1>", "<ponto 2>"],
  "melhorias": ["<melhoria concreta 1>", "<melhoria concreta 2>", "<melhoria concreta 3>"],
  "publicavel": <true|false>
}}"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CreativeEvaluator:
    """Avalia criativos usando Claude Vision API."""

    def __init__(self, model: str = "claude-haiku-4-5"):
        self.model = model
        self._client = None

    @property
    def client(self):
        """Inicializa cliente Anthropic de forma lazy."""
        if self._client is None:
            from anthropic import Anthropic
            self._client = Anthropic()
        return self._client

    def evaluate_creative(
        self,
        image_path: str,
        creative_type: str,
        width: int,
        height: int,
        title: str = "",
        price: str = "",
        location: str = "",
    ) -> Dict[str, Any]:
        """Avalia um criativo PNG via Claude Vision.

        Parametros
        ----------
        image_path:
            Caminho para o ficheiro PNG.
        creative_type:
            Tipo (ig_post, ig_story, fb_post, property_card).
        width, height:
            Dimensoes do criativo.
        title, price, location:
            Dados contextuais para avaliacao.

        Retorna
        -------
        Dict com score_global, criterios, melhorias, publicavel.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Criativo nao encontrado: {image_path}")

        # Ler imagem e converter para base64
        image_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        media_type = "image/png" if path.suffix == ".png" else "image/jpeg"

        prompt = _EVALUATION_PROMPT.format(
            creative_type=creative_type,
            width=width,
            height=height,
            title=title,
            price=price,
            location=location,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )

            # Extrair texto da resposta
            text = next(
                (b.text for b in response.content if b.type == "text"), ""
            )

            # Parse JSON — remover markdown wrapping se presente
            clean_text = text.strip()
            if clean_text.startswith("```"):
                # Remover ```json e ``` finais
                lines = clean_text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                clean_text = "\n".join(lines)
            evaluation = json.loads(clean_text)
            evaluation["_meta"] = {
                "model": self.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "creative_type": creative_type,
                "image_path": str(image_path),
            }

            logger.info(
                f"Criativo avaliado: {creative_type} | "
                f"score={evaluation.get('score_global', '?')}/10 | "
                f"publicavel={evaluation.get('publicavel', '?')}"
            )
            return evaluation

        except json.JSONDecodeError as exc:
            logger.warning(f"Resposta nao e JSON valido: {exc}")
            return {
                "score_global": 0,
                "error": f"Parse error: {exc}",
                "raw_response": text[:500],
            }
        except Exception as exc:
            logger.error(f"Erro na avaliacao Vision: {exc}")
            return {
                "score_global": 0,
                "error": str(exc),
            }

    def evaluate_all_for_listing(
        self, listing_id: str
    ) -> List[Dict[str, Any]]:
        """Avalia todos os criativos de uma listing.

        Busca criativos da BD, avalia cada um via Vision, e guarda
        o feedback no template_data do criativo.

        Retorna lista de avaliacoes.
        """
        from sqlalchemy import select
        from src.database.db import get_session
        from src.database.models_v2 import ListingCreative, Document

        results = []

        with get_session() as session:
            creatives = session.execute(
                select(ListingCreative)
                .where(ListingCreative.listing_id == listing_id)
                .where(ListingCreative.document_id.isnot(None))
                .order_by(ListingCreative.created_at.desc())
            ).scalars().all()

            # Deduplicate: pegar o mais recente de cada tipo
            seen_types: set[str] = set()
            unique_creatives = []
            for c in creatives:
                if c.creative_type not in seen_types:
                    seen_types.add(c.creative_type)
                    unique_creatives.append(c)

            for c in unique_creatives:
                if c.creative_type == "flyer":
                    continue  # Flyer e PNG/PDF, skip

                doc = session.get(Document, c.document_id)
                if not doc or not Path(doc.file_path).exists():
                    logger.warning(
                        f"Ficheiro nao encontrado para {c.creative_type}: "
                        f"{doc.file_path if doc else 'N/A'}"
                    )
                    continue

                td = c.template_data or {}
                evaluation = self.evaluate_creative(
                    image_path=doc.file_path,
                    creative_type=c.creative_type,
                    width=c.width or 0,
                    height=c.height or 0,
                    title=td.get("title", ""),
                    price=td.get("price_formatted", ""),
                    location=td.get("location", ""),
                )

                # Guardar avaliacao no template_data
                if c.template_data is None:
                    c.template_data = {}
                c.template_data["ai_evaluation"] = evaluation
                session.flush()

                results.append({
                    "creative_id": c.id,
                    "creative_type": c.creative_type,
                    "evaluation": evaluation,
                })

        logger.info(
            f"Avaliacao completa: {len(results)} criativos para "
            f"listing {listing_id}"
        )
        return results

    def evaluate_all_listings(self) -> Dict[str, Any]:
        """Avalia criativos de TODAS as listings.

        Retorna resumo global.
        """
        from sqlalchemy import select, func
        from src.database.db import get_session
        from src.database.models_v2 import Listing

        with get_session() as session:
            listing_ids = session.execute(
                select(Listing.id).order_by(Listing.created_at.desc())
            ).scalars().all()

        all_results = []
        for lid in listing_ids:
            results = self.evaluate_all_for_listing(lid)
            all_results.extend(results)

        # Resumo
        scores = [
            r["evaluation"].get("score_global", 0)
            for r in all_results
            if r["evaluation"].get("score_global", 0) > 0
        ]
        publishable = sum(
            1 for r in all_results
            if r["evaluation"].get("publicavel", False)
        )

        summary = {
            "total_evaluated": len(all_results),
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "publishable": publishable,
            "not_publishable": len(all_results) - publishable,
            "results": all_results,
        }

        logger.info(
            f"Avaliacao global: {summary['total_evaluated']} criativos | "
            f"media={summary['average_score']}/10 | "
            f"publicaveis={summary['publishable']}"
        )
        return summary
