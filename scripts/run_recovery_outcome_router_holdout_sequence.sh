#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
RUN_BASE="${RUN_BASE:-recovery_outcome_router_holdout_20260906}"
GPU_LIST="${P3E_GPUS:-2,3,4,5}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_BASE"
FREEZE_DIR="$PROJECT_ROOT/experiments/frozen_models/recovery_outcome_router_20260906"
MANIFEST_DIR="$CAMPAIGN_DIR/manifests"
MODEL_DIR="$PROJECT_ROOT/experiments/frozen_models/perception_regrasp_20260904"
LOCALIZER="$MODEL_DIR/perception_regrasp_localizer.npz"
TRIGGER="$MODEL_DIR/perception_regrasp_trigger_v1.json"
ROUTER="$FREEZE_DIR/recovery_outcome_router_v1.json"
STATUS_PATH="$CAMPAIGN_DIR/sequence_status.json"
HEARTBEAT_PATH="$CAMPAIGN_DIR/heartbeat.txt"
stage="starting"
final_status="completed"

IFS=',' read -r -a GPUS <<<"$GPU_LIST"
if ((${#GPUS[@]} != 4)); then
  echo "P3E_GPUS must contain four comma-separated physical GPU ids" >&2
  exit 2
fi
for gpu in "${GPUS[@]}"; do
  if [[ "$gpu" == "0" ]]; then
    echo "GPU 0 is reserved and cannot be used" >&2
    exit 2
  fi
done

mkdir -p "$CAMPAIGN_DIR/logs" "$MANIFEST_DIR"

write_status() {
  local state="$1"
  local code="$2"
  local temporary="$STATUS_PATH.tmp"
  printf '{\n  "run_base": "%s",\n  "status": "%s",\n  "stage": "%s",\n  "gpus": "%s",\n  "exit_code": %s,\n  "updated_at": "%s"\n}\n' \
    "$RUN_BASE" "$state" "$stage" "$GPU_LIST" "$code" "$(date --iso-8601=seconds)" \
    >"$temporary"
  mv "$temporary" "$STATUS_PATH"
}

heartbeat() {
  while true; do
    printf '%s pid=%s gpus=%s\n' "$(date --iso-8601=seconds)" "$$" "$GPU_LIST" \
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
    write_status "$final_status" 0
  else
    write_status "failed" "$code"
  fi
  exit "$code"
}

run_shard() {
  local position="$1"
  local tasks="$2"
  local gpu="$3"
  local safe_position="${position//./p}"
  local run_name="${RUN_BASE}__holdout__${safe_position}"
  local output_dir="$CAMPAIGN_DIR/runs/holdout"
  mkdir -p "$output_dir"
  CUDA_VISIBLE_DEVICES="$gpu" \
    P3C_MANIFEST="$MANIFEST_DIR/holdout_cases.parquet" \
    P3C_POSITION_LEVEL="$position" \
    P3C_TASK_IDS="$tasks" \
    P3C_TRIGGER_ARTIFACT="$TRIGGER" \
    P3C_TRIGGER_MODES=workspace_calibrated,workspace_retreat_only \
    P3C_PERCEPTION_MODEL="$LOCALIZER" \
    P3C_OUTPUT_DIR="$output_dir" \
    P3C_RUN_NAME="$run_name" \
    P3C_BASE_SEED=20260906 \
    P3C_RESUME=1 \
    P3C_SAVE_VIDEOS=0 \
    bash "$SCRIPT_DIR/run_online_perception_regrasp_shard.sh"
}

run_holdout() {
  local pids=()
  local labels=()
  local specs=(
    "x0.2|2,5,6,9|${GPUS[0]}"
    "y0.1|4,6,8,9|${GPUS[1]}"
    "y0.2|4,6,7,8,9|${GPUS[2]}"
    "y0.3|1,5|${GPUS[3]}"
  )
  for spec in "${specs[@]}"; do
    IFS='|' read -r position tasks gpu <<<"$spec"
    local safe_position="${position//./p}"
    run_shard "$position" "$tasks" "$gpu" \
      >"$CAMPAIGN_DIR/logs/holdout_${safe_position}.log" 2>&1 &
    pids+=("$!")
    labels+=("$position/gpu$gpu")
  done
  local failed=0
  for index in "${!pids[@]}"; do
    if ! wait "${pids[$index]}"; then
      echo "Shard failed: ${labels[$index]}" >&2
      failed=1
    fi
  done
  if ((failed)); then
    return 1
  fi
}

heartbeat &
heartbeat_pid=$!
trap finish EXIT
write_status "running" 0
cd "$PROJECT_ROOT"

stage="validate_frozen_inputs"
write_status "running" 0
test -s "$LOCALIZER"
test -s "$TRIGGER"
test -s "$ROUTER"
test -s "$FREEZE_DIR/manifests/holdout_cases.parquet"
(cd "$FREEZE_DIR" && sha256sum -c SHA256SUMS)
cp "$FREEZE_DIR/manifests/holdout_cases.csv" "$MANIFEST_DIR/"
cp "$FREEZE_DIR/manifests/holdout_cases.parquet" "$MANIFEST_DIR/"
cp "$FREEZE_DIR/manifests/manifest.json" "$MANIFEST_DIR/"
"$PYTHON_BIN" -m pytest -q \
  tests/test_recovery_outcome_router.py \
  tests/test_recovery_outcome_router_analysis.py \
  tests/test_perception_regrasp_trigger.py \
  tests/test_online_regrasp_transfer_cases.py \
  tests/test_perception_regrasp.py

stage="holdout_four_gpu"
write_status "running" 0
run_holdout

stage="analyze_holdout"
write_status "running" 0
"$PYTHON_BIN" scripts/analyze_recovery_outcome_router_holdout.py \
  --campaign-dir "$CAMPAIGN_DIR/runs/holdout" \
  --router-artifact "$ROUTER" \
  --output-dir "$CAMPAIGN_DIR/analysis/holdout" \
  --expected-cases 75

holdout_gate="$("$PYTHON_BIN" -c \
  "import json; print(str(json.load(open('$CAMPAIGN_DIR/analysis/holdout/summary.json'))['holdout_gate_pass']).lower())")"
if [[ "$holdout_gate" == "true" ]]; then
  final_status="completed_pass"
else
  final_status="completed_no_go"
fi
stage="finished"
