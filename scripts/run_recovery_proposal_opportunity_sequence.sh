#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
RUN_PREFIX="${RUN_PREFIX:-recovery_proposal_opportunity_20260904}"
GPU_LIST="${GPU_LIST:-2,3,4,6,7}"
CONFIG="${CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_recovery_proposal_opportunity_20260904.json}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_PREFIX"
STATUS_PATH="$CAMPAIGN_DIR/sequence_status.json"
HEARTBEAT_PATH="$CAMPAIGN_DIR/heartbeat.txt"
stage="starting"

mkdir -p "$CAMPAIGN_DIR"

write_status() {
  local state="$1"
  local code="$2"
  local temporary="$STATUS_PATH.tmp"
  printf '{\n  "run_prefix": "%s",\n  "status": "%s",\n  "stage": "%s",\n  "exit_code": %s,\n  "updated_at": "%s"\n}\n' \
    "$RUN_PREFIX" "$state" "$stage" "$code" "$(date --iso-8601=seconds)" >"$temporary"
  mv "$temporary" "$STATUS_PATH"
}

heartbeat() {
  while true; do
    printf '%s stage=%s pid=%s\n' "$(date --iso-8601=seconds)" "$stage" "$$" >"$HEARTBEAT_PATH.tmp"
    mv "$HEARTBEAT_PATH.tmp" "$HEARTBEAT_PATH"
    sleep 60
  done
}

finish() {
  local code=$?
  kill "$heartbeat_pid" 2>/dev/null || true
  wait "$heartbeat_pid" 2>/dev/null || true
  if ((code == 0)); then
    write_status "completed" 0
  else
    write_status "failed" "$code"
  fi
  exit "$code"
}

heartbeat &
heartbeat_pid=$!
trap finish EXIT
write_status "running" 0

stage="campaign"
write_status "running" 0
cd "$PROJECT_ROOT"
"$PYTHON_BIN" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile recovery_proposal_opportunity \
  --run-prefix "$RUN_PREFIX" \
  --gpus "$GPU_LIST" \
  --max-parallel 5 \
  --execute

stage="analysis"
write_status "running" 0
"$PYTHON_BIN" scripts/analyze_recovery_proposal_opportunity.py \
  --campaign-dir "$CAMPAIGN_DIR" \
  --output-dir "$CAMPAIGN_DIR/analysis" \
  --expected-states 80 \
  --bootstrap-repetitions 5000

stage="finished"
