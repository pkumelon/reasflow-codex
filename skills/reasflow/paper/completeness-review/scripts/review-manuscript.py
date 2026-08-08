#!/usr/bin/env python3
"""Run deterministic manuscript completeness checks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


TODO_PATTERNS = [
    r"\bTODO\b",
    r"\bTBD\b",
    r"\bFIXME\b",
    r"\bXXX\b",
    r"placeholder",
    r"to be added",
    r"待补充",
]
REQUIRED_SECTIONS = ["introduction", "conclusion", "references"]


def trace_inputs(main_tex: Path) -> list[Path]:
    visited: list[Path] = []
    seen: set[Path] = set()

    def _walk(tex_path: Path) -> None:
        if tex_path in seen or not tex_path.exists():
            return
        seen.add(tex_path)
        visited.append(tex_path)
        content = tex_path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"\\(?:input|include)\{([^}]+)\}", content):
            ref = match.group(1).strip()
            candidate = tex_path.parent / ref
            if not candidate.suffix:
                candidate = candidate.with_suffix(".tex")
            _walk(candidate)

    _walk(main_tex)
    return visited


def collect_content(files: list[Path]) -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files)


def find_todos(content: str) -> list[str]:
    findings: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in TODO_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                findings.append(stripped[:220])
                break
    return findings[:50]


def find_missing_sections(content: str) -> list[str]:
    lowered = content.lower()
    missing: list[str] = []
    for section in REQUIRED_SECTIONS:
        if section == "references":
            if "\\bibliography" not in lowered and "\\begin{thebibliography}" not in lowered:
                missing.append(section)
            continue
        if section not in lowered:
            missing.append(section)
    return missing


def summarize_log(log_path: Path) -> dict[str, int]:
    if not log_path.exists():
        return {"warnings": 0, "undefined_refs": 0, "duplicate_labels": 0}
    content = log_path.read_text(encoding="utf-8", errors="replace")
    return {
        "warnings": len(re.findall(r"warning:", content, re.IGNORECASE)),
        "undefined_refs": len(re.findall(r"undefined reference", content, re.IGNORECASE)),
        "duplicate_labels": len(re.findall(r"multiply defined", content, re.IGNORECASE)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review manuscript completeness")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--main-file", default="main.tex")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    main_tex = project_dir / args.main_file
    if not main_tex.exists():
        print(json.dumps({"success": False, "error": f"missing main file: {main_tex}"}, ensure_ascii=False))
        return 1

    files = trace_inputs(main_tex)
    content = collect_content(files)
    todos = find_todos(content)
    missing_sections = find_missing_sections(content)
    cite_count = len(re.findall(r"\\(?:cite|citep|citet|citeauthor|citeyear)\{", content))
    log_summary = summarize_log(project_dir / f"{main_tex.stem}.log")

    report = {
        "success": True,
        "project_dir": str(project_dir),
        "main_file": args.main_file,
        "compiled_tex_files": [str(path.relative_to(project_dir)) for path in files],
        "todo_markers": todos,
        "missing_sections": missing_sections,
        "cite_count": cite_count,
        "log_summary": log_summary,
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=== Completeness Review ===")
        print(f"Project: {project_dir}")
        print(f"Main file: {args.main_file}")
        print(f"Compiled chain: {len(files)} tex files")
        print(f"Citations: {cite_count}")
        print(
            "Log summary: "
            f"{log_summary['warnings']} warnings, "
            f"{log_summary['undefined_refs']} undefined refs, "
            f"{log_summary['duplicate_labels']} duplicate labels"
        )
        print("")
        print("TODO markers:")
        if todos:
            for item in todos:
                print(f"- {item}")
        else:
            print("- none")
        print("")
        print("Missing sections:")
        if missing_sections:
            for item in missing_sections:
                print(f"- {item}")
        else:
            print("- none")

    return 0


if __name__ == "__main__":
    sys.exit(main())
