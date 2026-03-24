"""Celery app para tarefas assincronas do ImoIA.

Usa Redis se configurado, senao filesystem broker (dev local).

Uso:
    celery -A src.worker worker --loglevel=info
"""

from __future__ import annotations

import os

from celery import Celery
from loguru import logger

# Usar Redis se disponivel, senao filesystem broker para dev local
_broker_url = os.getenv("REDIS_URL", "filesystem://")
_result_backend = os.getenv("REDIS_URL", "file:///tmp/celery-results")

celery_app = Celery(
    "imoia",
    broker=_broker_url,
    backend=_result_backend,
)

celery_app.conf.update(
    timezone=os.getenv("TIMEZONE", "Europe/Lisbon"),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    beat_schedule={
        "ingest-every-2h": {
            "task": "tasks.run_ingest_pipeline",
            "schedule": 7200.0,
        },
    },
)

# Configurar filesystem broker para dev (sem Redis)
if _broker_url == "filesystem://":
    import tempfile
    from pathlib import Path

    _broker_dir = Path(tempfile.gettempdir()) / "celery-broker"
    _broker_dir.mkdir(exist_ok=True)
    (_broker_dir / "out").mkdir(exist_ok=True)
    (_broker_dir / "processed").mkdir(exist_ok=True)

    celery_app.conf.update(
        broker_transport_options={
            "data_folder_in": str(_broker_dir / "out"),
            "data_folder_out": str(_broker_dir / "out"),
            "data_folder_processed": str(_broker_dir / "processed"),
        },
    )


@celery_app.task(name="tasks.run_ingest_pipeline")
def run_ingest_pipeline() -> dict:
    """Placeholder — pipeline de ingestao sera reimplementado nos modulos.

    O pipeline legacy (ImoScout) foi removido. A ingestao de novas propriedades
    deve ser feita via API (POST /api/v1/properties/) ou futura integracao directa.
    """
    logger.info("Pipeline de ingestao: a aguardar reimplementacao nos modulos")
    return {
        "status": "pendente_reimplementacao",
        "mensagem": "Pipeline legacy removido. Usar API para criar propriedades.",
    }
