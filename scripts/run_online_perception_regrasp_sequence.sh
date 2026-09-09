#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
GPU="${GPU:-6}"
RUN_BASE="${RUN_BASE:-perception_regrasp_online_trigger_20260904}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_BASE"
MANIFEST_DIR="$CAMPAIGN_DIR/manifests"
MODEL_DIR="$PROJECT_ROOT/experiments/frozen_models/perception_regrasp_20260904"
LOCALIZER="$MODEL_DIR/perception_regrasp_localizer.npz"
TRIGGER="$MODEL_DIR/perception_regrasp_trigger_v1.json"
STATUS_PATH="$CAMPAIGN_DIR/sequence_status.json"
HEARTBEAT_PATH="$CAMPAIGN_DIR/heartbeat.txt"
stage="starting"

mkdir -p "$CAMPAIGN_DIR" "$CAMPAIGN_DIR/logs"

write_status() {
  local state="$1"
  local code="$2"
  local temporary="$STATUS_PATH.tmp"
  printf '{\n  "run_base": "%s",\n  "status": "%s",\n  "stage": "%s",\n  "gpu": "%s",\n  "exit_code": %s,\n  "updated_at": "%s"\n}\n' \
    "$RUN_BASE" "$state" "$stage" "$GPU" "$code" "$(date --iso-8601=seconds)" >"$temporary"
  mv "$temporary" "$STATUS_PATH"
}

heartbeat() {
  while true; do
    printf '%s stage=%s pid=%s gpu=%s\n' "$(date --iso-8601=seconds)" "$stage" "$$" "$GPU" \
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
  local split="$1"
  local position="$2"
  local tasks="$3"
  local modes="$4"
  local safe_position="${position//./p}"
  local run_name="${RUN_BASE}__${split}__${safe_position}"
  local output_dir="$CAMPAIGN_DIR/runs/$split"
  mkdir -p "$output_dir"
  CUDA_VISIBLE_DEVICES="$GPU" \
    P3C_MANIFEST="$MANIFEST_DIR/${split}_cases.parquet" \
    P3C_POSITION_LEVEL="$position" \
    P3C_TASK_IDS="$tasks" \
    P3C_TRIGGER_ARTIFACT="$TRIGGER" \
    P3C_TRIGGER_MODES="$modes" \
    P3C_PERCEPTION_MODEL="$LOCALIZER" \
    P3C_OUTPUT_DIR="$output_dir" \
    P3C_RUN_NAME="$run_name" \
    P3C_RESUME=1 \
    P3C_SAVE_VIDEOS=0 \
    bash "$SCRIPT_DIR/run_online_perception_regrasp_shard.sh"
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
"$PYTHON_BIN" scripts/build_online_regrasp_cases.py --output-dir "$MANIFEST_DIR"
"$PYTHON_BIN" -m pytest -q \
  tests/test_perception_regrasp_trigger.py \
  tests/test_perception_regrasp.py

stage="screen_x0p2"
write_status "running" 0
run_shard screen x0.2 5 workspace_calibrated,global_conservative

stage="screen_y0p2"
write_status "running" 0
run_shard screen y0.2 4,6 workspace_calibrated,global_conservative

stage="analyze_screen"
write_status "running" 0
"$PYTHON_BIN" scripts/analyze_online_perception_regrasp.py \
  --campaign-dir "$CAMPAIGN_DIR/runs/screen" \
  --output-dir "$CAMPAIGN_DIR/analysis/screen" \
  --phase screen \
  --expected-cases 12 \
  --expected-strategies baseline_h8,workspace_calibrated,global_conservative \
  --require-gate
selected_method="$("$PYTHON_BIN" -c \
  "import json; print(json.load(open('$CAMPAIGN_DIR/analysis/screen/summary.json'))['recommended_method'])")"
printf '%s\n' "$selected_method" >"$CAMPAIGN_DIR/frozen_selected_method.txt"

stage="development_x0p2"
write_status "running" 0
run_shard development x0.2 5,6,9 "$selected_method"

stage="development_y0p2"
write_status "running" 0
run_shard development y0.2 4,6,9 "$selected_method"

stage="development_y0p3"
write_status "running" 0
run_shard development y0.3 1,5 "$selected_method"

stage="analyze_development"
write_status "running" 0
"$PYTHON_BIN" scripts/analyze_online_perception_regrasp.py \
  --campaign-dir "$CAMPAIGN_DIR/runs/development" \
  --output-dir "$CAMPAIGN_DIR/analysis/development" \
  --phase development \
  --expected-cases 40 \
  --expected-strategies "baseline_h8,$selected_method" \
  --require-gate

stage="holdout_x0p2"
write_status "running" 0
run_shard holdout x0.2 5,6,9 "$selected_method"

stage="holdout_y0p2"
write_status "running" 0
run_shard holdout y0.2 4,6,9 "$selected_method"

stage="holdout_y0p3"
write_status "running" 0
run_shard holdout y0.3 1,5 "$selected_method"

stage="analyze_holdout"
write_status "running" 0
"$PYTHON_BIN" scripts/analyze_online_perception_regrasp.py \
  --campaign-dir "$CAMPAIGN_DIR/runs/holdout" \
  --output-dir "$CAMPAIGN_DIR/analysis/holdout" \
  --phase holdout \
  --expected-cases 40 \
  --expected-strategies "baseline_h8,$selected_method" \
  --bootstrap-repetitions 10000

stage="finished"
write_status "completed" 0
