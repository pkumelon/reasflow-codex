#!/usr/bin/env python3
"""Compile a single LaTeX chapter in isolation."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from shutil import which
from typing import Any

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
VALID_ENGINES = {"pdflatex", "xelatex", "lualatex"}


def extract_preamble(main_tex: Path) -> str:
    content = main_tex.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\\begin\{document\}", content)
    if not match:
        raise ValueError(f"cannot find \\begin{{document}} in {main_tex}")
    return content[: match.start()]


def normalize_chapter_path(project_dir: Path, chapter: str) -> Path:
    chapter_path = project_dir / chapter
    if chapter_path.exists():
        return chapter_path
    if chapter_path.suffix:
        return chapter_path
    with_suffix = chapter_path.with_suffix(".tex")
    if with_suffix.exists():
        return with_suffix
    return chapter_path


def chapter_input_target(project_dir: Path, chapter_path: Path) -> str:
    rel = chapter_path.relative_to(project_dir).as_posix()
    return rel[:-4] if rel.endswith(".tex") else rel


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


def aux_has_citations(aux_path: Path) -> bool:
    if not aux_path.exists():
        return False
    content = aux_path.read_text(encoding="utf-8", errors="replace")
    return "\\citation{" in content or "\\bibdata{" in content


def compile_latexmk(
    project_dir: Path,
    temp_tex: str,
    engine: str,
    timeout: int,
    command_log: list[str],
) -> tuple[bool, str]:
    cmd = [
        "latexmk",
        "-interaction=nonstopmode",
        "-file-line-error",
        "-halt-on-error",
    ]
    if engine == "xelatex":
        cmd.append("-xelatex")
    elif engine == "lualatex":
        cmd.append("-lualatex")
    else:
        cmd.append("-pdf")
    cmd.append(temp_tex)
    result = run_step(cmd, project_dir, timeout, command_log)
    return result.returncode == 0, result.stdout + "\n" + result.stderr


def compile_engine(
    project_dir: Path,
    temp_tex: str,
    temp_stem: str,
    engine: str,
    timeout: int,
    command_log: list[str],
) -> tuple[bool, str]:
    outputs: list[str] = []
    pass1 = run_step(
        [engine, "-interaction=nonstopmode", "-file-line-error", temp_tex],
        project_dir,
        timeout,
        command_log,
    )
    outputs.append(pass1.stdout + "\n" + pass1.stderr)

    aux_path = project_dir / f"{temp_stem}.aux"
    if aux_has_citations(aux_path) and which("bibtex"):
        bib = run_step(["bibtex", temp_stem], project_dir, 60, command_log)
        outputs.append(bib.stdout + "\n" + bib.stderr)

    pass2 = run_step(
        [engine, "-interaction=nonstopmode", "-file-line-error", temp_tex],
        project_dir,
        timeout,
        command_log,
    )
    outputs.append(pass2.stdout + "\n" + pass2.stderr)

    pass3 = run_step(
        [engine, "-interaction=nonstopmode", "-file-line-error", temp_tex],
        project_dir,
        timeout,
        command_log,
    )
    outputs.append(pass3.stdout + "\n" + pass3.stderr)
    return pass3.returncode == 0, "\n".join(outputs)


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
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("!"):
            message = stripped[1:].strip()
            if index + 1 < len(lines) and lines[index + 1].strip():
                message = f"{message} | {lines[index + 1].strip()}"
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
                warnings.append(
                    {"file": "main.tex", "line": 0, "type": warning_type, "message": stripped[:300]}
                )
                break
    return dedupe(errors), dedupe(warnings)


def parse_log(log_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not log_path.exists():
        return [], []
    content = log_path.read_text(encoding="utf-8", errors="replace")
    return parse_messages(content)


def cleanup(project_dir: Path, temp_stem: str) -> None:
    for suffix in (
        ".tex",
        ".aux",
        ".bbl",
        ".blg",
        ".fdb_latexmk",
        ".fls",
        ".log",
        ".out",
        ".synctex.gz",
        ".toc",
    ):
        (project_dir / f"{temp_stem}{suffix}").unlink(missing_ok=True)


def format_text(report: dict[str, Any]) -> str:
    lines = [
        f"success: {report['success']}",
        f"backend: {report['backend']}",
        f"engine: {report['engine']}",
        f"pdf_path: {report['pdf_path'] or '(not generated)'}",
        f"total_pages: {report['total_pages']}",
        f"errors: {len(report['errors'])}",
        f"warnings: {len(report['warnings'])}",
        f"elapsed_seconds: {report['elapsed_seconds']}",
    ]
    if report["errors"]:
        item = report["errors"][0]
        lines.append("first_error:")
        lines.append(f"  {item['file']}:{item['line']} [{item['type']}] {item['message']}")
    if report["warnings"]:
        item = report["warnings"][0]
        lines.append("first_warning:")
        lines.append(f"  {item['file']}:{item['line']} [{item['type']}] {item['message']}")
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
    parser = argparse.ArgumentParser(description="Compile a single LaTeX chapter independently")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--main", "--main-file", dest="main_file", default="main.tex")
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--engine", default="pdflatex", choices=sorted(VALID_ENGINES))
    parser.add_argument("--backend", default="auto", choices=["auto", "latexmk", "engine"])
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--strict-warnings", action="store_true")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    main_tex = project_dir / args.main_file
    chapter_path = normalize_chapter_path(project_dir, args.chapter)

    if not main_tex.exists():
        return emit_error(args.format, f"main file not found: {main_tex}")
    if not chapter_path.exists():
        return emit_error(args.format, f"chapter file not found: {chapter_path}")

    try:
        preamble = extract_preamble(main_tex)
    except ValueError as error:
        return emit_error(args.format, str(error))

    chapter_stem = chapter_path.stem
    temp_stem = f"_chapter_{chapter_stem}"
    temp_tex = project_dir / f"{temp_stem}.tex"
    temp_pdf = project_dir / f"{temp_stem}.pdf"
    temp_log = project_dir / f"{temp_stem}.log"
    input_target = chapter_input_target(project_dir, chapter_path)

    temp_tex.write_text(
        f"{preamble}\n\\begin{{document}}\n\\input{{{input_target}}}\n\\end{{document}}\n",
        encoding="utf-8",
    )

    backend = args.backend
    if backend == "auto":
        backend = "latexmk" if which("latexmk") else "engine"

    if backend == "latexmk" and not which("latexmk"):
        return emit_error(args.format, "latexmk backend requested but latexmk is not available.")
    if backend == "engine" and not which(args.engine):
        return emit_error(args.format, f"latex engine not found: {args.engine}")

    command_log: list[str] = []
    start = time.time()
    success_flag = False
    output_text = ""

    try:
        if backend == "latexmk":
            success_flag, output_text = compile_latexmk(
                project_dir, temp_tex.name, args.engine, args.timeout, command_log
            )
        else:
            success_flag, output_text = compile_engine(
                project_dir, temp_tex.name, temp_stem, args.engine, args.timeout, command_log
            )
    except subprocess.TimeoutExpired:
        errors = [{"file": "", "line": 0, "type": "timeout", "message": f"compile timeout after {args.timeout}s"}]
        report = {
            "success": False,
            "backend": backend,
            "engine": args.engine,
            "project_dir": str(project_dir),
            "main_file": args.main_file,
            "chapter": str(chapter_path),
            "pdf_path": str(temp_pdf) if temp_pdf.exists() else None,
            "total_pages": count_pages(temp_pdf) if temp_pdf.exists() else 0,
            "errors": errors,
            "warnings": [],
            "commands": command_log,
            "elapsed_seconds": round(time.time() - start, 2),
        }
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_text(report))
        if not args.keep:
            cleanup(project_dir, temp_stem)
        return 1

    log_errors, log_warnings = parse_log(temp_log)
    out_errors, out_warnings = parse_messages(output_text)
    errors = dedupe(log_errors + out_errors)
    warnings = dedupe(log_warnings + out_warnings)

    success = bool(success_flag and temp_pdf.exists() and not errors and not (args.strict_warnings and warnings))
    report = {
        "success": success,
        "backend": backend,
        "engine": args.engine,
        "project_dir": str(project_dir),
        "main_file": args.main_file,
        "chapter": str(chapter_path),
        "pdf_path": str(temp_pdf) if temp_pdf.exists() else None,
        "total_pages": count_pages(temp_pdf) if temp_pdf.exists() else 0,
        "errors": errors[:100],
        "warnings": warnings[:200],
        "commands": command_log,
        "elapsed_seconds": round(time.time() - start, 2),
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(report))

    if not args.keep:
        cleanup(project_dir, temp_stem)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
