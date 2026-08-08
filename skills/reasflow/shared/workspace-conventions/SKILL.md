---
name: workspace-conventions
description: Conventions for tools, skills, and project state in reasflow workspaces.
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

## Tools

Standard shell tools are available in PATH. Use them directly.

- Build Lean projects: `lake build`, `lake build Mathlib.Order.Basic`
- Compile LaTeX documents: `latexmk`
- Run Python with the local project environment. Prefer an active or workspace-local virtual environment; otherwise use the available `python`/`python3` command.
- Search code: `rg`, `fd`, `jq`, `grep`, `find`
- Open a file in the web UI: `open main.pdf`

After compiling LaTeX, run `open main.pdf` to show the PDF
in the user's browser.

When the user asks to use MCP, or asks to compile LaTeX or
build Lean via MCP, just run the command directly (`latexmk`,
`lake build`, etc.). All tools are standard shell commands.

### Python

Use regular Python tooling for reasflow work. External runtime-specific
Python wrappers are not required by reasflow.

For experiment workflows, prefer the workspace-local environment when present:

- Windows: `Alg_Exp/.venv/Scripts/python.exe`
- Unix/macOS: `Alg_Exp/.venv/bin/python`

If the workflow or shell wrapper auto-selects `.venv`, plain `python` and
`python -m pip` are fine. If no environment exists yet, create one with
`python -m venv Alg_Exp/.venv` or `uv venv Alg_Exp/.venv` when `uv` is
available.

Examples:

- `python -c 'print(1+1)'` - run inline code
- `python script.py` - run a file
- `python -m pip install <pkg>` - install a package
- `python -m pip list` - list installed packages

## Skills

Skills are markdown files with YAML frontmatter (name, description).

- Built-in skills: ./.agents/skills/ (packaged in agent image)
- Project skills: ./.agents/skills/
