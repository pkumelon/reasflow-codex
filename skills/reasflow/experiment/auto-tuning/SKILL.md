---
name: auto-tuning
description: Use when searching hyperparameters with a real Optuna-backed helper script and reproducible output history
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
    echo "reasflow shared skills not found in ./.agents/skills or $HOME/.agents/skills" >&2
    exit 1
  fi
fi

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

# Auto Tuning

## Overview
This skill replaces the old prompt-only tuning advice with an actual Optuna-backed CLI.
Use it when Experiment needs a bounded parameter search and the experiment code exposes a callable objective function.

## Requirements
- A workspace-local Python environment, preferably `Alg_Exp/.venv/`
- `optuna` installed there
- An experiment module that defines a function like:

```python
def objective_for_tuning(params: dict[str, float]) -> float:
    result = run_experiment_with_params(params)
    return result["validation_loss"]
```

If `optuna` is missing, create or fix the environment with `uv`:

```bash
uv venv Alg_Exp/.venv
Alg_Exp/.venv/bin/pip install optuna numpy scipy pandas
```

## Helper Script
Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/experiment/auto-tuning"`.
Run:

```bash
Alg_Exp/.venv/bin/python "$SKILL_ROOT/scripts/optuna-search.py" \
  --experiment-file Alg_Exp/code/tuning_experiment.py \
  --objective-function objective_for_tuning \
  --param-space-file Alg_Exp/document/param_space.json \
  --direction minimize \
  --trials 50 \
  --output Alg_Exp/data/tuning_history.json
```

The parameter-space JSON should look like:

```json
{
  "learning_rate": {"type": "float", "low": 0.0001, "high": 0.1, "log": true},
  "momentum": {"type": "float", "low": 0.0, "high": 0.95},
  "batch_size": {"type": "int", "low": 16, "high": 128, "step": 16},
  "optimizer": {"type": "categorical", "choices": ["sgd", "adam"]}
}
```

## Tuning Contract
1. Keep the search space explicit in a JSON artifact.
2. Save the tuning history to `Alg_Exp/data/`.
3. Report the best parameters together with the objective value and trial count.
4. Do not call a parameter search complete unless the objective function was actually executed.

## Deliverables
- tuning history JSON
- best configuration summary
- rerun command for the selected configuration
