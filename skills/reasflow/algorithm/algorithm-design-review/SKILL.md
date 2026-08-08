---
name: algorithm-design-review
description: Use when reviewing an algorithm idea for assumptions, invariants, complexity, failure modes, and baseline comparisons
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

# Algorithm Design Review

## Overview
Review algorithm proposals before implementation hardens them. Focus on assumptions, invariants, complexity, and where the design can fail.

## Checklist
1. State inputs, outputs, and operating assumptions.
2. Identify invariants and the mechanism that maintains them.
3. Estimate complexity and likely bottlenecks.
4. Compare against the strongest baseline alternatives.

## Deliverables
- design review memo
- risks and failure modes list
- recommended next prototype or proof task
