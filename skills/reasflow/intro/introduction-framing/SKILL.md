---
name: introduction-framing
description: Use when framing an introduction around motivation, gap, approach, contributions, and reader expectations
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

# Introduction Framing

## Required pipeline

Follow these steps in order. The scripts only prepare and validate deterministic artifacts; native Codex subagents perform evidence extraction and writing. Never call an LLM API from these scripts.

Set once:
```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/intro/introduction-framing"
```

### 1. Prepare and delegate evidence tasks

Run one prepare command per source type found in the workspace:

```bash
# Survey / related works / gap
python3 "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode prepare --source-type survey --workspace . --source survey/survey.md \
  --output intro/tasks/survey.json --extracted-output intro/survey_info.json

# Method description
python3 "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode prepare --source-type method --workspace . --source Alg_Exp/document/method.md \
  --output intro/tasks/method.json --extracted-output intro/method_info.json

# Experiment results
python3 "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode prepare --source-type experiment --workspace . --source Alg_Exp/experiment/results.md \
  --output intro/tasks/experiment.json --extracted-output intro/experiment_info.json

# Theory / proofs
python3 "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode prepare --source-type theory --workspace . --source prover/proof.md \
  --output intro/tasks/theory.json --extracted-output intro/theory_info.json
```

For each task, spawn `intro-evidence-extractor` without a model or reasoning override, wait for it, and validate its assigned output:

```bash
python3 "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode validate --task intro/tasks/survey.json --input intro/survey_info.json
```

`--source` accepts a file or directory. All source types are optional; only prepare existing sources. Never organize unvalidated extraction output.

### 2. Organize
```bash
python3 "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode organize \
  --inputs intro/survey_info.json intro/method_info.json \
  --output intro/organized_info.json
```
Pass only the `--inputs` files that were actually produced in step 1.

### 3. Supplement incomplete source bibliography

Use the `supplement-intro-literature` skill before writing. It copies existing entries and resolves missing claim keys with ReaScholar first and Semantic Scholar fallback:

```bash
SUPPLEMENT_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/intro/supplement-intro-literature"
python3 "$SUPPLEMENT_ROOT/scripts/supplement-intro-literature.py" \
  --workspace . \
  --bib-input survey/references.bib \
  --bib-output intro/source_references.bib \
  --citation-json intro/organized_info.json \
  --trace-output intro/literature_retrieval.json
```

### 4. Prepare and delegate writing

Prepare a native writer task:

```bash
python3 "$SKILL_ROOT/scripts/write-introduction.py" \
  --mode prepare \
  --title "Paper Title" \
  --organized-info intro/organized_info.json \
  --style math \
  --bib-input intro/source_references.bib \
  --task-output intro/tasks/writer.json \
  --draft-output intro/introduction.draft.tex \
  --trace-output intro/citation_trace.json
```

Spawn `intro-writer` with `intro/tasks/writer.json`, without model or reasoning overrides, and wait for both assigned outputs. Then finalize locally:

```bash
python3 "$SKILL_ROOT/scripts/write-introduction.py" \
  --mode finalize \
  --organized-info intro/organized_info.json \
  --bib-input intro/source_references.bib \
  --draft-input intro/introduction.draft.tex \
  --trace-input intro/citation_trace.json \
  --tex-output intro/introduction.tex \
  --bib-output intro/references.bib \
  --citation-report intro/citation_report.json \
  --strict-citations
```

`--style`: `ml` (machine learning), `math` (optimization/theory), `default` (other).
The scripts do not read model/provider/API-key settings. Codex owns the native subagent model, reasoning, authentication, and tools.

### 5. Run the strict citation gate and repair once

```bash
python3 "$REASFLOW_SKILLS_ROOT/citation-hygiene/scripts/check_citation_hygiene.py" \
  --project-dir intro \
  --main-file main.tex \
  --bib intro/references.bib \
  --claim-ledger intro/organized_info.json \
  --trace-json intro/citation_report.json \
  --allow-unused \
  --strict
```

Do not deliver an introduction that fails this command. Send the report back to the same `intro-writer` thread for at most one focused repair, then finalize and check again. An earlier citation in a paragraph does not cover a later sentence that makes its own literature claim.

## Deliverables
- `intro/introduction.tex` + `intro/references.bib`
- `intro/main.tex` (compilable wrapper)
- `intro/*_info.json` intermediate extraction files
- `intro/tasks/*.json` native subagent contracts
- `intro/source_references.bib` verified source bibliography
- `intro/literature_retrieval.json` supplemental search trace
- `intro/citation_trace.json` writer claim provenance
- `intro/citation_report.json` for every generated introduction
- missing-evidence list for any fields that came back empty
