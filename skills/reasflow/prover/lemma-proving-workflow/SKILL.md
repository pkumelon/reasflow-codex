---
name: lemma-proving-workflow
description: Full workflow for systematically proving and verifying mathematical lemmas via prover/verifier sub-agent tasks. Read this before dispatching any lemma-prover or lemma-verifier task.
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

# Lemma Prover Workflow

## Overview

This skill provides the complete workflow for proving and verifying mathematical lemmas in sequence, coordinating lemma-prover and lemma-verifier sub-agent tasks with correct context packing.

**Reliability First**: Thorough preparation before starting any proof is mandatory. Starting proofs without comprehensive knowledge of references and problem context will be considered unreliable.

**STRICT LEMMA SEPARATION**: Each lemma MUST be handled by separate sub-agent tasks for prover and verifier. No sharing of tasks across different lemmas.

**ITERATIVE VERIFICATION**: Prove and verify lemmas **one at a time** in sequence. Do NOT prove all lemmas first, then verify all later.

**⚠️ Codex Architecture Note**: Background sub-agent tasks always start with fresh context — there is no session memory between calls. For correction tasks, you MUST embed the full draft file path (as "read this first"), the complete verifier error report, and all context file paths in the prompt so the sub-agent can restore its understanding from files.

---

## 1. Essential Preparation

**CRITICAL**: Before starting any lemma proving, you MUST thoroughly understand ALL relevant materials. Attempting proofs with incomplete understanding is unreliable and will be rejected.

Read and understand ALL of the following before proceeding:

**From references:**
- All Algorithms — understand the computational framework
- All Assumptions — know the foundational constraints
- All Lemmas and Theorems — understand intermediate and main results
- Key Proofs — understand proof techniques and frameworks

**From current workspace:**
- `<workspace>/prover/problem/algorithm.tex` — user's specific algorithm
- `<workspace>/prover/problem/description.tex` — problem background
- `<workspace>/prover/drafts/plan.tex` — overall proof framework
- `<workspace>/prover/problem/assumptions.tex` — all constraints
- `<workspace>/prover/proven/` — all previously proven lemmas

**If any materials are missing**: Stop immediately, report what is missing, wait for user confirmation before proceeding. Do NOT attempt to prove lemmas with incomplete information.

---

## 2. Core Loop: For Each Lemma

**ONE LEMMA AT A TIME.** Complete the full prove → verify → promote cycle before starting the next lemma. Early verification prevents cascading errors.

### Step A — Delegate to lemma-prover

For each **NEW lemma**, start a fresh lemma-prover background task. The prompt MUST include:

```
Task: Prove [Lemma N — exact goal statement and expected bound form]

⚠️ Context Loading (read ALL before starting):
- <workspace>/prover/problem/algorithm.tex
- <workspace>/prover/problem/assumptions.tex
- <workspace>/prover/problem/description.tex
- <workspace>/prover/drafts/plan.tex
- <workspace>/prover/proven/ (all files)

Reference files (read source .tex, not just conclusions):
- <workspace>/prover/references/<ref_name>/[file.tex]:[line range]
  → Borrow the proof framework and bounding techniques from [specific theorem/lemma name]

Knowledge card content (paste relevant card YAML content here, not just IDs):
[paste card content if Coordinator retrieved relevant cards]

Output path: <workspace>/prover/drafts/lemma_N.tex
```

For **correction** of the same lemma, start a NEW lemma-prover background task. Since the sub-agent starts with fresh context, the correction prompt MUST include ALL of the following:

```
Task: Correction — Fix Lemma N

⚠️ FIRST ACTION REQUIRED: Read <workspace>/prover/drafts/lemma_N.tex BEFORE anything else.
   This is your previous proof. Restore your understanding of it before making corrections.

Verifier errors to fix (complete error report):
[ISSUES_FOUND]:
[paste the COMPLETE ISSUES_FOUND section verbatim from the FAIL report]

Context files to read after reading the draft:
- <workspace>/prover/problem/algorithm.tex
- <workspace>/prover/problem/assumptions.tex
- <workspace>/prover/problem/description.tex
- <workspace>/prover/drafts/plan.tex
- <workspace>/prover/proven/ (all files)

Reference files:
- [same as original task — include specific file paths and line numbers]
```

### Step B — Verify file was created

```bash
ls <workspace>/prover/drafts/lemma_N.tex
```

- ✅ File exists → proceed to Step C
- ❌ File missing → report error and re-dispatch prover task

### Step C — Delegate to lemma-verifier

For each lemma (new or corrected), start a fresh lemma-verifier background task. The prompt MUST include:

```
Task: Verify <workspace>/prover/drafts/lemma_N.tex

Context files to read:
- <workspace>/prover/problem/algorithm.tex
- <workspace>/prover/problem/assumptions.tex
- <workspace>/prover/problem/description.tex
- <workspace>/prover/drafts/plan.tex
- <workspace>/prover/proven/ (all files)

Tightness check: Verify the conclusion matches plan.tex's expected bound form.

Required output format:
[COMMENTS]: (one paragraph per section — Logic, Calculations, Bounds, Completeness, Big-O, LaTeX)
[ISSUES_FOUND]: (numbered list of issues, or "None" if PASS)
[VERIFICATION_RESULT]: PASS or FAIL
```

### Step D — Act on verification result

**PASS**:
```bash
mv <workspace>/prover/drafts/lemma_N.tex <workspace>/prover/proven/lemma_N_final.tex
```
Then check the promoted file:
- Assumptions reference `prover/problem/assumptions.tex`, not restated inline
- Algorithm update rules reference `prover/problem/algorithm.tex`, not treated as assumptions
- Conclusion is consistent with plan.tex; if format or result mismatch, re-assign

**FAIL**:
- Read the ISSUES_FOUND section carefully
- Dispatch correction task (Step A, correction mode) with the COMPLETE verifier error report pasted in
- After correction, dispatch new verifier task (Step C)
- Repeat until PASS

Do NOT start the next lemma until the current one passes verification.

---

## 3. Reliability Checklist

Before dispatching ANY lemma-prover task, confirm:

- ✅ All references: Algorithms, Assumptions, Lemmas, Theorems, and Proofs understood
- ✅ User's algorithm fully understood from algorithm.tex
- ✅ Problem description clear and complete
- ✅ Proof plan exists and makes sense
- ✅ All assumptions documented in assumptions.tex
- ✅ All previous proven lemmas reviewed from proven/
- ✅ Lemma separation enforced: dedicated prover+verifier tasks per lemma only
- ✅ Iterative strategy confirmed: prove and verify one lemma at a time

---

## 4. Error Handling

If a sub-agent returns unexpected output (tool call dumps, JSON, error text instead of proof content):
- **Must restart the task** with a new sub-agent call
- Do not continue with a corrupted response

---

## 5. Prohibited Behaviors

- ❌ Dispatching the same sub-agent task for multiple different lemmas
- ❌ Proving all lemmas first, then verifying all later
- ❌ Dispatching correction task without including the draft file path as "read first"
- ❌ Dispatching correction task without pasting the complete verifier error report
- ❌ Omitting reference file paths and line numbers from prover prompts
