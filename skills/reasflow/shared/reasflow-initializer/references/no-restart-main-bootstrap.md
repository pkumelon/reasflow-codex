# No-Restart Reasflow Execution

Use only when the project was just initialized and the user explicitly confirms they want to force a reasflow run before restarting Codex.

Codex does not hot reload `.codex/config.toml`, `.codex/agents/`, or newly installed skills. Restarting Codex is preferred.

## Rule

- The current main agent must read `.codex/config.toml` first.
- Reasflow work must still be delegated to subagents. If subagent tools are unavailable in the current session, stop and tell the user to restart Codex.
- Subagents must not read `.codex/config.toml`.
- Every subagent prompt must tell that subagent to read only its own `.codex/agents/<subagent>.toml`.
- Prefer project-local `.codex/agents/*.toml`; use `~/.codex/agents/*.toml` only if the project-local file is absent.

## Mandatory Read Gate

Before any research, survey, proof, experiment, or writing work:

1. Read this file completely to EOF.
2. Read `.codex/config.toml` completely to EOF.
3. Confirm that subagent dispatch tools are available.
4. Confirm in one concise sentence that `.codex/config.toml` was read and whether subagent dispatch is available.

If `.codex/config.toml` cannot be read, or subagent dispatch is unavailable, stop and tell the user to restart Codex instead.

For every spawned or resumed subagent, the child prompt must make that subagent read its own TOML completely to EOF before task work. If it cannot read the TOML, it must stop.

## Main Prompt Prefix

```text
You are the current main reasflow orchestrator. Before doing any task work, read .codex/config.toml completely to EOF to understand the project's reasflow orchestration rules. If .codex/config.toml cannot be read, or if subagent dispatch tools are unavailable, stop and tell the user to restart Codex.

If you spawn or resume any reasflow subagent, do not ask it to read .codex/config.toml. Identify that subagent's TOML file, and prepend its prompt with: "You are <subagent-name>. Before doing any task work, read <subagent-toml-path> completely to EOF to understand your identity, developer instructions, mounted skills, and workflow. Follow that TOML role file as authoritative for this task. If the TOML file cannot be read, stop."
```

Append the user's actual task after this prefix.

## Child Prompt Prefix

```text
You are <subagent-name>. Before doing any task work, read <subagent-toml-path> completely to EOF to understand your identity, developer instructions, mounted skills, and workflow. Follow that TOML role file as authoritative for this task. If the TOML file cannot be read, stop.
```

After the immediate task finishes, tell the user to restart Codex before continuing normal reasflow work.
