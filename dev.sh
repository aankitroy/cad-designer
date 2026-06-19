#!/usr/bin/env bash
set -e

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "warning: ANTHROPIC_API_KEY is not set — chat edits will fail until it is." >&2
fi

( cd engine && .venv/bin/uvicorn app.main:app --reload --port 8000 ) &
ENGINE_PID=$!
( cd web && npm run dev ) &
WEB_PID=$!

trap 'kill $ENGINE_PID $WEB_PID 2>/dev/null' EXIT
wait
