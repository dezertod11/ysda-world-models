#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
LIBERO_PRO_REPO="${LIBERO_PRO_REPO:-$PROJECT_ROOT/LIBERO-PRO}"

LEVEL="${1:-}"
case "$LEVEL" in
  x0.1|x0.2|x0.3|x0.4|x0.5|y0.1|y0.2|y0.3|y0.4|y0.5) ;;
  *)
    echo "Usage: $0 {x0.1|x0.2|x0.3|x0.4|x0.5|y0.1|y0.2|y0.3|y0.4|y0.5}" >&2
    exit 2
    ;;
esac

SOURCE_BDDL="$LIBERO_PRO_REPO/libero/libero/bddl_files/libero_object_temp_${LEVEL}"
SOURCE_INIT="$LIBERO_PRO_REPO/libero/libero/init_files/libero_object_temp_${LEVEL}"
TARGET_ROOT="$PROJECT_ROOT/.runtime/libero_pro_position/$LEVEL"
TARGET_BDDL="$TARGET_ROOT/bddl_files/libero_object_temp"
TARGET_INIT="$TARGET_ROOT/init_files/libero_object_temp"
LOCK_PATH="$PROJECT_ROOT/.runtime/libero_pro_position_${LEVEL//./p}.lock"

if [[ ! -d "$SOURCE_BDDL" || ! -d "$SOURCE_INIT" ]]; then
  echo "LIBERO-PRO position variant is missing for level $LEVEL" >&2
  exit 1
fi

mkdir -p "$PROJECT_ROOT/.runtime"
exec 9>"$LOCK_PATH"
flock 9

mkdir -p "$TARGET_BDDL" "$TARGET_INIT"
cp -a "$SOURCE_BDDL/." "$TARGET_BDDL/"
cp -a "$SOURCE_INIT/." "$TARGET_INIT/"

printf '%s\n' "$LEVEL" >"$TARGET_ROOT/variant.txt"
printf '%s\n' "$TARGET_ROOT"
