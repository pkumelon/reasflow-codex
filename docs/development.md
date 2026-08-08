# Reasflow-dev Development Notes

`reasflow-codex` is a resource repository for Codex:

- `skills/`
- `agents/`
- installer scripts

There is no Rust code, no opencode runtime, and no build step.

## Design

The default installer design:

1. Default scope is local.
2. Default mode does not require git.
3. Default install is directly usable and does not pollute global configuration.

Main installer switches:

- `--global`
- `--dev`
- `--force`

## Repository Layout

```text
reasflow-codex/
├── agents/
├── docs/
├── skills/
├── install.sh
├── install.ps1
└── README.md
```

## Skill Visibility

Treat skills as resources explicitly mounted by agents instead of globally exposing everything.

- Shared skills live under `skills/reasflow/shared/`.
- Private skills live under `skills/reasflow/<category>/`.
- `agents/*.toml` should only list the `[[skills.config]]` entries that agent needs.
- Do not put private project skills in global `~/.codex/config.toml`.

Recommended source layout:

```text
skills/
└── reasflow/
    ├── shared/
    ├── common/
    ├── intro/
    ├── paper/
    ├── prover/
    ├── survey/
    ├── experiment/
    └── algorithm/
```

Installed layout:

```text
.agents/skills/<shared-skill>/
.codex/reasflow-skills/<category>/<private-skill>/
```

Shared skills are auto-scanned. Private skills must be mounted explicitly from agent config, for example:

```toml
[[skills.config]]
path = "../../.codex/reasflow-skills/prover/knowledge-card-retrieval/SKILL.md"
enabled = true
```

`enabled = true` is required for each `[[skills.config]]` entry. Do not put `enabled` at the top level of `agents/*.toml`.

## Development Install

Dev mode keeps a git checkout and installs symlinks:

```bash
curl -fsSL https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/install.sh | bash -s -- --dev
```

Global dev mode:

```bash
curl -fsSL https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/install.sh | bash -s -- --dev --global
```

When working from a local checkout, install from that checkout:

```bash
REASFLOW_DEV_SOURCE_DIR=/path/to/reasflow-codex bash /path/to/reasflow-codex/install.sh
```

Use `--force` only when replacing existing installed targets is intended.

## Updating

Rerun the same install command to update.

If previous install used `--dev`, rerunning the installer refreshes the local clone and keeps symlink-based installation.

## Conflict Handling

If a target skill or agent already exists, the installer stops by default.

Replace managed targets explicitly:

```bash
./install.sh --force
```

## Content Notes

- `agents/*.toml` defines Codex custom agents.
- `skills/*/SKILL.md` defines project/global Codex skills.
- Older prompts that depended on `$PACK_ROOT` have been migrated to installed skill root resolution.
- Compatibility scripts exist for older agent entrypoints that referenced missing paths.
