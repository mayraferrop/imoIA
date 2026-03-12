#!/usr/bin/env python3
"""Launcher para o pipeline ImoScout via launchd.

Configura sys.path e loguru antes de chamar run_pipeline().
Grava estado em logs/pipeline_status.json para o dashboard.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Garantir que o projeto está no sys.path e que o CWD é o projeto
PROJECT_ROOT = str(Path(__file__).resolve().parent)
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from loguru import logger

# Configurar loguru para ficheiro + stderr
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(
    Path(PROJECT_ROOT) / "logs" / "pipeline_{time:YYYYMMDD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
)

STATUS_FILE = Path(PROJECT_ROOT) / "logs" / "pipeline_status.json"


def _write_status(state: str, **extra: object) -> None:
    """Grava estado do pipeline em JSON."""
    data = {"state": state, "timestamp": datetime.now().isoformat(), **extra}
    STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False))


def _notify(title: str, message: str) -> None:
    """Envia notificacao do macOS."""
    import subprocess
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}"',
    ], check=False)


from src.pipeline.run import run_pipeline

if __name__ == "__main__":
    logger.info("=== Launcher launchd iniciado ===")
    _write_status("a_correr")
    try:
        result = run_pipeline()
        logger.info(f"Resultado final: {result}")
        _write_status(
            "concluido",
            mensagens=result.messages_fetched,
            oportunidades=result.opportunities_found,
            grupos=result.groups_processed,
            erros=len(result.errors),
        )
        _notify(
            "ImoScout Pipeline",
            f"{result.opportunities_found} oportunidades | {result.groups_processed} grupos | {result.messages_fetched} msgs",
        )
    except Exception as e:
        logger.exception("Pipeline falhou")
        _write_status("erro", detalhe=str(e)[:200])
        _notify("ImoScout Pipeline ERRO", str(e)[:100])
