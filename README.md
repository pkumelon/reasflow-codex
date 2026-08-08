# reasflow-codex

Codex resources for running reasflow, an academic paper-writing pipeline.

This repository ships:

- Codex skills
- Codex agents
- installers for global use and per-project initialization

## Install With an Agent

Paste this into Codex, Claude Code, Cursor, or another shell-capable agent:

```text
Install or update only the reasflow initializer skill globally for Codex by following this guide:
https://raw.githubusercontent.com/pkumelon/reasflow-codex/main/docs/install-initializer-skill.md
```

Restart Codex after installation.

## Use Reasflow

Inside any folder you want to turn into a reasflow project, tell Codex:

```text
Initialize this folder as a reasflow project.
```

The initializer skill teaches Codex how to initialize individual reasflow projects later. It does not install the full reasflow agent set globally.

## More

- Initializer skill installation guide: [docs/install-initializer-skill.md](docs/install-initializer-skill.md)
- Development notes: [docs/development.md](docs/development.md)

## License

MIT — see [LICENSE](LICENSE).
