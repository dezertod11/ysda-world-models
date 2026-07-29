#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${BASH_VERSION:-}" ]]; then
  SCRIPT_PATH="${BASH_SOURCE[0]}"
elif [[ -n "${ZSH_VERSION:-}" ]]; then
  SCRIPT_PATH="${(%):-%N}"
else
  echo "Unsupported shell: use bash or zsh." >&2
  return 1 2>/dev/null || exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/cosmos_env.sh"

export LIBERO_PRO_REPO="${LIBERO_PRO_REPO:-$PROJECT_ROOT/LIBERO-PRO}"
export LIBERO_CONFIG_PATH="${LIBERO_CONFIG_PATH:-$PROJECT_ROOT/.runtime/libero_pro}"
export LIBERO_DATASETS_PATH="${LIBERO_DATASETS_PATH:-$PROJECT_ROOT/.runtime/libero_datasets}"
export LIBERO_BENCHMARK_ROOT="${LIBERO_BENCHMARK_ROOT:-$LIBERO_PRO_REPO/libero/libero}"
export LIBERO_BDDL_FILES_PATH="${LIBERO_BDDL_FILES_PATH:-$LIBERO_BENCHMARK_ROOT/bddl_files}"
export LIBERO_INIT_STATES_PATH="${LIBERO_INIT_STATES_PATH:-$LIBERO_BENCHMARK_ROOT/init_files}"
export LIBERO_ASSETS_PATH="${LIBERO_ASSETS_PATH:-$LIBERO_BENCHMARK_ROOT/assets}"
export PYTHONPATH="$LIBERO_PRO_REPO:$COSMOS_REPO${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$LIBERO_CONFIG_PATH" "$LIBERO_DATASETS_PATH"
cat >"$LIBERO_CONFIG_PATH/config.yaml" <<EOF
benchmark_root: $LIBERO_BENCHMARK_ROOT
bddl_files: $LIBERO_BDDL_FILES_PATH
init_states: $LIBERO_INIT_STATES_PATH
datasets: $LIBERO_DATASETS_PATH
assets: $LIBERO_ASSETS_PATH
EOF
