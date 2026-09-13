#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
: "${CUDA_VISIBLE_DEVICES:?Choose an admitted GPU explicitly; this wrapper does not reserve GPUs}"

# A private LIBERO config avoids changing paths used by another running worker.
export LIBERO_CONFIG_PATH="${LIBERO_CONFIG_PATH:-$PROJECT_ROOT/.runtime/event_feedback/config_$$}"
if [[ -n "${EVENT_POSITION_LEVEL:-}" ]]; then
  VARIANT_ROOT="$PROJECT_ROOT/.runtime/libero_pro_position/$EVENT_POSITION_LEVEL"
  if [[ ! -d "$VARIANT_ROOT/bddl_files/libero_object_temp" || ! -d "$VARIANT_ROOT/init_files/libero_object_temp" ]]; then
    echo "Prepare the position variant first: scripts/prepare_libero_pro_position_variant.sh $EVENT_POSITION_LEVEL" >&2
    exit 2
  fi
  export LIBERO_BDDL_FILES_PATH="$VARIANT_ROOT/bddl_files"
  export LIBERO_INIT_STATES_PATH="$VARIANT_ROOT/init_files"
fi
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"
exec "$COSMOS_VENV/bin/python" "$SCRIPT_DIR/collect_event_feedback.py" "$@"
