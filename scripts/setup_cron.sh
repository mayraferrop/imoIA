#!/bin/bash
# Configura cron job para executar o pipeline diariamente às 08:00.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Criar directório de logs se não existir
mkdir -p "$PROJECT_DIR/logs"

(crontab -l 2>/dev/null; echo "0 8 * * * cd $PROJECT_DIR && /usr/bin/python3 -m src.pipeline.run >> logs/pipeline.log 2>&1") | crontab -
echo "Cron job configurado: todos os dias às 08:00"
