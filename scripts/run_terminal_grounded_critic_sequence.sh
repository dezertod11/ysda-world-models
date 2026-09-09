#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COSMOS_VENV="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos}"
BASE="${TERMINAL_CRITIC_RUN_PREFIX:-terminal_grounded_critic_20260829}"
GPUS="${TERMINAL_CRITIC_GPUS:-4,6}"
MODEL_PATH="$PROJECT_ROOT/experiments/frozen_models/terminal_grounded_conservative_critic_v1.json"
SEQUENCE_DIR="$PROJECT_ROOT/experiments/campaigns/$BASE"
ANALYSIS_DIR="$SEQUENCE_DIR/analysis"
STATUS_PATH="$SEQUENCE_DIR/sequence_status.json"
FROZEN_SNAPSHOT="$SEQUENCE_DIR/frozen_model_before_holdout.json"

mkdir -p "$ANALYSIS_DIR" "$(dirname -- "$MODEL_PATH")"
shopt -s nullglob

write_status() {
  local stage="$1"
  local completed="$2"
  "$COSMOS_VENV/bin/python" - "$STATUS_PATH" "$stage" "$completed" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(
    json.dumps(
        {
            "stage": sys.argv[2],
            "completed": sys.argv[3].lower() == "true",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY
}

write_status "development_collection" false
"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$PROJECT_ROOT/experiments/configs/libero_campaign_terminal_critic_development.json" \
  --profile terminal_critic_development \
  --run-prefix "${BASE}__development" \
  --gpus "$GPUS" \
  --execute

DEV_RUNS="$PROJECT_ROOT/experiments/campaigns/${BASE}__development/runs"
TRAIN_FILES=("$DEV_RUNS"/*__object_development_*__candidate_outcomes.parquet)
CALIBRATION_FILES=("$DEV_RUNS"/*__object_calibration_*__candidate_outcomes.parquet)
if [[ ${#TRAIN_FILES[@]} -ne 2 || ${#CALIBRATION_FILES[@]} -ne 2 ]]; then
  echo "[terminal-critic] expected 2 development and 2 calibration tables" >&2
  printf '[terminal-critic] train: %s\n' "${TRAIN_FILES[@]:-missing}" >&2
  printf '[terminal-critic] calibration: %s\n' "${CALIBRATION_FILES[@]:-missing}" >&2
  exit 2
fi

write_status "opportunity_gate_and_fit" false
if [[ -f "$FROZEN_SNAPSHOT" ]]; then
  cp "$FROZEN_SNAPSHOT" "$MODEL_PATH"
  echo "[terminal-critic] reuse pre-holdout frozen model: $FROZEN_SNAPSHOT"
else
  set +e
  "$COSMOS_VENV/bin/python" "$SCRIPT_DIR/terminal_grounded_critic.py" fit \
    --training-files "${TRAIN_FILES[@]}" \
    --calibration-files "${CALIBRATION_FILES[@]}" \
    --output-model "$MODEL_PATH" \
    --output-dir "$ANALYSIS_DIR/development"
  FIT_STATUS=$?
  set -e
  if [[ $FIT_STATUS -eq 4 ]]; then
    echo "[terminal-critic] opportunity gate failed; holdout and closed-loop are intentionally skipped"
    write_status "opportunity_gate_failed" true
    exit 0
  fi
  if [[ $FIT_STATUS -ne 0 ]]; then
    write_status "fit_failed" false
    exit "$FIT_STATUS"
  fi
  cp "$MODEL_PATH" "$FROZEN_SNAPSHOT"
fi

write_status "holdout_collection" false
"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$PROJECT_ROOT/experiments/configs/libero_campaign_terminal_critic_holdout.json" \
  --profile terminal_critic_holdout \
  --run-prefix "${BASE}__holdout" \
  --gpus "$GPUS" \
  --execute

HOLDOUT_RUNS="$PROJECT_ROOT/experiments/campaigns/${BASE}__holdout/runs"
HOLDOUT_FILES=("$HOLDOUT_RUNS"/*holdout*__candidate_outcomes.parquet)
if [[ ${#HOLDOUT_FILES[@]} -ne 10 ]]; then
  echo "[terminal-critic] expected 10 per-init holdout candidate tables" >&2
  exit 2
fi

write_status "offline_evaluation" false
"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/terminal_grounded_critic.py" evaluate \
  --model "$MODEL_PATH" \
  --candidate-files "${HOLDOUT_FILES[@]}" \
  --output-dir "$ANALYSIS_DIR/holdout"

OFFLINE_PASS="$($COSMOS_VENV/bin/python - "$ANALYSIS_DIR/holdout/offline_gate.json" <<'PY'
import json
import sys
print("1" if json.load(open(sys.argv[1], encoding="utf-8"))["passed"] else "0")
PY
)"
if [[ "$OFFLINE_PASS" != "1" ]]; then
  echo "[terminal-critic] offline gate failed; closed-loop is intentionally skipped"
  write_status "offline_gate_failed" true
  exit 0
fi

write_status "closed_loop" false
"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/run_libero_experiment_campaign.py" \
  --config "$PROJECT_ROOT/experiments/configs/libero_campaign_terminal_critic_closed_loop.json" \
  --profile terminal_critic_closed_loop \
  --run-prefix "${BASE}__closed_loop" \
  --gpus "$GPUS" \
  --execute

write_status "closed_loop_analysis" false
MODEL_SHA="$($COSMOS_VENV/bin/python - "$MODEL_PATH" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["frozen_payload_sha256"])
PY
)"
"$COSMOS_VENV/bin/python" "$SCRIPT_DIR/analyze_terminal_critic_closed_loop.py" \
  --campaign-dir "$PROJECT_ROOT/experiments/campaigns/${BASE}__closed_loop" \
  --output-dir "$ANALYSIS_DIR/closed_loop" \
  --expected-pairs-per-task 60 \
  --expected-model-sha "$MODEL_SHA" \
  --expected-candidates 8

write_status "closed_loop_complete" true
echo "[terminal-critic] sequence complete: $SEQUENCE_DIR"
