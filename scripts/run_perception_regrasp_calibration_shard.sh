#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"

EXTRA_ARGS=()
if [[ "${PERCEPTION_CALIBRATION_RESUME:-1}" == "1" ]]; then
  EXTRA_ARGS+=(--resume)
fi

exec "$COSMOS_VENV/bin/python" "$SCRIPT_DIR/collect_perception_regrasp_calibration.py" \
  --manifest "${PERCEPTION_CALIBRATION_MANIFEST:?manifest is required}" \
  --position-level "${PERCEPTION_CALIBRATION_POSITION_LEVEL:?position level is required}" \
  --task-id "${PERCEPTION_CALIBRATION_TASK_ID:?task id is required}" \
  --output-dir "${PERCEPTION_CALIBRATION_OUTPUT_DIR:?output directory is required}" \
  --run-name "${PERCEPTION_CALIBRATION_RUN_NAME:?run name is required}" \
  --resolution "${PERCEPTION_CALIBRATION_RESOLUTION:-256}" \
  --max-states "${PERCEPTION_CALIBRATION_MAX_STATES:-0}" \
  "${EXTRA_ARGS[@]}"
