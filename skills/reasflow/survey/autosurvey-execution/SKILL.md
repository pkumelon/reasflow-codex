---
name: autosurvey-execution
description: Use when running the full survey outline, draft, related-works, or unattended survey pipeline
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

# AutoSurvey Execution

## Overview
Run the survey pipeline using Codex's configured model for all LLM work. Python handles data operations and prompt preparation; Codex survey subagents handle the actual drafting stages.

## Architecture

Three layers:
1. **Python `autosurvey_tools.py`** — pure data operations + prompt preparation using vendored prompt templates. Outputs JSON files with prepared prompts.
2. **Codex subagents** — `survey-outline`, `survey-section-writer`, `survey-related-works`, `survey-judge`.
3. **Workspace artifacts** — prompt JSON, outline Markdown, survey draft, and LaTeX/BibTeX outputs.

`batch_chat` maps to multiple `spawn_agent` calls, each followed by `wait_agent`.
`chat` maps to one `spawn_agent` + `wait_agent`.

Retrieval inside the writing stages uses the local paper pool. `--library-dir` (default `survey/library`) contains paper JSON produced by the `autosurvey-paper-retrieval` skill; `autosurvey_tools.py` builds an in-memory `ExternalPaperDatabase` from it. Commands that need a paper database require a non-empty library.

## Environment
Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/autosurvey-execution"`.
Use `python3` by default:

```bash
python3 "$SKILL_ROOT/scripts/autosurvey_tools.py" ...
```

Dependencies are limited to the Python standard library plus the optional `arxiv`/`paper` extras (see `pyproject.toml`).

## Helper Script

`autosurvey_tools.py` provides these commands:

### Data + Prompt Preparation
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-outline-data --topic "..." --output-path survey/stage1.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" merge-outline-data --outlines-path survey/outlines.json --output-path survey/stage2.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-subsection-outline-data --topic "..." --section-outline-path survey/section_outline.md --output-path survey/stage3.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-edit-outline-data --merged-outline-path survey/merged.md --output-path survey/stage4.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" merge-outline --section-outline-path survey/section_outline.md --subsection-outlines-path survey/subsections.json --output-path survey/merged_outline.md`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-subsection-data --topic "..." --outline-path survey/outline.md --output-path survey/stage5.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-native-survey-data --topic "..." --outline-path survey/outline.md --output-path survey/native_survey_prompt.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-citation-check-data --topic "..." --drafts-path survey/drafts.json --output-path survey/cite_check.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-lce-data --topic "..." --content-path survey/sections.json --output-path survey/lce.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" resolve-references --survey-path survey/survey_raw.md --output-path survey/survey.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" generate-bibtex --survey-json survey/survey.json --bib-output related_works/references.bib --key-map-output related_works/citation_key_map.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" assemble-survey --outline-path survey/outline.md --sections-dir survey/sections --output-path survey/survey_raw.md`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-related-works-data --topic "..." --survey-path survey/survey.json --output-path related_works/rw_prompt.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-judge-data --topic "..." --survey-path survey/survey.json --output-path survey/judge.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" finalize-package --topic "..." --survey-root survey --related-root related_works --json`

### Validation
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" validate --workspace . --survey-root survey --tex related_works/related_works.tex --bib related_works/references.bib --json`

## Default Native Pipeline

Use this path first. It keeps the retrieval, citation resolution, BibTeX rendering, and packaging guards, while letting the model write the survey as a coherent long-form artifact.

1. Create `survey/`, `survey/library/`, and `related_works/`.
2. Prepare and write an outline:
   - `prepare-outline-data` → `survey/stage1.json`
   - `spawn_agent` survey-outline with the prepared prompt, then `wait_agent` → `survey/outline.md`
3. Prepare one complete survey-writing prompt:
   - `prepare-native-survey-data --topic "..." --outline-path survey/outline.md --output-path survey/native_survey_prompt.json`
4. Run one native long-form writing stage:
   - `spawn_agent` survey-section-writer with `survey/native_survey_prompt.json`, then `wait_agent` → `survey/survey.md`
5. Resolve title-bracket citations to numbered citations:
   - `resolve-references --survey-path survey/survey.md --output-path survey/survey.json`
6. Generate BibTeX and related-work prompt:
   - `generate-bibtex --survey-json survey/survey.json --bib-output related_works/references.bib --key-map-output related_works/citation_key_map.json`
   - `prepare-related-works-data --topic "..." --survey-path survey/survey.json --output-path related_works/rw_prompt.json`
7. Run related-work synthesis:
   - `spawn_agent` survey-related-works with `related_works/rw_prompt.json`, then `wait_agent` → `related_works/related_works.tex`
8. Enforce package layout and citation consistency:
   - `finalize-package --topic "..." --survey-root survey --related-root related_works --json`
   - `validate --workspace . --survey-root survey --tex related_works/related_works.tex --bib related_works/references.bib --json`
   - `finalize-package` removes prompt/stage/library intermediates by default so the final workspace is a clean survey delivery. Use `--keep-intermediates` only for debugging failed runs.

Required final files:
- `survey/outline.md`
- `survey/survey.md`
- `survey/survey.json`
- `survey/references.bib`
- `related_works/related_works.tex`
- `related_works/references.bib`

## Legacy Full Pipeline (fallback only)

Use the legacy multi-stage flow only when the native survey draft is too short, does not cite the paper library, or fails to resolve citations. Do not use it as the normal path.

# Phase 1: Outline Generation
1. `autosurvey_tools.py prepare-outline-data` → survey/stage1.json
2. For each prompt: `spawn_agent` survey-outline, then `wait_agent` → rough outlines
3. `autosurvey_tools.py merge-outline-data` → survey/stage2.json
4. `spawn_agent` survey-outline, then `wait_agent` → survey/section_outline.md
5. `autosurvey_tools.py prepare-subsection-outline-data` → survey/stage3.json
6. For each prompt: `spawn_agent` survey-outline, then `wait_agent` → subsection outlines
7. `autosurvey_tools.py merge-outline` → survey/merged_outline.md
8. `autosurvey_tools.py prepare-edit-outline-data` → survey/stage4.json
9. `spawn_agent` survey-outline, then `wait_agent` → survey/outline.md

# Phase 2: Survey Writing
10. `autosurvey_tools.py prepare-subsection-data` → survey/stage5.json
11. For each section: `spawn_agent` survey-section-writer, then `wait_agent`
12. For each section: citation-check prompts → `spawn_agent` survey-section-writer, then `wait_agent`
13. `autosurvey_tools.py assemble-survey` → survey/survey_raw.md
14. `autosurvey_tools.py resolve-references` → survey/survey.json

# Phase 3: LCE Refinement (two-pass even/odd)
15. `autosurvey_tools.py prepare-lce-data` (even) → survey/lce_even.json
16. For even-indexed subsections: `spawn_agent` survey-section-writer, then `wait_agent`
17. `autosurvey_tools.py prepare-lce-data` (odd, updated content) → survey/lce_odd.json
18. For odd-indexed subsections: `spawn_agent` survey-section-writer, then `wait_agent`
19. `autosurvey_tools.py assemble-survey` → survey/survey_refined.md
20. `autosurvey_tools.py resolve-references` → survey/survey.json (final)

# Phase 4: Related Works
21. `autosurvey_tools.py prepare-related-works-data` → related_works/rw_prompt.json
22. `spawn_agent` survey-related-works, then `wait_agent` → related_works/related_works_raw.tex
23. `autosurvey_tools.py generate-bibtex` → related_works/references.bib
24. Sanitize related_works_raw.tex → related_works/related_works.tex

# Phase 5: Judging
25. `autosurvey_tools.py prepare-judge-data` → survey/judge.json
26. For each criterion: `spawn_agent` survey-judge, then `wait_agent`

# Phase 6: Validation
27. `autosurvey_tools.py finalize-package` → enforce required files and cite/BibTeX consistency; also sync `related_works/references.bib` to `survey/references.bib` for benchmark-compatible survey evaluation.
28. `autosurvey_tools.py validate` → consistency report

## Deliverables
- `survey/outline.md`
- `survey/survey.md` + `survey/survey.json`
- `survey/references.bib` (synced copy for survey-mode evaluation)
- `related_works/related_works.tex`
- `related_works/references.bib`
- validation report with cite/BibTeX mismatches or preamble cleanup notes
