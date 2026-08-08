---
name: domain-knowledge-cards
description: Use when algorithm or experiment work needs to search workspace-local domain knowledge and generate new knowledge cards from arXiv papers
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

# Domain Knowledge Cards

## Overview
Treat domain knowledge as a local artifact set, not a vague memory. Search existing cards first, then generate new workspace-local cards from arXiv only for papers that materially affect method or experiment decisions.

## Helper Scripts
- `SKILL_ROOT="$REASFLOW_SKILLS_ROOT/domain-knowledge-cards"`
- `python "$SKILL_ROOT/scripts/search-domain-knowledge.py" --root Alg_Exp/src/domain_knowledge --query "variance reduced decentralized optimization" --top-k 5`
- `python "$SKILL_ROOT/scripts/create-knowledge-card-from-arxiv.py" --query "decentralized variance reduction" --max-results 3 --output-dir Alg_Exp/src/domain_knowledge`

## Workflow
1. Search existing workspace-local cards before creating new ones.
2. Generate cards only for papers that inform the active algorithm or experiment question.
3. Keep generated YAML under `src/domain_knowledge/` or another explicit workspace-local card directory.
4. Record which cards were reused versus newly generated from arXiv.

## Deliverables
- ranked local card shortlist with exact file paths
- generated YAML cards with title, method, evidence, baselines, and limitations
- note on which experiment or design choice each card informs
