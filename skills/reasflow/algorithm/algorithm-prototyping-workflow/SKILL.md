---
name: algorithm-prototyping-workflow
description: Use when turning an algorithm idea into pseudocode, runnable code, and a quick feasibility experiment with reproducible artifacts
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

# Algorithm Prototyping Workflow

## Overview
Use this when Algorithm must deliver concrete method artifacts, not only discussion.
The minimum bar is pseudocode plus runnable code plus one executed feasibility run.

## Required Artifacts
1. `Alg_Exp/document/pseudocode.tex`
2. `Alg_Exp/code/algorithm.py`
3. `Alg_Exp/code/test_algorithm.py`
4. `Alg_Exp/code/quick_experiment.py` (or equivalent experiment section in test code)
5. `Alg_Exp/data/test_run.json` or `Alg_Exp/data/test_run.csv`
6. `Alg_Exp/document/algorithm_design.md`
7. `Alg_Exp/document/test_experiment_report.md`

## Workflow
1. Lock assumptions and invariants first with `algorithm-design-review`.
2. Draft and save pseudocode before implementation.
3. Implement the minimal runnable algorithm API.
4. Add and run at least one basic executable test.
5. Run one quick experiment on a controllable toy problem and capture logs.
6. If numeric traces are available, use `smart-plotting` to save at least one figure under `Alg_Exp/picture/`.
7. Record commands, metrics, pass or fail judgment, and next steps in `test_experiment_report.md`.

## Command Logging
Use `experiment-execution` for reproducible command logging and seed tracking whenever scripts are run from `Alg_Exp/code/`.

## Final Response Contract
Before finishing, include:
- a short pseudocode snippet
- the executed test command and result
- the executed quick experiment command and key metrics
- an explicit feasibility judgment
- paths to all generated artifacts
