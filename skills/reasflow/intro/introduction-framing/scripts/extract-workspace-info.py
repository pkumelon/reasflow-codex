#!/usr/bin/env python3
"""Prepare, validate, and organize evidence for native Codex Intro subagents."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_CHUNK_CHARS = 14000

EXTRACT_PROMPTS: dict[str, str] = {
    "survey": """Extract Introduction-relevant information from this literature survey.

Extract:
1. Research background: field, importance, applications, and source-backed claims
2. Related work categories: each category name, description, representative works
   (method name, paper title, authors, year, arxiv_id, bibtex_key, key contribution, applicable scenarios)
3. Gaps: gap description, affected methods, evidence, impact, supporting bibtex keys
4. Citations: bibtex_key, paper_title, authors

Citation rules:
- Preserve the exact BibTeX keys already present in [CITE:key] markers.
- Attach bibtex_keys to every background, category, representative-work, or gap claim supported by literature.
- Do not attach a key unless the source text actually uses that citation for the claim.

Output JSON:
{
  "background": {"research_field": "", "importance": "", "applications": [], "claims": [
    {"claim": "", "bibtex_keys": [], "evidence": ""}
  ]},
  "related_works": {"categories": [{"category_name": "", "description": "", "bibtex_keys": [], "representative_works": [
    {"method_name": "", "paper_title": "", "authors": "", "year": "", "arxiv_id": "", "bibtex_key": "", "key_contribution": "", "applicable_scenarios": ""}
  ]}]},
  "gaps": [{"gap_description": "", "affected_methods": "", "evidence": "", "impact": "", "bibtex_keys": []}],
  "citations": [{"bibtex_key": "", "paper_title": "", "authors": ""}]
}""",

    "method": """Extract Introduction-relevant information from this method description.

Extract:
1. Method summary: core idea, key steps, key techniques
2. Innovations: innovation description, significance
3. Contributions: contribution, addresses_gap, value
4. Differences vs existing methods: main differences, why important, advantages

Output JSON:
{
  "method_summary": {"core_idea": "", "key_steps": [], "key_techniques": []},
  "innovations": [{"innovation": "", "significance": ""}],
  "contributions": [{"contribution": "", "addresses_gap": "", "value": ""}],
  "differences": {"vs_existing_methods": "", "why_important": "", "advantages": ""}
}""",

    "experiment": """Extract Introduction-relevant information from these experiment results.

Extract:
1. Key results: description, significance
2. Performance metrics: metric name, value (only explicit values), baseline value, improvement
3. Baseline comparison: baselines, improvements per metric
4. Validation: datasets, scenarios, experimental setup

IMPORTANT: Never fabricate numeric values. Use descriptive text if numbers are not explicit.

Output JSON:
{
  "key_results": [{"result_description": "", "significance": ""}],
  "performance_metrics": [{"metric_name": "", "value": "", "baseline_value": "", "improvement": ""}],
  "baseline_comparison": {"baselines": [], "improvements": [{"metric": "", "improvement_description": "", "improvement_value": ""}]},
  "validation": {"datasets": [], "scenarios": [], "experimental_setup": ""}
}""",

    "theory": """Extract Introduction-relevant information from this theoretical work.

Extract:
1. Theoretical contributions: contribution, problem solved, innovation
2. Key theorems/lemmas: name, statement, significance, conditions
3. Convergence analysis: convergence rate (only explicit), conditions, significance
4. Complexity analysis: time/space complexity (only explicit), significance
5. Theoretical advantages vs existing theory

IMPORTANT: Never fabricate theorems or complexity bounds not in the text.

Output JSON:
{
  "theoretical_contributions": [{"contribution": "", "problem_solved": "", "innovation": ""}],
  "key_theorems": [{"theorem_name": "", "statement": "", "significance": "", "conditions": ""}],
  "convergence_analysis": {"convergence_rate": "", "convergence_conditions": "", "significance": ""},
  "complexity_analysis": {"time_complexity": "", "space_complexity": "", "significance": ""},
  "theoretical_advantages": {"advantages": [], "vs_existing_theory": ""}
}""",
}


def _preprocess_tex(content: str) -> str:
    lines = []
    for line in content.split("\n"):
        if "%" in line:
            line = line[:line.index("%")]
        lines.append(line.rstrip())
    text = "\n".join(lines)
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = re.sub(
        r"\\cite[a-zA-Z*]*(?:\s*\[[^\]]*\]){0,2}\s*\{([^}]*)\}",
        r"[CITE:\1]",
        text,
    )
    text = re.sub(r"\\ref\{[^}]*\}", "", text)
    text = re.sub(r"\\(sub)*section\{([^}]*)\}", r"\n### \2\n", text)
    for cmd in ("textbf", "textit", "emph"):
        text = re.sub(rf"\\{cmd}\{{([^}}]*)\}}", r"\1", text)
    return text


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _read_text_file(path: Path, workspace: Path, visited: set[Path] | None = None) -> str:
    resolved = path.resolve()
    if not _is_within(resolved, workspace):
        raise ValueError(f"Path outside workspace: {path}")
    if visited is None:
        visited = set()
    if resolved in visited:
        return ""
    visited.add(resolved)

    content = resolved.read_text(encoding="utf-8")
    if resolved.suffix.lower() != ".tex":
        return content

    include_pattern = re.compile(r"\\(?:input|include)\{([^}]+)\}")

    def expand_include(match: re.Match[str]) -> str:
        reference = match.group(1).strip()
        child = resolved.parent / reference
        if not child.suffix:
            child = child.with_suffix(".tex")
        if not child.exists() or not _is_within(child.resolve(), workspace):
            return match.group(0)
        try:
            expanded = _read_text_file(child, workspace, visited)
        except (OSError, UnicodeError, ValueError):
            return match.group(0)
        return f"\n\n=== included: {child.relative_to(workspace)} ===\n{expanded}\n"

    return _preprocess_tex(include_pattern.sub(expand_include, content))


def _read_source(path: str, workspace: Path) -> tuple[str, str | None]:
    """Return (content, error_json). If directory, reads top files."""
    workspace = workspace.resolve()
    full = (workspace / path).resolve()
    if not _is_within(full, workspace):
        return "", json.dumps({"error": f"Path outside workspace: {path}", "extracted": {}})
    if not full.exists():
        return "", json.dumps({"error": f"Path not found: {path}", "extracted": {}})
    if full.is_dir():
        supported = {".md", ".tex", ".txt", ".json", ".py", ".bib", ".rst", ".yaml", ".yml"}
        files = sorted(
            (f for f in full.rglob("*") if f.is_file() and f.suffix.lower() in supported
             and not any(p in f.parts for p in (".git", "__pycache__", ".venv", "node_modules"))),
            key=lambda f: (
                {".md": 0, ".tex": 1, ".bib": 2, ".json": 3}.get(f.suffix.lower(), 4),
                str(f.relative_to(full)),
            ),
        )
        if not files:
            return "", json.dumps({"error": f"No readable files in directory: {path}", "extracted": {}})
        parts = []
        for f in files:
            try:
                text = _read_text_file(f, workspace)
                parts.append(f"\n\n=== {f.relative_to(full)} ===\n{text}")
            except Exception:
                continue
        return "\n".join(parts), None
    try:
        return _read_text_file(full, workspace), None
    except Exception as exc:
        return "", json.dumps({"error": str(exc), "extracted": {}})


def _split_content(content: str, chunk_chars: int) -> list[str]:
    if len(content) <= chunk_chars:
        return [content]

    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(start + chunk_chars, len(content))
        if end < len(content):
            boundary = content.rfind("\n\n", start, end)
            if boundary <= start + chunk_chars // 2:
                boundary = content.rfind("\n", start, end)
            if boundary > start:
                end = boundary
        chunks.append(content[start:end].strip())
        start = end
        while start < len(content) and content[start].isspace():
            start += 1
    return [chunk for chunk in chunks if chunk]


def cmd_prepare(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    content, err = _read_source(args.source, workspace)
    if err:
        print(err)
        return 1

    chunks = _split_content(content, args.chunk_chars)
    prompt_base = EXTRACT_PROMPTS[args.source_type]
    if args.focus:
        prompt_base += f"\n\nFocus especially on: {args.focus}"
    result = {
        "task_version": 1,
        "task_type": "intro_evidence_extraction",
        "source_type": args.source_type,
        "source_path": args.source,
        "instructions": (
            "Read every chunk and extract only explicitly supported information. "
            "Preserve exact citation keys. Do not infer missing claims, results, or references. "
            "Write one JSON object to expected_output_path using output_contract.\n\n"
            + prompt_base
        ),
        "chunks": [
            {"chunk_id": index, "content": chunk}
            for index, chunk in enumerate(chunks, start=1)
        ],
        "source_metadata": {
            "source_chars": len(content),
            "chunk_chars": args.chunk_chars,
            "truncated": False,
        },
        "expected_output_path": args.extracted_output,
        "output_contract": {
            "source_type": args.source_type,
            "source_path": args.source,
            "extracted": "object matching the schema in instructions",
            "extraction_metadata": {
                "source_chars": len(content),
                "chunk_chars": args.chunk_chars,
                "chunks_processed": len(chunks),
                "processed_chunk_ids": list(range(1, len(chunks) + 1)),
                "truncated": False,
                "executor": "codex_subagent",
            },
        },
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    print(output)
    return 0


def validate_extraction(task: dict[str, Any], extraction: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if extraction.get("source_type") != task.get("source_type"):
        errors.append("source_type does not match task")
    if extraction.get("source_path") != task.get("source_path"):
        errors.append("source_path does not match task")
    if not isinstance(extraction.get("extracted"), dict):
        errors.append("extracted must be an object")

    metadata = extraction.get("extraction_metadata")
    if not isinstance(metadata, dict):
        errors.append("extraction_metadata must be an object")
        return errors

    source_metadata = task.get("source_metadata", {})
    expected_ids = [
        int(chunk.get("chunk_id"))
        for chunk in task.get("chunks", [])
        if isinstance(chunk, dict) and isinstance(chunk.get("chunk_id"), int)
    ]
    if metadata.get("source_chars") != source_metadata.get("source_chars"):
        errors.append("source_chars does not match task")
    if metadata.get("chunk_chars") != source_metadata.get("chunk_chars"):
        errors.append("chunk_chars does not match task")
    if metadata.get("chunks_processed") != len(expected_ids):
        errors.append("chunks_processed does not cover every task chunk")
    if metadata.get("processed_chunk_ids") != expected_ids:
        errors.append("processed_chunk_ids does not cover every task chunk in order")
    if metadata.get("truncated") is not False:
        errors.append("truncated must be false")
    if metadata.get("executor") != "codex_subagent":
        errors.append("executor must be codex_subagent")
    return errors


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        task = json.loads(Path(args.task).read_text(encoding="utf-8"))
        extraction = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"passed": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    errors = validate_extraction(task, extraction)
    print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def cmd_organize(args: argparse.Namespace) -> int:
    parsed: list[dict] = []
    for inp in args.inputs:
        try:
            parsed.append(json.loads(Path(inp).read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"WARNING: could not read {inp}: {exc}", file=sys.stderr)

    survey = next((p.get("extracted", {}) for p in parsed if p.get("source_type") == "survey"), None)
    method = next((p.get("extracted", {}) for p in parsed if p.get("source_type") == "method"), None)
    experiment = next((p.get("extracted", {}) for p in parsed if p.get("source_type") == "experiment"), None)
    theory = next((p.get("extracted", {}) for p in parsed if p.get("source_type") == "theory"), None)

    organized: dict[str, object] = {
        "problem_background": "",
        "related_works": "",
        "method_summary": "",
        "results_preview": "",
        "citations": [],
        "citation_claims": [],
    }
    citation_claims: list[dict[str, object]] = []

    def normalized_keys(value: object) -> list[str]:
        if isinstance(value, str):
            values = value.split(",")
        elif isinstance(value, list):
            values = value
        else:
            values = []
        return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))

    def append_claim(
        text: str,
        claim_type: str,
        keys: object,
        source_path: str,
        evidence: str = "",
    ) -> None:
        cleaned_text = str(text or "").strip()
        if not cleaned_text:
            return
        bibtex_keys = normalized_keys(keys)
        citation_claims.append(
            {
                "claim_id": f"claim-{len(citation_claims) + 1:04d}",
                "text": cleaned_text,
                "claim_type": claim_type,
                "citation_required": bool(bibtex_keys),
                "bibtex_keys": bibtex_keys,
                "source_path": source_path,
                "evidence": str(evidence or "").strip(),
            }
        )

    if survey:
        survey_path = next(
            (str(p.get("source_path", "")) for p in parsed if p.get("source_type") == "survey"),
            "",
        )
        bg = survey.get("background", {})
        if isinstance(bg, dict):
            background_claims = bg.get("claims", []) if isinstance(bg.get("claims", []), list) else []
            background_lines = [
                str(claim.get("claim", "")).strip()
                for claim in background_claims
                if isinstance(claim, dict) and str(claim.get("claim", "")).strip()
            ]
            organized["problem_background"] = (
                f"Field: {bg.get('research_field', '')}\n"
                f"Importance: {bg.get('importance', '')}\n"
                f"Applications: {', '.join(bg.get('applications', []))}"
                + (f"\nSource-backed claims: {'; '.join(background_lines)}" if background_lines else "")
            )
            for claim in background_claims:
                if isinstance(claim, dict):
                    append_claim(
                        claim.get("claim", ""),
                        "background",
                        claim.get("bibtex_keys", []),
                        survey_path,
                        claim.get("evidence", ""),
                    )
        rw_parts: list[str] = []
        for cat in survey.get("related_works", {}).get("categories", []):
            rw_parts.append(f"\n### {cat.get('category_name', '')}")
            if cat.get("description"):
                category_keys = normalized_keys(cat.get("bibtex_keys", []))
                citation_hint = f" [cite: {', '.join(category_keys)}]" if category_keys else ""
                rw_parts.append(f"{cat['description']}{citation_hint}")
                append_claim(
                    cat["description"],
                    "related_work_category",
                    category_keys,
                    survey_path,
                )
            for work in cat.get("representative_works", []):
                bits = [f"{k}: {work[k]}" for k in ("method_name", "paper_title", "authors", "year", "arxiv_id", "bibtex_key", "key_contribution") if work.get(k)]
                if bits:
                    rw_parts.append("- " + " | ".join(bits))
                work_text = str(work.get("key_contribution") or work.get("paper_title") or "")
                append_claim(
                    work_text,
                    "representative_work",
                    work.get("bibtex_key", ""),
                    survey_path,
                )
        gaps = survey.get("gaps", [])
        if gaps:
            rw_parts.append("\n### Limitations of existing methods:")
            for i, gap in enumerate(gaps, 1):
                gap_keys = normalized_keys(gap.get("bibtex_keys", []))
                citation_hint = f" [cite: {', '.join(gap_keys)}]" if gap_keys else ""
                rw_parts.append(f"{i}. {gap.get('gap_description', '')}" + (f" (Impact: {gap['impact']})" if gap.get("impact") else "") + citation_hint)
                append_claim(
                    gap.get("gap_description", ""),
                    "literature_gap",
                    gap_keys,
                    survey_path,
                    gap.get("evidence", ""),
                )
        organized["related_works"] = "\n".join(rw_parts)
        organized["citations"] = survey.get("citations", [])  # type: ignore[assignment]

    if method:
        ms = method.get("method_summary", {})
        parts: list[str] = []
        if ms.get("core_idea"):
            parts.append(f"Core idea: {ms['core_idea']}")
        if ms.get("key_steps"):
            parts.append(f"Key steps: {'; '.join(ms['key_steps'])}")
        for i, c in enumerate(method.get("contributions", []), 1):
            if c.get("contribution"):
                parts.append(f"{i}. {c['contribution']}")
        organized["method_summary"] = "\n".join(parts)

    res_parts: list[str] = []
    if experiment:
        for r in experiment.get("key_results", []):
            if r.get("result_description"):
                res_parts.append(f"- {r['result_description']}")
        for m in experiment.get("performance_metrics", []):
            if m.get("metric_name") and m.get("value"):
                s = f"- {m['metric_name']}: {m['value']}"
                if m.get("improvement"):
                    s += f" (improvement: {m['improvement']})"
                res_parts.append(s)
    if theory:
        for c in theory.get("theoretical_contributions", []):
            if c.get("contribution"):
                res_parts.append(f"- {c['contribution']}")
        cr = theory.get("convergence_analysis", {}).get("convergence_rate", "")
        if cr:
            res_parts.append(f"Convergence: {cr}")
    organized["results_preview"] = "\n".join(res_parts)
    organized["citation_claims"] = citation_claims

    result = {
        "organized_info": organized,
        "source_summary": {
            t: [p.get("source_path") for p in parsed if p.get("source_type") == t]
            for t in ("survey", "method", "experiment", "theory")
        },
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and organize Intro evidence tasks")
    parser.add_argument("--mode", required=True, choices=["prepare", "validate", "organize"])
    parser.add_argument("--source-type", choices=["survey", "method", "experiment", "theory"])
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--source", default="", help="Source file/dir relative to workspace")
    parser.add_argument("--inputs", nargs="+", default=[], help="JSON files from extract modes; required for organize mode")
    parser.add_argument("--task", default="", help="Prepared task JSON; required for validate mode")
    parser.add_argument("--input", default="", help="Subagent extraction JSON; required for validate mode")
    parser.add_argument("--focus", default="", help="Comma-separated focus areas")
    parser.add_argument("--output", default="", help="Write JSON result to this path")
    parser.add_argument("--extracted-output", default="", help="Output path assigned to the evidence subagent")
    parser.add_argument(
        "--chunk-chars",
        type=int,
        default=DEFAULT_CHUNK_CHARS,
        help="Maximum characters sent in each extraction request; all chunks are processed.",
    )
    args = parser.parse_args()

    if args.mode == "organize":
        if not args.inputs:
            print("ERROR: --inputs required for organize mode", file=sys.stderr)
            return 1
        return cmd_organize(args)

    if args.mode == "validate":
        if not args.task or not args.input:
            print("ERROR: --task and --input required for validate mode", file=sys.stderr)
            return 1
        return cmd_validate(args)

    if not args.source_type or not args.source or not args.output or not args.extracted_output:
        print(
            "ERROR: --source-type, --source, --output, and --extracted-output "
            "are required for prepare mode",
            file=sys.stderr,
        )
        return 1
    if args.chunk_chars < 2000:
        print("ERROR: --chunk-chars must be at least 2000", file=sys.stderr)
        return 1
    return cmd_prepare(args)


if __name__ == "__main__":
    raise SystemExit(main())
