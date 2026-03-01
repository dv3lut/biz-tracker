#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DEPLOY_HOST:-}" ]; then
  echo "DEPLOY_HOST must be set" >&2
  exit 1
fi

if [ -z "${DEPLOY_USER:-}" ]; then
  echo "DEPLOY_USER must be set" >&2
  exit 1
fi

if [ -z "${DEPLOY_PATH:-}" ]; then
  echo "DEPLOY_PATH must be set" >&2
  exit 1
fi

if [ -z "${API_IMAGE:-}" ]; then
  echo "API_IMAGE must be set" >&2
  exit 1
fi

# Copy project files to the remote host while skipping git metadata and local artifacts.
rsync -az --delete \
  --exclude ".git" \
  --exclude "logs" \
  --exclude "__pycache__" \
  --exclude ".env" \
  ./ "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/"

# Trigger a remote deployment using docker compose and the freshly published image.
ssh "${DEPLOY_USER}@${DEPLOY_HOST}" bash -s <<REMOTE_CMDS
set -euo pipefail
DEPLOY_PATH="${DEPLOY_PATH}"
API_IMAGE="${API_IMAGE}"
cd "\$DEPLOY_PATH"
if [ ! -f .env ]; then
  echo "Missing .env file in \$DEPLOY_PATH (copy it before deploying)." >&2
  exit 1
fi

API_IMAGE="\$API_IMAGE" docker compose pull api || true
API_IMAGE="\$API_IMAGE" docker compose up -d --remove-orphans
REMOTE_CMDS
