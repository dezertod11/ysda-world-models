#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
RUN_BASE="${P4B_RUN_BASE:-p4b_residual_risk_20260907}"
HOLDOUT_RUN="${P4B_HOLDOUT_RUN:-p4b_terminal_candidates_20260907}"
GPU_LIST="${P4B_GPUS:-2,3,4,5,6,7}"
GPU_MAX_USED_MIB="${P4B_GPU_MAX_USED_MIB:-256}"
GPU_STABLE_POLLS="${P4B_GPU_STABLE_POLLS:-2}"
POLL_SECONDS="${P4B_POLL_SECONDS:-60}"

CAMPAIGN_DIR="$PROJECT_ROOT/experiments/campaigns/$RUN_BASE"
HOLDOUT_CAMPAIGN="$PROJECT_ROOT/experiments/campaigns/$HOLDOUT_RUN"
CONFIG="$PROJECT_ROOT/experiments/configs/libero_campaign_p4b_terminal_candidates_20260907.json"
P4_DATASET="$PROJECT_ROOT/experiments/campaigns/p4_residual_dynamics_20260906/dataset"
P4_ARTIFACT="$PROJECT_ROOT/experiments/frozen_models/p4_residual_dynamics_20260906"
ARTIFACT_ROOT="$PROJECT_ROOT/experiments/frozen_models/$RUN_BASE"
DEVELOPMENT_DIR="$CAMPAIGN_DIR/development"
HOLDOUT_DATASET="$CAMPAIGN_DIR/terminal_holdout_dataset"
HOLDOUT_FEATURES="$HOLDOUT_DATASET/residual_dynamics_features.npz"
HOLDOUT_ANALYSIS="$CAMPAIGN_DIR/terminal_holdout_analysis"
STATUS_PATH="$CAMPAIGN_DIR/sequence_status.json"
HEARTBEAT_PATH="$CAMPAIGN_DIR/heartbeat.txt"
stage="starting"
final_status="completed"

IFS=',' read -r -a GPUS <<<"$GPU_LIST"
if ((${#GPUS[@]} != 6)); then
  echo "P4B_GPUS must contain six comma-separated physical GPU ids" >&2
  exit 2
fi
for gpu in "${GPUS[@]}"; do
  gpu="${gpu//[[:space:]]/}"
  if [[ "$gpu" == "0" || "$gpu" == "1" ]]; then
    echo "P4b long jobs may use only physical GPUs 2-7" >&2
    exit 2
  fi
done
mkdir -p "$CAMPAIGN_DIR/logs" "$DEVELOPMENT_DIR" "$HOLDOUT_DATASET" "$HOLDOUT_ANALYSIS"

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
    write_status "$final_status" 0
  else
    write_status "failed" "$code"
  fi
  exit "$code"
}

gpu_snapshot() {
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu \
    --format=csv,noheader,nounits
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
    snapshot="$(gpu_snapshot)"
    if gpus_have_capacity "$snapshot"; then
      stable=$((stable + 1))
      echo "[p4b] GPU capacity check $stable/$GPU_STABLE_POLLS passed"
    else
      stable=0
      echo "[p4b] waiting for GPUs $GPU_LIST (used-memory limit ${GPU_MAX_USED_MIB} MiB)"
      echo "$snapshot"
    fi
    if ((stable < GPU_STABLE_POLLS)); then
      sleep "$POLL_SECONDS"
    fi
  done
}

train_variant() {
  local name="$1"
  local gpu="$2"
  local loss_mode="$3"
  local regularization="$4"
  local output="$ARTIFACT_ROOT/$name"
  if [[ -s "$output/ensemble.json" ]]; then
    (cd "$output" && sha256sum -c SHA256SUMS)
    return
  fi
  CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON_BIN" \
    "$SCRIPT_DIR/train_p4b_residual_ensemble.py" \
    --variant-name "$name" \
    --manifest "$P4_DATASET/transition_manifest.parquet" \
    --features "$P4_DATASET/residual_dynamics_features.npz" \
    --preprocessing-from "$P4_ARTIFACT/preprocessing.npz" \
    --output-dir "$output" \
    --loss-mode "$loss_mode" \
    --log-variance-l2 "$regularization" \
    --num-heads 5 \
    --max-epochs 160 \
    --min-epochs 12 \
    --patience 15 \
    --seed 20260907 \
    --device cuda
  (cd "$output" && sha256sum -c SHA256SUMS)
}

heartbeat &
heartbeat_pid=$!
trap finish EXIT
write_status "running" 0
cd "$PROJECT_ROOT"

stage="validate_protocol_and_code"
write_status "running" 0
test -s "$PROJECT_ROOT/experiments/P4B_RESIDUAL_RISK_PROTOCOL_20260907.md"
test -s "$CONFIG"
test -s "$P4_DATASET/transition_manifest.parquet"
test -s "$P4_DATASET/residual_dynamics_features.npz"
(cd "$P4_ARTIFACT" && sha256sum -c SHA256SUMS)
"$PYTHON_BIN" -m pytest -q \
  tests/test_p4b_residual_risk.py \
  tests/test_p4b_development_analysis.py \
  tests/test_p4b_terminal_holdout.py \
  tests/test_p4b_campaign_config.py

stage="wait_for_gpu_capacity"
write_status "running" 0
wait_for_gpus

stage="train_early_stopped_variants"
write_status "running" 0
mkdir -p "$ARTIFACT_ROOT"
train_variant hetero_earlystop "${GPUS[0]}" gaussian_nll 0.0 \
  >"$CAMPAIGN_DIR/logs/train_hetero_earlystop.log" 2>&1 &
pid_hetero=$!
train_variant hetero_regularized "${GPUS[1]}" gaussian_nll 0.01 \
  >"$CAMPAIGN_DIR/logs/train_hetero_regularized.log" 2>&1 &
pid_regularized=$!
train_variant mean_mse_shared "${GPUS[2]}" mean_mse 0.0 \
  >"$CAMPAIGN_DIR/logs/train_mean_mse_shared.log" 2>&1 &
pid_mean=$!
wait "$pid_hetero"
wait "$pid_regularized"
wait "$pid_mean"

stage="development_score_and_freeze"
write_status "running" 0
if [[ ! -s "$DEVELOPMENT_DIR/frozen_selector.json" ]]; then
  CUDA_VISIBLE_DEVICES="${GPUS[3]}" "$PYTHON_BIN" \
    "$SCRIPT_DIR/analyze_p4b_development.py" \
    --manifest "$P4_DATASET/transition_manifest.parquet" \
    --features "$P4_DATASET/residual_dynamics_features.npz" \
    --artifact "p4_original=$P4_ARTIFACT" \
    --artifact "hetero_earlystop=$ARTIFACT_ROOT/hetero_earlystop" \
    --artifact "hetero_regularized=$ARTIFACT_ROOT/hetero_regularized" \
    --artifact "mean_mse_shared=$ARTIFACT_ROOT/mean_mse_shared" \
    --output-dir "$DEVELOPMENT_DIR" \
    --device cuda \
    --mc-samples 32 \
    --seed 20260907
fi
test -s "$DEVELOPMENT_DIR/frozen_selector.json"
test -s "$DEVELOPMENT_DIR/FROZEN_SELECTOR_SHA256"
(cd "$DEVELOPMENT_DIR" && sha256sum -c FROZEN_SELECTOR_SHA256)

stage="prospective_all_candidate_terminal_holdout"
write_status "running" 0
holdout_status=""
if [[ -s "$HOLDOUT_CAMPAIGN/manifest.json" ]]; then
  holdout_status="$($PYTHON_BIN -c "import json; print(json.load(open('$HOLDOUT_CAMPAIGN/manifest.json')).get('status',''))")"
fi
if [[ "$holdout_status" != "completed" ]]; then
  "$PYTHON_BIN" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
    --config "$CONFIG" \
    --profile p4b_terminal_candidates \
    --run-prefix "$HOLDOUT_RUN" \
    --gpus "$GPU_LIST" \
    --execute
fi

stage="build_terminal_holdout_manifest"
write_status "running" 0
if [[ ! -s "$HOLDOUT_DATASET/transition_manifest.parquet" ]]; then
  "$PYTHON_BIN" "$SCRIPT_DIR/build_residual_dynamics_dataset.py" \
    --campaign-dir "$HOLDOUT_CAMPAIGN" \
    --output-dir "$HOLDOUT_DATASET" \
    --split-salt p4b-terminal-holdout-v1 \
    --required-open-loop-steps 16
fi
test -s "$HOLDOUT_DATASET/transition_manifest.parquet"

stage="extract_terminal_holdout_features"
write_status "running" 0
if [[ ! -s "$HOLDOUT_FEATURES" ]]; then
  CUDA_VISIBLE_DEVICES="${GPUS[4]}" HF_HUB_OFFLINE=1 \
    "$PYTHON_BIN" "$SCRIPT_DIR/extract_residual_dynamics_features.py" \
    --manifest "$HOLDOUT_DATASET/transition_manifest.parquet" \
    --output "$HOLDOUT_FEATURES" \
    --device cuda \
    --row-batch-size 24
fi
test -s "$HOLDOUT_FEATURES"

stage="frozen_terminal_holdout_analysis"
write_status "running" 0
CUDA_VISIBLE_DEVICES="${GPUS[5]}" "$PYTHON_BIN" \
  "$SCRIPT_DIR/analyze_p4b_terminal_holdout.py" \
  --campaign-dir "$HOLDOUT_CAMPAIGN" \
  --manifest "$HOLDOUT_DATASET/transition_manifest.parquet" \
  --features "$HOLDOUT_FEATURES" \
  --selector "$DEVELOPMENT_DIR/frozen_selector.json" \
  --output-dir "$HOLDOUT_ANALYSIS" \
  --device cuda \
  --mc-samples 32 \
  --bootstrap-repetitions 5000 \
  --seed 20260907
test -s "$HOLDOUT_ANALYSIS/summary.json"

gate="$($PYTHON_BIN -c "import json; print(str(json.load(open('$HOLDOUT_ANALYSIS/summary.json'))['offline_gate_pass']).lower())")"
if [[ "$gate" == "true" ]]; then
  final_status="completed_pass_ready_for_closed_loop"
else
  final_status="completed_no_go"
fi
stage="finished"
