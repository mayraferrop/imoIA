#!/bin/bash
# ImoScout Pipeline Runner
# Executado pelo launchd às 9h e 13h

PROJECT_DIR="/Users/mayaraferro/Documents/GitHub/Opportunity Detector/imoscout"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/pipeline_${TIMESTAMP}.log"

cd "$PROJECT_DIR"

# Verificar se o bridge está a correr
if ! curl -s --max-time 5 http://localhost:3000/status | grep -q '"connected":true'; then
    echo "[$(date)] Bridge nao conectado, a ignorar execucao" >> "$LOG_FILE"
    exit 1
fi

echo "[$(date)] Pipeline iniciado" >> "$LOG_FILE"
/usr/bin/python3 -m src.pipeline.run >> "$LOG_FILE" 2>&1
echo "[$(date)] Pipeline concluido" >> "$LOG_FILE"

# Limpar logs com mais de 30 dias
find "$LOG_DIR" -name "pipeline_*.log" -mtime +30 -delete 2>/dev/null
