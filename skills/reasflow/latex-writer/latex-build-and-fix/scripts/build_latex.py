#!/usr/bin/env python3
"""Compile a LaTeX project with structured diagnostics."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from shutil import which
from typing import Any

VALID_ENGINES = {"pdflatex", "xelatex", "lualatex"}
FLE_PATTERN = re.compile(r"^\.?/?([^\s:]+\.tex):(\d+):\s+(.+)$")
WARNING_PATTERNS = [
    (re.compile(r"LaTeX Warning:"), "latex_warning"),
    (re.compile(r"Package \w+ Warning:"), "package_warning"),
    (re.compile(r"Citation .* undefined"), "citation_undefined"),
    (re.compile(r"Reference .* undefined"), "reference_undefined"),
    (re.compile(r"There were undefined references"), "undefined_references"),
    (re.compile(r"There were undefined citations"), "undefined_citations"),
    (re.compile(r"Label .* multiply defined"), "duplicate_label"),
    (re.compile(r"Overfull \\hbox"), "overfull_hbox"),
    (re.compile(r"Underfull \\hbox"), "underfull_hbox"),
    (re.compile(r"Overfull \\vbox"), "overfull_vbox"),
    (re.compile(r"Underfull \\vbox"), "underfull_vbox"),
    (re.compile(r"Float too large for page"), "float_too_large"),
]


def run_step(
    cmd: list[str],
    cwd: Path,
    timeout: int,
    command_log: list[str],
) -> subprocess.CompletedProcess[str]:
    command_log.append(" ".join(cmd))
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        stdin=subprocess.DEVNULL,
    )


def dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for item in records:
        key = (item["file"], item["line"], item["type"], item["message"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def parse_messages(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("!"):
            message = stripped[1:].strip()
            if i + 1 < len(lines) and lines[i + 1].strip():
                message = f"{message} | {lines[i + 1].strip()}"
            errors.append({"file": "main.tex", "line": 0, "type": "latex_error", "message": message[:300]})
            continue
        if (match := FLE_PATTERN.match(stripped)):
            errors.append(
                {
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "type": "latex_error",
                    "message": match.group(3)[:300],
                }
            )
            continue
        for pattern, warning_type in WARNING_PATTERNS:
            if pattern.search(stripped):
                warnings.append({"file": "main.tex", "line": 0, "type": warning_type, "message": stripped[:300]})
                break
    return dedupe(errors), dedupe(warnings)


def parse_log(log_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not log_path.exists():
        return [], []
    return parse_messages(log_path.read_text(encoding="utf-8", errors="replace"))


def count_pages(pdf_path: Path) -> int:
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        for line in result.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":", 1)[1].strip())
    except Exception:
        pass
    try:
        content = pdf_path.read_bytes()
        pages = content.count(b"/Type /Page") - content.count(b"/Type /Pages")
        return max(0, pages)
    except Exception:
        return 0


def aux_has_bib(aux_path: Path) -> bool:
    if not aux_path.exists():
        return False
    content = aux_path.read_text(encoding="utf-8", errors="replace")
    return "\\citation{" in content or "\\bibdata{" in content


def detect_bib_tool(project_dir: Path, stem: str, requested: str) -> str:
    if requested in {"bibtex", "biber", "none"}:
        return requested
    if (project_dir / f"{stem}.bcf").exists() and which("biber"):
        return "biber"
    if aux_has_bib(project_dir / f"{stem}.aux") and which("bibtex"):
        return "bibtex"
    return "none"


def compile_latexmk(
    project_dir: Path,
    main_file: str,
    engine: str,
    timeout: int,
    clean: bool,
    command_log: list[str],
) -> tuple[bool, str]:
    if clean:
        run_step(["latexmk", "-C", main_file], project_dir, 45, command_log)
    cmd = ["latexmk", "-interaction=nonstopmode", "-file-line-error", "-halt-on-error"]
    if clean:
        cmd.append("-gg")
    if engine == "xelatex":
        cmd.append("-xelatex")
    elif engine == "lualatex":
        cmd.append("-lualatex")
    else:
        cmd.append("-pdf")
    cmd.append(main_file)
    result = run_step(cmd, project_dir, timeout, command_log)
    return result.returncode == 0, result.stdout + "\n" + result.stderr


def compile_engine(
    project_dir: Path,
    main_file: str,
    engine: str,
    bib_tool: str,
    timeout: int,
    command_log: list[str],
) -> tuple[bool, str]:
    outputs: list[str] = []
    stem = Path(main_file).stem
    pass1 = run_step(
        [engine, "-interaction=nonstopmode", "-file-line-error", main_file],
        project_dir,
        timeout,
        command_log,
    )
    outputs.append(pass1.stdout + "\n" + pass1.stderr)

    chosen_bib = detect_bib_tool(project_dir, stem, bib_tool)
    if chosen_bib == "bibtex":
        bib = run_step(["bibtex", stem], project_dir, 60, command_log)
        outputs.append(bib.stdout + "\n" + bib.stderr)
    elif chosen_bib == "biber":
        biber = run_step(["biber", stem], project_dir, 90, command_log)
        outputs.append(biber.stdout + "\n" + biber.stderr)

    pass2 = run_step(
        [engine, "-interaction=nonstopmode", "-file-line-error", main_file],
        project_dir,
        timeout,
        command_log,
    )
    outputs.append(pass2.stdout + "\n" + pass2.stderr)

    pass3 = run_step(
        [engine, "-interaction=nonstopmode", "-file-line-error", main_file],
        project_dir,
        timeout,
        command_log,
    )
    outputs.append(pass3.stdout + "\n" + pass3.stderr)
    return pass3.returncode == 0, "\n".join(outputs)


def warning_summary(warnings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in warnings:
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def format_text(report: dict[str, Any]) -> str:
    lines = [
        f"success: {report['success']}",
        f"backend: {report['backend']}",
        f"engine: {report['engine']}",
        f"project_dir: {report['project_dir']}",
        f"main_file: {report['main_file']}",
        f"pdf_path: {report['pdf_path'] or '(not generated)'}",
        f"page_count: {report['page_count']}",
        f"errors: {len(report['errors'])}",
        f"warnings: {len(report['warnings'])}",
        f"elapsed_seconds: {report['elapsed_seconds']}",
    ]
    if report["errors"]:
        first_error = report["errors"][0]
        lines.append("first_error:")
        lines.append(
            f"  {first_error['file']}:{first_error['line']} [{first_error['type']}] {first_error['message']}"
        )
    if report["warning_summary"]:
        lines.append("warning_summary:")
        for kind, count in report["warning_summary"].items():
            lines.append(f"  {kind}: {count}")
    return "\n".join(lines)


def emit_error(output_format: str, message: str) -> int:
    report = {
        "success": False,
        "errors": [{"file": "", "line": 0, "type": "argument_error", "message": message}],
        "warnings": [],
    }
    if output_format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"success: False\nerrors: 1\nfirst_error:\n  :0 [argument_error] {message}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a LaTeX project")
    parser.add_argument("target", nargs="?", default="main.tex", help="Main TeX file to compile.")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--main-file", default="", help="Deprecated alias for positional target.")
    parser.add_argument("--engine", default="pdflatex", choices=sorted(VALID_ENGINES))
    parser.add_argument("--backend", default="auto", choices=["auto", "latexmk", "engine"])
    parser.add_argument("--bib-tool", default="auto", choices=["auto", "bibtex", "biber", "none"])
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--strict-warnings", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    main_file = args.main_file if args.main_file else args.target
    main_path = project_dir / main_file

    if not project_dir.exists():
        return emit_error(args.format, f"project directory not found: {project_dir}")
    if not main_path.exists():
        return emit_error(args.format, f"missing TeX entrypoint: {main_path}")
    if args.backend == "latexmk" and not which("latexmk"):
        return emit_error(args.format, "latexmk backend selected but latexmk is not available.")
    if args.backend == "engine" and not which(args.engine):
        return emit_error(args.format, f"latex engine not found: {args.engine}")

    backend = args.backend
    if backend == "auto":
        backend = "latexmk" if which("latexmk") else "engine"

    command_log: list[str] = []
    start = time.time()
    success_flag = False
    output_text = ""

    try:
        if backend == "latexmk":
            success_flag, output_text = compile_latexmk(
                project_dir, main_file, args.engine, args.timeout, args.clean, command_log
            )
        else:
            success_flag, output_text = compile_engine(
                project_dir, main_file, args.engine, args.bib_tool, args.timeout, command_log
            )
    except subprocess.TimeoutExpired:
        return emit_error(args.format, f"compilation timed out after {args.timeout}s per step")

    stem = Path(main_file).stem
    log_errors, log_warnings = parse_log(project_dir / f"{stem}.log")
    out_errors, out_warnings = parse_messages(output_text)
    errors = dedupe(log_errors + out_errors)
    warnings = dedupe(log_warnings + out_warnings)

    pdf_path = project_dir / f"{stem}.pdf"
    success = bool(success_flag and pdf_path.exists() and not errors and not (args.strict_warnings and warnings))

    report = {
        "success": success,
        "backend": backend,
        "engine": args.engine,
        "project_dir": str(project_dir),
        "main_file": main_file,
        "pdf_path": str(pdf_path) if pdf_path.exists() else None,
        "page_count": count_pages(pdf_path) if pdf_path.exists() else 0,
        "errors": errors[:100],
        "warnings": warnings[:400],
        "warning_summary": warning_summary(warnings),
        "commands": command_log,
        "elapsed_seconds": round(time.time() - start, 2),
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(report))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
