#!/bin/sh

set -eu

ARXIV_ID="${1:-}"
TARGET_DIR="${2:-}"

if [ -z "$ARXIV_ID" ]; then
  printf 'Usage: %s <arxiv_id> [target_directory]\n' "$0" >&2
  exit 1
fi

if [ -z "$TARGET_DIR" ]; then
  TARGET_DIR="prover/references/ref_${ARXIV_ID}"
fi

mkdir -p "$TARGET_DIR"
TMP_ARCHIVE="$(mktemp "${TMPDIR:-/tmp}/arxiv-${ARXIV_ID}.XXXXXX")"

cleanup() {
  rm -f "$TMP_ARCHIVE"
}
trap cleanup EXIT INT TERM

curl -fsSL "https://arxiv.org/e-print/$ARXIV_ID" -o "$TMP_ARCHIVE"

if tar -xf "$TMP_ARCHIVE" -C "$TARGET_DIR" 2>/dev/null; then
  :
elif unzip -oq "$TMP_ARCHIVE" -d "$TARGET_DIR" >/dev/null 2>&1; then
  :
else
  printf 'Failed to unpack arXiv source for %s\n' "$ARXIV_ID" >&2
  exit 1
fi

printf 'Downloaded %s into %s\n' "$ARXIV_ID" "$TARGET_DIR"
