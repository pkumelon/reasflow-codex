#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import platform
import re
from pathlib import Path


MAX_ALLOWED_TIMEOUT = 1800


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--command", required=True)
    parser.add_argument("--scripts-root")
    parser.add_argument("--output-root")
    parser.add_argument("--venv-root")
    parser.add_argument("--log-dir", default="logs")
    parser.add_argument("--name", default="run_experiment")
    parser.add_argument("--script-name")
    return parser.parse_args()


def estimate_runtime_seconds(command: str) -> int:
    lowered = command.lower()
    if "pip install" in lowered:
        return 180
    match_epoch = re.search(r"--epochs?\s+(\d+)", lowered)
    if match_epoch:
        return min(MAX_ALLOWED_TIMEOUT, max(60, int(match_epoch.group(1)) * 30))
    match_rounds = re.search(r"--(rounds|communication_rounds)\s+(\d+)", lowered)
    if match_rounds:
        return min(MAX_ALLOWED_TIMEOUT, max(60, int(match_rounds.group(2)) * 20))
    if any(token in lowered for token in ["train", "experiment", "run_experiment", "uv run"]):
        return 1200
    if lowered.startswith("python ") or " python " in lowered:
        return 180
    return 60


def quote(path: Path) -> str:
    text = str(path)
    return f'"{text}"' if " " in text else text


def build_platform_commands(command: str, workspace: Path, venv_root: Path | None) -> tuple[str, str]:
    if venv_root is None:
        venv_root = workspace / ".venv"
    posix_python = venv_root / "bin" / "python"
    posix_pip = venv_root / "bin" / "pip"
    win_python = venv_root / "Scripts" / "python.exe"
    win_pip = venv_root / "Scripts" / "pip.exe"

    def adjust(cmd: str, is_windows: bool) -> str:
        stripped = cmd.strip()
        if stripped.startswith("python "):
            exe = win_python if is_windows and win_python.exists() else posix_python if posix_python.exists() else "python"
            return f"{quote(exe) if isinstance(exe, Path) else exe} {stripped[len('python '):]}".strip()
        if stripped.startswith("pip "):
            exe = win_pip if is_windows and win_pip.exists() else posix_pip if posix_pip.exists() else "pip"
            return f"{quote(exe) if isinstance(exe, Path) else exe} {stripped[len('pip '):]}".strip()
        return stripped

    posix_cmd = f'cd {quote(workspace)} && {adjust(command, False)}'
    win_cmd = f'cd /d {quote(workspace)} && {adjust(command, True)}'
    return posix_cmd, win_cmd


def write_scripts(
    workspace: Path,
    scripts_root: Path,
    command: str,
    log_dir: str,
    name: str,
    venv_root: Path | None,
) -> dict:
    scripts_dir = scripts_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    posix_cmd, win_cmd = build_platform_commands(command, workspace, venv_root)
    bash_path = scripts_dir / f"{name}.sh"
    bat_path = scripts_dir / f"{name}.bat"

    bash_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'WORKSPACE={quote(workspace)}',
                f'LOG_DIR={quote((scripts_root / log_dir).resolve())}',
                "mkdir -p \"$LOG_DIR\"",
                "STAMP=${RUN_STAMP:-$(date +%Y%m%d-%H%M%S)}",
                f'LOG_FILE="$LOG_DIR/{name}-$STAMP.log"',
                f'printf "command: %s\\n" {json.dumps(command)} | tee "$LOG_FILE"',
                f'{posix_cmd} 2>&1 | tee -a "$LOG_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    bash_path.chmod(0o755)

    bat_path.write_text(
        "\r\n".join(
            [
                "@echo off",
                "setlocal",
                f'set LOG_DIR={(scripts_root / log_dir).resolve()}',
                "if not exist \"%LOG_DIR%\" mkdir \"%LOG_DIR%\"",
                f'set LOG_FILE=%LOG_DIR%\\{name}.log',
                f'echo command: {command} > "%LOG_FILE%"',
                f'{win_cmd} >> "%LOG_FILE%" 2>&1',
            ]
        )
        + "\r\n",
        encoding="utf-8",
    )

    return {
        "script_bash": str(bash_path.relative_to(workspace)) if bash_path.is_relative_to(workspace) else str(bash_path),
        "script_windows": str(bat_path.relative_to(workspace))
        if bat_path.is_relative_to(workspace)
        else str(bat_path),
        "command_posix": posix_cmd,
        "command_windows": win_cmd,
    }


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    scripts_root_arg = args.scripts_root or args.output_root
    if scripts_root_arg:
        scripts_root_path = Path(scripts_root_arg)
        scripts_root = (
            scripts_root_path.resolve()
            if scripts_root_path.is_absolute()
            else (workspace / scripts_root_path).resolve()
        )
    else:
        scripts_root = workspace
    venv_root = Path(args.venv_root).resolve() if args.venv_root else None
    name = args.script_name or args.name
    estimated = estimate_runtime_seconds(args.command)
    scripts = write_scripts(
        workspace,
        scripts_root,
        args.command,
        args.log_dir,
        name,
        venv_root,
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "estimated_runtime_seconds": estimated,
                "defer_recommended": estimated > 300,
                "scripts": scripts,
                "log_dir": str((scripts_root / args.log_dir).resolve()),
                "platform": platform.system(),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
