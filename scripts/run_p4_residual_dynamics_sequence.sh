#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
RUN_BASE="${RUN_BASE:-p4_residual_dynamics_20260906}"
ID_RUN="${P4_ID_RUN:-p4_standard_id_20260906}"
GPU_LIST="${P4_GPUS:-3,4,6,7}"
CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_BASE"
ID_CAMPAIGN="$PROJECT_ROOT/experiments/campaigns/$ID_RUN"
OOD_CAMPAIGN="$PROJECT_ROOT/experiments/campaigns/terminal_event_atlas_20260901"
CONFIG="$PROJECT_ROOT/experiments/configs/libero_campaign_p4_standard_id_20260906.json"
DATASET_DIR="$CAMPAIGN_DIR/dataset"
FEATURES="$DATASET_DIR/residual_dynamics_features.npz"
ARTIFACT_DIR="$PROJECT_ROOT/experiments/frozen_models/p4_residual_dynamics_20260906"
ANALYSIS_DIR="$CAMPAIGN_DIR/analysis"
STATUS_PATH="$CAMPAIGN_DIR/sequence_status.json"
HEARTBEAT_PATH="$CAMPAIGN_DIR/heartbeat.txt"
DIAGNOSTIC_DIR="$PROJECT_ROOT/experiments/campaigns/recovery_outcome_router_diagnostic_videos_20260906"
stage="starting"
final_status="completed"

IFS=',' read -r -a GPUS <<<"$GPU_LIST"
if ((${#GPUS[@]} != 4)); then
  echo "P4_GPUS must contain four comma-separated physical GPU ids" >&2
  exit 2
fi
for gpu in "${GPUS[@]}"; do
  if [[ "$gpu" == "0" ]]; then
    echo "GPU 0 is reserved and cannot be used" >&2
    exit 2
  fi
done
mkdir -p "$CAMPAIGN_DIR/logs" "$DATASET_DIR" "$ANALYSIS_DIR"

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

wait_for_diagnostics() {
  local diagnostic_status="$DIAGNOSTIC_DIR/sequence_status.json"
  if [[ -s "$diagnostic_status" ]]; then
    local state
    state="$($PYTHON_BIN -c "import json; print(json.load(open('$diagnostic_status'))['status'])")"
    while [[ "$state" == "running" ]]; do
      sleep 60
      state="$($PYTHON_BIN -c "import json; print(json.load(open('$diagnostic_status'))['status'])")"
    done
    if [[ "$state" != "completed" ]]; then
      echo "Diagnostic replay sequence ended with status=$state" >&2
      return 1
    fi
    return 0
  fi
  P3E_DIAGNOSTIC_GPUS="${GPUS[0]},${GPUS[1]}" \
    bash "$SCRIPT_DIR/run_recovery_outcome_router_diagnostic_videos.sh"
}

heartbeat &
heartbeat_pid=$!
trap finish EXIT
write_status "running" 0
cd "$PROJECT_ROOT"

stage="validate_protocol_and_code"
write_status "running" 0
test -s "$PROJECT_ROOT/experiments/P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md"
test -s "$CONFIG"
test -d "$OOD_CAMPAIGN"
"$PYTHON_BIN" -m pytest -q \
  tests/test_build_residual_dynamics_dataset.py \
  tests/test_extract_residual_dynamics_features.py \
  tests/test_residual_dynamics_ensemble.py \
  tests/test_analyze_residual_dynamics_ensemble.py \
  tests/test_p4_campaign_config.py \
  tests/test_recovery_outcome_router_diagnostic_videos.py

stage="diagnostic_replay_videos"
write_status "running" 0
wait_for_diagnostics

stage="collect_standard_libero_id"
write_status "running" 0
id_status=""
if [[ -s "$ID_CAMPAIGN/manifest.json" ]]; then
  id_status="$($PYTHON_BIN -c "import json; print(json.load(open('$ID_CAMPAIGN/manifest.json')).get('status',''))")"
fi
if [[ "$id_status" != "completed" ]]; then
  "$PYTHON_BIN" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
    --config "$CONFIG" \
    --profile p4_standard_id \
    --run-prefix "$ID_RUN" \
    --gpus "$GPU_LIST" \
    --execute
fi

stage="freeze_transition_manifest"
write_status "running" 0
if [[ ! -s "$DATASET_DIR/transition_manifest.parquet" ]]; then
  "$PYTHON_BIN" "$SCRIPT_DIR/build_residual_dynamics_dataset.py" \
    --campaign-dir "$ID_CAMPAIGN" \
    --campaign-dir "$OOD_CAMPAIGN" \
    --output-dir "$DATASET_DIR" \
    --split-salt p4-residual-dynamics-v1
fi
test -s "$DATASET_DIR/transition_manifest.parquet"
test -s "$DATASET_DIR/dataset.json"
test -s "$DATASET_DIR/split_counts.csv"

stage="extract_frozen_clip_features"
write_status "running" 0
if [[ ! -s "$FEATURES" ]]; then
  CUDA_VISIBLE_DEVICES="${GPUS[0]}" HF_HUB_OFFLINE=1 \
    "$PYTHON_BIN" "$SCRIPT_DIR/extract_residual_dynamics_features.py" \
    --manifest "$DATASET_DIR/transition_manifest.parquet" \
    --output "$FEATURES" \
    --device cuda \
    --row-batch-size 24
fi
test -s "$FEATURES"
test -s "${FEATURES%.npz}.json"

stage="train_independent_gaussian_heads"
write_status "running" 0
if [[ ! -s "$ARTIFACT_DIR/ensemble.json" ]]; then
  CUDA_VISIBLE_DEVICES="${GPUS[1]}" \
    "$PYTHON_BIN" "$SCRIPT_DIR/train_residual_dynamics_ensemble.py" \
    --manifest "$DATASET_DIR/transition_manifest.parquet" \
    --features "$FEATURES" \
    --output-dir "$ARTIFACT_DIR" \
    --num-heads 5 \
    --hidden-dim 256 \
    --input-visual-components 64 \
    --target-visual-components 64 \
    --epochs 120 \
    --seed 20260906 \
    --device cuda \
    --min-train-rows 400
fi
(cd "$ARTIFACT_DIR" && sha256sum -c SHA256SUMS)

stage="offline_conformal_analysis"
write_status "running" 0
CUDA_VISIBLE_DEVICES="${GPUS[2]}" \
  "$PYTHON_BIN" "$SCRIPT_DIR/analyze_residual_dynamics_ensemble.py" \
  --manifest "$DATASET_DIR/transition_manifest.parquet" \
  --features "$FEATURES" \
  --artifact-dir "$ARTIFACT_DIR" \
  --output-dir "$ANALYSIS_DIR" \
  --device cuda \
  --alpha 0.1 \
  --bootstrap-repetitions 1000
test -s "$ANALYSIS_DIR/summary.json"
test -s "$ANALYSIS_DIR/ood_detection_metrics.csv"
test -s "$ANALYSIS_DIR/conformal_alarm_rates.csv"

gate="$($PYTHON_BIN -c "import json; print(str(json.load(open('$ANALYSIS_DIR/summary.json'))['offline_gate_pass']).lower())")"
if [[ "$gate" == "true" ]]; then
  final_status="completed_pass"
else
  final_status="completed_no_go"
fi
stage="finished"
