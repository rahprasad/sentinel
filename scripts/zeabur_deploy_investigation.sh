#!/usr/bin/env bash
# Deploy the investigation service to Zeabur.
#
# Prereqs:
#   1. `zeabur auth login` has been run (browser flow) OR
#      ZEABUR_TOKEN env var set + we'll auto-login below.
#   2. A Zeabur project already exists (where Postgres lives).
#
# What this does:
#   1. Find the project the user wants to deploy into.
#   2. Run `zeabur deploy` from apps/investigation/ with --create.
#   3. Set every env var from .env on the new service via `zeabur variable set`.
#   4. Print the service URL.

set -euo pipefail

cd "$(dirname "$0")/.."  # repo root

# ─── auth ────────────────────────────────────────────────────────────────────
if ! zeabur auth status 2>&1 | grep -q "Logged in"; then
  if [ -n "${ZEABUR_TOKEN:-}" ]; then
    echo "→ auth via ZEABUR_TOKEN"
    zeabur auth login --token "$ZEABUR_TOKEN"
  else
    echo "FAIL: not authenticated. Run \`zeabur auth login\` or export ZEABUR_TOKEN." >&2
    exit 2
  fi
fi

# ─── pick project ───────────────────────────────────────────────────────────
PROJECT_ID="${ZEABUR_PROJECT_ID:-}"
if [ -z "$PROJECT_ID" ]; then
  echo "→ available projects:"
  zeabur project list
  echo
  echo "FAIL: set ZEABUR_PROJECT_ID env var to the project containing your Postgres" >&2
  exit 3
fi
echo "→ project: $PROJECT_ID"

# ─── deploy investigation ───────────────────────────────────────────────────
SERVICE_NAME="${SERVICE_NAME:-sentinel-investigation}"
echo "→ deploying service: $SERVICE_NAME"

pushd apps/investigation >/dev/null
zeabur deploy \
  --create \
  --name "$SERVICE_NAME" \
  --project-id "$PROJECT_ID"
popd >/dev/null

# ─── push env vars ──────────────────────────────────────────────────────────
# Only the ones the investigation service actually reads.
RELEVANT_VARS=(
  DATABASE_URL
  TOKENROUTER_API_KEY
  TOKENROUTER_BASE_URL
  SYNTHESIZER_MODEL
  SYNTHESIZER_TEMPERATURE
  SYNTHESIZER_TIMEOUT_SECONDS
  AGENTFIELD_SERVER
  AGENT_CALLBACK_URL
  SANDBOX_URL
  WALKER_TIMEOUT_SECONDS
  FIXTURE_MODE
  LOG_LEVEL
  PYTHON_ENV
)

echo "→ pushing env vars to $SERVICE_NAME"
for var in "${RELEVANT_VARS[@]}"; do
  value=$(grep -E "^${var}=" .env | head -1 | cut -d'=' -f2- | sed -e 's/^"//' -e 's/"$//')
  if [ -z "$value" ]; then
    echo "    skip   $var (empty)"
    continue
  fi
  zeabur variable set \
    --project-id "$PROJECT_ID" \
    --service-name "$SERVICE_NAME" \
    --key "$var" \
    --value "$value" \
    >/dev/null
  echo "    set    $var"
done

echo
echo "✓ investigation service deployed. Check the dashboard for the public URL."
