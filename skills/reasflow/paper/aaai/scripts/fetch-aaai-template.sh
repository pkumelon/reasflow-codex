#!/usr/bin/env bash
set -euo pipefail

dest="${1:-templates/aaai}"
url="https://aaai.org/authorkit26-1/"
guidelines_url="https://aaai.org/conference/aaai/aaai-26/main-technical-track-call/"
ua="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

command -v unzip >/dev/null 2>&1 || { echo "missing required command: unzip" >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

curl -fsSL -A "$ua" "$url" -o "$tmp/aaai.zip" || {
  echo "download failed: $url" >&2
  echo "AAAI Author Kit is also available from: $guidelines_url" >&2
  exit 1
}

if [ "$(head -c 2 "$tmp/aaai.zip")" != "PK" ]; then
  echo "unexpected response from AAAI (likely a Cloudflare challenge page)" >&2
  echo "retry the script, or download the Author Kit manually from: $guidelines_url" >&2
  exit 1
fi

unzip -o -q "$tmp/aaai.zip" -d "$tmp"
mkdir -p "$dest"
src="$(find "$tmp" -type d -path '*/CameraReady/LaTeX' | head -n 1)"
[ -n "$src" ] || { echo "unexpected Author Kit layout" >&2; exit 1; }
cp "$src"/aaai2026.sty "$src"/aaai2026.bst "$src"/aaai2026.bib "$dest/"

echo "AAAI template ready: $dest"
