---
name: workspace-cartography
description: Use when entering an unfamiliar research or code workspace and needing a fast map of folders, artifacts, and ownership boundaries
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

# Workspace Cartography

## Overview
Build a practical map before deep work. The goal is to identify where code, paper sources, experiments, data, and generated outputs live.

## Scan Order
1. Read top-level docs, configs, and build entrypoints first.
2. Note directories for source, paper drafts, experiments, figures, data, and logs.
3. Separate hand-written files from generated outputs.
4. Record commands for build, test, and paper compilation.
5. Surface missing or ambiguous ownership boundaries before editing.

## Deliverables
- directory map with purpose for major folders
- key commands and entrypoints
- risk notes for generated artifacts or unclear source of truth
