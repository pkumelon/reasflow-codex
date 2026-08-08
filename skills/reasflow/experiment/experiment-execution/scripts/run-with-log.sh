#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  printf 'usage: %s <log-dir> <command> [args...]\n' "$0" >&2
  exit 1
fi

log_dir="$1"
shift
mkdir -p "$log_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
log_file="$log_dir/$stamp.log"

printf 'command: %s\n' "$*" | tee "$log_file"
"$@" 2>&1 | tee -a "$log_file"
