#!/usr/bin/env bash
# Supervisor simples: roda um script Python do pipeline repetidamente,
# com timeout por tentativa, até ele completar sem timeout ou até
# atingir o número máximo de tentativas. Como todos os scripts do
# pipeline são resumíveis (checkpoint em CSV), reiniciar após um travamento
# apenas retoma de onde parou, sem perder trabalho já feito.
#
# Uso: scripts/supervisor.sh <script.py> [timeout_segundos] [max_tentativas]
set -uo pipefail

SCRIPT="$1"
TIMEOUT_S="${2:-600}"
MAX_TENTATIVAS="${3:-30}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$DIR"

for i in $(seq 1 "$MAX_TENTATIVAS"); do
  echo "[supervisor] Tentativa $i/$MAX_TENTATIVAS de $SCRIPT (timeout ${TIMEOUT_S}s)"
  DISPLAY=:0 timeout --signal=KILL "$TIMEOUT_S" .venv/bin/python "$SCRIPT"
  code=$?
  # mata qualquer processo chromium/playwright órfão remanescente
  pkill -f "playwright/driver" 2>/dev/null
  pkill -9 -f "chrome.*--disable-blink-features=AutomationControlled" 2>/dev/null
  sleep 2
  if [ "$code" -eq 0 ]; then
    echo "[supervisor] $SCRIPT terminou normalmente (exit 0)."
    exit 0
  fi
  echo "[supervisor] $SCRIPT saiu com código $code (provável timeout/travamento). Reiniciando..."
done

echo "[supervisor] Máximo de tentativas atingido sem conclusão limpa."
exit 1
