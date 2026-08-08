---
name: experiment-design
description: Use when defining hypotheses, baselines, metrics, ablations, and evaluation protocols for an experiment plan
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

# Experiment Design

## Overview
Design experiments to answer a narrow question. Every run should test a hypothesis, not just generate more numbers.

## Checklist
1. State the hypothesis and falsification condition.
2. Choose baselines, metrics, and evaluation splits.
3. Reserve ablations for the claims that matter most.
4. Define logging requirements and stopping criteria.

## Deliverables
- experiment plan with hypotheses and metrics
- baseline and ablation table
- required artifacts for reproducibility
