---
name: check-asset-usage
description: Use when verifying that assigned assets or full-paper assets were actually consumed by the manuscript output
---

## Installed Root

Resolve the installed reasflow-codex private skills root before running packaged scripts:

```bash
REASFLOW_PRIVATE_SKILLS_ROOT="${REASFLOW_PRIVATE_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_PRIVATE_SKILLS_ROOT" ]; then
  if [ -d ./.codex/reasflow-skills ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$(pwd)/.codex/reasflow-skills"
  elif [ -d "$HOME/.codex/reasflow-skills" ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$HOME/.codex/reasflow-skills"
  else
    echo "reasflow private skills not found in ./.codex/reasflow-skills or $HOME/.codex/reasflow-skills" >&2
    exit 1
  fi
fi
```

# Check Asset Usage

## Overview
Treat asset utilization as a hard constraint, not a nice-to-have. Run this after a chapter draft or full-paper integration pass to confirm the output really uses the assets it was supposed to use.

## Helper Script
Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/paper/check-asset-usage"`.

Preferred command:

```bash
python3 "$SKILL_ROOT/scripts/check_asset_usage.py" \
  --assets-dir assets/example-paper \
  --output-dir output/example-paper \
  --main-file main.tex \
  --format text
```

JSON for automation:

```bash
python3 "$SKILL_ROOT/scripts/check_asset_usage.py" \
  --assets-dir assets/example-paper \
  --output-dir output/example-paper \
  --format json
```

If Python runtime/setup is missing:

```bash
uv run "$SKILL_ROOT/scripts/check_asset_usage.py" \
  --assets-dir assets/example-paper \
  --output-dir output/example-paper \
  --format text
```

## What It Checks
1. `\input{}` and `\include{}` references for `.tex` assets.
2. `\includegraphics{}` references for figures and diagrams.
3. bibliography and `\cite{}` coverage for `.bib`, `.yaml`, and `.yml` assets.
4. signature phrases from `.md` and `.txt` notes that should have been incorporated.

## Expected Output
- overall utilization rate (`used/total`, percentage)
- per top-level directory and subdirectory breakdown
- missing file names for each subgroup
- machine-readable JSON directory stats when `--format json` is used

## Deliverables
- overall utilization rate
- per-directory missing-asset list
- explicit confirmation when utilization reaches 100%
