#!/bin/bash
# ImoScout WhatsApp Bridge Starter
# Executado pelo launchd como serviço permanente

PROJECT_DIR="/Users/mayaraferro/Documents/GitHub/Opportunity Detector/imoscout"
BRIDGE_DIR="$PROJECT_DIR/whatsapp-bridge"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

cd "$BRIDGE_DIR"
exec /opt/homebrew/bin/node server.js >> "$LOG_DIR/bridge.log" 2>&1
