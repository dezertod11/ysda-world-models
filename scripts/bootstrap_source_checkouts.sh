#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

COSMOS_REPO="$PROJECT_ROOT/cosmos-policy"
LIBERO_PRO_REPO="$PROJECT_ROOT/LIBERO-PRO"

COSMOS_URL="https://github.com/NVlabs/cosmos-policy.git"
COSMOS_COMMIT="18a2accadf4e7a3531e56754102af5a24d2316da"
COSMOS_PATCH="$PROJECT_ROOT/patches/cosmos-policy-ysda.patch"

LIBERO_PRO_URL="https://github.com/Zxy-MLlab/LIBERO-PRO.git"
LIBERO_PRO_COMMIT="eafdb809426b13153aa1e4c42d6601844217dfec"
LIBERO_PRO_PATCH="$PROJECT_ROOT/patches/libero-pro-ysda.patch"

clone_and_patch() {
  local name="$1"
  local url="$2"
  local commit="$3"
  local patch="$4"
  local destination="$5"

  if [[ -e "$destination" ]]; then
    echo "$name checkout already exists: $destination" >&2
    echo "Move it aside or remove it intentionally, then rerun this script." >&2
    return 1
  fi
  if [[ ! -f "$patch" ]]; then
    echo "$name patch is missing: $patch" >&2
    return 1
  fi

  git clone "$url" "$destination"
  git -C "$destination" checkout --detach "$commit"
  git -C "$destination" apply --check "$patch"
  git -C "$destination" apply "$patch"
  echo "$name restored at $commit with $(basename "$patch")"
}

clone_and_patch \
  "Cosmos Policy" \
  "$COSMOS_URL" \
  "$COSMOS_COMMIT" \
  "$COSMOS_PATCH" \
  "$COSMOS_REPO"

clone_and_patch \
  "LIBERO-PRO" \
  "$LIBERO_PRO_URL" \
  "$LIBERO_PRO_COMMIT" \
  "$LIBERO_PRO_PATCH" \
  "$LIBERO_PRO_REPO"

echo
echo "Source checkouts are ready."
echo "Next: bash scripts/setup_mlspace_cosmos.sh"
