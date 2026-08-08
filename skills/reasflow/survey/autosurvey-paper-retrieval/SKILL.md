---
name: autosurvey-paper-retrieval
description: Use when building survey-style paper pools and retrieval traces for survey writing
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

# AutoSurvey Paper Retrieval

## Overview
Build a reusable paper pool before drafting survey prose. Keep retrieval traces in `survey/library/` so outline, section writing, and related-work synthesis all cite the same evidence base.

This skill is the executable replacement for the upstream `literature_*` tool family. Its default source policy is ReaScholar first, with Semantic Scholar as a metadata and graph supplement/fallback:

- `search` ~= `literature_search`
- `paper` ~= `literature_get_paper`
- `citations` ~= `literature_get_citations`
- `references` ~= `literature_get_references`
- `bibtex` turns retrieval JSON into `references.bib`

Use native Codex web search first when you need broad discovery or freshness. Use this script when you need reproducible paper metadata, citation graphs, reference graphs, or BibTeX output under `survey/`. Set `SEMANTIC_SCHOLAR_API_KEY` in the environment when S2 enrichment or citation/reference graph calls are needed; never store the key in generated files.

## Installed Paths
Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/autosurvey-paper-retrieval"` before invoking the packaged helper script.

## Helper Script
- `python "$SKILL_ROOT/scripts/autosurvey_literature.py" search --query "federated optimization" --limit 25 --out survey/library/search_seed.json`
- `python "$SKILL_ROOT/scripts/autosurvey_literature.py" search --query "gradient tracking update rules" --limit 25 --reascholar-mode algorithm --out survey/library/search_algorithm.json`
- `python "$SKILL_ROOT/scripts/autosurvey_literature.py" paper --paper-id "arXiv:1602.05629" --out survey/library/fedavg.json`
- `python "$SKILL_ROOT/scripts/autosurvey_literature.py" citations --paper-id "arXiv:1602.05629" --limit 20 --out survey/library/fedavg_citations.json`
- `python "$SKILL_ROOT/scripts/autosurvey_literature.py" references --paper-id "arXiv:1602.05629" --limit 20 --out survey/library/fedavg_references.json`
- `python "$SKILL_ROOT/scripts/autosurvey_literature.py" bibtex --input survey/library/search_seed.json --out survey/references.bib`

## Workflow
1. Create `survey/library/` early and store every retrieval artifact there.
2. Use `search` to collect seed papers for each coverage axis in the outline. Use the default `fast` ReaScholar mode for broad retrieval; use `--reascholar-mode algorithm`, `theorem`, `model`, or `code` only for targeted facets.
3. Use `paper`, `citations`, and `references` to validate metadata and expand missing clusters. `citations` and `references` are S2-backed because ReaScholar does not expose citation graph edges.
4. Use `bibtex` to create or refresh `survey/references.bib` from retrieved records.
5. Pass the exact JSON paths and generated citation keys to `survey-section-writer` and `survey-related-works`.

## Deliverables
- retrieval traces under `survey/library/`
- normalized paper pool with stable IDs and metadata
- BibTeX output synchronized with the survey LaTeX files
