#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONFIG="${LIBERO_8H_CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_8h.json}"
RUN_PREFIX="${LIBERO_8H_RUN_PREFIX:-libero_full_validation_$(date +%Y%m%d_%H%M%S)}"
GPUS="${LIBERO_8H_GPUS:-2,3,4,5,6,7}"
PYTHON="${LIBERO_8H_PYTHON:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing Cosmos environment: $PYTHON" >&2
  exit 2
fi

mkdir -p "$CAMPAIGN_DIR"
printf '%s\n' "$RUN_PREFIX" >"$PROJECT_ROOT/experiments/campaigns/LATEST_8H_RUN"

set +e
"$PYTHON" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$CONFIG" \
  --profile full_validation_8h \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPUS" \
  --execute
campaign_status=$?
set -e

echo "[8h] campaign runner exit status: $campaign_status"
echo "[8h] producing analysis from all complete and partial traces"
"$PYTHON" "$SCRIPT_DIR/analyze_libero_8h_validation.py" \
  --campaign-dir "$CAMPAIGN_DIR" \
  --output-dir "$CAMPAIGN_DIR/analysis/full_validation" || true

exit "$campaign_status"
