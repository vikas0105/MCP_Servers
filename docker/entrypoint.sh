#!/usr/bin/env sh
set -eu

MODE="${1:-web}"

if [ "$MODE" = "web" ]; then
  exec uvicorn web_ui:app --app-dir /app/src --host 0.0.0.0 --port 8000
elif [ "$MODE" = "mcp" ]; then
  exec python /app/src/mcp_server.py
else
  echo "Unknown mode: $MODE (expected: web|mcp)" >&2
  exit 1
fi
