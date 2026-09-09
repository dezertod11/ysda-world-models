#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
RUN_BASE="${CONSENSUS_RUN_BASE:-consensus_medoid_pre_p5_20260907}"
GPU_LIST="${CONSENSUS_GPUS:-2,3,4}"
GPU_MAX_USED_MIB="${CONSENSUS_GPU_MAX_USED_MIB:-256}"
GPU_STABLE_POLLS="${CONSENSUS_GPU_STABLE_POLLS:-2}"
POLL_SECONDS="${CONSENSUS_POLL_SECONDS:-60}"
CONFIG="$PROJECT_ROOT/experiments/configs/libero_campaign_consensus_medoid_pre_p5_20260907.json"
SEQUENCE_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_BASE"
STATUS_PATH="$SEQUENCE_DIR/sequence_status.json"
HEARTBEAT_PATH="$SEQUENCE_DIR/heartbeat.txt"
stage="starting"

source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"

IFS=',' read -r -a GPUS <<<"$GPU_LIST"
if ((${#GPUS[@]} != 3)); then
  echo "CONSENSUS_GPUS must contain three comma-separated physical GPU ids" >&2
  exit 2
fi
for gpu in "${GPUS[@]}"; do
  gpu="${gpu//[[:space:]]/}"
  if [[ "$gpu" == "0" || "$gpu" == "1" ]]; then
    echo "Long consensus jobs may use only physical GPUs 2-7" >&2
    exit 2
  fi
done
mkdir -p "$SEQUENCE_DIR/logs"

write_status() {
  local state="$1"
  local code="$2"
  printf '{\n  "run_base": "%s",\n  "status": "%s",\n  "stage": "%s",\n  "gpus": "%s",\n  "exit_code": %s,\n  "updated_at": "%s"\n}\n' \
    "$RUN_BASE" "$state" "$stage" "$GPU_LIST" "$code" "$(date --iso-8601=seconds)" \
    >"$STATUS_PATH.tmp"
  mv "$STATUS_PATH.tmp" "$STATUS_PATH"
}

heartbeat() {
  while true; do
    local current_stage
    current_stage="$(awk -F'"' '/"stage":/ {print $4; exit}' "$STATUS_PATH" 2>/dev/null || true)"
    printf '%s pid=%s stage=%s gpus=%s\n' \
      "$(date --iso-8601=seconds)" "$$" "${current_stage:-unknown}" "$GPU_LIST" \
      >"$HEARTBEAT_PATH.tmp"
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

gpus_have_capacity() {
  local snapshot="$1"
  local gpu
  for gpu in "${GPUS[@]}"; do
    gpu="${gpu//[[:space:]]/}"
    local used
    used="$(awk -F',' -v target="$gpu" '
      {gsub(/ /, "", $1); gsub(/ /, "", $2); if ($1 == target) print $2}
    ' <<<"$snapshot")"
    if [[ -z "$used" || "$used" -gt "$GPU_MAX_USED_MIB" ]]; then
      return 1
    fi
  done
}

wait_for_gpus() {
  local stable=0
  while ((stable < GPU_STABLE_POLLS)); do
    local snapshot
    snapshot="$(nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits)"
    if gpus_have_capacity "$snapshot"; then
      stable=$((stable + 1))
      echo "[consensus] GPU capacity check $stable/$GPU_STABLE_POLLS passed"
    else
      stable=0
      echo "[consensus] waiting for GPUs $GPU_LIST"
      echo "$snapshot"
    fi
    if ((stable < GPU_STABLE_POLLS)); then
      sleep "$POLL_SECONDS"
    fi
  done
}

run_campaign() {
  local profile="$1"
  local run_prefix="$2"
  local manifest="$PROJECT_ROOT/experiments/campaigns/$run_prefix/manifest.json"
  local status=""
  if [[ -s "$manifest" ]]; then
    status="$($PYTHON_BIN -c "import json; print(json.load(open('$manifest')).get('status',''))")"
  fi
  if [[ "$status" != "completed" ]]; then
    "$PYTHON_BIN" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
      --config "$CONFIG" \
      --profile "$profile" \
      --run-prefix "$run_prefix" \
      --gpus "$GPU_LIST" \
      --execute
  fi
  "$PYTHON_BIN" "$SCRIPT_DIR/analyze_consensus_medoid_campaign.py" \
    --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$run_prefix"
}

heartbeat &
heartbeat_pid=$!
trap finish EXIT
write_status "running" 0
cd "$PROJECT_ROOT"

stage="validate_implementation"
write_status "running" 0
test -s "$CONFIG"
test -s "$PROJECT_ROOT/experiments/CONSENSUS_MEDOID_PRE_P5_PROTOCOL_20260907.md"
(cd "$PROJECT_ROOT/cosmos-policy" && "$PYTHON_BIN" -m pytest -q \
  tests/test_consensus_medoid.py tests/test_planning_selection.py)
"$PYTHON_BIN" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$CONFIG" \
  --profile consensus_medoid_exact_smoke \
  --run-prefix "${RUN_BASE}__dryrun" \
  --gpus "$GPU_LIST"

stage="wait_for_gpu_capacity"
write_status "running" 0
wait_for_gpus

stage="exact_method_smoke"
write_status "running" 0
run_campaign consensus_medoid_exact_smoke "${RUN_BASE}__exact_smoke"

stage="exact_method_40_paired_rollouts"
write_status "running" 0
run_campaign consensus_medoid_exact_development "${RUN_BASE}__exact_development"

stage="architecture_method_smoke"
write_status "running" 0
run_campaign cosmos_consensus_architecture_smoke "${RUN_BASE}__architecture_smoke"

stage="architecture_method_20_paired_rollouts"
write_status "running" 0
run_campaign cosmos_consensus_architecture_development "${RUN_BASE}__architecture_development"

stage="complete"
write_status "running" 0
echo "[consensus] all pre-P5 stages completed"
