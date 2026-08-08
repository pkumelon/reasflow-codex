---
name: asset-inventory
description: Use when collecting datasets, checkpoints, figures, bibliographies, prompts, or templates needed for a paper workflow
---

## Installed Root

Resolve the installed reasflow-codex skills root before running packaged scripts:

```bash
REASFLOW_SKILLS_ROOT="${REASFLOW_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_SKILLS_ROOT" ]; then
  if [ -d ./.agents/skills ]; then
    REASFLOW_SKILLS_ROOT="$(pwd)/.agents/skills"
  elif [ -d "$HOME/.agents/skills" ]; then
    REASFLOW_SKILLS_ROOT="$HOME/.agents/skills"
  else
    echo "reasflow-codex skills not found in ./.agents/skills or $HOME/.agents/skills" >&2
    exit 1
  fi
fi
```

# Asset Inventory

## Overview
Generate a reproducible asset ledger (type, size, path, optional hash) before writing or integration work.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_SKILLS_ROOT/asset-inventory"
```

## Helper Commands
Text inventory:

```bash
python3 "$SKILL_ROOT/scripts/inventory_assets.py" \
  --root assets/example-paper \
  --format text
```

JSON inventory with per-file hash:

```bash
python3 "$SKILL_ROOT/scripts/inventory_assets.py" \
  --root assets/example-paper \
  --with-hash \
  --format json
```

Python env fallback:

```bash
uv run "$SKILL_ROOT/scripts/inventory_assets.py" \
  --root assets/example-paper --format text
```

## Expected Output
- aggregate totals (`total_files`, `total_size`)
- per-kind counts (`latex`, `bibtex`, `image`, `notes`, `data`)
- file-level rows with path, kind, size, readability, optional hash

## Deliverables
- inventory table with status and path
- gap list for missing or unreadable assets
- regenerate/reuse decision notes
