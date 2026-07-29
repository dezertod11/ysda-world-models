#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 TRACE_FILE [OUTPUT_DIR]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/cosmos_env_libero_pro.sh"
cd "$COSMOS_REPO"

TRACE_FILE="$1"
OUTPUT_DIR="${2:-}"

if [[ -n "$OUTPUT_DIR" ]]; then
  python -m cosmos_policy.experiments.robot.libero.uncertainty_comparison analyze \
    --trace-file "$TRACE_FILE" \
    --output-dir "$OUTPUT_DIR"
else
  python -m cosmos_policy.experiments.robot.libero.uncertainty_comparison analyze \
    --trace-file "$TRACE_FILE"
fi
