# Reasflow Initializer Skill Installation Guide

Use this guide when a user asks you to install or update the reasflow initializer skill globally for Codex.

## Goal

Install only the small `reasflow-initializer` skill globally so future Codex sessions know how to initialize a folder as a reasflow project.

Do not run the full reasflow-codex global installer unless the user explicitly asks for the full global reasflow agent set.

This guide writes only to:

```text
~/.agents/skills/reasflow-initializer/
```

It does not write:

```text
~/.codex/agents/
~/.codex/reasflow-skills/
~/.codex/config.toml
```

## Unix or macOS

Install or update the initializer skill:

```bash
skill_dir="$HOME/.agents/skills/reasflow-initializer"
mkdir -p "$skill_dir/agents" "$skill_dir/references"
curl -fsSL https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/skills/reasflow/shared/reasflow-initializer/SKILL.md -o "$skill_dir/SKILL.md"
curl -fsSL https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/skills/reasflow/shared/reasflow-initializer/agents/openai.yaml -o "$skill_dir/agents/openai.yaml"
curl -fsSL https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/skills/reasflow/shared/reasflow-initializer/references/no-restart-main-bootstrap.md -o "$skill_dir/references/no-restart-main-bootstrap.md"
```

Verify:

```bash
test -f "$HOME/.agents/skills/reasflow-initializer/SKILL.md"
test -f "$HOME/.agents/skills/reasflow-initializer/agents/openai.yaml"
test -f "$HOME/.agents/skills/reasflow-initializer/references/no-restart-main-bootstrap.md"
```

## Windows PowerShell

Install or update the initializer skill:

```powershell
$skillDir = Join-Path $env:USERPROFILE ".agents\skills\reasflow-initializer"
New-Item -ItemType Directory -Force -Path (Join-Path $skillDir "agents") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $skillDir "references") | Out-Null
irm https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/skills/reasflow/shared/reasflow-initializer/SKILL.md -OutFile (Join-Path $skillDir "SKILL.md")
irm https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/skills/reasflow/shared/reasflow-initializer/agents/openai.yaml -OutFile (Join-Path $skillDir "agents\openai.yaml")
irm https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/skills/reasflow/shared/reasflow-initializer/references/no-restart-main-bootstrap.md -OutFile (Join-Path $skillDir "references\no-restart-main-bootstrap.md")
```

Verify:

```powershell
Test-Path "$env:USERPROFILE\.agents\skills\reasflow-initializer\SKILL.md"
Test-Path "$env:USERPROFILE\.agents\skills\reasflow-initializer\agents\openai.yaml"
Test-Path "$env:USERPROFILE\.agents\skills\reasflow-initializer\references\no-restart-main-bootstrap.md"
```

Tell the user to restart Codex after installation so the global skill is reloaded.

## Initialize a Project Later

After installing this skill, the user can ask Codex from a target project:

```text
Initialize this folder as a reasflow project.
```

The `reasflow-initializer` skill tells Codex to run the local project installer from that project root.
For later project initialization, the repository provides both `install.sh` for bash-capable shells and `install.ps1` for Windows PowerShell / pwsh; use the one that matches the user's environment.
