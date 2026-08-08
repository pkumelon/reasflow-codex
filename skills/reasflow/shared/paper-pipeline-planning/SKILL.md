---
name: paper-pipeline-planning
description: Use when coordinating a multi-stage paper workflow across survey, method, theorem, experiment, and writing agents
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

# Paper Pipeline Planning

## Overview
Plan the paper as a dependency graph, not a flat task list. Define what each stage must consume, produce, and unblock before delegation starts.

## Workflow
1. Lock the paper goal, target venue, constraints, and success criteria.
2. Split work into survey, proof, algorithm, experiment, intro, and paper tracks.
3. For each track, record owner, inputs, outputs, and approval gates.
4. Mark which tracks can run in parallel and which need upstream artifacts first.
5. End with a delegation order and one shared status note for handoffs.

## Deliverables
- pipeline table with stage, owner, inputs, outputs, and blockers
- next actions with dependency order
- assumptions list for any unattended continuation
