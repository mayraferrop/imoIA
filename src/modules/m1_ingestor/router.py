"""Router FastAPI para o modulo M1 (Ingestor).

Expoe o pipeline de ingestao WhatsApp como endpoints REST.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks
from loguru import logger

router = APIRouter()


@router.post("/trigger", summary="Disparar pipeline de ingestao")
def trigger_pipeline(background_tasks: BackgroundTasks) -> Dict[str, str]:
    """Dispara o pipeline de ingestao em background."""
    from src.modules.m1_ingestor.service import run_pipeline

    background_tasks.add_task(run_pipeline)
    logger.info("Pipeline M1 disparado via API")
    return {
        "status": "pipeline_iniciado",
        "mensagem": "Pipeline a correr em background",
    }
