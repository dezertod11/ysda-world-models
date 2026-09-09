#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
RUN_BASE="${RUN_BASE:-recovery_outcome_router_diagnostic_videos_20260906}"
GPU_LIST="${P3E_DIAGNOSTIC_GPUS:-3,4}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_BASE"
PRIMARY="$PROJECT_ROOT/experiments/campaigns/recovery_outcome_router_holdout_20260906"
FREEZE_DIR="$PROJECT_ROOT/experiments/frozen_models/recovery_outcome_router_20260906"
MODEL_DIR="$PROJECT_ROOT/experiments/frozen_models/perception_regrasp_20260904"
MANIFEST_DIR="$CAMPAIGN_DIR/manifests"
RUN_DIR="$CAMPAIGN_DIR/runs"
STATUS_PATH="$CAMPAIGN_DIR/sequence_status.json"
HEARTBEAT_PATH="$CAMPAIGN_DIR/heartbeat.txt"
stage="starting"

IFS=',' read -r -a GPUS <<<"$GPU_LIST"
if ((${#GPUS[@]} != 2)); then
  echo "P3E_DIAGNOSTIC_GPUS must contain two comma-separated physical GPU ids" >&2
  exit 2
fi
for gpu in "${GPUS[@]}"; do
  if [[ "$gpu" == "0" ]]; then
    echo "GPU 0 is reserved and cannot be used" >&2
    exit 2
  fi
done

mkdir -p "$CAMPAIGN_DIR/logs" "$MANIFEST_DIR" "$RUN_DIR"

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
    write_status "completed" 0
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
  CUDA_VISIBLE_DEVICES="$gpu" \
    P3C_MANIFEST="$MANIFEST_DIR/diagnostic_cases.parquet" \
    P3C_POSITION_LEVEL="$position" \
    P3C_TASK_IDS="$tasks" \
    P3C_TRIGGER_ARTIFACT="$MODEL_DIR/perception_regrasp_trigger_v1.json" \
    P3C_TRIGGER_MODES=workspace_calibrated,workspace_retreat_only \
    P3C_PERCEPTION_MODEL="$MODEL_DIR/perception_regrasp_localizer.npz" \
    P3C_OUTPUT_DIR="$RUN_DIR" \
    P3C_RUN_NAME="${RUN_BASE}__${safe_position}" \
    P3C_BASE_SEED=20260906 \
    P3C_RESUME=1 \
    P3C_SAVE_VIDEOS=1 \
    bash "$SCRIPT_DIR/run_online_perception_regrasp_shard.sh"
}

heartbeat &
heartbeat_pid=$!
trap finish EXIT
write_status "running" 0
cd "$PROJECT_ROOT"

stage="freeze_manifest"
write_status "running" 0
test -s "$FREEZE_DIR/manifests/holdout_cases.parquet"
test -s "$MODEL_DIR/perception_regrasp_localizer.npz"
test -s "$MODEL_DIR/perception_regrasp_trigger_v1.json"
"$PYTHON_BIN" "$SCRIPT_DIR/build_recovery_outcome_router_diagnostic_manifest.py" \
  --source "$FREEZE_DIR/manifests/holdout_cases.parquet" \
  --output-dir "$MANIFEST_DIR"

stage="exact_replay_videos"
write_status "running" 0
run_shard x0.2 2 "${GPUS[0]}" >"$CAMPAIGN_DIR/logs/x0p2.log" 2>&1 &
pid_x=$!
run_shard y0.2 7,9 "${GPUS[1]}" >"$CAMPAIGN_DIR/logs/y0p2.log" 2>&1 &
pid_y=$!
failed=0
wait "$pid_x" || failed=1
wait "$pid_y" || failed=1
if ((failed)); then
  exit 1
fi

stage="validate_and_index"
write_status "running" 0
"$PYTHON_BIN" "$SCRIPT_DIR/index_recovery_outcome_router_diagnostic_videos.py" \
  --replay-dir "$RUN_DIR" \
  --primary-dir "$PRIMARY/runs/holdout" \
  --manifest "$MANIFEST_DIR/diagnostic_cases.parquet" \
  --output-dir "$CAMPAIGN_DIR/diagnostics"

stage="finished"
