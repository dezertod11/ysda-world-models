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
export LIBERO_SAFETY_COMMIT="${LIBERO_SAFETY_COMMIT:-19ec8df23eedfbb9265bafd3e56495fcebfcfcd0}"

export COSMOS_VENV="${COSMOS_VENV:-$PROJECT_ROOT/.venv-cosmos-safety}"
source "$SCRIPT_DIR/cosmos_env.sh"

export LIBERO_SAFETY_REPO="${LIBERO_SAFETY_REPO:-$PROJECT_ROOT/.external/LIBERO-Safety-$LIBERO_SAFETY_COMMIT}"
export LIBERO_CONFIG_PATH="${LIBERO_CONFIG_PATH:-$PROJECT_ROOT/.runtime/libero_safety/config}"
export LIBERO_DATASETS_PATH="${LIBERO_DATASETS_PATH:-$PROJECT_ROOT/.runtime/libero_safety/datasets}"
export LIBERO_BENCHMARK_ROOT="${LIBERO_BENCHMARK_ROOT:-$LIBERO_SAFETY_REPO/libero/libero}"
export LIBERO_BDDL_FILES_PATH="${LIBERO_BDDL_FILES_PATH:-$LIBERO_BENCHMARK_ROOT/bddl_files}"
export LIBERO_INIT_STATES_PATH="${LIBERO_INIT_STATES_PATH:-$LIBERO_BENCHMARK_ROOT/init_files}"
export LIBERO_ASSETS_PATH="${LIBERO_ASSETS_PATH:-$LIBERO_BENCHMARK_ROOT/assets}"
export COSMOS_POLICY_T5_EMBEDDINGS_PATH="${COSMOS_POLICY_T5_EMBEDDINGS_PATH:-$PROJECT_ROOT/.runtime/libero_safety/libero_t5_embeddings.pkl}"
export LIBERO_SAFETY_IMAGEMAGICK_PREFIX="${LIBERO_SAFETY_IMAGEMAGICK_PREFIX:-$PROJECT_ROOT/.runtime/libero_safety/imagemagick}"
if [[ -d "$LIBERO_SAFETY_IMAGEMAGICK_PREFIX/lib" ]]; then
  export MAGICK_HOME="${MAGICK_HOME:-$LIBERO_SAFETY_IMAGEMAGICK_PREFIX}"
  export LD_LIBRARY_PATH="$LIBERO_SAFETY_IMAGEMAGICK_PREFIX/lib:${LD_LIBRARY_PATH:-}"
fi
export PYTHONPATH="$LIBERO_SAFETY_REPO:$COSMOS_REPO${PYTHONPATH:+:$PYTHONPATH}"

if [[ ! -d "$LIBERO_SAFETY_REPO" ]]; then
  echo "LIBERO-Safety checkout is missing: $LIBERO_SAFETY_REPO" >&2
  echo "Run scripts/setup_mlspace_libero_safety.sh first." >&2
  return 1 2>/dev/null || exit 1
fi

mkdir -p "$LIBERO_CONFIG_PATH" "$LIBERO_DATASETS_PATH"
cat >"$LIBERO_CONFIG_PATH/config.yaml" <<EOF
benchmark_root: $LIBERO_BENCHMARK_ROOT
bddl_files: $LIBERO_BDDL_FILES_PATH
init_states: $LIBERO_INIT_STATES_PATH
datasets: $LIBERO_DATASETS_PATH
assets: $LIBERO_ASSETS_PATH
EOF
