---
name: reasflow-initializer
description: Use when the user asks Codex to initialize, set up, convert, or bootstrap a folder/workspace/project as a reasflow project, or asks how an agent should install reasflow into the current directory. Also use after a just-completed reasflow initialization when the user asks for research, survey, algorithm, proof, experiment, introduction, paper writing, or other academic-paper work that may need reasflow, even if they do not explicitly mention reasflow.
---

# Reasflow Initializer

## Goal

Initialize a target folder as a reasflow Codex project by running the reasflow-codex local installer from that folder.

Only this initializer skill should be installed globally by default. Full reasflow agents and private skills should be installed locally into a target project when the user asks to initialize that project.

## Workflow

1. Identify the target project root. If the user says "this folder" or "current project", use the current working directory.
2. Check for existing reasflow files:
   ```bash
   find . -maxdepth 3 \( -path './.codex/config.toml' -o -path './.codex/agents' -o -path './.agents/skills' -o -path './.codex/reasflow-skills' \) -print
   ```
3. If no conflicting reasflow targets exist, run the local installer from the target root.

   Unix/macOS or other bash-capable shells:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/install.sh | bash
   ```

   Windows PowerShell / pwsh:
   ```powershell
   $installer = Join-Path $env:TEMP "reasflow-codex-install.ps1"
   irm https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/install.ps1 -OutFile $installer
   pwsh -NoProfile -ExecutionPolicy Bypass -File $installer
   ```

4. If targets already exist and the user wants to refresh/replace them, run the same installer with force enabled.

   Unix/macOS or other bash-capable shells:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/install.sh | bash -s -- --force
   ```

   Windows PowerShell / pwsh:
   ```powershell
   $installer = Join-Path $env:TEMP "reasflow-codex-install.ps1"
   irm https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/install.ps1 -OutFile $installer
   pwsh -NoProfile -ExecutionPolicy Bypass -File $installer -Force
   ```
5. Tell the user to restart Codex in that project so `.codex/config.toml`, `.codex/agents/`, and `.agents/skills/` are reloaded.

Codex does not hot reload project config, agents, or skills. Restarting Codex is the default and safest path after initialization.

## After Initialization

If this session just initialized a folder as reasflow and the user has not restarted Codex yet, treat later academic-paper requests as likely reasflow requests even when the user does not say "reasflow".

Requests in scope include literature survey, related work, algorithm design, convergence proof, theorem/lemma work, experiments, introduction/abstract writing, paper assembly, LaTeX report generation, or other research-paper pipeline work.

Before doing such work, tell the user Codex must restart to load the newly installed `.codex/config.toml`, `.codex/agents/`, and `.agents/skills/`. Ask whether they want to restart Codex or force a no-restart run.

Only if the user explicitly confirms forcing a no-restart run, read `references/no-restart-main-bootstrap.md` completely before doing task work. Follow its manual role-bootstrap procedure exactly; do not start survey, proof, experiment, or writing work until the main project config has been read and subagent dispatch availability has been checked.

## Local Source Checkout

When working inside or near a checked-out `reasflow-codex` repository, prefer installing from that checkout instead of downloading from GitHub:

```bash
REASFLOW_DEV_SOURCE_DIR=/path/to/reasflow-codex bash /path/to/reasflow-codex/install.sh
```

On Windows PowerShell / pwsh, the equivalent is:

```powershell
$env:REASFLOW_DEV_SOURCE_DIR = "C:\path\to\reasflow-codex"
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\reasflow-codex\install.ps1"
```

Use `--force` for bash or `-Force` for pwsh only when replacing existing installed reasflow targets is intended.

## Expected Result

After local initialization, the target project should contain:

```text
.agents/skills/
.codex/agents/
.codex/config.toml
.codex/reasflow-skills/
.reasflow-dev/manifest.txt
```

To install or update only this initializer skill globally, follow:

https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/docs/install-initializer-skill.md

Do not run the full global installer unless the user explicitly asks for the full global reasflow agent set.
