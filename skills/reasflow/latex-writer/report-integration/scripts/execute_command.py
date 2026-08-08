#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_command(command: str, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        return {
            "success": result.returncode == 0,
            "command": command,
            "cwd": str(cwd),
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "command": command,
            "cwd": str(cwd),
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timeout ({timeout}s)",
        }
    except Exception as error:
        return {
            "success": False,
            "command": command,
            "cwd": str(cwd),
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command execution error: {error}",
        }


def format_text(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "=== Command Execution Report ===",
            f"success: {report['success']}",
            f"command: {report['command']}",
            f"cwd: {report['cwd']}",
            f"exit_code: {report['exit_code']}",
            "--- stdout ---",
            report["stdout"] or "(empty)",
            "--- stderr ---",
            report["stderr"] or "(empty)",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute shell command with timeout and structured report.")
    parser.add_argument("command", help="Shell command string to execute.")
    parser.add_argument("--cwd", default=".", help="Working directory.")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout in seconds.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve()
    if not cwd.exists():
        print(f"Error: working directory not found: {cwd}", file=sys.stderr)
        return 1

    report = run_command(args.command, cwd, args.timeout)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(report))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
