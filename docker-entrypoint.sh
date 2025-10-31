#!/bin/sh
set -e

if [ "${ENABLE_DEBUGPY:-0}" = "1" ]; then
  DEBUG_PORT="${DEBUGPY_PORT:-5678}"
  APP_PORT="${API__PORT:-8080}"
  DEBUG_ARGS="--listen 0.0.0.0:${DEBUG_PORT}"
  if [ "${WAIT_FOR_DEBUGGER:-0}" = "1" ]; then
    DEBUG_ARGS="${DEBUG_ARGS} --wait-for-client"
  fi
  exec python -m debugpy ${DEBUG_ARGS} -m uvicorn app.api:create_app --factory --host 0.0.0.0 --port "${APP_PORT}" --reload
fi

exec "$@"
