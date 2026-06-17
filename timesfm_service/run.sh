#!/usr/bin/env bash
# Start the TimesFM microservice in the dedicated venv.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$WORKSPACE_ROOT/timesfm/venv"
PYTHON="$VENV/bin/python"

export TIMESFM_DEVICE="${TIMESFM_DEVICE:-cuda}"
export HF_HUB_DISABLE_SYMLINKS_WARNING=1

# Load optional .env with TIMESFM_API_KEY
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
  set +a
fi

cd "$WORKSPACE_ROOT"
exec "$PYTHON" -m uvicorn timesfm_service.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8001}" --log-level info
