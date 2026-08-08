#!/bin/sh

set -eu

SEARCH_DIR="${1:-}"
PATTERN="${2:-all}"

if [ -z "$SEARCH_DIR" ]; then
  printf 'Usage: %s <directory> [pattern]\n' "$0" >&2
  exit 1
fi

if [ ! -d "$SEARCH_DIR" ]; then
  printf 'Directory not found: %s\n' "$SEARCH_DIR" >&2
  exit 1
fi

case "$PATTERN" in
  theorem)
    QUERY='^[^%]*\\begin\{(theorem|thm|restatable.*theorem)'
    ;;
  lemma)
    QUERY='^[^%]*\\begin\{(lemma|lem|restatable.*lemma)'
    ;;
  proof)
    QUERY='^[^%]*\\begin\{(proof|pf)'
    ;;
  assumption)
    QUERY='^[^%]*\\begin\{(assumption|assump|assm|assum)'
    ;;
  algorithm)
    QUERY='^[^%]*\\begin\{(algorithm|alg|algorithmic)'
    ;;
  all)
    QUERY='^[^%]*\\begin\{(theorem|thm|lemma|lem|proof|pf|assumption|assump|assm|assum|algorithm|alg|algorithmic)'
    ;;
  *)
    QUERY="$PATTERN"
    ;;
esac

rg -n -i "$QUERY" "$SEARCH_DIR"
