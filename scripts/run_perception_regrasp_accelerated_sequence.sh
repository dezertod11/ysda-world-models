#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
GPU_LIST="${GPU_LIST:-3,6,7}"
REUSE_OOF_FOLDS="${REUSE_OOF_FOLDS:-0}"
CONFIG="${CONFIG:-$PROJECT_ROOT/experiments/configs/libero_campaign_perception_regrasp_20260904.json}"
RUN_BASE="${RUN_BASE:-perception_regrasp_accelerated_20260904}"
CALIBRATION_RUN="${CALIBRATION_RUN:-${RUN_BASE}__calibration}"
SCREEN_RUN="${RUN_BASE}__screen20"
DEVELOPMENT_RUN="${RUN_BASE}__development80"
RESERVE_RUN="${RUN_BASE}__reserve72"
MODEL_DIR="$PROJECT_ROOT/experiments/frozen_models/perception_regrasp_20260904"
MODEL_PATH="$MODEL_DIR/perception_regrasp_localizer.npz"
DEVELOPMENT_MANIFEST="$PROJECT_ROOT/experiments/campaigns/recovery_proposal_opportunity_20260904/frozen_development_manifest.parquet"
RESERVE_MANIFEST="$PROJECT_ROOT/experiments/campaigns/recovery_proposal_opportunity_20260904/frozen_untouched_reserve_manifest.parquet"
STRICT_RESERVE_MANIFEST="$PROJECT_ROOT/experiments/campaigns/recovery_proposal_opportunity_20260904/frozen_strict_group_reserve_manifest.parquet"
SEQUENCE_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_BASE"
STATUS_PATH="$SEQUENCE_DIR/sequence_status.json"
HEARTBEAT_PATH="$SEQUENCE_DIR/heartbeat.txt"
stage="starting"

mkdir -p "$SEQUENCE_DIR" "$MODEL_DIR"

write_status() {
  local state="$1"
  local code="$2"
  local temporary="$STATUS_PATH.tmp"
  printf '{\n  "run_base": "%s",\n  "status": "%s",\n  "stage": "%s",\n  "exit_code": %s,\n  "updated_at": "%s"\n}\n' \
    "$RUN_BASE" "$state" "$stage" "$code" "$(date --iso-8601=seconds)" >"$temporary"
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

first_gpu="${GPU_LIST%%,*}"
heartbeat &
heartbeat_pid=$!
trap finish EXIT
write_status "running" 0
cd "$PROJECT_ROOT"

stage="freeze_calibration_manifest"
write_status "running" 0
"$PYTHON_BIN" scripts/build_strict_group_reserve.py \
  --reserve "$RESERVE_MANIFEST" \
  --development "$DEVELOPMENT_MANIFEST" \
  --output "$STRICT_RESERVE_MANIFEST"
"$PYTHON_BIN" scripts/build_perception_regrasp_manifest.py \
  --source experiments/campaigns/object_contact_vof_development_20260903/analysis/object_contact_development_corpus.parquet \
  --exclude "$DEVELOPMENT_MANIFEST" \
  --exclude "$RESERVE_MANIFEST" \
  --output "$MODEL_DIR/calibration_manifest.parquet" \
  --per-cell 0 \
  --seed 20260904

stage="collect_rgb_calibration"
write_status "running" 0
"$PYTHON_BIN" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile calibration \
  --run-prefix "$CALIBRATION_RUN" \
  --gpus "$GPU_LIST" \
  --max-parallel 3 \
  --execute

stage="fit_grouped_oof_heatmap_folds"
write_status "running" 0
IFS=',' read -r -a gpu_array <<<"$GPU_LIST"
if [[ "$REUSE_OOF_FOLDS" == 1 ]]; then
  for fold in 0 1 2; do
    test -s "$MODEL_DIR/heatmap_fold_${fold}_predictions.csv"
  done
else
  fold_pids=()
  for fold in 0 1 2; do
    gpu="${gpu_array[$((fold % ${#gpu_array[@]}))]}"
    CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON_BIN" scripts/train_perception_regrasp_heatmap.py \
      --mode fold \
      --fold "$fold" \
      --folds 3 \
      --calibration-dir "$PROJECT_ROOT/experiments/campaigns/$CALIBRATION_RUN" \
      --output-dir "$MODEL_DIR" \
      --device cuda \
      >"$SEQUENCE_DIR/heatmap_fold_${fold}.log" 2>&1 &
    fold_pids+=("$!")
  done
  fold_failure=0
  for pid in "${fold_pids[@]}"; do
    if ! wait "$pid"; then
      fold_failure=1
    fi
  done
  if ((fold_failure)); then
    stage="failed_heatmap_fold"
    write_status "failed" 1
    exit 1
  fi
fi

stage="fit_full_heatmap_and_oof_gate"
write_status "running" 0
if ! CUDA_VISIBLE_DEVICES="$first_gpu" "$PYTHON_BIN" scripts/train_perception_regrasp_heatmap.py \
  --mode finalize \
  --folds 3 \
  --calibration-dir "$PROJECT_ROOT/experiments/campaigns/$CALIBRATION_RUN" \
  --output-dir "$MODEL_DIR" \
  --device cuda \
  >"$SEQUENCE_DIR/heatmap_finalize.log" 2>&1; then
  stage="stopped_localization_gate"
  write_status "completed_no_go" 0
  exit 0
fi
(
  cd "$MODEL_DIR"
  sha256sum \
    perception_regrasp_localizer.npz \
    perception_regrasp_heatmap_weights.pt \
    >perception_regrasp_artifacts.sha256
)

stage="terminal_screen20"
write_status "running" 0
"$PYTHON_BIN" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile screen20 \
  --run-prefix "$SCREEN_RUN" \
  --gpus "$GPU_LIST" \
  --max-parallel 3 \
  --execute
"$PYTHON_BIN" scripts/analyze_recovery_proposal_opportunity.py \
  --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$SCREEN_RUN" \
  --output-dir "$PROJECT_ROOT/experiments/campaigns/$SCREEN_RUN/analysis" \
  --expected-states 20 \
  --expected-proposals perception_regrasp_h8 \
  --bootstrap-repetitions 5000
if ! "$PYTHON_BIN" scripts/evaluate_perception_regrasp_gate.py \
  --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$SCREEN_RUN" \
  --output "$PROJECT_ROOT/experiments/campaigns/$SCREEN_RUN/analysis/screen_gate.json" \
  --expected-states 20 \
  --min-success-rate 0.20 \
  --min-cells 3 \
  --min-tasks 3; then
  stage="stopped_terminal_screen_gate"
  write_status "completed_no_go" 0
  exit 0
fi

stage="terminal_development80"
write_status "running" 0
"$PYTHON_BIN" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile development80 \
  --run-prefix "$DEVELOPMENT_RUN" \
  --gpus "$GPU_LIST" \
  --max-parallel 3 \
  --execute
"$PYTHON_BIN" scripts/analyze_recovery_proposal_opportunity.py \
  --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$DEVELOPMENT_RUN" \
  --output-dir "$PROJECT_ROOT/experiments/campaigns/$DEVELOPMENT_RUN/analysis" \
  --expected-states 80 \
  --expected-proposals perception_regrasp_h8 \
  --bootstrap-repetitions 5000
if ! "$PYTHON_BIN" scripts/evaluate_perception_regrasp_gate.py \
  --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$DEVELOPMENT_RUN" \
  --output "$PROJECT_ROOT/experiments/campaigns/$DEVELOPMENT_RUN/analysis/development_gate.json" \
  --expected-states 80 \
  --min-success-rate 0.10 \
  --min-cells 4 \
  --min-tasks 3 \
  --require-ci-positive; then
  stage="stopped_development_gate"
  write_status "completed_no_go" 0
  exit 0
fi

stage="confirmatory_strict_reserve72"
write_status "running" 0
"$PYTHON_BIN" scripts/run_libero_experiment_campaign.py \
  --config "$CONFIG" \
  --profile reserve72 \
  --run-prefix "$RESERVE_RUN" \
  --gpus "$GPU_LIST" \
  --max-parallel 3 \
  --execute
"$PYTHON_BIN" scripts/analyze_recovery_proposal_opportunity.py \
  --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$RESERVE_RUN" \
  --output-dir "$PROJECT_ROOT/experiments/campaigns/$RESERVE_RUN/analysis" \
  --expected-states 72 \
  --expected-proposals perception_regrasp_h8 \
  --bootstrap-repetitions 10000
"$PYTHON_BIN" scripts/evaluate_perception_regrasp_gate.py \
  --campaign-dir "$PROJECT_ROOT/experiments/campaigns/$RESERVE_RUN" \
  --output "$PROJECT_ROOT/experiments/campaigns/$RESERVE_RUN/analysis/confirmatory_gate.json" \
  --expected-states 72 \
  --min-success-rate 0.10 \
  --min-cells 4 \
  --min-tasks 3 \
  --require-ci-positive || true

stage="finished"
