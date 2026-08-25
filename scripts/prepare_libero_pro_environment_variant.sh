#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"

NUM_INITS="${1:-50}"
SEED="${2:-20260825}"
OUTPUT_ROOT="${LIBERO_PRO_ENVIRONMENT_ROOT:-$PROJECT_ROOT/.runtime/libero_pro_environment}"
LOCK_PATH="$PROJECT_ROOT/.runtime/libero_pro_environment.lock"

mkdir -p "$PROJECT_ROOT/.runtime"
exec 9>"$LOCK_PATH"
flock 9

"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/materialize_libero_pro_environment.py" \
  --output-root "$OUTPUT_ROOT" \
  --num-inits "$NUM_INITS" \
  --seed "$SEED"
