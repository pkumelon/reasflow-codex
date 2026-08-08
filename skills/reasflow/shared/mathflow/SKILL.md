---
name: mathflow
description: Use when mathematical research, modeling, derivation, simulation, validation, or report-writing needs staged guidance before proceeding.
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

## Role

`mathflow` is the only top-level skill for staged mathematical work. It is a router and state tracker, not a request to eagerly read every stage guide.

Use the `skill` tool only for `mathflow`; do not load stage files as top-level skills.

## Use when

Use this skill for mathematical research, contest modeling, derivations, proof checks, numerical experiments, result validation, or final mathematical reporting when the work may need staged judgment.

## Stage Files

Stage guidance lives in subordinate files under this skill directory:

- `stages/problem-analysis.md`
- `stages/mathematical-modeling.md`
- `stages/derivation-and-proof-checking.md`
- `stages/research-planning.md`
- `stages/numerical-experimentation.md`
- `stages/result-validation.md`
- `stages/self-audit-loop.md`
- `stages/report-writing.md`

When the next step requires detailed stage rules, read only the one relevant stage file. Do not read all stage files up front.

## Mathflow State

Start each staged response with a compact state block:

```text
Mathflow State
- Current stage: <stage name or "triage">
- Evidence so far: <one short sentence>
- Next stage: <one stage name or "fast path">
- Why this stage: <one short sentence>
- Needs from user: <missing input or "none">
```

For small tasks, use `fast path` and answer directly after the state block when a full stage handoff would add ceremony without reducing risk.

## Routing Rules

- Start underspecified or open-ended work in `problem-analysis`.
- Use `mathematical-modeling` before introducing new variables, equations, assumptions, or model families.
- Use `derivation-and-proof-checking` when a claim depends on proof, derivation, symbolic manipulation, or mathematical argument quality.
- Use `research-planning` before simulations, solver runs, sweeps, empirical checks, or numerical comparisons.
- Use `numerical-experimentation` for reproducible computational execution after an objective, baseline, metric, and stop rule exist.
- Use `result-validation` when a result needs special cases, limit cases, sensitivity, consistency, or counterexample checks.
- Use `self-audit-loop` only as the final adversarial review before strong conclusions or final reporting.
- Use `report-writing` only when prior work has enough grounded material to write honestly.

## Light And Full Modes

Use light mode for small, local tasks such as checking one equation, clarifying one model choice, or explaining one result. In light mode, keep the state block brief and read a stage file only if the task crosses into real modeling, proof, computation, validation, or reporting risk.

Use full mode for contest problems, papers, multi-step research, model-backed claims, numerical studies, or any work where premature certainty would be costly. In full mode, move one stage at a time and preserve handoffs.

For full-mode deliverable requests, such as "solve the problem", "run the experiments", "write the report", or "generate/compile the final artifact", Stage handoffs are internal checkpoints, not a reason to end the turn. If the next stage is known and Needs from user is none, do not stop after printing a Stage Handoff; immediately read the relevant stage file and continue into the next stage. Pause at a handoff only when the user explicitly asked for a checkpoint, missing input is required, or an external blocker prevents meaningful progress.

## Handoff Format

When handing off to a stage, use:

```text
Stage Handoff
- Stage file to read: stages/<stage>.md
- Work to do now: <concrete next action>
- Stop condition: <what must be true before moving on>
- Likely return path: <where to route if this stage finds a problem>
```

## Common Pitfalls

- Do not let child stage names compete with `mathflow`; they are internal stage files.
- Do not collapse planning and numerical execution for nontrivial computational work.
- Do not treat numerical evidence as proof.
- Do not promote a validated-looking result to a final claim before checking overreach.
- Do not force the full pipeline when a small task only needs a light check.
