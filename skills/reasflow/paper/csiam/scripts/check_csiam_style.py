#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_PATTERNS = {
    "documentclass_csiam_am": re.compile(r"\\documentclass(?:\[[^\]]*\])?\{csiam-am\}"),
    "bibliographystyle_plain": re.compile(r"\\bibliographystyle\{plain\}"),
}
SUGGESTED_PATTERNS = {
    "ams_code": re.compile(r"\\ams\{[^}]+\}"),
    "keywords": re.compile(r"\\keywords\{[^}]+\}"),
}


def collect_tex(project_dir: Path, main_file: str) -> tuple[Path, str]:
    main_path = project_dir / main_file
    if not main_path.exists():
        raise FileNotFoundError(f"main file not found: {main_path}")
    content = main_path.read_text(encoding="utf-8", errors="replace")
    return main_path, content


def run_checks(main_file: Path, content: str) -> dict[str, Any]:
    required_missing = [
        name for name, pattern in REQUIRED_PATTERNS.items() if not pattern.search(content)
    ]
    suggested_missing = [
        name for name, pattern in SUGGESTED_PATTERNS.items() if not pattern.search(content)
    ]

    issues: list[str] = []
    if re.search(r"\\thanks\{", content):
        issues.append("Avoid \\thanks in CSIAM author block; use \\corrauth and \\address.")
    if re.search(r"\\footnote\{", content):
        issues.append("Avoid \\footnote in heading metadata block for CSIAM.")
    if re.search(r"\\cref\{", content):
        issues.append("CSIAM template usually expects \\ref instead of \\cref unless cleveref is configured.")
    if not re.search(r"\\bibliography\{[^}]+\}", content):
        issues.append("No \\bibliography{...} command found in main file.")

    has_abstract_env = "\\begin{abstract}" in content and "\\end{abstract}" in content
    has_include_guard = bool(re.search(r"\\IfFileExists\{[^}]+\.tex\}\{\\input\{[^}]+\}\}\{\}", content))

    return {
        "main_file": str(main_file),
        "required_missing": required_missing,
        "suggested_missing": suggested_missing,
        "issues": issues,
        "has_abstract_env": has_abstract_env,
        "uses_iffileexists_include_pattern": has_include_guard,
    }


def format_text(report: dict[str, Any]) -> str:
    lines = [
        "=== CSIAM Style Check ===",
        f"main_file: {report['main_file']}",
        f"required_missing: {len(report['required_missing'])}",
    ]
    for item in report["required_missing"]:
        lines.append(f"  - {item}")

    lines.append(f"suggested_missing: {len(report['suggested_missing'])}")
    for item in report["suggested_missing"]:
        lines.append(f"  - {item}")

    lines.append(f"issues: {len(report['issues'])}")
    for issue in report["issues"]:
        lines.append(f"  - {issue}")

    lines.append(f"has_abstract_env: {report['has_abstract_env']}")
    lines.append(f"uses_iffileexists_include_pattern: {report['uses_iffileexists_include_pattern']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check CSIAM-AM template and style expectations in main.tex."
    )
    parser.add_argument("--project-dir", default=".", help="Project directory.")
    parser.add_argument("--main-file", default="main.tex", help="Main TeX file.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.exists():
        print(f"Error: project directory not found: {project_dir}", file=sys.stderr)
        return 1

    try:
        main_path, content = collect_tex(project_dir, args.main_file)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    report = run_checks(main_path, content)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(report))

    failed = bool(report["required_missing"] or report["issues"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
