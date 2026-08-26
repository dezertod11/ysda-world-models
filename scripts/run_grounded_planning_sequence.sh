#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv-cosmos/bin/python}"
P0_RUN_NAME="${P0_RUN_NAME:-pro_object_horizon_controls_p0_20260826}"
P1_RUN_NAME="${P1_RUN_NAME:-counterfactual_feedback_p1_p2_20260826}"
PHYSICAL_GPU="${PHYSICAL_GPU:-6}"
POLL_SECONDS="${POLL_SECONDS:-300}"

P0_DIR="$PROJECT_ROOT/experiments/campaigns/$P0_RUN_NAME"
P1_DIR="$PROJECT_ROOT/experiments/campaigns/$P1_RUN_NAME"
SEQUENCE_DIR="$PROJECT_ROOT/experiments/campaigns/grounded_planning_sequence_20260826"
STATUS_PATH="$SEQUENCE_DIR/status.json"
LOCK_PATH="$SEQUENCE_DIR/sequence.lock"

if [[ "$PHYSICAL_GPU" == "0" ]]; then
  echo "Physical GPU 0 is reserved on MLSpace." >&2
  exit 2
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python environment does not exist: $PYTHON_BIN" >&2
  exit 2
fi

mkdir -p "$SEQUENCE_DIR"
exec 9>"$LOCK_PATH"
if ! flock -n 9; then
  echo "Another grounded-planning sequence is already running." >&2
  exit 3
fi

write_status() {
  local stage="$1"
  local state="$2"
  local message="$3"
  "$PYTHON_BIN" - "$STATUS_PATH" "$stage" "$state" "$message" <<'PY'
import json
import os
import sys
from datetime import datetime
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "schema_version": 1,
    "updated_at": datetime.now().isoformat(timespec="seconds"),
    "pid": os.getppid(),
    "stage": sys.argv[2],
    "state": sys.argv[3],
    "message": sys.argv[4],
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

manifest_status() {
  local manifest_path="$1"
  "$PYTHON_BIN" - "$manifest_path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print("missing")
else:
    print(json.loads(path.read_text(encoding="utf-8")).get("status", "unknown"))
PY
}

log_event() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$1"
}

wait_for_campaign() {
  local name="$1"
  local directory="$2"
  local status
  while true; do
    status="$(manifest_status "$directory/manifest.json")"
    case "$status" in
      completed)
        log_event "$name completed"
        return 0
        ;;
      failed)
        write_status "$name" "blocked" "$name failed; inspect its campaign logs"
        log_event "$name failed"
        return 1
        ;;
      running|planned)
        write_status "$name" "waiting" "$name is $status"
        ;;
      *)
        write_status "$name" "waiting" "$name manifest status is $status"
        ;;
    esac
    sleep "$POLL_SECONDS"
  done
}

write_status "P0" "waiting" "waiting for $P0_RUN_NAME"
wait_for_campaign "$P0_RUN_NAME" "$P0_DIR"

write_status "P0-analysis" "running" "building causal horizon-control report"
log_event "analyzing $P0_RUN_NAME"
"$PYTHON_BIN" "$PROJECT_ROOT/scripts/analyze_pro_object_horizon_controls.py" \
  "$P0_DIR" \
  --baseline-dir "$PROJECT_ROOT/experiments/campaigns/pro_object_baselines_pilot_20260825" \
  --output-dir "$P0_DIR/analysis/horizon_controls"

write_status "P1-P2" "running" "launching exact-state snapshot campaign on GPU $PHYSICAL_GPU"
log_event "launching $P1_RUN_NAME on physical GPU $PHYSICAL_GPU"
"$PYTHON_BIN" "$PROJECT_ROOT/scripts/run_libero_experiment_campaign.py" \
  --config "$PROJECT_ROOT/experiments/configs/libero_campaign_counterfactual_feedback_pilot.json" \
  --profile counterfactual_feedback_pilot_p1_p2 \
  --run-prefix "$P1_RUN_NAME" \
  --gpus "$PHYSICAL_GPU" \
  --execute

wait_for_campaign "$P1_RUN_NAME" "$P1_DIR"
write_status "P1-P2-analysis" "running" "building VoF and grounded-ranking report"
log_event "analyzing $P1_RUN_NAME"
"$PYTHON_BIN" "$PROJECT_ROOT/scripts/analyze_counterfactual_feedback.py" \
  --campaign-dir "$P1_DIR" \
  --output-dir "$P1_DIR/analysis/counterfactual_feedback"

write_status "complete" "completed" "P0 and the P1/P2 offline pilot were analyzed"
log_event "grounded-planning sequence completed"
