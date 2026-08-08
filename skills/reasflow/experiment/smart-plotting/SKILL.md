---
name: smart-plotting
description: Use when producing paper-grade figures or image-based plot review with concrete helper scripts
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

# Smart Plotting

## Overview
Two modes — always prefer **request mode** for new figures; use spec mode only when you already know the exact layout.

Set:
```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/experiment/smart-plotting"
```

## Request mode (recommended)
Pass a natural-language description. The script generates matplotlib code via LLM, executes it, scores quality with vision analysis (target ≥ 8.5), and iterates automatically up to `--max-iterations` times.

```bash
Alg_Exp/.venv/bin/python "$SKILL_ROOT/scripts/smart-plot.py" \
  --request "Convergence curves: X=iteration, Y=MSE log-scale, compare methods A B C with mean±std shading, 14pt font, DPI 300, paper style" \
  --data-sources Alg_Exp/data/results.csv \
  --output Alg_Exp/picture/convergence.png \
  --auto-analyze --max-iterations 3 \
  --metadata-output Alg_Exp/data/convergence_meta.json
```

If the user requests changes after the first run, pass the feedback:
```bash
Alg_Exp/.venv/bin/python "$SKILL_ROOT/scripts/smart-plot.py" \
  --request "same convergence figure" \
  --data-sources Alg_Exp/data/results.csv \
  --output Alg_Exp/picture/convergence_v2.png \
  --previous-feedback "legend overlaps the curves; move it outside the plot area" \
  --auto-analyze --max-iterations 3
```

The generated matplotlib code is saved alongside the image (`.py` extension) for reproducibility.

## Spec mode
When the exact chart layout is already decided, write a JSON spec and pass it:

```json
{
  "chart": "line",
  "style": "paper",
  "title": "Convergence on Quadratic Toy Problem",
  "xlabel": "Iteration",
  "ylabel": "Objective Gap",
  "yscale": "log",
  "data": [
    {"file": "Alg_Exp/data/results.csv", "label": "Ours", "x": "step", "y": "gap", "groupby": "seed"}
  ]
}
```

```bash
Alg_Exp/.venv/bin/python "$SKILL_ROOT/scripts/smart-plot.py" \
  --spec-file Alg_Exp/document/plot_spec.json \
  --output Alg_Exp/picture/convergence.png \
  --metadata-output Alg_Exp/data/convergence_meta.json
```

Supported chart types: `line`, `bar`, `scatter`, `heatmap`.

## Plot review
When a figure already exists and you need quality review:

```bash
python "$SKILL_ROOT/scripts/analyze-plot.py" \
  --image Alg_Exp/picture/convergence.png \
  --question "Summarize the trend, spot presentation issues, and suggest one concrete improvement." \
  --output Alg_Exp/data/convergence_review.json
```

Both scripts read `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` from the environment.

## Contract
1. **Do not write matplotlib code manually** — use request mode; let the LLM generate and iterate.
2. Vision score threshold is 8.5; below that the script iterates automatically.
3. Put final figures under `Alg_Exp/picture/` and metadata under `Alg_Exp/data/`.
4. Use log scales, uncertainty bands, and labels only when they answer the actual claim.

## Deliverables
- figure file + generated `.py` source
- metadata JSON with iteration history and vision scores
- optional review JSON when analyze-plot was used separately

